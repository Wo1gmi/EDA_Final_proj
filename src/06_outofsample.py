"""Прогноз с расширяющимся обучением и приближённый тест Clark-West."""

import sys
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.regression.linear_model import OLS
from statsmodels.tsa.vector_ar.var_model import VAR

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config as cfg

MIN_TRAIN = 36
MAX_H = 3
LAG = cfg.VAR_LAG
CRISIS_YEARS = {2014, 2015, 2022}


def load_diffed() -> tuple[pd.DataFrame, pd.Series]:
    panel = pd.read_parquet(cfg.MONTHLY_PANEL_FILE)
    data = panel[["key_rate", "usdrub", "brent"]].copy()
    data[["usdrub", "brent"]] = np.log(data[["usdrub", "brent"]])
    diffed = data.diff().dropna().reset_index(drop=True)
    return diffed, panel["date"].iloc[1:].reset_index(drop=True)


def rolling_forecast(diffed: pd.DataFrame, diff_dates: pd.Series) -> pd.DataFrame:
    rows = []
    for origin in range(MIN_TRAIN, len(diffed)):
        train3 = diffed.iloc[:origin][["key_rate", "usdrub", "brent"]].values
        train2 = diffed.iloc[:origin][["usdrub", "brent"]].values
        steps = min(MAX_H, len(diffed)-origin)
        fc3 = VAR(train3).fit(LAG).forecast(train3[-LAG:], steps=steps)
        fc2 = VAR(train2).fit(LAG).forecast(train2[-LAG:], steps=steps)
        for horizon in range(1, steps+1):
            target_idx = origin+horizon-1
            rows.append({"origin": origin, "origin_date": diff_dates.iloc[origin-1],
                         "train_end_date": diff_dates.iloc[origin-1], "n_train": origin,
                         "h": horizon, "target_date": diff_dates.iloc[target_idx],
                         "target_year": diff_dates.iloc[target_idx].year,
                         "actual_dlog_usdrub": diffed["usdrub"].iloc[target_idx],
                         "naive": 0.0, "var2_no_rate": fc2[horizon-1,0],
                         "var3_with_rate": fc3[horizon-1,1]})
    forecasts = pd.DataFrame(rows)
    if not np.isfinite(forecasts[["actual_dlog_usdrub", "naive", "var2_no_rate", "var3_with_rate"]]).all().all():
        raise ValueError("Часть прогнозов содержит пропуски или бесконечные значения.")
    return forecasts


def summarize(forecasts: pd.DataFrame) -> pd.DataFrame:
    crisis = forecasts["target_year"].isin(CRISIS_YEARS)
    observed_crisis = ", ".join(str(year) for year in sorted(set(forecasts.loc[crisis,"target_year"])))
    rows = []
    for label, mask in [("вся OOS-выборка", np.ones(len(forecasts), dtype=bool)),
                        (f"кризисные цели, доступный год: {observed_crisis}", crisis),
                        ("остальные годы OOS-выборки", ~crisis)]:
        for horizon in range(1, MAX_H+1):
            sub = forecasts[mask & forecasts["h"].eq(horizon)]
            if sub.empty:
                continue
            row = {"regime": label, "h": horizon, "n": len(sub),
                   "target_min": sub["target_date"].min(), "target_max": sub["target_date"].max()}
            for model in ["naive", "var2_no_rate", "var3_with_rate"]:
                error = sub["actual_dlog_usdrub"]-sub[model]
                row[f"rmse_{model}"] = np.sqrt(np.mean(error**2))
                row[f"mae_{model}"] = np.mean(np.abs(error))
            rows.append(row)
    return pd.DataFrame(rows)


