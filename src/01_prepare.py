"""Подготовка данных и диагностика моделируемых рядов."""

import sys
import json
import hashlib
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tools.sm_exceptions import InterpolationWarning
from statsmodels.tsa.stattools import adfuller, kpss
from statsmodels.tsa.vector_ar.var_model import VAR
from statsmodels.tsa.vector_ar.vecm import coint_johansen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config as cfg

VAR_SPEC_FILE = cfg.DATA_PROCESSED / "var_spec_decision.txt"


def within_source_window(df: pd.DataFrame) -> pd.DataFrame:
    start = pd.to_datetime(cfg.SAMPLE_START, dayfirst=True)
    end = pd.to_datetime(cfg.SAMPLE_END, dayfirst=True)
    return df[df["date"].between(start, end)].copy()


def load_keyrate() -> pd.DataFrame:
    df = pd.read_csv(cfg.RAW_KEYRATE_FILE)
    df["date"] = pd.to_datetime(df["date"], format="%d.%m.%Y")
    df = within_source_window(df).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    return df[["date", "rate"]].rename(columns={"rate": "key_rate"})


def load_usdrub() -> pd.DataFrame:
    df = pd.read_csv(cfg.RAW_USDRUB_FILE)
    df["date"] = pd.to_datetime(df["date"], format="%d.%m.%Y")
    df["usdrub"] = df["value"] / df["nominal"]
    df = within_source_window(df).drop_duplicates("date").sort_values("date").reset_index(drop=True)
    return df[["date", "usdrub"]]


def load_brent() -> pd.DataFrame:
    df = pd.read_csv(cfg.RAW_BRENT_FILE)
    df.columns = ["date", "brent"]
    df["date"] = pd.to_datetime(df["date"])
    df["brent"] = pd.to_numeric(df["brent"], errors="coerce")
    df = within_source_window(df).dropna(subset=["brent"])
    return df.drop_duplicates("date").sort_values("date").reset_index(drop=True)


def build_monthly_panel(key: pd.DataFrame, usd: pd.DataFrame, brent: pd.DataFrame,
                        rate_agg: str = "last", fx_agg: str = "mean") -> pd.DataFrame:
    key_m = key.set_index("date")["key_rate"].resample("ME").agg(rate_agg)
    usd_m = usd.set_index("date")["usdrub"].resample("ME").agg(fx_agg)
    brent_m = brent.set_index("date")["brent"].resample("ME").agg(fx_agg)
    panel = pd.concat([key_m, usd_m, brent_m], axis=1, sort=True)
    panel.columns = ["key_rate", "usdrub", "brent"]
    panel = panel.loc[cfg.MONTHLY_START:cfg.MONTHLY_END].dropna().reset_index()
    expected_dates = pd.date_range(cfg.MONTHLY_START, cfg.MONTHLY_END, freq="ME")
    if not panel["date"].equals(pd.Series(expected_dates, name="date")):
        raise ValueError("В полной месячной панели есть пропуски или изменились границы.")
    if (panel[["key_rate", "usdrub", "brent"]] <= 0).any().any():
        raise ValueError("В панели обнаружены неположительные значения.")
    panel["volatile_tail"] = panel["date"] >= pd.to_datetime(cfg.VOLATILE_TAIL_START)
    return panel


def build_daily_returns(usd: pd.DataFrame, key: pd.DataFrame) -> pd.DataFrame:
    df = usd.sort_values("date").reset_index(drop=True).copy()
    df["log_return"] = np.log(df["usdrub"]).diff()
    df = df.dropna(subset=["log_return"])
    df = df[df["date"] >= key["date"].min()].reset_index(drop=True)
    changes = key.assign(change_pp=key["key_rate"].diff())
    changes = changes[changes["change_pp"].notna() & changes["change_pp"].ne(0)].copy()
    changes = changes.rename(columns={"date": "effective_date"})
    changes["fx_proxy_date"] = changes["effective_date"] + pd.Timedelta(days=1)
    changes["matched_official_fx_record"] = changes["fx_proxy_date"].isin(df["date"])
    changes["date_definition"] = "Дата вступления ставки в силу + 1 календарный день; прокси даты наблюдения официального курса"
    changes["announcement_date_verified"] = False
    changes.to_csv(cfg.EVENT_CALENDAR_FILE, index=False)
    if not changes["matched_official_fx_record"].all():
        raise ValueError("Часть прокси дат изменений ставки отсутствует в ряду официального курса.")
    df["rate_effective_proxy_day"] = df["date"].isin(changes["fx_proxy_date"])
    return df


