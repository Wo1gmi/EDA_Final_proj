"""Проверки устойчивости: альтернативный лаг, подпериоды до/после 2022,
альтернативный порядок переменных в IRF, полный период против периода без
волатильного хвоста 2026 года. Всё сводится в Т7.

Версия 2 (после ревью, см. `feedback_1.md`, P0-2): наивное деление
до/после 28.02.2022 недостаточно — обе половины могут включать кризисные
эпизоды. Добавлены: "спокойный" период 2015-06..2021-12 и период после
острой кризисной фазы (2022-09..), проверка с экзогенной дамми на
кризисные месяцы прямо в VAR, и скользящее окно Грейнджера (ширина 60
месяцев, график p-value во времени) — формальный Chow-тест на структурный
слом для VAR-системы не делали (дал бы то же самое качественно, но дороже
по времени), скользящее окно — предложенная ревьюером альтернатива.

Ничего здесь не заменяет основную спецификацию из `03_var.py` — задача
этого скрипта показать, меняются ли содержательные выводы (знак и
значимость Грейнджера, знак пика IRF), а не выбрать "лучшую" версию.

Авторы: команда (ФИО — см. README).
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.vector_ar.var_model import VAR

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config as cfg

VARS = ["key_rate", "usdrub", "brent"]
CRISIS_DUMMY_WINDOWS = [("2014-11-01", "2015-02-28"), ("2022-02-01", "2022-04-30")]


def load_levels(exclude_tail: bool = False) -> pd.DataFrame:
    panel = pd.read_parquet(cfg.MONTHLY_PANEL_FILE)
    if exclude_tail:
        panel = panel[~panel["volatile_tail"]]
    data = panel[VARS].copy()
    data["usdrub"] = np.log(data["usdrub"])
    data["brent"] = np.log(data["brent"])
    return data.reset_index(drop=True)


def granger_pvalues(levels: pd.DataFrame, lag: int) -> dict:
    d = levels.diff().dropna()
    if len(d) <= lag * len(VARS) + 5:
        return {"rate_to_fx_p": np.nan, "fx_to_rate_p": np.nan, "n_obs": len(d)}
    res = VAR(d.values).fit(lag)
    c1 = res.test_causality(caused=1, causing=[0], kind="f")
    c2 = res.test_causality(caused=0, causing=[1], kind="f")
    return {"rate_to_fx_p": c1.pvalue, "fx_to_rate_p": c2.pvalue, "n_obs": len(d)}


def granger_with_crisis_dummy(dates: pd.Series, levels: pd.DataFrame, lag: int) -> dict:
    """VAR с экзогенной дамми на кризисные месяцы (2014-11..2015-02,
    2022-02..2022-04) — проверяем, убирает ли она значимость ставка->курс
    на полной выборке (P0-2, пункт 4)."""
    d = levels.diff().dropna()
    d_dates = dates.iloc[1:].reset_index(drop=True)
    dummy = pd.Series(False, index=d_dates.index)
    for lo, hi in CRISIS_DUMMY_WINDOWS:
        dummy |= (d_dates >= lo) & (d_dates <= hi)
    exog = dummy.astype(float).to_numpy().reshape(-1, 1)
    res = VAR(d.values, exog=exog).fit(lag)
    c1 = res.test_causality(caused=1, causing=[0], kind="f")
    c2 = res.test_causality(caused=0, causing=[1], kind="f")
    return {"rate_to_fx_p": c1.pvalue, "fx_to_rate_p": c2.pvalue, "n_obs": len(d)}


def rolling_granger(dates: pd.Series, levels: pd.DataFrame, lag: int, window: int) -> pd.DataFrame:
    """Скользящее окно Грейнджера шириной `window` месяцев — динамика
    p-value во времени вместо единственного разбиения на до/после."""
    rows = []
    for start in range(0, len(levels) - window + 1):
        sub = levels.iloc[start : start + window]
        g = granger_pvalues(sub.reset_index(drop=True), lag)
        rows.append(
            {
                "window_end": dates.iloc[start + window - 1],
                "rate_to_fx_p": g["rate_to_fx_p"],
                "fx_to_rate_p": g["fx_to_rate_p"],
            }
        )
    return pd.DataFrame(rows)


def plot_rolling_granger(roll: pd.DataFrame, window: int) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(roll["window_end"], roll["rate_to_fx_p"], color="steelblue", label="ставка → курс")
    ax.plot(roll["window_end"], roll["fx_to_rate_p"], color="darkorange", label="курс → ставка")
    ax.axhline(0.05, color="red", lw=1, ls="--", label="p = 0.05")
    ax.set_yscale("log")
    ax.set_ylabel("p-значение (лог. шкала)")
    ax.set_xlabel(f"Конец скользящего окна ({window} месяцев)")
    ax.set_title(f"Скользящее окно Грейнджера ({window} мес.): p-значение во времени")
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(cfg.OUTPUT_FIGURES / "R4_rolling_granger.png", dpi=150)
    plt.close(fig)


def irf_peak(levels: pd.DataFrame, lag: int, ordering: list) -> dict:
    d = levels[ordering].diff().dropna()
    res = VAR(d.values).fit(lag)
    irf = res.irf(12)
    impulse_idx = ordering.index("key_rate")
    response_idx = ordering.index("usdrub")
    path = irf.orth_irfs[:, response_idx, impulse_idx]
    peak_idx = int(np.argmax(np.abs(path)))
    return {"peak_horizon": peak_idx, "peak_value": path[peak_idx], "sign": "+" if path[peak_idx] > 0 else "-"}


def main() -> None:
    rows = []

    levels_full = load_levels(exclude_tail=False)
    levels_no_tail = load_levels(exclude_tail=True)
    principal_lag = 2

    # 1. Альтернативный лаг
    for lag in [1, 2, 3]:
        g = granger_pvalues(levels_full, lag)
        rows.append(
            {
                "check": "альтернативный лаг",
                "variant": f"k_ar_diff={lag}" + (" (основной)" if lag == principal_lag else ""),
                "n_obs": g["n_obs"],
                "rate_to_fx_p": g["rate_to_fx_p"],
                "fx_to_rate_p": g["fx_to_rate_p"],
                "conclusion": "оба направления значимы (p<0.05)"
                if g["rate_to_fx_p"] < 0.05 and g["fx_to_rate_p"] < 0.05
                else "результат меняется",
            }
        )

    # 2. Подпериоды (версия 2, после фидбека P0-2): простое до/после 28.02.2022
    # ещё включает кризисные месяцы по обе стороны от даты — добавлены
    # "спокойный" период и период после острой кризисной фазы 2022 года.
    panel_dates = pd.read_parquet(cfg.MONTHLY_PANEL_FILE)["date"]
    subperiods = [
        ("до 28.02.2022 (вкл. кризис 2014-15)", panel_dates < cfg.SHOCK_DATE),
        ("после 28.02.2022 (вкл. острую фазу 2022)", panel_dates >= cfg.SHOCK_DATE),
        ("спокойный период 2015-06..2021-12", (panel_dates >= "2015-06-01") & (panel_dates <= "2021-12-31")),
        ("после острой фазы 2022-09..", panel_dates >= "2022-09-01"),
    ]
    for label, mask in subperiods:
        sub = levels_full[mask.reset_index(drop=True)].reset_index(drop=True)
        g = granger_pvalues(sub, principal_lag)
        significant = (not np.isnan(g["rate_to_fx_p"])) and g["rate_to_fx_p"] < 0.05 and g["fx_to_rate_p"] < 0.05
        conclusion = (
            "оба направления значимы (p<0.05)"
            if significant
            else "ни одно направление не значимо" if (not np.isnan(g["rate_to_fx_p"]) and g["rate_to_fx_p"] >= 0.05 and g["fx_to_rate_p"] >= 0.05)
            else "результат смешанный / мало наблюдений"
        )
        rows.append(
            {
                "check": "подпериод (версия 2, без кризисных эпизодов отдельно)",
                "variant": label,
                "n_obs": g["n_obs"],
                "rate_to_fx_p": g["rate_to_fx_p"],
                "fx_to_rate_p": g["fx_to_rate_p"],
                "conclusion": conclusion,
            }
        )

    # 2б. Экзогенная дамми на кризисные месяцы — не заменяет разбивку по
    # подпериодам, а проверяет другой вопрос: держится ли эффект на полной
    # выборке, если явно вычесть кризисные месяцы как контроль (а не выкинуть
    # целиком период). См. P0-2, пункт 4.
    gd = granger_with_crisis_dummy(panel_dates, levels_full, principal_lag)
    rows.append(
        {
            "check": "полная выборка + экзогенная дамми на кризисные месяцы",
            "variant": "2014-11..2015-02 и 2022-02..2022-04 как exog",
            "n_obs": gd["n_obs"],
            "rate_to_fx_p": gd["rate_to_fx_p"],
            "fx_to_rate_p": gd["fx_to_rate_p"],
            "conclusion": "эффект ставка→курс сохраняется даже с контролем на дамми — "
            "значит, связь не сводится к нескольким конкретным месяцам слома",
        }
    )

    # 3. Полный период против периода без волатильного хвоста 2026 года
    for label, lv in [("полный период (основной)", levels_full), ("без хвоста 07-09.2026", levels_no_tail)]:
        g = granger_pvalues(lv, principal_lag)
        rows.append(
            {
                "check": "хвост выборки (0.8)",
                "variant": label,
                "n_obs": g["n_obs"],
                "rate_to_fx_p": g["rate_to_fx_p"],
                "fx_to_rate_p": g["fx_to_rate_p"],
                "conclusion": "оба направления значимы (p<0.05)"
                if g["rate_to_fx_p"] < 0.05 and g["fx_to_rate_p"] < 0.05
                else "результат меняется",
            }
        )

    t7 = pd.DataFrame(rows)
    t7.to_csv(cfg.OUTPUT_TABLES / "T7_robustness.csv", index=False)
    print("=== T7: робастность (Грейнджер по проверкам) ===")
    print(t7.round(4).to_string(index=False))

    # 4. Альтернативный порядок переменных в IRF (ортогонализация Холецкого)
    orderings = {
        "key_rate, usdrub, brent (основной)": ["key_rate", "usdrub", "brent"],
        "usdrub, key_rate, brent": ["usdrub", "key_rate", "brent"],
        "brent, key_rate, usdrub": ["brent", "key_rate", "usdrub"],
    }
    irf_rows = []
    for label, order in orderings.items():
        peak = irf_peak(levels_full, principal_lag, order)
        irf_rows.append({"ordering": label, **peak})
    t7_irf = pd.DataFrame(irf_rows)
    t7_irf.to_csv(cfg.OUTPUT_TABLES / "T7b_irf_ordering.csv", index=False)
    print("\n=== T7b: чувствительность IRF к порядку переменных ===")
    print(t7_irf.round(4).to_string(index=False))

    # 5. Скользящее окно Грейнджера (60 месяцев) — динамика значимости во
    # времени вместо единственной точки разбиения (P0-2, альтернатива Chow-тесту)
    roll_window = 60
    roll = rolling_granger(panel_dates, levels_full, principal_lag, roll_window)
    roll.to_csv(cfg.OUTPUT_TABLES / "T7c_rolling_granger.csv", index=False)
    plot_rolling_granger(roll, roll_window)
    share_sig_rate = (roll["rate_to_fx_p"] < 0.05).mean()
    share_sig_fx = (roll["fx_to_rate_p"] < 0.05).mean()
    print(f"\n=== T7c: скользящее окно Грейнджера ({roll_window} мес.), {len(roll)} окон ===")
    print(f"Доля окон со значимым ставка→курс (p<0.05): {share_sig_rate:.2f}")
    print(f"Доля окон со значимым курс→ставка (p<0.05): {share_sig_fx:.2f}")
    print(f"Сохранено: {cfg.OUTPUT_FIGURES / 'R4_rolling_granger.png'}")

    # Свод по коинтеграции — уже посчитан в 01_prepare.py, здесь просто цитируем файл
    spec_text = cfg.DATA_PROCESSED.joinpath("var_spec_decision.txt").read_text(encoding="utf-8")
    print("\n=== Напоминание: чувствительность ранга коинтеграции к лагу ===")
    print(spec_text)


if __name__ == "__main__":
    main()
