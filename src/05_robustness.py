"""Чувствительность к лагам, периодам, дамми и порядку Холецкого."""

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
    import importlib
    prepare = importlib.import_module("src.01_prepare")
    panel = prepare.build_monthly_panel(prepare.load_keyrate(), prepare.load_usdrub(),
                                         prepare.load_brent(), rate_agg, fx_agg)
    levels = panel[VARS].copy()
    levels[["usdrub", "brent"]] = np.log(levels[["usdrub", "brent"]])
    return levels


def granger_pvalues(levels: pd.DataFrame, lag: int, exog: np.ndarray | None = None) -> dict:
    d = levels.diff().dropna()
    if exog is not None:
        exog = exog[-len(d):]
        exog = exog[:, np.any(exog[lag:] != 0, axis=0)]
        if exog.shape[1] == 0:
            exog = None
    n_exog = 0 if exog is None else exog.shape[1]
    if len(d)-lag <= lag*len(VARS)+1+n_exog+2:
        return {"rate_to_fx_p": np.nan, "fx_to_rate_p": np.nan, "n_obs": len(d)-lag}
    res = VAR(d.values, exog=exog).fit(lag)
    c1 = res.test_causality(caused=1, causing=[0], kind="f")
    c2 = res.test_causality(caused=0, causing=[1], kind="f")
    return {"rate_to_fx_p": c1.pvalue, "fx_to_rate_p": c2.pvalue, "n_obs": res.nobs}


def result_label(rate_p: float, fx_p: float) -> str:
    if not (np.isfinite(rate_p) and np.isfinite(fx_p)):
        return "недостаточно эффективных наблюдений"
    directions = []
    if rate_p < .05:
        directions.append("ставка→курс")
    if fx_p < .05:
        directions.append("курс→ставка")
    return "p<0.05: " + ", ".join(directions) if directions else "оба p>=0.05; отсутствие связи не установлено"


def effect_size_ci(levels: pd.DataFrame, lag: int) -> dict:
    res = VAR(levels.diff().dropna().values).fit(lag)
    parameter_rows = 1 + np.arange(lag)*len(VARS)
    flat_indices = parameter_rows*len(VARS) + VARS.index("usdrub")
    coefficient_sum = res.params[parameter_rows, VARS.index("usdrub")].sum()
    covariance = res.cov_params()[np.ix_(flat_indices, flat_indices)]
    se = np.sqrt(covariance.sum())
    return {"lag_order": lag, "sum_rate_lag_coefficients": coefficient_sum,
            "ci_lo": coefficient_sum-1.96*se, "ci_hi": coefficient_sum+1.96*se,
            "interpretation": "сумма условных коэффициентов уравнения Δlog курса; динамический отклик дан отдельно в IRF"}


def _month_index(dates: pd.Series, month: str) -> int | None:
    idx = dates[dates.dt.to_period("M") == pd.Period(month, freq="M")].index
    return int(idx[0]) if len(idx) else None


def crisis_dummy_matrix(dates: pd.Series, months: list, with_lag_propagation: bool, lag: int = cfg.VAR_LAG) -> np.ndarray | None:
    idx_set = set()
    for m in months:
        i = _month_index(dates, m)
        if i is None:
            continue
        targets = [i] if not with_lag_propagation else list(range(i, i+lag+1))
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
    all_crisis_months = CRISIS_MONTHS_2022 + CRISIS_MONTHS_1415
    rows = []
    global_dummy = crisis_dummy_matrix(dates.reset_index(drop=True), all_crisis_months, True, lag)
    for start in range(0, len(levels) - window + 1):
        sub = levels.iloc[start : start + window].reset_index(drop=True)
        sub_dates = dates.iloc[start : start + window].reset_index(drop=True)
        g = granger_pvalues(sub, lag)

        dummy = None if global_dummy is None else global_dummy[start:start+window]
        if dummy is None:
            g_neutral = g
        else:
            try:
                g_neutral = granger_pvalues(sub, lag, exog=dummy)
            except np.linalg.LinAlgError:


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
        label="ставка → курс, дамми кризисных изменений и следующих лагов",
    )
    ax.axhline(0.05, color="red", lw=1, ls="--", label="p = 0.05")
    ax.set_yscale("log")
    ax.set_ylim(1e-8, 2)
    ax.set_ylabel("p-значение (лог. шкала, обрезано на 10⁻⁸)")
    ax.set_xlabel(f"Конец скользящего окна ({window} месяцев)")
    ax.set_title(
        f"Скользящий тест Грейнджера ({window} мес.): чувствительность\n"
        "к включению дамми кризисных изменений и следующих лагов"
    )
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
    shock_sd = np.linalg.cholesky(res.sigma_u)[impulse_idx, impulse_idx]
    path = irf.orth_irfs[:, response_idx, impulse_idx] / shock_sd
    peak_idx = int(np.argmax(np.abs(path)))
    cum3 = float(np.sum(path[:4]))
    return {
        "peak_horizon": peak_idx,
        "peak_value_per_pp": path[peak_idx],
        "sign": "+" if path[peak_idx] > 0 else "-",
        "cum_effect_h3_per_pp": cum3,
        "own_shock_per_pp": float(irf.orth_irfs[0, impulse_idx, impulse_idx]/shock_sd),
        "note": "нормировка на собственный одновременный импульс P[j,j]; порядок задаёт идентификационные ограничения",
    }


