"""GARCH и описательное сравнение окон изменений ставки с плацебо."""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from arch import arch_model
from statsmodels.stats.diagnostic import acorr_ljungbox, het_arch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config as cfg

RNG_SEED = 20260101
N_PLACEBO = 1000
CRISIS_YEARS = {2014, 2015, 2022}
BASELINE_WINDOW = 30


def load_daily() -> pd.DataFrame:
    df = pd.read_parquet(cfg.DAILY_RETURNS_FILE)
    df["return_pct"] = df["log_return"] * 100
    df["year"] = df["date"].dt.year
    return df


def arch_lm_test(df: pd.DataFrame) -> float:
    _, p_value, *_ = het_arch(df["return_pct"], nlags=10, result_object=False)
    return p_value


GARCH_CANDIDATES = {
    "Normal, const-mean": dict(mean="Constant", vol="GARCH", p=1, q=1, dist="normal"),
    "t, const-mean": dict(mean="Constant", vol="GARCH", p=1, q=1, dist="t"),
    "t, AR(1)-mean": dict(mean="AR", lags=1, vol="GARCH", p=1, q=1, dist="t"),
    "t, AR(1)-mean, GJR": dict(mean="AR", lags=1, vol="GARCH", p=1, o=1, q=1, dist="t"),
}


def select_garch_spec(returns: pd.Series) -> tuple[str, dict, pd.DataFrame]:
    rows = []
    fitted = {}
    for name, kw in GARCH_CANDIDATES.items():
        res = arch_model(returns, hold_back=1, **kw).fit(disp="off")
        fitted[name] = res
        rows.append({"spec": name, "aic": res.aic, "bic": res.bic, "loglik": res.loglikelihood, "n_obs": res.nobs, "convergence_flag": res.convergence_flag})
    table = pd.DataFrame(rows).sort_values("bic").reset_index(drop=True)
    if table["convergence_flag"].ne(0).any():
        raise RuntimeError("Часть GARCH-кандидатов не сошлась; сравнение остановлено.")
    best_name = table.iloc[0]["spec"]
    print("=== Выбор спецификации GARCH (по BIC) ===")
    print(table.round(1).to_string(index=False))
    print(f"Выбрана: {best_name}\n")
    return best_name, GARCH_CANDIDATES[best_name], table


def fit_garch(returns: pd.Series, spec_kwargs: dict):
    return arch_model(returns, hold_back=1, **spec_kwargs).fit(disp="off")


def garch_diagnostics(res) -> dict:
    std_resid = res.std_resid.dropna()
    lb_resid = acorr_ljungbox(std_resid, lags=[12], return_df=True)
    lb_sq = acorr_ljungbox(std_resid**2, lags=[12], return_df=True)
    return {
        "lb_resid_p": lb_resid["lb_pvalue"].iloc[0],
        "lb_resid_sq_p": lb_sq["lb_pvalue"].iloc[0],
    }


def build_t5(df: pd.DataFrame, spec_kwargs: dict) -> tuple[pd.DataFrame, pd.Series]:
    rows = []
    full_cond_vol = None

    periods = {
        "весь период": df,
        "до 28.02.2022": df[df["date"] < cfg.SHOCK_DATE],
        "после 28.02.2022": df[df["date"] >= cfg.SHOCK_DATE],
        "до смены измерения 13.06.2024": df[df["date"] < cfg.FX_MEASUREMENT_BREAK],
        "после смены измерения 13.06.2024": df[df["date"] >= cfg.FX_MEASUREMENT_BREAK],
    }
    for label, sub in periods.items():
        res = fit_garch(sub["return_pct"], spec_kwargs)
        diag = garch_diagnostics(res)
        omega = res.params["omega"]
        alpha = res.params.get("alpha[1]", 0.0)
        beta = res.params.get("beta[1]", 0.0)
        gamma = res.params.get("gamma[1]", 0.0)


        persistence = alpha + beta + gamma / 2


        denom = 1 - persistence
        unconditional_var = omega / denom if denom > 1e-3 else np.nan
        rows.append(
            {
                "period": label,
                "n_obs": res.nobs,
                "convergence_flag": res.convergence_flag,
                "omega": omega,
                "alpha": alpha,
                "gamma_asym": gamma,
                "beta": beta,
                "persistence": persistence,
                "unconditional_var_pct2": unconditional_var,
                "ljung_box_resid_p": diag["lb_resid_p"],
                "ljung_box_resid_sq_p": diag["lb_resid_sq_p"],
            }
        )
        if label == "весь период":
            full_cond_vol = pd.Series(res.conditional_volatility, index=sub.index)

    return pd.DataFrame(rows), full_cond_vol


def _window_mask(centers: np.ndarray, window: int, n: int) -> np.ndarray:
    mask = np.zeros(n, dtype=bool)
    for center in centers:
        mask[max(0, center-window):min(n, center+window+1)] = True
    return mask


