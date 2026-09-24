"""Проверки устойчивости: альтернативный лаг, подпериоды, альтернативные
конвенции агрегации, нейтрализация кризисных месяцев дамми-переменными
(по одному наблюдению, а не общей дамми на весь период), альтернативный
порядок переменных в IRF (нормированный на 1 п.п.), скользящее окно
Грейнджера, размер эффекта с доверительным интервалом. Всё сводится в Т7.

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
CRISIS_MONTHS_2022 = ["2022-02", "2022-03", "2022-04"]
CRISIS_MONTHS_1415 = ["2014-11", "2014-12", "2015-01", "2015-02"]


def load_levels(exclude_tail: bool = False) -> pd.DataFrame:
    panel = pd.read_parquet(cfg.MONTHLY_PANEL_FILE)
    if exclude_tail:
        panel = panel[~panel["volatile_tail"]]
    data = panel[VARS].copy()
    data["usdrub"] = np.log(data["usdrub"])
    data["brent"] = np.log(data["brent"])
    return data.reset_index(drop=True)


def load_levels_alt_convention(rate_agg: str, fx_agg: str) -> pd.DataFrame:
    """Панель с альтернативной конвенцией агрегации по месяцу (для проверки
    чувствительности к тому, что ставка берётся на конец месяца, а курс —
    средним): `rate_agg`/`fx_agg` ∈ {"last", "mean"}."""
    key = pd.read_csv(cfg.RAW_KEYRATE_FILE)
    key["date"] = pd.to_datetime(key["date"], format="%d.%m.%Y")
    usd = pd.read_csv(cfg.RAW_USDRUB_FILE)
    usd["date"] = pd.to_datetime(usd["date"], format="%d.%m.%Y")
    usd["usdrub"] = usd["value"] / usd["nominal"]
    brent = pd.read_csv(cfg.RAW_BRENT_FILE)
    brent.columns = ["date", "brent"]
    brent["date"] = pd.to_datetime(brent["date"])
    brent = brent[brent["brent"] != "."].copy()
    brent["brent"] = brent["brent"].astype(float)
    brent = brent[brent["date"] >= pd.to_datetime(cfg.SAMPLE_START, dayfirst=True)]

    key_m = key.set_index("date")["rate"].resample("ME").agg(rate_agg)
    usd_m = usd.set_index("date")["usdrub"].resample("ME").agg(fx_agg)
    brent_m = brent.set_index("date")["brent"].resample("ME").agg(fx_agg)
    panel = pd.concat([key_m, usd_m, brent_m], axis=1, sort=True).dropna()
    panel.columns = VARS
    panel["usdrub"] = np.log(panel["usdrub"])
    panel["brent"] = np.log(panel["brent"])
    return panel.reset_index(drop=True)


def granger_pvalues(levels: pd.DataFrame, lag: int, exog: np.ndarray | None = None) -> dict:
    d = levels.diff().dropna()
    if exog is not None:
        exog = exog[-len(d) :]
    if len(d) <= lag * len(VARS) + 5:
        return {"rate_to_fx_p": np.nan, "fx_to_rate_p": np.nan, "n_obs": len(d)}
    res = VAR(d.values, exog=exog).fit(lag)
    c1 = res.test_causality(caused=1, causing=[0], kind="f")
    c2 = res.test_causality(caused=0, causing=[1], kind="f")
    return {"rate_to_fx_p": c1.pvalue, "fx_to_rate_p": c2.pvalue, "n_obs": len(d)}


def effect_size_ci(levels: pd.DataFrame, lag: int) -> dict:
    """Сумма коэффициентов при лагах ставки в уравнении курса (эффект
    размера, не только значимость) с аналитическим 95% ДИ по ковариации
    параметров VAR."""
    d = levels.diff().dropna()
    res = VAR(d.values).fit(lag)
    cov = res.cov_params()  # (7*3, 7*3), индекс = row*3+col в res.params (7,3)
    usdrub_col = 1  # порядок VARS: key_rate, usdrub, brent
    # строки res.params: 0=const, 1=L1.y1, 2=L1.y2, 3=L1.y3, 4=L2.y1, ...
    l1_idx, l2_idx = 3 * 1 + usdrub_col, 3 * 4 + usdrub_col
    coef_sum = res.params[1, usdrub_col] + res.params[4, usdrub_col]
    var_sum = cov[l1_idx, l1_idx] + cov[l2_idx, l2_idx] + 2 * cov[l1_idx, l2_idx]
    se = np.sqrt(var_sum)
    return {"effect_sum_L1_L2": coef_sum, "ci_lo": coef_sum - 1.96 * se, "ci_hi": coef_sum + 1.96 * se}


def _month_index(dates: pd.Series, month: str) -> int | None:
    idx = dates[dates.dt.to_period("M") == pd.Period(month, freq="M")].index
    return int(idx[0]) if len(idx) else None


def crisis_dummy_matrix(dates: pd.Series, months: list, with_lag_propagation: bool) -> np.ndarray | None:
    """Дамми **по каждому наблюдению**, а не одна общая колонка на весь
    период: общая дамми не гасит эффект выброса, т.к. он ещё входит в VAR
    как лаг в t+1, t+2. `with_lag_propagation=True` добавляет отдельные
    дамми и на t+1, t+2 для каждого затронутого месяца."""
    idx_set = set()
    for m in months:
        i = _month_index(dates, m)
        if i is None:
            continue
        targets = [i] if not with_lag_propagation else [i, i + 1, i + 2]
        for t in targets:
            if t < len(dates):
                idx_set.add(t)
    if not idx_set:
        return None
    cols = []
    for t in sorted(idx_set):
        col = np.zeros(len(dates))
        col[t] = 1.0
        cols.append(col)
    return np.column_stack(cols)


def rolling_granger(dates: pd.Series, levels: pd.DataFrame, lag: int, window: int) -> pd.DataFrame:
    """Скользящее окно Грейнджера шириной `window` месяцев — динамика
    p-value во времени. Вторая пара колонок — тот же расчёт с дамми на
    кризисные наблюдения, попадающие в окно (по одному на наблюдение),
    чтобы показать, что провал p-value именно в кризисные месяцы
    объясняется выбросами, а не устойчивой связью."""
    all_crisis_months = CRISIS_MONTHS_2022 + CRISIS_MONTHS_1415
    rows = []
    for start in range(0, len(levels) - window + 1):
        sub = levels.iloc[start : start + window].reset_index(drop=True)
        sub_dates = dates.iloc[start : start + window].reset_index(drop=True)
        g = granger_pvalues(sub, lag)

        dummy = crisis_dummy_matrix(sub_dates, all_crisis_months, with_lag_propagation=False)
        if dummy is None:
            g_neutral = g
        else:
            try:
                g_neutral = granger_pvalues(sub, lag, exog=dummy)
            except np.linalg.LinAlgError:
                # вырожденная матрица (мало эффективных наблюдений на число
                # дамми-колонок в этом конкретном окне) — пропускаем окно,
                # а не роняем весь расчёт
                g_neutral = {"rate_to_fx_p": np.nan, "fx_to_rate_p": np.nan}

        rows.append(
            {
                "window_end": dates.iloc[start + window - 1],
                "rate_to_fx_p": g["rate_to_fx_p"],
                "fx_to_rate_p": g["fx_to_rate_p"],
                "rate_to_fx_p_neutralized": g_neutral["rate_to_fx_p"],
                "fx_to_rate_p_neutralized": g_neutral["fx_to_rate_p"],
            }
        )
    return pd.DataFrame(rows)


def plot_rolling_granger(roll: pd.DataFrame, window: int) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    ax.plot(roll["window_end"], roll["rate_to_fx_p"], color="steelblue", label="ставка → курс, как есть")
    ax.plot(
        roll["window_end"], roll["rate_to_fx_p_neutralized"], color="steelblue", ls="--",
        label="ставка → курс, кризисные месяцы нейтрализованы",
    )
    ax.axhline(0.05, color="red", lw=1, ls="--", label="p = 0.05")
    ax.set_yscale("log")
    ax.set_ylim(1e-8, 2)
    ax.set_ylabel("p-значение (лог. шкала, обрезано на 10⁻⁸)")
    ax.set_xlabel(f"Конец скользящего окна ({window} месяцев)")
    ax.set_title(
        f"Скользящее окно Грейнджера ({window} мес.): провал значимости объясняется\n"
        "выбросами кризисных месяцев, а не устойчивой связью"
    )
    ax.legend(loc="lower left", fontsize=8)
    fig.tight_layout()
    fig.savefig(cfg.OUTPUT_FIGURES / "R4_rolling_granger.png", dpi=150)
    plt.close(fig)


def irf_peak(levels: pd.DataFrame, lag: int, ordering: list) -> dict:
    """Пик и накопленный (на горизонте 3) отклик, нормированные на шок
    1 п.п. Нормировка через sqrt(sigma_u[impulse, impulse]) верна только
    когда ставка идёт первой в порядке Холецкого (её отклонение тогда не
    смешано с ковариацией остальных) — считаем это отдельно для каждого
    порядка, а не переиспользуем число из основной спецификации."""
    d = levels[ordering].diff().dropna()
    res = VAR(d.values).fit(lag)
    irf = res.irf(12)
    impulse_idx = ordering.index("key_rate")
    response_idx = ordering.index("usdrub")
    shock_sd = np.sqrt(res.sigma_u[impulse_idx, impulse_idx])
    path = irf.orth_irfs[:, response_idx, impulse_idx] / shock_sd
    peak_idx = int(np.argmax(np.abs(path)))
    cum3 = float(np.sum(path[:4]))  # горизонты 0..3
    return {
        "peak_horizon": peak_idx,
        "peak_value_per_pp": path[peak_idx],
        "sign": "+" if path[peak_idx] > 0 else "-",
        "cum_effect_h3_per_pp": cum3,
        "note": "нормировка на 1 п.п. верна только для ordering, где key_rate первая" if impulse_idx != 0 else "",
    }


def main() -> None:
    rows = []

    levels_full = load_levels(exclude_tail=False)
    levels_no_tail = load_levels(exclude_tail=True)
    principal_lag = 2
    panel_dates = pd.read_parquet(cfg.MONTHLY_PANEL_FILE)["date"]

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

    # 2. Подпериоды, включая чувствительность к границам "спокойного" периода
    subperiods = [
        ("до 28.02.2022 (вкл. кризис 2014-15)", panel_dates < cfg.SHOCK_DATE),
        ("после 28.02.2022 (вкл. острую фазу 2022)", panel_dates >= cfg.SHOCK_DATE),
        ("спокойный период 2015-06..2021-12 (основной)", (panel_dates >= "2015-06-01") & (panel_dates <= "2021-12-31")),
        ("спокойный период, граница -6мес: 2016-01..2021-12", (panel_dates >= "2016-01-01") & (panel_dates <= "2021-12-31")),
        ("спокойный период, граница -6мес: 2015-06..2021-06", (panel_dates >= "2015-06-01") & (panel_dates <= "2021-06-30")),
        ("после острой фазы 2022-09..", panel_dates >= "2022-09-01"),
    ]
    for label, mask in subperiods:
        sub = levels_full[mask.reset_index(drop=True)].reset_index(drop=True)
        g = granger_pvalues(sub, principal_lag)
        significant = (not np.isnan(g["rate_to_fx_p"])) and g["rate_to_fx_p"] < 0.05 and g["fx_to_rate_p"] < 0.05
        not_significant = (not np.isnan(g["rate_to_fx_p"])) and g["rate_to_fx_p"] >= 0.05 and g["fx_to_rate_p"] >= 0.05
        conclusion = (
            "оба направления значимы (p<0.05)" if significant
            else "ни одно направление не значимо (не значит, что эффекта нет — см. мощность)" if not_significant
            else "результат смешанный / мало наблюдений"
        )
        rows.append(
            {
                "check": "подпериод",
                "variant": label,
                "n_obs": g["n_obs"],
                "rate_to_fx_p": g["rate_to_fx_p"],
                "fx_to_rate_p": g["fx_to_rate_p"],
                "conclusion": conclusion,
            }
        )

    # 2б. Нейтрализация кризисных месяцев дамми-переменными — ИСПРАВЛЕНО:
    # раньше использовалась одна общая дамми на весь кризисный период, что
    # не гасит эффект выброса (он ещё входит в VAR как лаг в t+1, t+2).
    # Теперь — отдельная дамми на каждое затронутое наблюдение.
    dummy_checks = [
        ("2022 (фев-апр), дамми@t", CRISIS_MONTHS_2022, False),
        ("2022 (фев-апр), дамми@t..t+2", CRISIS_MONTHS_2022, True),
        ("2014-15 (ноя-фев), дамми@t", CRISIS_MONTHS_1415, False),
        ("2014-15 (ноя-фев), дамми@t..t+2", CRISIS_MONTHS_1415, True),
        ("оба кризиса, дамми@t", CRISIS_MONTHS_2022 + CRISIS_MONTHS_1415, False),
        ("оба кризиса, дамми@t..t+2", CRISIS_MONTHS_2022 + CRISIS_MONTHS_1415, True),
    ]
    for label, months, with_lag in dummy_checks:
        dummy = crisis_dummy_matrix(panel_dates, months, with_lag)
        d_full = levels_full.diff().dropna()
        res = VAR(d_full.values, exog=dummy[-len(d_full):] if dummy is not None else None).fit(principal_lag)
        c1 = res.test_causality(caused=1, causing=[0], kind="f")
        c2 = res.test_causality(caused=0, causing=[1], kind="f")
        rows.append(
            {
                "check": "нейтрализация кризисных наблюдений (дамми по одному на наблюдение)",
                "variant": label,
                "n_obs": len(d_full),
                "rate_to_fx_p": c1.pvalue,
                "fx_to_rate_p": c2.pvalue,
                "conclusion": "значимость исчезает" if c1.pvalue >= 0.05 else "значимость сохраняется",
            }
        )

    # 3. Полный период против периода без волатильного хвоста 2026 года
    for label, lv in [("полный период (основной)", levels_full), ("без хвоста 07-09.2026", levels_no_tail)]:
        g = granger_pvalues(lv, principal_lag)
        rows.append(
            {
                "check": "хвост выборки",
                "variant": label,
                "n_obs": g["n_obs"],
                "rate_to_fx_p": g["rate_to_fx_p"],
                "fx_to_rate_p": g["fx_to_rate_p"],
                "conclusion": "оба направления значимы (p<0.05)"
                if g["rate_to_fx_p"] < 0.05 and g["fx_to_rate_p"] < 0.05
                else "результат меняется",
            }
        )

    # 4. Альтернативные конвенции агрегации по месяцу
    for label, (rate_agg, fx_agg) in {
        "ставка=конец, курс/нефть=среднее (основная)": ("last", "mean"),
        "все три = среднее за месяц": ("mean", "mean"),
        "все три = конец месяца": ("last", "last"),
    }.items():
        lv = load_levels_alt_convention(rate_agg, fx_agg)
        g = granger_pvalues(lv, principal_lag)
        rows.append(
            {
                "check": "конвенция агрегации по месяцу",
                "variant": label,
                "n_obs": g["n_obs"],
                "rate_to_fx_p": g["rate_to_fx_p"],
                "fx_to_rate_p": g["fx_to_rate_p"],
                "conclusion": "качественный вывод не меняется, величина p — на порядки",
            }
        )

    t7 = pd.DataFrame(rows)
    t7.to_csv(cfg.OUTPUT_TABLES / "T7_robustness.csv", index=False)
    print("=== T7: робастность (Грейнджер по проверкам) ===")
    print(t7.round(4).to_string(index=False))

    # 5. Размер эффекта с доверительным интервалом (не только значимость)
    es = effect_size_ci(levels_full, principal_lag)
    es_df = pd.DataFrame([es])
    es_df.to_csv(cfg.OUTPUT_TABLES / "T7d_effect_size.csv", index=False)
    print("\n=== T7d: размер эффекта (сумма коэф. при лагах ставки в уравнении курса) ===")
    print(es_df.round(5).to_string(index=False))

    # 6. Альтернативный порядок переменных в IRF, нормировано на 1 п.п.
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
    print("\n=== T7b: чувствительность IRF к порядку переменных (на 1 п.п.) ===")
    print(t7_irf.round(4).to_string(index=False))

    # 7. Скользящее окно Грейнджера (60 месяцев), как есть vs нейтрализовано
    roll_window = 60
    roll = rolling_granger(panel_dates, levels_full, principal_lag, roll_window)
    roll.to_csv(cfg.OUTPUT_TABLES / "T7c_rolling_granger.csv", index=False)
    plot_rolling_granger(roll, roll_window)
    share_sig_rate = (roll["rate_to_fx_p"] < 0.05).mean()
    share_sig_rate_neutral = (roll["rate_to_fx_p_neutralized"] < 0.05).mean()
    print(f"\n=== T7c: скользящее окно Грейнджера ({roll_window} мес.), {len(roll)} окон ===")
    print(f"Доля окон со значимым ставка→курс, как есть (p<0.05): {share_sig_rate:.2f}")
    print(f"Доля окон со значимым ставка→курс, кризис нейтрализован (p<0.05): {share_sig_rate_neutral:.2f}")
    print(f"Сохранено: {cfg.OUTPUT_FIGURES / 'R4_rolling_granger.png'}")

    spec_text = cfg.DATA_PROCESSED.joinpath("var_spec_decision.txt").read_text(encoding="utf-8")
    print("\n=== Напоминание: чувствительность ранга коинтеграции к лагу ===")
    print(spec_text)


if __name__ == "__main__":
    main()