def stationarity_tests(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    model_levels = panel[["key_rate", "usdrub", "brent"]].copy()
    model_levels[["usdrub", "brent"]] = np.log(model_levels[["usdrub", "brent"]])
    for col in model_levels:
        for transform, series in [("model_level", model_levels[col]),
                                  ("model_diff", model_levels[col].diff().dropna())]:
            for regression in ["c", "ct"]:
                adf_stat, adf_p, *_ = adfuller(series, regression=regression, autolag="AIC", result_object=False)
                with warnings.catch_warnings(record=True) as caught:
                    warnings.simplefilter("always", InterpolationWarning)
                    kpss_stat, kpss_p, *_ = kpss(series, regression=regression, nlags="auto")
                bounded = any(issubclass(item.category, InterpolationWarning) for item in caught)
                rows.append({"variable": col, "scale": "percentage_points" if col == "key_rate" else "log",
                             "transform": transform, "regression": regression, "n_obs": len(series),
                             "adf_stat": adf_stat, "adf_p": adf_p, "kpss_stat": kpss_stat,
                             "kpss_p": kpss_p, "kpss_p_is_table_bound": bounded})
    return pd.DataFrame(rows)


def stationarity_decisions(table: pd.DataFrame) -> list[str]:
    lines = []
    for _, row in table.iterrows():
        adf = "отвергается единичный корень" if row.adf_p < .05 else "единичный корень не отвергается"
        kpss_result = "стационарность отвергается" if row.kpss_p < .05 else "стационарность не отвергается"
        boundary = " (табличная граница p)" if row.kpss_p_is_table_bound else ""
        lines.append(f"{row.variable}, {row['transform']}, {row.regression}: ADF {adf}; KPSS {kpss_result}{boundary}.")
    lines.append("Тесты относятся к моделируемым шкалам: ставка в п.п., курс и Brent в логарифмах. "
                 "Расхождение тестов и структурные сдвиги ограничивают классификацию порядка интеграции.")
    return lines


def johansen_rank(data: np.ndarray, k_ar_diff: int) -> tuple[int, list[str]]:
    result = coint_johansen(data, det_order=0, k_ar_diff=k_ar_diff)
    rank, stopped, lines = 0, False, []
    for r, (stat, critical) in enumerate(zip(result.lr1, result.cvt[:, 1])):
        reject = stat > critical
        lines.append(f"r<={r}: trace={stat:.4f}, critical_95={critical:.4f}, reject={reject}")
        if reject and not stopped:
            rank += 1
        else:
            stopped = True
    return rank, lines


def johansen_decision(panel: pd.DataFrame) -> str:
    levels = panel[["key_rate", "usdrub", "brent"]].copy()
    levels[["usdrub", "brent"]] = np.log(levels[["usdrub", "brent"]])
    level_order = VAR(levels.values).select_order(cfg.VAR_MAX_LAG)
    level_p = int(level_order.selected_orders["bic"])
    principal_kd = max(level_p - 1, 0)
    diff_order = VAR(levels.diff().dropna().values).select_order(cfg.VAR_MAX_LAG)
    lines = [f"BIC для VAR в уровнях: p={level_p}; k_ar_diff={principal_kd}.",
             f"BIC для VAR в разностях: p={diff_order.selected_orders['bic']}.",
             f"Основная модель: VAR({cfg.VAR_LAG}) изменений ставки и логарифмов курса/Brent.",
             "Лаг 2 фиксирован для базовой модели и прогноза; лаги 1 и 3 проверяются отдельно.",
             "Тест Йохансена служит диагностикой чувствительности долгосрочной спецификации.",
             "Его интерпретация предполагает интеграцию рядов первого порядка; ADF/KPSS дают ограничения."]
    for kd in sorted({0, 1, 2, 3, principal_kd}):
        rank, detail = johansen_rank(levels.values, kd)
        lines.extend([f"k_ar_diff={kd}: rank={rank}", *detail])
    lines.extend(["VECM с rank=1 и k_ar_diff=1 показана как условная проверка чувствительности.",
                  "Результат VECM зависит от принятого ранга; модель не устанавливает причинный эффект.",
                  "SPEC=var_diff", f"KD={cfg.VAR_LAG}", f"JOHANSEN_KD={principal_kd}"])
    text = "\n".join(lines) + "\n"
    VAR_SPEC_FILE.write_text(text, encoding="utf-8")
    print(text)
    return "var_diff"


def print_audit_facts(key: pd.DataFrame, usd: pd.DataFrame, brent: pd.DataFrame, panel: pd.DataFrame) -> None:
    for name, data in [("Ключевая ставка", key), ("USD/RUB", usd), ("Brent", brent)]:
        print(f"{name}: {len(data)} строк; {data.date.min().date()} .. {data.date.max().date()}")
    print(f"Полные месяцы: {len(panel)}; {panel.date.min().date()} .. {panel.date.max().date()}")
    print(f"Изменений ставки: {int(key.key_rate.diff().dropna().ne(0).sum())}")


def source_audit(panel: pd.DataFrame, daily: pd.DataFrame) -> None:
    sources = []
    for name, path, date_format, value_columns, units in [
        ("key_rate", cfg.RAW_KEYRATE_FILE, "%d.%m.%Y", ["rate"], "проценты годовых"),
        ("usdrub", cfg.RAW_USDRUB_FILE, "%d.%m.%Y", ["nominal", "value"], "рублей за 1 доллар США после деления на nominal"),
        ("brent", cfg.RAW_BRENT_FILE, None, None, "долларов США за баррель")]:
        raw = pd.read_csv(path)
        if name == "brent":
            raw.columns = ["date", "brent"]
            value_columns = ["brent"]
        dates = pd.to_datetime(raw["date"], format=date_format)
        numeric = raw[value_columns].apply(pd.to_numeric, errors="coerce")
        same_date = raw.groupby("date")[value_columns].nunique(dropna=False)
        start = pd.to_datetime(cfg.SAMPLE_START, dayfirst=True)
        end = pd.to_datetime(cfg.SAMPLE_END, dayfirst=True)
        sources.append({"series": name, "raw_rows": len(raw), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                        "raw_min_date": str(dates.min().date()), "raw_max_date": str(dates.max().date()),
                        "duplicate_dates": int(dates.duplicated().sum()),
                        "conflicting_duplicate_dates": int(same_date.gt(1).any(axis=1).sum()),
                        "missing_numeric_rows": int(numeric.isna().any(axis=1).sum()),
                        "rows_outside_source_window": int((~dates.between(start,end)).sum()), "units": units})
    payload = {"authors": cfg.__author__.split("; "), "source_start": cfg.SAMPLE_START, "source_cutoff": cfg.SAMPLE_END,
               "monthly_start": str(panel.date.min().date()), "monthly_end": str(panel.date.max().date()),
               "monthly_n": len(panel), "daily_start": str(daily.date.min().date()),
               "daily_end": str(daily.date.max().date()), "daily_n": len(daily),
               "rate_change_proxy_n": int(daily.rate_effective_proxy_day.sum()),
               "partial_months_excluded": ["2013-09", "2026-09"],
               "monthly_rule": "ставка последняя в месяце; USD/RUB и Brent среднее доступных наблюдений",
               "daily_rule": "логарифмическая разность последовательных опубликованных значений официального курса",
               "event_date_rule": "дата вступления изменения ставки в силу плюс 1 календарный день",
               "event_announcement_dates_verified": False,
               "fx_measurement_break": cfg.FX_MEASUREMENT_BREAK,
               "sources": sources}
    (cfg.OUTPUT_TABLES / "T0_data_audit.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")


def main() -> None:
    key, usd, brent = load_keyrate(), load_usdrub(), load_brent()
    panel = build_monthly_panel(key, usd, brent)
    daily = build_daily_returns(usd, key)
    print_audit_facts(key, usd, brent, panel)
    source_audit(panel, daily)
    table = stationarity_tests(panel)
    table.to_csv(cfg.OUTPUT_TABLES / "T2_stationarity.csv", index=False)
    decisions = "\n".join(stationarity_decisions(table))
    (cfg.OUTPUT_TABLES / "T2_stationarity_interpretation.txt").write_text(decisions + "\n", encoding="utf-8")
    print(table.round(4).to_string(index=False))
    print(decisions)
    johansen_decision(panel)
    panel.to_parquet(cfg.MONTHLY_PANEL_FILE, index=False)
    daily.to_parquet(cfg.DAILY_RETURNS_FILE, index=False)


if __name__ == "__main__":
    main()