def event_geometry(df: pd.DataFrame, window: int, restrict_years: set | None = None) -> tuple:
    n = len(df)
    years = df["year"].to_numpy()
    observed_centers = np.flatnonzero(df["rate_effective_proxy_day"].to_numpy())
    complete_centers = np.arange(BASELINE_WINDOW + window, n-window)
    if restrict_years is not None:
        complete_centers = np.asarray([
            center for center in complete_centers
            if np.isin(years[center-window-BASELINE_WINDOW:center+window+1], list(restrict_years)).all()
        ], dtype=int)
    event_centers = np.intersect1d(observed_centers, complete_centers)
    event_mask = _window_mask(observed_centers, window, n)
    pool = np.asarray([center for center in complete_centers
                       if not event_mask[center-window:center+window+1].any()], dtype=int)
    if not len(event_centers):
        raise ValueError("Нет событий с полными окнами и базовым периодом.")
    return event_centers, pool


def _event_mean(centers: np.ndarray, values: np.ndarray, window: int) -> float:
    return float(np.mean([np.mean(values[c-window:c+window+1]) for c in centers]))


def _abnormal_stat(centers: np.ndarray, abs_ret: np.ndarray, window: int, n: int) -> float:
    return float(np.mean([
        abs_ret[c-window:c+window+1].mean() - abs_ret[c-window-BASELINE_WINDOW:c-window].mean()
        for c in centers
    ]))


def event_study_naive(df: pd.DataFrame, cond_vol: pd.Series, window: int) -> dict:
    event_idx, pool = event_geometry(df, window)
    abs_ret = df["return_pct"].abs().to_numpy()
    vol = cond_vol.reindex(df.index).to_numpy()
    observed_abs = _event_mean(event_idx, abs_ret, window)
    observed_vol = _event_mean(event_idx, vol, window)
    rng = np.random.default_rng(RNG_SEED)
    placebo_abs, placebo_vol = [], []
    for _ in range(N_PLACEBO):
        centers = rng.choice(pool, size=len(event_idx), replace=False)
        placebo_abs.append(_event_mean(centers, abs_ret, window))
        placebo_vol.append(_event_mean(centers, vol, window))
    placebo_abs, placebo_vol = np.asarray(placebo_abs), np.asarray(placebo_vol)
    count_abs, count_vol = int((placebo_abs >= observed_abs).sum()), int((placebo_vol >= observed_vol).sum())
    np.savez_compressed(cfg.OUTPUT_TABLES / "T6_placebo_naive_draws.npz",
                        abs_return=placebo_abs, conditional_volatility=placebo_vol,
                        observed_centers=event_idx, eligible_centers=pool, seed=RNG_SEED)
    return {"test": "описательное сравнение с глобальным плацебо, равный вес событий",
            "n_events": len(event_idx), "observed_abs_return_pct": observed_abs,
            "placebo_abs_return_mean": placebo_abs.mean(),
            "p_value_abs_return": (count_abs+1)/(N_PLACEBO+1),
            "n_exceed_abs_return": count_abs,
            "observed_cond_vol": observed_vol, "placebo_cond_vol_mean": placebo_vol.mean(),
            "p_value_cond_vol": (count_vol+1)/(N_PLACEBO+1), "n_exceed_cond_vol": count_vol,
            "n_permutations": N_PLACEBO, "seed": RNG_SEED}


def event_study_stratified(df: pd.DataFrame, window: int, restrict_years: set | None = None) -> dict:
    event_idx, pool = event_geometry(df, window, restrict_years)
    abs_ret = df["return_pct"].abs().to_numpy()
    years = df["year"].to_numpy()
    observed = _abnormal_stat(event_idx, abs_ret, window, len(df))
    event_years, counts = np.unique(years[event_idx], return_counts=True)
    pools = {year: pool[years[pool] == year] for year in event_years}
    for year, count in zip(event_years, counts):
        if len(pools[year]) < count:
            raise ValueError(f"В {year} недостаточно сопоставимых плацебо: {len(pools[year])} < {count}.")
    rng = np.random.default_rng(RNG_SEED)
    values, center_draws = [], []
    for _ in range(N_PLACEBO):
        centers = np.concatenate([rng.choice(pools[year], size=count, replace=False)
                                  for year, count in zip(event_years, counts)])
        center_draws.append(centers)
        values.append(_abnormal_stat(centers, abs_ret, window, len(df)))
    values = np.asarray(values)
    n_exceed = int((values >= observed).sum())
    label = "all" if restrict_years is None else "noncrisis"
    np.savez_compressed(cfg.OUTPUT_TABLES / f"T6b_placebo_{label}_draws.npz",
                        values=values, centers=np.asarray(center_draws),
                        observed_centers=event_idx, eligible_centers=pool, seed=RNG_SEED)
    return {"n_events": len(event_idx), "n_years": len(event_years),
            "observed_abnormal_abs_return_pct": observed,
            "placebo_abnormal_mean": values.mean(), "placebo_abnormal_p95": np.percentile(values,95),
            "p_value": (n_exceed+1)/(N_PLACEBO+1), "n_exceed": n_exceed,
            "n_permutations": N_PLACEBO, "seed": RNG_SEED,
            "event_window_obs": 2*window+1, "baseline_obs": BASELINE_WINDOW,
            "inference": "описательное Monte Carlo сравнение; сопоставимость внутри года является предположением"}