def clark_west(forecasts: pd.DataFrame) -> pd.DataFrame:
    f1 = forecasts[forecasts["h"].eq(1)].sort_values("target_date")
    n = len(f1)
    hac_lags = max(1, int(np.floor(4*(n/100)**(2/9))))
    actual, unrestricted = f1["actual_dlog_usdrub"], f1["var3_with_rate"]
    rows = []
    for restricted_name in ["naive", "var2_no_rate"]:
        restricted = f1[restricted_name]
        raw_difference = (actual-restricted)**2-(actual-unrestricted)**2
        adjusted_difference = raw_difference+(restricted-unrestricted)**2
        fit = OLS(adjusted_difference.to_numpy(), np.ones((n,1))).fit(
            cov_type="HAC", cov_kwds={"maxlags": hac_lags, "use_correction": True})
        z = float(fit.tvalues[0])
        p_value = float(stats.norm.sf(z))
        rows.append({"restricted_model": restricted_name, "unrestricted_model": "var3_with_rate",
                     "h": 1, "n": n, "hac_lags": hac_lags,
                     "mean_raw_loss_difference": raw_difference.mean(),
                     "mean_adjusted_loss_difference": adjusted_difference.mean(),
                     "hac_standard_error": fit.bse[0], "z_stat": z, "p_one_sided": p_value,
                     "conclusion": "приближённый тест поддерживает добавочную прогнозную информацию"
                         if p_value<.05 else "добавочная прогнозная информация не подтверждена на 5%",
                     "method": "Clark-West для вложенных моделей, HAC Bartlett; асимптотическая аппроксимация"})
    return pd.DataFrame(rows)


def write_slide_values() -> None:
    files = {"granger": "T4_granger.csv", "irf": "T3c_irf_bootstrap.csv",
             "garch_selection": "T5b_garch_spec_selection.csv", "garch": "T5_garch.csv",
             "event": "T6b_event_study_stratified.csv", "event_before_after": "T6c_before_after.csv",
             "forecast_summary": "T8_outofsample_summary.csv", "forecast_comparison": "T8b_clark_west.csv",
             "robustness": "T7_robustness.csv", "irf_ordering": "T7b_irf_ordering.csv",
             "effect_size": "T7d_effect_size.csv", "lag_selection": "T3_lag_selection.csv"}
    values = {"source_audit": json.loads((cfg.OUTPUT_TABLES/"T0_data_audit.json").read_text()),
              "baseline_var_lag": cfg.VAR_LAG, "authors": cfg.__author__.split("; ")}
    for key, filename in files.items():
        values[key] = json.loads(pd.read_csv(cfg.OUTPUT_TABLES/filename).to_json(orient="records"))
    rolling = pd.read_csv(cfg.OUTPUT_TABLES/"T7c_rolling_granger.csv")
    values["rolling_summary"] = {"n_windows": len(rolling)}
    for key in ["rate_to_fx_p", "rate_to_fx_p_neutralized"]:
        valid = rolling[key].dropna()
        values["rolling_summary"][key] = {"n_valid": len(valid), "fraction_below_005": float((valid<.05).mean())}
    (cfg.OUTPUT_TABLES/"slide_values.json").write_text(json.dumps(values,ensure_ascii=False,indent=2)+"\n", encoding="utf-8")


def main() -> None:
    diffed, dates = load_diffed()
    forecasts = rolling_forecast(diffed, dates)
    forecasts.to_csv(cfg.OUTPUT_TABLES / "T8_outofsample_forecasts.csv", index=False)
    summary = summarize(forecasts)
    summary.to_csv(cfg.OUTPUT_TABLES / "T8_outofsample_summary.csv", index=False)
    comparison = clark_west(forecasts)
    comparison.to_csv(cfg.OUTPUT_TABLES / "T8b_clark_west.csv", index=False)
    outdated = cfg.OUTPUT_TABLES / "T8b_diebold_mariano.csv"
    if outdated.exists():
        outdated.unlink()
    write_slide_values()
    print(f"Прогнозы: {len(forecasts)}; минимальное обучение {MIN_TRAIN} разностей; фиксированный VAR({LAG}).")
    print(summary.to_string(index=False, float_format=lambda value: f"{value:.5f}"))
    print(comparison.round(5).to_string(index=False))
    print("Режимы сравниваются описательно по RMSE/MAE. Проверка Clark-West относится к полной OOS-выборке, "
          "горизонту 1 и приближённой асимптотике. Данные взяты из текущего снимка; исторические версии и "
          "календарь их доступности не восстановлены. Целевая переменная: месячное Δlog курса в месяце t+h.")


if __name__ == "__main__":
    main()
