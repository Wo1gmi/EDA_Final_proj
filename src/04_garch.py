"""Слой 2 плана: GARCH(1,1) на дневных доходностях курса + событийное
исследование вокруг 65 дат решений по ставке (с плацебо-перестановками).

Даты решений уже скорректированы на Э2 (см. plan_keyrate.md, п. 0.11 —
курс в выгрузке ЦБ датирован T+1 от торговой сессии, решение по ставке —
датой вступления в силу; прямое сравнение дат совпадало в 5 случаях из 65).

Авторы: команда (ФИО — см. README).
"""

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


def load_daily() -> pd.DataFrame:
    df = pd.read_parquet(cfg.DAILY_RETURNS_FILE)
    df["return_pct"] = df["log_return"] * 100  # для численной устойчивости GARCH
    return df


def arch_lm_test(df: pd.DataFrame) -> float:
    _, p_value, *_ = het_arch(df["return_pct"], nlags=10)
    return p_value


def fit_garch(returns: pd.Series):
    model = arch_model(returns, mean="Constant", vol="GARCH", p=1, q=1, dist="normal")
    return model.fit(disp="off")


def garch_diagnostics(res) -> dict:
    std_resid = res.std_resid.dropna()
    lb_resid = acorr_ljungbox(std_resid, lags=[12], return_df=True)
    lb_sq = acorr_ljungbox(std_resid**2, lags=[12], return_df=True)
    return {
        "lb_resid_p": lb_resid["lb_pvalue"].iloc[0],
        "lb_resid_sq_p": lb_sq["lb_pvalue"].iloc[0],
    }


def build_t5(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    rows = []
    full_res = None
    full_cond_vol = None

    periods = {
        "весь период": df,
        "до 28.02.2022": df[df["date"] < cfg.SHOCK_DATE],
        "после 28.02.2022": df[df["date"] >= cfg.SHOCK_DATE],
    }
    for label, sub in periods.items():
        res = fit_garch(sub["return_pct"])
        diag = garch_diagnostics(res)
        omega, alpha, beta = res.params["omega"], res.params["alpha[1]"], res.params["beta[1]"]
        rows.append(
            {
                "period": label,
                "n_obs": len(sub),
                "omega": omega,
                "alpha": alpha,
                "beta": beta,
                "persistence": alpha + beta,
                "ljung_box_resid_p": diag["lb_resid_p"],
                "ljung_box_resid_sq_p": diag["lb_resid_sq_p"],
            }
        )
        if label == "весь период":
            full_res = res
            full_cond_vol = pd.Series(res.conditional_volatility, index=sub.index)

    return pd.DataFrame(rows), full_cond_vol


def event_study(df: pd.DataFrame, cond_vol: pd.Series, window: int) -> dict:
    df = df.reset_index(drop=True)
    n = len(df)
    event_idx = df.index[df["rate_decision_day"]].to_numpy()

    def window_mask(centers: np.ndarray) -> np.ndarray:
        mask = np.zeros(n, dtype=bool)
        for c in centers:
            lo, hi = max(c - window, 0), min(c + window, n - 1)
            mask[lo : hi + 1] = True
        return mask

    event_mask = window_mask(event_idx)
    abs_ret = df["return_pct"].abs().to_numpy()
    vol = cond_vol.reindex(df.index).to_numpy()

    observed_abs_ret = abs_ret[event_mask].mean()
    observed_vol = np.nanmean(vol[event_mask])

    # Плацебо: N_PLACEBO случайных наборов из 65 "псевдо-дат", вне окон
    # реальных событий, чтобы не подмешивать в нулевое распределение сами
    # события.
    eligible = np.where(~event_mask)[0]
    rng = np.random.default_rng(RNG_SEED)
    placebo_abs_ret = np.empty(N_PLACEBO)
    placebo_vol = np.empty(N_PLACEBO)
    n_events = len(event_idx)
    for i in range(N_PLACEBO):
        centers = rng.choice(eligible, size=n_events, replace=False)
        mask = window_mask(centers)
        placebo_abs_ret[i] = abs_ret[mask].mean()
        placebo_vol[i] = np.nanmean(vol[mask])

    p_abs_ret = (placebo_abs_ret >= observed_abs_ret).mean()
    p_vol = (placebo_vol >= observed_vol).mean()

    return {
        "window_days": window,
        "n_events": n_events,
        "observed_abs_return_pct": observed_abs_ret,
        "placebo_abs_return_mean": placebo_abs_ret.mean(),
        "placebo_abs_return_p95": np.percentile(placebo_abs_ret, 95),
        "p_value_abs_return": p_abs_ret,
        "observed_cond_vol": observed_vol,
        "placebo_cond_vol_mean": placebo_vol.mean(),
        "placebo_cond_vol_p95": np.percentile(placebo_vol, 95),
        "p_value_cond_vol": p_vol,
    }


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
    event_dates = dates[df["rate_decision_day"].reset_index(drop=True)]
    for d in event_dates:
        ax.axvline(d, color="orange", lw=0.3, alpha=0.3)
    ax.set_title("Условная волатильность курса USD/RUB (GARCH(1,1)) и даты решений по ставке")
    ax.set_xlabel("Дата")
    ax.set_ylabel("%")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(cfg.OUTPUT_FIGURES / "R3_conditional_volatility.png", dpi=150)
    plt.close(fig)


def main() -> None:
    df = load_daily()

    arch_p = arch_lm_test(df)
    print(f"ARCH-LM тест (H0: нет ARCH-эффекта): p={arch_p:.2e}")

    t5, cond_vol = build_t5(df)
    t5.to_csv(cfg.OUTPUT_TABLES / "T5_garch.csv", index=False)
    print("\n=== T5: параметры GARCH(1,1) ===")
    print(t5.round(4).to_string(index=False))

    plot_conditional_vol(df, cond_vol)
    print(f"\nСохранено: {cfg.OUTPUT_FIGURES / 'R3_conditional_volatility.png'}")

    es = event_study(df, cond_vol, cfg.EVENT_WINDOW_DAYS)
    t6 = pd.DataFrame([es])
    t6.to_csv(cfg.OUTPUT_TABLES / "T6_event_study.csv", index=False)
    print("\n=== T6: событийное исследование вокруг решений ЦБ ===")
    print(t6.round(4).to_string(index=False))


if __name__ == "__main__":
    main()