def event_study_before_after(df: pd.DataFrame, window: int, restrict_years: set | None = None) -> dict:
    event_idx, _ = event_geometry(df, window, restrict_years)
    abs_ret = df["return_pct"].abs().to_numpy()
    return {"n_events": len(event_idx),
            "pre_proxy_abs_return_pct": float(np.mean([abs_ret[c-window:c].mean() for c in event_idx])),
            "post_proxy_abs_return_pct": float(np.mean([abs_ret[c:c+window+1].mean() for c in event_idx])),
            "baseline_30obs_before_window_pct": float(np.mean([
                abs_ret[c-window-BASELINE_WINDOW:c-window].mean() for c in event_idx])),
            "pre_window_obs": window, "post_window_obs": window+1}


def plot_conditional_vol(df: pd.DataFrame, cond_vol: pd.Series) -> None:
    fig, ax = plt.subplots(figsize=(9, 4.5))
    dates = df["date"].reset_index(drop=True)
    ax.plot(dates, cond_vol.values, color="steelblue", lw=1, label="Условная волатильность (GARCH)")
    ax.plot(
        dates,
        df["return_pct"].reset_index(drop=True).abs(),
        color="gray",
        lw=0.4,
        alpha=0.5,
        label="|доходность|, %",
    )
    event_dates = dates[df["rate_effective_proxy_day"].reset_index(drop=True)]
    for d in event_dates:
        ax.axvline(d, color="orange", lw=0.3, alpha=0.3)
    for y0, y1 in [(2014, 2016), (2022, 2023)]:
        ax.axvspan(pd.Timestamp(f"{y0}-01-01"), pd.Timestamp(f"{y1}-01-01"), color="red", alpha=0.06)
    ax.set_title("Условная волатильность USD/RUB; прокси дат изменений ставки,\nкризисные годы 2014-15/2022 выделены розовым")
    ax.set_xlabel("Дата")
    ax.set_ylabel("%")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(cfg.OUTPUT_FIGURES / "R3_conditional_volatility.png", dpi=150)
    plt.close(fig)


def main() -> None:
    df = load_daily()

    arch_p = arch_lm_test(df)
    print(f"ARCH-LM тест (H0: нет ARCH-эффекта): p={arch_p:.2e}\n")

    best_name, best_kwargs, spec_table = select_garch_spec(df["return_pct"])
    spec_table.to_csv(cfg.OUTPUT_TABLES / "T5b_garch_spec_selection.csv", index=False)

    t5, cond_vol = build_t5(df, best_kwargs)
    t5.to_csv(cfg.OUTPUT_TABLES / "T5_garch.csv", index=False)
    print(f"=== T5: параметры GARCH ({best_name}) ===")
    print(t5.round(4).to_string(index=False))

    plot_conditional_vol(df, cond_vol)
    print(f"\nСохранено: {cfg.OUTPUT_FIGURES / 'R3_conditional_volatility.png'}")


    naive = event_study_naive(df, cond_vol, cfg.EVENT_WINDOW_DAYS)
    print("\n=== T6a: наивный тест (плацебо по всей выборке) ===")
    print(pd.DataFrame([naive]).round(4).to_string(index=False))


    strat_all = event_study_stratified(df, cfg.EVENT_WINDOW_DAYS, restrict_years=None)
    strat_all["subset"] = "все события (плацебо по годам, аномальная |r|)"
    strat_noncrisis = event_study_stratified(
        df, cfg.EVENT_WINDOW_DAYS, restrict_years=set(df["year"].unique()) - CRISIS_YEARS
    )
    strat_noncrisis["subset"] = "без 2014/2015/2022 (кризисные годы)"

    t6b = pd.DataFrame([strat_all, strat_noncrisis])
    t6b.to_csv(cfg.OUTPUT_TABLES / "T6b_event_study_stratified.csv", index=False)
    print("\n=== T6b: событийное исследование, плацебо по годам, аномальная |r| ===")
    print(t6b.round(4).to_string(index=False))


    before_after_all = event_study_before_after(df, cfg.EVENT_WINDOW_DAYS)
    before_after_all["subset"] = "все события"
    before_after_noncrisis = event_study_before_after(
        df, cfg.EVENT_WINDOW_DAYS, restrict_years=set(df["year"].unique()) - CRISIS_YEARS
    )
    before_after_noncrisis["subset"] = "без 2014/2015/2022 (кризисные годы)"
    t6c = pd.DataFrame([before_after_all, before_after_noncrisis])
    t6c.to_csv(cfg.OUTPUT_TABLES / "T6c_before_after.csv", index=False)
    print("\n=== T6c: до/после прокси даты изменения ставки, база за 30 наблюдений до окна ===")
    print(t6c.round(4).to_string(index=False))

    pd.DataFrame([naive]).to_csv(cfg.OUTPUT_TABLES / "T6_event_study.csv", index=False)


if __name__ == "__main__":
    main()
