"""Независимая численная проверка приложенных данных и результатов проекта."""

import argparse
import ast
import hashlib
import importlib.metadata
import json
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

for variable in ["OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"]:
    os.environ[variable] = "8"

import numpy as np
import pandas as pd
from scipy import stats

__author__ = "Анастасия Казакова, Степан Селезнев, Светлана Калошкина"

RAW_SHA256 = {
    "keyrate_raw.csv": "e1e56132781b1477437a7857e56f772e56b77b056e78f92be71b8e4a72f1076f",
    "usdrub_raw.csv": "0edc56f497a383258ecc14691028e6612d81ff9c35a83784c6749429541d0f40",
    "brent_raw.csv": "fc3ab55170885e666085c1bdcb9ecf864826055d6370b305c6f8cb1b3e34edd0",
}
VARS = ["key_rate", "usdrub", "brent"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not bool(condition):
        raise AssertionError(message)


def close(actual, expected, label, atol=1e-10, rtol=1e-7):
    a, b = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    require(a.shape == b.shape, f"{label}: разные размеры {a.shape} и {b.shape}")
    require(np.allclose(a, b, rtol=rtol, atol=atol, equal_nan=True), f"{label}: результаты различаются")


def pclose(actual, expected, label):
    a, b = np.asarray(actual, dtype=float), np.asarray(expected, dtype=float)
    require(np.all((a > 0) & (a <= 1)), f"{label}: p вне (0, 1]")
    close(np.log(a), np.log(b), label, atol=1e-7, rtol=1e-6)


def literal_settings(path):
    values = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                values[node.targets[0].id] = ast.literal_eval(node.value)
            except (ValueError, TypeError):
                pass
    return values


def read_source(root, settings):
    raw = root / "data/raw"
    listed = dict(line.split()[::-1] for line in (raw / "checksums.txt").read_text().splitlines() if line.strip())
    for name, expected in RAW_SHA256.items():
        actual = digest(raw / name)
        require(actual == expected == listed.get(name), f"SHA256 исходных данных: {name}")
    start = pd.to_datetime(settings["SAMPLE_START"], dayfirst=True)
    cutoff = pd.to_datetime(settings["SAMPLE_END"], dayfirst=True)
    frames = {}
    for name, filename in zip(VARS, RAW_SHA256):
        frame = pd.read_csv(raw / filename)
        if name == "brent":
            frame.columns = ["date", "brent"]
            frame["date"] = pd.to_datetime(frame["date"])
            frame["brent"] = pd.to_numeric(frame["brent"], errors="coerce")
        else:
            frame["date"] = pd.to_datetime(frame["date"], format="%d.%m.%Y")
            frame[name] = frame["rate"] if name == "key_rate" else frame["value"] / frame["nominal"]
        frame = frame.loc[frame["date"].between(start, cutoff), ["date", name]].dropna()
        require(not frame["date"].duplicated().any(), f"Повторные даты: {name}")
        require((frame[name] > 0).all(), f"Неположительные значения: {name}")
        frames[name] = frame.sort_values("date").reset_index(drop=True)
    return frames, cutoff


def monthly(frames, cutoff, rate_agg="last", other_agg="mean"):
    columns = []
    for name, frame in frames.items():
        grouped = frame.groupby(frame["date"].dt.to_period("M"))[name]
        columns.append(grouped.agg(rate_agg if name == "key_rate" else other_agg))
    result = pd.concat(columns, axis=1).dropna()
    result.index = result.index.to_timestamp(how="end").normalize()
    joint_start = max(frame["date"].min() for frame in frames.values())
    first_month = joint_start.to_period("M") + int(joint_start.day > 1)
    result = result.loc[(result.index >= first_month.to_timestamp()) & (result.index <= cutoff)].reset_index(names="date")
    return result


def transformed(panel):
    values = panel[VARS].to_numpy(dtype=float).copy()
    values[:, 1:] = np.log(values[:, 1:])
    return values


def ols_var(y, lag=2, exog=None):
    n, k = y.shape
    pieces = [np.ones((n - lag, 1))]
    if exog is not None:
        e = np.asarray(exog)[lag:]
        pieces.append(e[:, np.any(e != 0, axis=0)])
    pieces += [y[lag - l:n - l] for l in range(1, lag + 1)]
    x = np.column_stack(pieces)
    coef, _, rank, _ = np.linalg.lstsq(x, y[lag:], rcond=None)
    require(rank == x.shape[1], "Вырожденная матрица независимого OLS")
    residual = y[lag:] - x @ coef
    df_resid = n - lag - x.shape[1]
    sigma = residual.T @ residual / df_resid
    offset = x.shape[1] - lag * k
    return {
        "coef": coef, "sigma": sigma, "inverse": np.linalg.inv(x.T @ x),
        "residual": residual, "lag": lag, "k": k, "offset": offset, "df": df_resid,
        "A": np.stack([coef[offset + i * k:offset + (i + 1) * k].T for i in range(lag)]),
    }


def granger(fit, caused, causing):
    rows = fit["offset"] + causing + np.arange(fit["lag"]) * fit["k"]
    b = fit["coef"][rows, caused]
    cov = fit["sigma"][caused, caused] * fit["inverse"][np.ix_(rows, rows)]
    f = float(b @ np.linalg.solve(cov, b) / len(rows))
    p = float(stats.f.sf(f, len(rows), fit["k"] * fit["df"]))
    return f, p


def irf(fit, impulse=0, response=1, horizons=12):
    lower = np.linalg.cholesky(fit["sigma"])
    matrices = [np.eye(fit["k"])]
    for h in range(1, horizons + 1):
        value = np.zeros_like(matrices[0])
        for ell in range(1, min(h, fit["lag"]) + 1):
            value += fit["A"][ell - 1] @ matrices[h - ell]
        matrices.append(value)
    normalized = lower[:, impulse] / lower[impulse, impulse]
    close(normalized[impulse], 1, "Масштаб шока ставки")
    return np.array([(value @ normalized)[response] for value in matrices])


def predict(fit, history, horizon):
    history = list(np.asarray(history))
    forecasts = []
    for _ in range(horizon):
        value = fit["coef"][0].copy()
        for ell in range(1, fit["lag"] + 1):
            value += fit["A"][ell - 1] @ history[-ell]
        history.append(value)
        forecasts.append(value)
    return np.asarray(forecasts)


def check_data(root, frames, cutoff):
    expected = monthly(frames, cutoff)
    saved = pd.read_parquet(root / "data/processed/monthly_panel.parquet")
    require(list(pd.to_datetime(saved["date"])) == list(expected["date"]), "Даты месячной панели")
    close(saved[VARS], expected[VARS], "Значения месячной панели")
    periods = expected["date"].dt.to_period("M")
    require(list(periods) == list(pd.period_range(periods.iloc[0], periods.iloc[-1], freq="M")), "Пропущенный месяц")
    require(expected["date"].max() <= cutoff, "Неполный или будущий месяц в панели")
    daily = pd.read_parquet(root / "data/processed/daily_returns.parquet")
    usd = frames["usdrub"].copy()
    usd["log_return"] = np.log(usd["usdrub"]).diff()
    usd = usd.loc[usd["date"] >= frames["key_rate"]["date"].min()].dropna()
    require(list(pd.to_datetime(daily["date"])) == list(usd["date"]), "Даты дневных доходностей")
    close(daily["log_return"], usd["log_return"], "Дневные логарифмические доходности")
    close(daily["usdrub"], usd["usdrub"], "Уровни дневного курса")
    key = frames["key_rate"].copy()
    key["change_pp"] = key["key_rate"].diff()
    changes = key.loc[key["change_pp"].notna() & key["change_pp"].ne(0)]
    calendar = pd.read_csv(root / "data/processed/rate_change_calendar.csv")
    require(list(pd.to_datetime(calendar["effective_date"])) == list(changes["date"]), "Даты вступления ставки в силу")
    close(calendar["change_pp"], changes["change_pp"], "Величины изменения ставки")
    require(list(pd.to_datetime(calendar["fx_proxy_date"])) == list(changes["date"] + pd.Timedelta(days=1)), "Прокси даты курса")
    require(not calendar["announcement_date_verified"].any(), "Прокси объявлена подтверждённой датой объявления")
    expected_flags = pd.to_datetime(daily["date"]).isin(pd.to_datetime(calendar["fx_proxy_date"]))
    require(np.array_equal(daily["rate_effective_proxy_day"], expected_flags), "Разметка изменений ставки")
    description = pd.read_csv(root / "output/tables/T1_sample.csv")
    for row in description.itertuples(index=False):
        data = frames[row.series]
        require(row.n_obs == len(data), f"T1 число строк {row.series}")
        require(pd.Timestamp(row.date_min) == data["date"].min(), f"T1 начало {row.series}")
        require(pd.Timestamp(row.date_max) == data["date"].max(), f"T1 конец {row.series}")
        close([row.value_min, row.value_max, row.value_mean],
              [data[row.series].min(), data[row.series].max(), data[row.series].mean()], f"T1 {row.series}")
    return expected, daily


def check_var(root, panel):
    tables = root / "output/tables"
    values = np.diff(transformed(panel), axis=0)
    fit = ols_var(values)
    grangers = pd.read_csv(tables / "T4_granger.csv").iloc[:4]
    for i, row in enumerate(grangers.itertuples(index=False)):
        local = fit if i < 2 else ols_var(values[:, :2])
        f, p = granger(local, VARS.index(row.caused), VARS.index(row.causing))
        close(row.f_stat, f, f"T4 F строка {i + 1}")
        pclose(row.p_value, p, f"T4 p строка {i + 1}")
    table = pd.read_csv(tables / "T3c_irf_bootstrap.csv")
    point = irf(fit, horizons=len(table) - 1)
    close(table["response_per_pp"], point, "IRF независимая матричная рекурсия")
    close(table["cum_response_per_pp"], point.cumsum(), "Накопленная IRF")
    draws_file = tables / "T3c_irf_bootstrap_draws.npz"
    require(draws_file.exists(), "Отсутствуют bootstrap траектории для проверки интервалов")
    with np.load(draws_file, allow_pickle=False) as archive:
        paths = archive["paths"]
        require(paths.ndim == 2 and paths.shape[1] == len(table), "Размер bootstrap траекторий")
        accepted = paths[np.isfinite(paths).all(axis=1)]
        requested, rejected = int(archive["n_requested"]), int(archive["n_rejected"])
        require(requested == 500 and int(archive["seed"]) == 20260101, "Параметры bootstrap")
        require(len(accepted) == int(archive["n_accepted"]) == requested - rejected, "Счётчик bootstrap реплик")
        require(len(accepted) >= .95 * requested, "Мало успешных bootstrap реплик")
        close(table[["ci_lo", "ci_hi"]], np.quantile(accepted, [.025, .975], axis=0).T, "Поточечные bootstrap интервалы")
        close(table[["cum_ci_lo", "cum_ci_hi"]], np.quantile(accepted.cumsum(axis=1), [.025, .975], axis=0).T, "Накопленные bootstrap интервалы")
        if rejected == 0:
            rng = np.random.default_rng(int(archive["seed"]))
            residual = fit["residual"] - fit["residual"].mean(axis=0)
            innovations = residual[rng.integers(len(residual), size=len(residual))]
            simulated = list(values[:fit["lag"]])
            for innovation in innovations:
                prediction = fit["coef"][0].copy()
                for ell in range(1, fit["lag"] + 1):
                    prediction += fit["A"][ell - 1] @ simulated[-ell]
                simulated.append(prediction + innovation)
            close(accepted[0], irf(ols_var(np.asarray(simulated))), "Независимая первая bootstrap реплика")
    effect = pd.read_csv(tables / "T7d_effect_size.csv").iloc[0]
    ix = fit["offset"] + np.arange(fit["lag"]) * fit["k"]
    coef_sum = fit["coef"][ix, 1].sum()
    se = np.sqrt(fit["sigma"][1, 1] * fit["inverse"][np.ix_(ix, ix)].sum())
    close(effect["sum_rate_lag_coefficients"], coef_sum, "Сумма коэффициентов ставки")
    close([effect["ci_lo"], effect["ci_hi"]], [coef_sum - 1.96 * se, coef_sum + 1.96 * se], "Интервал суммы коэффициентов")
    alternatives = pd.read_csv(tables / "T7b_irf_ordering.csv")
    for i, ordering in enumerate([[0, 1, 2], [1, 0, 2], [2, 0, 1]]):
        local = ols_var(values[:, ordering])
        path = irf(local, impulse=ordering.index(0), response=ordering.index(1))
        peak = int(np.argmax(abs(path)))
        row = alternatives.iloc[i]
        require(row["peak_horizon"] == peak, f"IRF порядок {ordering}: горизонт пика")
        close(row["peak_value_per_pp"], path[peak], f"IRF порядок {ordering}: пик")
        close(row["cum_effect_h3_per_pp"], path[:4].sum(), f"IRF порядок {ordering}: сумма 0..3")
    return {"granger_rate_to_fx_p": granger(fit, 1, 0)[1], "granger_fx_to_rate_p": granger(fit, 0, 1)[1],
            "irf_h1_per_pp": float(point[1]), "sum_rate_lag_coefficients": float(coef_sum), "bootstrap_accepted": len(accepted)}


def check_forecasts(root, panel):
    table_dir = root / "output/tables"
    forecasts = pd.read_csv(table_dir / "T8_outofsample_forecasts.csv")
    values = np.diff(transformed(panel), axis=0)
    dates = panel["date"].iloc[1:].reset_index(drop=True)
    require(not forecasts.duplicated(["origin", "h"]).any(), "Повторные прогнозы origin/h")
    require(np.isfinite(forecasts[["actual_dlog_usdrub", "naive", "var2_no_rate", "var3_with_rate"]]).all().all(), "Пропуски прогнозов")
    max_h = int(forecasts["h"].max())
    expected_pairs = {(origin, h) for origin in range(36, len(values)) for h in range(1, min(max_h, len(values)-origin)+1)}
    require(set(zip(forecasts["origin"], forecasts["h"])) == expected_pairs, "Полный набор доступных прогнозов origin/h")
    for origin, sub in forecasts.groupby("origin", sort=True):
        origin = int(origin)
        require(origin >= 36, "Недостаточная начальная обучающая выборка")
        with_rate = predict(ols_var(values[:origin]), values[:origin], max_h)
        no_rate = predict(ols_var(values[:origin, 1:]), values[:origin, 1:], max_h)
        for row in sub.itertuples(index=False):
            j = origin + row.h - 1
            require(pd.Timestamp(row.target_date) == dates.iloc[j], "Дата прогнозируемой доходности")
            require(row.target_year == dates.iloc[j].year, "Год целевого месяца")
            require(dates.iloc[origin - 1] < pd.Timestamp(row.target_date), "Обучение включает целевой месяц")
            close(row.actual_dlog_usdrub, values[j, 1], "Фактическая целевая доходность")
            close(row.naive, 0, "Наивный прогноз")
            close(row.var3_with_rate, with_rate[row.h - 1, 1], "Независимый прогноз VAR со ставкой")
            close(row.var2_no_rate, no_rate[row.h - 1, 0], "Независимый прогноз VAR без ставки")
            if hasattr(row, "train_end_date"):
                require(pd.Timestamp(row.train_end_date) == dates.iloc[origin - 1], "Дата конца обучения")
    require(int(forecasts["origin"].max()) >= len(values) - max_h, "Потерян последний полностью доступный origin")
    summary = pd.read_csv(table_dir / "T8_outofsample_summary.csv")
    regimes = list(dict.fromkeys(summary["regime"]))
    require(len(regimes) == 3, "Ожидаются три режима OOS")
    masks = [np.ones(len(forecasts), dtype=bool), forecasts["target_year"].isin([2014, 2015, 2022]), ~forecasts["target_year"].isin([2014, 2015, 2022])]
    for label, mask in zip(regimes, masks):
        for row in summary[summary["regime"] == label].itertuples(index=False):
            sub = forecasts[mask & (forecasts["h"] == row.h)]
            require(row.n == len(sub), "Число прогнозов OOS")
            for model in ["naive", "var2_no_rate", "var3_with_rate"]:
                errors = sub["actual_dlog_usdrub"] - sub[model]
                close(getattr(row, f"rmse_{model}"), np.sqrt(np.mean(errors**2)), f"RMSE {model}")
                close(getattr(row, f"mae_{model}"), np.mean(abs(errors)), f"MAE {model}")
    cw = pd.read_csv(table_dir / "T8b_clark_west.csv")
    one_step = forecasts.loc[forecasts["h"] == 1].sort_values("target_date")
    for row in cw.itertuples(index=False):
        actual = one_step["actual_dlog_usdrub"].to_numpy()
        restricted = one_step[row.restricted_model].to_numpy()
        unrestricted = one_step["var3_with_rate"].to_numpy()
        raw_loss = (actual-restricted)**2 - (actual-unrestricted)**2
        adjusted_loss = raw_loss + (restricted-unrestricted)**2
        n = len(adjusted_loss)
        require(row.n == n, "Размер выборки Clark-West")
        residual = adjusted_loss-adjusted_loss.mean()
        long_run_sum = residual @ residual
        for lag in range(1, row.hac_lags+1):
            long_run_sum += 2*(1-lag/(row.hac_lags+1))*(residual[lag:] @ residual[:-lag])
        se = np.sqrt(long_run_sum / (n*(n-1)))
        z = adjusted_loss.mean()/se
        close([row.mean_raw_loss_difference, row.mean_adjusted_loss_difference, row.hac_standard_error, row.z_stat],
              [raw_loss.mean(), adjusted_loss.mean(), se, z], "Clark-West и HAC через явную сумму автоковариаций")
        pclose(row.p_one_sided, stats.norm.sf(z), "Одностороннее p Clark-West")
    return {"forecast_count": len(forecasts), "origins": int(forecasts["origin"].nunique()),
            "target_first": str(pd.to_datetime(forecasts["target_date"]).min().date()),
            "target_last": str(pd.to_datetime(forecasts["target_date"]).max().date()),
            "crisis_target_years": sorted(int(y) for y in forecasts.loc[masks[1], "target_year"].unique())}


def check_garch(root):
    tables = root / "output/tables"
    selected = pd.read_csv(tables / "T5b_garch_spec_selection.csv")
    require(selected["bic"].is_monotonic_increasing, "Выбор GARCH по BIC")
    if "n_obs" in selected:
        require(selected["n_obs"].nunique() == 1, "GARCH BIC на разных выборках")
    table = pd.read_csv(tables / "T5_garch.csv")
    close(table["persistence"], table["alpha"] + table["beta"] + table["gamma_asym"] / 2, "Персистентность GARCH")
    denominator = 1 - table["persistence"]
    expected = np.where(denominator > .001, table["omega"] / denominator, np.nan)
    close(table["unconditional_var_pct2"], expected, "Безусловная дисперсия GARCH")
    for column in ["ljung_box_resid_p", "ljung_box_resid_sq_p"]:
        require(table[column].between(0, 1).all(), f"Диагностика GARCH {column}")
    return {"selected_garch": selected.iloc[0]["spec"]}


def check_events(root, daily):
    tables = root / "output/tables"
    stratified = pd.read_csv(tables / "T6b_event_study_stratified.csv")
    before_after = pd.read_csv(tables / "T6c_before_after.csv")
    values = np.abs(daily["log_return"].to_numpy() * 100)
    years = pd.to_datetime(daily["date"]).dt.year.to_numpy()
    prefix = np.r_[0, np.cumsum(values)]
    observed = np.flatnonzero(daily["rate_effective_proxy_day"].to_numpy())
    window, baseline = 5, 30
    event_mask = np.any(np.abs(np.arange(len(daily))[:, None] - observed) <= window, axis=1)
    counts = {}
    for i, label in enumerate(["all", "noncrisis"]):
        complete = np.arange(window + baseline, len(daily) - window)
        if label == "noncrisis":
            complete = np.array([c for c in complete if not np.isin(years[c-window-baseline:c+window+1], [2014, 2015, 2022]).any()])
        expected_events = np.intersect1d(complete, observed)
        expected_pool = np.array([c for c in complete if not event_mask[c-window:c+window+1].any()])
        with np.load(tables / f"T6b_placebo_{label}_draws.npz", allow_pickle=False) as archive:
            events, pool, draws = archive["observed_centers"], archive["eligible_centers"], archive["centers"]
            require(np.array_equal(events, expected_events), f"События {label}: полные окна на непрерывной оси дат")
            require(np.array_equal(pool, expected_pool), f"Плацебо {label}: окна вне реальных событий")
            require(draws.shape == (1000, len(events)), f"Размер плацебо {label}")
            require(np.isin(draws, pool).all(), f"Плацебо {label}: недопустимые центры")
            require(all(len(set(row)) == len(row) for row in draws), f"Плацебо {label}: повтор центра в реплике")
            for year in np.unique(years[events]):
                require(np.all((years[draws] == year).sum(axis=1) == (years[events] == year).sum()), f"Плацебо {label}: стратификация {year}")
            def window_values(centers):
                win = (prefix[centers+window+1] - prefix[centers-window]) / (2*window+1)
                base = (prefix[centers-window] - prefix[centers-window-baseline]) / baseline
                return win - base
            observed_value = window_values(events).mean()
            placebo = window_values(draws).mean(axis=1)
            close(archive["values"], placebo, f"Все статистики плацебо {label}")
            row = stratified.iloc[i]
            require(row["n_events"] == len(events), f"Число событий {label}")
            close(row["observed_abnormal_abs_return_pct"], observed_value, f"Аномальная доходность {label}")
            close([row["placebo_abnormal_mean"], row["placebo_abnormal_p95"]],
                  [placebo.mean(), np.quantile(placebo, .95)], f"Агрегаты плацебо {label}")
            exceed = int(np.count_nonzero(placebo >= observed_value))
            require(row["n_exceed"] == exceed and row["n_permutations"] == len(placebo), f"Счётчик плацебо {label}")
            close(row["p_value"], (exceed + 1) / (len(placebo) + 1), f"Monte Carlo p {label}")
            before = before_after.iloc[i]
            close(before["pre_proxy_abs_return_pct"], ((prefix[events] - prefix[events-window]) / window).mean(), f"До прокси {label}")
            close(before["post_proxy_abs_return_pct"], ((prefix[events+window+1] - prefix[events]) / (window+1)).mean(), f"После прокси {label}")
            close(before["baseline_30obs_before_window_pct"], ((prefix[events-window] - prefix[events-window-baseline]) / baseline).mean(), f"Базовые окна {label}")
            counts[f"events_{label}"] = len(events)
            counts[f"event_stratified_p_{label}"] = float(row["p_value"])
    return counts


def dummy_columns(dates, months, propagation):
    observed = list(pd.to_datetime(dates).dt.to_period("M"))
    positions = set()
    for month in months:
        value = pd.Period(month, freq="M")
        if value in observed:
            position = observed.index(value)
            positions.update(i for i in range(position, position + propagation + 1) if i < len(observed))
    matrix = np.zeros((len(observed), len(positions)))
    for column, position in enumerate(sorted(positions)):
        matrix[position, column] = 1
    return matrix


def check_robustness(root, panel, frames, cutoff):
    table = pd.read_csv(root / "output/tables/T7_robustness.csv")
    levels = transformed(panel)
    dates = panel["date"]
    expected = []
    for lag in [1, 2, 3]:
        expected.append(ols_var(np.diff(levels, axis=0), lag))
    masks = [dates < "2022-02-28", dates >= "2022-02-28",
             dates.between("2015-06-01", "2021-12-31"), dates.between("2016-01-01", "2021-12-31"),
             dates.between("2015-06-01", "2021-06-30"), dates >= "2022-09-01",
             dates < "2024-06-01", dates >= "2024-07-01"]
    for mask in masks:
        expected.append(ols_var(np.diff(levels[mask], axis=0)))
    crisis22 = ["2022-02", "2022-03", "2022-04"]
    crisis14 = ["2014-11", "2014-12", "2015-01", "2015-02"]
    for months in [crisis22, crisis14, crisis22 + crisis14]:
        for propagation in [0, 2]:
            dummy = dummy_columns(dates, months, propagation)
            expected.append(ols_var(np.diff(levels, axis=0), exog=dummy[1:]))
    for mask in [np.ones(len(levels), dtype=bool), dates < "2026-07-01"]:
        expected.append(ols_var(np.diff(levels[mask], axis=0)))
    for rate_agg, other_agg in [("last", "mean"), ("mean", "mean"), ("last", "last")]:
        alternative = monthly(frames, cutoff, rate_agg, other_agg)
        expected.append(ols_var(np.diff(transformed(alternative), axis=0)))
    require(len(table) == len(expected), "Число вариантов устойчивости")
    for i, fit in enumerate(expected):
        row = table.iloc[i]
        require(row["n_obs"] == fit["df"] + fit["coef"].shape[0], f"Число эффективных наблюдений варианта {i + 1}")
        pclose(row["rate_to_fx_p"], granger(fit, 1, 0)[1], f"Устойчивость {i + 1}, ставка-курс")
        pclose(row["fx_to_rate_p"], granger(fit, 0, 1)[1], f"Устойчивость {i + 1}, курс-ставка")
    rolling = pd.read_csv(root / "output/tables/T7c_rolling_granger.csv")
    window = 60
    require(len(rolling) == len(levels)-window+1, "Число скользящих окон")
    global_dummy = dummy_columns(dates, crisis22+crisis14, 2)
    for start, row in enumerate(rolling.itertuples(index=False)):
        require(pd.Timestamp(row.window_end) == dates.iloc[start+window-1], "Конец скользящего окна")
        diff = np.diff(levels[start:start+window], axis=0)
        local = ols_var(diff)
        controlled = ols_var(diff, exog=global_dummy[start+1:start+window])
        for direction, caused, causing in [("rate_to_fx", 1, 0), ("fx_to_rate", 0, 1)]:
            pclose(getattr(row, direction+"_p"), granger(local, caused, causing)[1], f"Окно {start+1}: {direction}")
            pclose(getattr(row, direction+"_p_neutralized"), granger(controlled, caused, causing)[1], f"Окно {start+1} с дамми: {direction}")
    return {"robustness_variants_verified": len(expected), "rolling_windows_verified": len(rolling)}


def check_manifest(root):
    path = root / "output/run_manifest.json"
    require(path.exists(), "Отсутствует журнал полного расчёта output/run_manifest.json")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    require(manifest["schema_version"] == 1, "Версия схемы журнала запуска")
    count = 0
    for group in ["source_files", "code_files", "results_files"]:
        require(bool(manifest[group]), f"Пустой раздел журнала: {group}")
        for relative, expected in manifest[group].items():
            target = (root / relative).resolve()
            require(target.is_relative_to(root), "Путь журнала выходит из проекта")
            require(target.is_file() and digest(target) == expected, f"Файл изменился после расчёта: {relative}")
            count += 1
    require(manifest["code_files"].get("verify_results.py") == digest(Path(__file__)), "Версия проверяющего скрипта")
    require(len(manifest["scripts"]) == 7 and all(s["returncode"] == 0 for s in manifest["scripts"]), "Полный запуск семи этапов")
    require(manifest["runtime"]["numerical_thread_limit"] <= 8, "Ограничение вычислительных потоков")
    require(manifest["elapsed_seconds"] < 1800, "Продолжительность расчёта превышает 30 минут")
    dependencies = 0
    for line in (root / "requirements.txt").read_text().splitlines():
        if not line.strip():
            continue
        package, version = line.strip().split("==")
        require(importlib.metadata.version(package) == version, f"Версия зависимости: {package}")
        dependencies += 1
    return {"run_manifest_sha256": digest(path), "manifest_files_verified": count,
            "dependencies_verified": dependencies, "requirements_sha256": digest(root / "requirements.txt")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    target = args.output or root / "output/numerical_verification.json"
    started = time.perf_counter()
    report = {"status": "FAIL", "checked_utc": datetime.now(timezone.utc).isoformat(), "authors": __author__,
              "method": "Независимая сборка данных, OLS через numpy.linalg.lstsq, матричная IRF, пересчёт прогнозов и метрик; модули src не импортируются",
              "scope_limits": ["Параметры GARCH получены полным расчётом; здесь проверяются выбор спецификации и алгебраические тождества",
                               "Альтернативные тесты VECM и ADF/KPSS выполняются основным расчётом",
                               "Визуальная проверка презентации выполняется отдельно"],
              "checks": []}
    try:
        settings = literal_settings(root / "src/config.py")
        frames, cutoff = read_source(root, settings)
        report["checks"].append("Контрольные суммы трёх исходных файлов и границы дат")
        panel, daily = check_data(root, frames, cutoff)
        report["checks"].append("Все значения месячной панели, дневных доходностей и таблицы описания данных")
        report["key_results"] = check_var(root, panel)
        report["checks"].append("OLS, тесты Грейнджера, нормировка IRF на 1 п.п., bootstrap интервалы и сумма коэффициентов")
        report["key_results"].update(check_forecasts(root, panel))
        report["checks"].append("Все прогнозы: обучение до origin, соответствие целевых дат, RMSE и MAE")
        report["key_results"].update(check_garch(root))
        report["checks"].append("Выбор и диагностические тождества GARCH")
        report["key_results"].update(check_events(root, daily))
        report["checks"].append("Событийные окна, непрерывность дат, 2000 стратифицированных плацебо и Monte Carlo p")
        report["key_results"].update(check_robustness(root, panel, frames, cutoff))
        report["checks"].append("Все варианты устойчивости: лаги, подпериоды, кризисные дамми и агрегации")
        report.update(check_manifest(root))
        report["checks"].append("Хеши исходных данных, кода и результатов соответствуют журналу полного запуска")
        report["data"] = {"monthly_rows": len(panel), "daily_rows": len(daily), "cutoff": str(cutoff.date())}
        report["status"] = "PASS"
    except Exception as exc:
        report["error"] = f"{type(exc).__name__}: {exc}"
    report["elapsed_seconds"] = time.perf_counter() - started
    report["python"] = platform.python_version()
    try:
        import resource
        report["peak_rss_mib"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / (1024**2 if sys.platform == "darwin" else 1024)
    except ImportError:
        report["peak_rss_mib"] = None
    report["source_sha256"] = {f"data/raw/{name}": digest(root / "data/raw" / name) for name in RAW_SHA256}
    report["code_sha256"] = {str(p.relative_to(root)): digest(p) for p in sorted((root / "src").glob("*.py"))}
    report["code_sha256"]["verify_results.py"] = digest(Path(__file__))
    report["results_sha256"] = {str(p.relative_to(root)): digest(p) for p in sorted((root / "output/tables").glob("*")) if p.is_file()}
    report["results_sha256"].update({str(p.relative_to(root)): digest(p) for p in sorted((root / "data/processed").glob("*")) if p.is_file()})
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "checks": len(report["checks"]), "elapsed_seconds": report["elapsed_seconds"], "error": report.get("error")}, ensure_ascii=False))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
