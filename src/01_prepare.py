"""Строит два аналитических файла из трёх сырых рядов:

- monthly_panel.parquet  — ключевая ставка (конец месяца), курс и Brent
  (средние за месяц) — вход для VAR/Грейнджера/IRF.
- daily_returns.parquet  — дневные лог-доходности курса с флагом дат
  решений по ставке — вход для GARCH и событийного исследования.

Здесь же пересчитываются факты раздела 0 плана (`plan_keyrate.md`) и
тест на коинтеграцию, определяющий спецификацию VAR (Э2 плана).

Авторы: команда (ФИО — см. README).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller, kpss
from statsmodels.tsa.vector_ar.vecm import coint_johansen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config as cfg

VAR_SPEC_FILE = cfg.DATA_PROCESSED / "var_spec_decision.txt"


def load_keyrate() -> pd.DataFrame:
    df = pd.read_csv(cfg.RAW_KEYRATE_FILE)
    df["date"] = pd.to_datetime(df["date"], format="%d.%m.%Y")
    df = df.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    return df[["date", "rate"]].rename(columns={"rate": "key_rate"})


def load_usdrub() -> pd.DataFrame:
    df = pd.read_csv(cfg.RAW_USDRUB_FILE)
    df["date"] = pd.to_datetime(df["date"], format="%d.%m.%Y")
    df["usdrub"] = df["value"] / df["nominal"]
    df = df.drop_duplicates("date").sort_values("date").reset_index(drop=True)
    return df[["date", "usdrub"]]


def load_brent() -> pd.DataFrame:
    df = pd.read_csv(cfg.RAW_BRENT_FILE)
    df.columns = ["date", "brent"]
    df["date"] = pd.to_datetime(df["date"])
    df = df[df["brent"] != "."].copy()
    df["brent"] = df["brent"].astype(float)
    df = df[(df["date"] >= pd.to_datetime(cfg.SAMPLE_START, dayfirst=True))]
    return df.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def build_monthly_panel(key: pd.DataFrame, usd: pd.DataFrame, brent: pd.DataFrame) -> pd.DataFrame:
    key_m = key.set_index("date")["key_rate"].resample("ME").last()
    usd_m = usd.set_index("date")["usdrub"].resample("ME").mean()
    brent_m = brent.set_index("date")["brent"].resample("ME").mean()
    panel = pd.concat([key_m, usd_m, brent_m], axis=1, sort=True)
    panel.columns = ["key_rate", "usdrub", "brent"]
    panel = panel.dropna().reset_index().rename(columns={"index": "date"})
    panel["volatile_tail"] = panel["date"] >= pd.to_datetime(cfg.VOLATILE_TAIL_START)
    return panel


def build_daily_returns(usd: pd.DataFrame, key: pd.DataFrame) -> pd.DataFrame:
    df = usd.sort_values("date").reset_index(drop=True).copy()
    df["log_return"] = np.log(df["usdrub"]).diff()
    df = df.dropna(subset=["log_return"]).reset_index(drop=True)

    key_sorted = key.sort_values("date").reset_index(drop=True)
    changes = key_sorted[key_sorted["key_rate"].diff() != 0].iloc[1:]  # drop first row (no diff)

    # ВАЖНО (см. plan_keyrate.md, п. 0.11): дата в выгрузке ставки — дата
    # вступления решения в силу, а дата в выгрузке курса — дата действия
    # официального фиксинга (T+1 от торговой сессии, отсюда 0 понедельников
    # в usd_dates). Прямое сравнение дат совпадает только в 5 случаях из 65;
    # сдвиг даты решения на +1 календарный день даёт 65 совпадений из 65.
    shifted_dates = set(changes["date"] + pd.Timedelta(days=1))
    df["rate_decision_day"] = df["date"].isin(shifted_dates)
    n_flagged = df["rate_decision_day"].sum()
    if n_flagged != len(changes):
        raise RuntimeError(
            f"Ожидал {len(changes)} размеченных дат решений, получил {n_flagged} — "
            "смещение дат больше не 1 день, проверить заново."
        )
    return df


def stationarity_tests(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in ["key_rate", "usdrub", "brent"]:
        for transform, series in [
            ("level", panel[col]),
            ("diff", panel[col].diff().dropna()),
        ]:
            adf_stat, adf_p, *_ = adfuller(series, autolag="AIC")
            try:
                kpss_stat, kpss_p, *_ = kpss(series, regression="c", nlags="auto")
            except Exception:
                kpss_stat, kpss_p = np.nan, np.nan
            rows.append(
                {
                    "variable": col,
                    "transform": transform,
                    "adf_stat": adf_stat,
                    "adf_p": adf_p,
                    "kpss_stat": kpss_stat,
                    "kpss_p": kpss_p,
                }
            )
    return pd.DataFrame(rows)


def johansen_rank(data: np.ndarray, k_ar_diff: int) -> tuple[int, list[str]]:
    """Ранг коинтеграции по последовательной процедуре теста Йохансена:
    ранг = число подряд отвергнутых H0 начиная с r=0, остановка на первом
    "не отвергаем" (а не просто подсчёт строк, где stat > crit — это дало бы
    неверный ранг при немонотонном разрыве последовательности)."""
    result = coint_johansen(data, det_order=0, k_ar_diff=k_ar_diff)
    trace_stats, crit_95 = result.lr1, result.cvt[:, 1]
    rank, stopped, lines = 0, False, []
    for r, (stat, crit) in enumerate(zip(trace_stats, crit_95)):
        reject = stat > crit
        verdict = "отвергаем H0" if reject else "не отвергаем H0"
        margin_note = " (граница, разница <1)" if abs(stat - crit) < 1 else ""
        lines.append(f"    r<={r}: stat={stat:.2f}, crit_95={crit:.2f} -> {verdict}{margin_note}")
        if reject and not stopped:
            rank += 1
        else:
            stopped = True
    return rank, lines


def johansen_decision(panel: pd.DataFrame) -> str:
    from statsmodels.tsa.vector_ar.var_model import VAR

    data = panel[["key_rate", "usdrub", "brent"]].copy()
    data["usdrub"] = np.log(data["usdrub"])
    data["brent"] = np.log(data["brent"])
    values = data.values

    # Лаг для VECM выбираем из данных, а не произвольно: сначала подбираем
    # порядок VAR в уровнях (AIC/BIC/HQIC/FPE), затем k_ar_diff = p - 1.
    # Произвольный k_ar_diff=1 (первая версия скрипта) давал ранг=1 на самой
    # границе критического значения — это была ошибка методики, не находка.
    order = VAR(values).select_order(cfg.VAR_MAX_LAG)
    p_bic = order.selected_orders["bic"]
    principal_kd = max(p_bic - 1, 1)

    lines = [
        f"Выбор лага VAR по BIC (обоснование в plan_keyrate.md, п. 0.5): p={p_bic}",
        f"=> k_ar_diff для VECM/Йохансена = {principal_kd}",
        "",
        "Чувствительность ранга коинтеграции к k_ar_diff (обязательная проверка,",
        "т.к. ранг оказался чувствителен к выбору лага):",
    ]
    ranks = {}
    for kd in sorted({1, 2, 3, principal_kd}):
        rank, detail = johansen_rank(values, kd)
        ranks[kd] = rank
        lines.append(f"  k_ar_diff={kd} (trace, 5%): ранг={rank}")
        lines.extend(detail)

    n_coint = ranks[principal_kd]
    decision = "vecm" if n_coint > 0 else "var_diff"
    lines.append(
        f"\nОсновная спецификация использует лаг, выбранный по данным (k_ar_diff={principal_kd}), "
        f"а не произвольный: ранг={n_coint} => {decision}."
    )
    if len(set(ranks.values())) > 1:
        lines.append(
            "ВНИМАНИЕ: ранг не одинаков при разных k_ar_diff — вывод о коинтеграции "
            "неустойчив к выбору лага. Показывать обе спецификации (VECM и VAR-в-разностях) "
            "в результатах, не только основную."
        )
    print("\n".join(lines))
    VAR_SPEC_FILE.write_text("\n".join(lines) + f"\n\nSPEC={decision}\nKD={principal_kd}\n", encoding="utf-8")
    return decision


def print_audit_facts(key: pd.DataFrame, usd: pd.DataFrame, brent: pd.DataFrame, panel: pd.DataFrame) -> None:
    print("\n=== Пересчёт фактов раздела 0 плана ===")
    print(f"Ключевая ставка: {len(key)} строк, {key['date'].min().date()} .. {key['date'].max().date()}")
    n_changes = int((key["key_rate"].diff() != 0).sum() - 1)
    print(f"  фактических изменений ставки: {n_changes}")
    print(f"  диапазон: {key['key_rate'].min()}% .. {key['key_rate'].max()}%")

    print(f"Курс USD/RUB: {len(usd)} строк, {usd['date'].min().date()} .. {usd['date'].max().date()}")
    peak = usd.loc[usd["usdrub"].idxmax()]
    print(f"  пик: {peak['usdrub']:.2f} на {peak['date'].date()}")

    print(f"Brent: {len(brent)} строк, {brent['date'].min().date()} .. {brent['date'].max().date()}")
    print(f"  последнее значение: {brent['brent'].iloc[-1]:.1f}$ на {brent['date'].iloc[-1].date()}")

    print(f"\nМесячная панель: {len(panel)} месяцев, {panel['date'].min().date()} .. {panel['date'].max().date()}")
    corr = panel[["key_rate", "usdrub", "brent"]].corr()
    print("Корреляция уровней:")
    print(corr.round(3))


def main() -> None:
    key = load_keyrate()
    usd = load_usdrub()
    brent = load_brent()

    panel = build_monthly_panel(key, usd, brent)
    daily = build_daily_returns(usd, key)

    print_audit_facts(key, usd, brent, panel)

    t2 = stationarity_tests(panel)
    t2.to_csv(cfg.OUTPUT_TABLES / "T2_stationarity.csv", index=False)
    print("\n=== T2: тесты на стационарность ===")
    print(t2.round(3).to_string(index=False))

    johansen_decision(panel)

    panel.to_parquet(cfg.MONTHLY_PANEL_FILE, index=False)
    daily.to_parquet(cfg.DAILY_RETURNS_FILE, index=False)
    print(f"\nСохранено: {cfg.MONTHLY_PANEL_FILE.relative_to(cfg.ROOT)} ({len(panel)} строк)")
    print(f"Сохранено: {cfg.DAILY_RETURNS_FILE.relative_to(cfg.ROOT)} ({len(daily)} строк)")


if __name__ == "__main__":
    main()