def main() -> None:
    rows = []

    levels_full = load_levels(exclude_tail=False)
    levels_no_tail = load_levels(exclude_tail=True)
    principal_lag = cfg.VAR_LAG
    panel_dates = pd.read_parquet(cfg.MONTHLY_PANEL_FILE)["date"]


    for lag in [1, 2, 3]:
        g = granger_pvalues(levels_full, lag)
        rows.append(
            {
                "check": "альтернативный лаг",
                "variant": f"VAR({lag})" + (" (основной)" if lag == principal_lag else ""),
                "n_obs": g["n_obs"],
                "rate_to_fx_p": g["rate_to_fx_p"],
                "fx_to_rate_p": g["fx_to_rate_p"],
                "conclusion": "оба направления значимы (p<0.05)"
                if g["rate_to_fx_p"] < 0.05 and g["fx_to_rate_p"] < 0.05
                else "результат меняется",
            }
        )


    subperiods = [
        ("до 28.02.2022 (вкл. кризис 2014-15)", panel_dates < cfg.SHOCK_DATE),
        ("после 28.02.2022 (вкл. острую фазу 2022)", panel_dates >= cfg.SHOCK_DATE),
        ("спокойный период 2015-06..2021-12 (основной)", (panel_dates >= "2015-06-01") & (panel_dates <= "2021-12-31")),
        ("спокойный период, начало сдвинуто на 7 мес.: 2016-01..2021-12", (panel_dates >= "2016-01-01") & (panel_dates <= "2021-12-31")),
        ("спокойный период, конец сдвинут на 6 мес.: 2015-06..2021-06", (panel_dates >= "2015-06-01") & (panel_dates <= "2021-06-30")),
        ("после острой фазы 2022-09..", panel_dates >= "2022-09-01"),
        ("до смены измерения курса, полные месяцы по 2024-05", panel_dates < "2024-06-01"),
        ("после смены измерения курса, полные месяцы с 2024-07", panel_dates >= "2024-07-01"),
    ]
    for label, mask in subperiods:
        sub = levels_full[mask.reset_index(drop=True)].reset_index(drop=True)
        g = granger_pvalues(sub, principal_lag)
        significant = (not np.isnan(g["rate_to_fx_p"])) and g["rate_to_fx_p"] < 0.05 and g["fx_to_rate_p"] < 0.05
        not_significant = (not np.isnan(g["rate_to_fx_p"])) and g["rate_to_fx_p"] >= 0.05 and g["fx_to_rate_p"] >= 0.05
        conclusion = (
            "оба направления значимы (p<0.05)" if significant
            else "ни одно направление не значимо (не значит, что эффекта нет - см. мощность)" if not_significant
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
                "n_obs": res.nobs,
                "rate_to_fx_p": c1.pvalue,
                "fx_to_rate_p": c2.pvalue,
                "conclusion": "значимость исчезает" if c1.pvalue >= 0.05 else "значимость сохраняется",
            }
        )


    for label, lv in [("полный период (основной)", levels_full), ("без хвоста 07-08.2026", levels_no_tail)]:
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
                "conclusion": result_label(g["rate_to_fx_p"], g["fx_to_rate_p"]),
            }
        )

    for row in rows:
        row["conclusion"] = result_label(row["rate_to_fx_p"], row["fx_to_rate_p"])
    t7 = pd.DataFrame(rows)
    t7.to_csv(cfg.OUTPUT_TABLES / "T7_robustness.csv", index=False)
    print("=== T7: робастность (Грейнджер по проверкам) ===")
    print(t7.round(4).to_string(index=False))


    es = effect_size_ci(levels_full, principal_lag)
    es_df = pd.DataFrame([es])
    es_df.to_csv(cfg.OUTPUT_TABLES / "T7d_effect_size.csv", index=False)
    print("\n=== T7d: размер эффекта (сумма коэф. при лагах ставки в уравнении курса) ===")
    print(es_df.round(5).to_string(index=False))


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


    roll_window = 60
    roll = rolling_granger(panel_dates, levels_full, principal_lag, roll_window)
    roll.to_csv(cfg.OUTPUT_TABLES / "T7c_rolling_granger.csv", index=False)
    plot_rolling_granger(roll, roll_window)
    share_sig_rate = (roll["rate_to_fx_p"].dropna() < 0.05).mean()
    share_sig_rate_neutral = (roll["rate_to_fx_p_neutralized"].dropna() < 0.05).mean()
    print(f"\n=== T7c: скользящее окно Грейнджера ({roll_window} мес.), {len(roll)} окон ===")
    print(f"Доля окон со значимым ставка→курс, как есть (p<0.05): {share_sig_rate:.2f}")
    print(f"Доля окон со значимым ставка→курс, кризис нейтрализован (p<0.05): {share_sig_rate_neutral:.2f}")
    print(f"Сохранено: {cfg.OUTPUT_FIGURES / 'R4_rolling_granger.png'}")

    spec_text = cfg.DATA_PROCESSED.joinpath("var_spec_decision.txt").read_text(encoding="utf-8")
    print("\n=== Напоминание: чувствительность ранга коинтеграции к лагу ===")
    print(spec_text)


if __name__ == "__main__":
    main()
