"""GARCH на дневных доходностях курса + событийное исследование вокруг
65 дат решений по ставке.

GARCH-спецификация выбирается сравнением по AIC/BIC (Normal/t,
const/AR(1)-среднее, с GJR-асимметрией и без), а не фиксируется заранее —
у const-mean/Normal диагностика остатков не проходит (Ljung-Box p<0.001),
у выбранной по BIC — проходит.

Событийное исследование учитывает, что 19 из 65 решений физически лежат в
кризисных годах (2014/2015/2022) — самых волатильных периодах на графике
R3. Наивный тест (плацебо равномерно по всей выборке) оставлен рядом с
тестом на плацебо, стратифицированном по году, и аномальной |доходности|
(за вычетом базового уровня за 30 торговых дней до окна) — сравнение двух
методов показывает, почему стратификация по году важна.

Даты решений скорректированы в `01_prepare.py`: курс в выгрузке ЦБ
датирован T+1 от торговой сессии, решение по ставке — датой вступления в
силу; прямое сравнение дат совпадало в 5 случаях из 65 (детали — там же).

Ограничение (зафиксировано, не устранено): контрольная группа "заседания
СД без изменения ставки" не построена. Проверено: архив решений на
cbr.ru (`/dkp/mp_dec/decision_key_rate/`) при запросе диапазона дат
2013-2023 не возвращает записей старше 2024 года — самостоятельно собрать
календарь заседаний 2013-2023 без парсинга других источников не удалось.
Без контрольной группы тест остаётся ослабленным: подтверждаем реакцию на
волатильность в целом вокруг решений, а не специфичность именно к решению
как событию.

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
CRISIS_YEARS = {2014, 2015, 2022}
BASELINE_WINDOW = 30  # торговых дней до окна события, база для "аномальной" величины


def load_daily() -> pd.DataFrame:
    df = pd.read_parquet(cfg.DAILY_RETURNS_FILE)
    df["return_pct"] = df["log_return"] * 100  # для численной устойчивости GARCH
    df["year"] = df["date"].dt.year
    return df


def arch_lm_test(df: pd.DataFrame) -> float:
    _, p_value, *_ = het_arch(df["return_pct"], nlags=10)
    return p_value


# --- Выбор спецификации GARCH (было зафиксировано заранее — теперь выбирается) ---

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
        res = arch_model(returns, **kw).fit(disp="off")
        fitted[name] = res
        rows.append({"spec": name, "aic": res.aic, "bic": res.bic, "loglik": res.loglikelihood})
    table = pd.DataFrame(rows).sort_values("bic").reset_index(drop=True)
    best_name = table.iloc[0]["spec"]
    print("=== Выбор спецификации GARCH (по BIC) ===")
    print(table.round(1).to_string(index=False))
    print(f"Выбрана: {best_name}\n")
    return best_name, GARCH_CANDIDATES[best_name], table


def fit_garch(returns: pd.Series, spec_kwargs: dict):
    return arch_model(returns, **spec_kwargs).fit(disp="off")


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
    }
    for label, sub in periods.items():
        res = fit_garch(sub["return_pct"], spec_kwargs)
        diag = garch_diagnostics(res)
        omega = res.params["omega"]
        alpha = res.params.get("alpha[1]", 0.0)
        beta = res.params.get("beta[1]", 0.0)
        gamma = res.params.get("gamma[1]", 0.0)
        # Для GJR безусловная дисперсия — omega / (1 - alpha - beta - gamma/2)
        # (при среднем по вероятности знака остатка 1/2). omega сама по себе —
        # это НЕ базовая/безусловная дисперсия, это константа уравнения.
        persistence = alpha + beta + gamma / 2
        # Персистентность ~1 (интегрированный GARCH) — известный артефакт на
        # подвыборках с кластером экстремальной волатильности: безусловная
        # дисперсия в этом случае не идентифицируется устойчиво, честно
        # репортим NaN, а не астрономическое число.
        denom = 1 - persistence
        unconditional_var = omega / denom if denom > 1e-3 else np.nan
        rows.append(
            {
                "period": label,
                "n_obs": len(sub),
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


# --- Событийное исследование ---


def _window_mask(centers: np.ndarray, window: int, n: int) -> np.ndarray:
    mask = np.zeros(n, dtype=bool)
    for c in centers:
        lo, hi = max(c - window, 0), min(c + window, n - 1)
        mask[lo : hi + 1] = True
    return mask


def event_study_naive(df: pd.DataFrame, cond_vol: pd.Series, window: int) -> dict:
    """Наивный тест: плацебо равномерно по всей выборке, без учёта
    кластеризации решений в кризисных годах. Оставлен рядом со
    стратифицированным тестом ниже, чтобы явно показать разницу."""
    n = len(df)
    event_idx = df.index[df["rate_decision_day"]].to_numpy()
    event_mask = _window_mask(event_idx, window, n)
    abs_ret = df["return_pct"].abs().to_numpy()
    vol = cond_vol.reindex(df.index).to_numpy()

    observed_abs_ret = abs_ret[event_mask].mean()
    observed_vol = np.nanmean(vol[event_mask])

    eligible = np.where(~event_mask)[0]
    rng = np.random.default_rng(RNG_SEED)
    placebo_abs_ret = np.empty(N_PLACEBO)
    placebo_vol = np.empty(N_PLACEBO)
    n_events = len(event_idx)
    for i in range(N_PLACEBO):
        centers = rng.choice(eligible, size=n_events, replace=False)
        mask = _window_mask(centers, window, n)
        placebo_abs_ret[i] = abs_ret[mask].mean()
        placebo_vol[i] = np.nanmean(vol[mask])

    return {
        "test": "наивный (плацебо по всей выборке, без учёта кризисных кластеров)",
        "n_events": n_events,
        "observed_abs_return_pct": observed_abs_ret,
        "placebo_abs_return_mean": placebo_abs_ret.mean(),
        "p_value_abs_return": (placebo_abs_ret >= observed_abs_ret).mean(),
        "observed_cond_vol": observed_vol,
        "placebo_cond_vol_mean": placebo_vol.mean(),
        "p_value_cond_vol": (placebo_vol >= observed_vol).mean(),
    }


def _abnormal_stat(centers: np.ndarray, abs_ret: np.ndarray, window: int, n: int) -> float:
    """Средняя |доходность| в окнах вокруг centers минус средняя |доходность|
    за BASELINE_WINDOW торговых дней непосредственно до каждого окна —
    "аномальная" величина, а не сырой уровень."""
    vals = []
    for c in centers:
        lo, hi = max(c - window, 0), min(c + window, n - 1)
        win_mean = abs_ret[lo : hi + 1].mean()
        base_lo, base_hi = max(c - window - BASELINE_WINDOW, 0), max(c - window - 1, 0)
        if base_hi < base_lo:
            continue
        base_mean = abs_ret[base_lo : base_hi + 1].mean()
        vals.append(win_mean - base_mean)
    return float(np.mean(vals)) if vals else np.nan


def event_study_stratified(df: pd.DataFrame, window: int, restrict_years: set | None = None) -> dict:
    """Плацебо стратифицировано по календарному году события — псевдо-дата
    берётся из того же года, что и реальное решение, чтобы не сравнивать
    кризисные окна со спокойными днями."""
    work = df if restrict_years is None else df[df["year"].isin(restrict_years)]
    work = work.reset_index(drop=True)
    n = len(work)
    abs_ret = work["return_pct"].abs().to_numpy()
    years = work["year"].to_numpy()
    event_idx = work.index[work["rate_decision_day"]].to_numpy()
    event_years = years[event_idx]

    if len(event_idx) == 0:
        return {"n_events": 0}

    event_mask = _window_mask(event_idx, window, n)
    observed = _abnormal_stat(event_idx, abs_ret, window, n)

    rng = np.random.default_rng(RNG_SEED)
    placebo_vals = np.empty(N_PLACEBO)
    for i in range(N_PLACEBO):
        centers = np.empty(len(event_idx), dtype=int)
        for j, yr in enumerate(event_years):
            pool = np.where((years == yr) & (~event_mask))[0]
            if len(pool) == 0:
                pool = np.where(~event_mask)[0]  # запасной вариант, если год исчерпан
            centers[j] = rng.choice(pool)
        placebo_vals[i] = _abnormal_stat(centers, abs_ret, window, n)

    return {
        "n_events": len(event_idx),
        "n_years": len(set(event_years)),
        "observed_abnormal_abs_return_pct": observed,
        "placebo_abnormal_mean": np.nanmean(placebo_vals),
        "placebo_abnormal_p95": np.nanpercentile(placebo_vals, 95),
        "p_value": float((placebo_vals >= observed).mean()),
    }


def event_study_before_after(df: pd.DataFrame, window: int, restrict_years: set | None = None) -> dict:
    """Разбивка окна на 'до решения' и 'после решения' + базовый уровень
    за 30 дней до окна. `restrict_years` — посчитать только на подмножестве
    лет (например, без кризисных), чтобы не смешивать эффект решения с
    эффектом самого кризиса."""
    work = df if restrict_years is None else df[df["year"].isin(restrict_years)]
    work = work.reset_index(drop=True)
    n = len(work)
    abs_ret = work["return_pct"].abs().to_numpy()
    event_idx = work.index[work["rate_decision_day"]].to_numpy()

    pre_vals, post_vals, base_vals = [], [], []
    for c in event_idx:
        lo_pre, hi_pre = max(c - window, 0), c - 1
        lo_post, hi_post = c, min(c + window, n - 1)
        base_lo, base_hi = max(c - window - BASELINE_WINDOW, 0), max(c - window - 1, 0)
        if hi_pre >= lo_pre:
            pre_vals.append(abs_ret[lo_pre : hi_pre + 1].mean())
        if hi_post >= lo_post:
            post_vals.append(abs_ret[lo_post : hi_post + 1].mean())
        if base_hi >= base_lo:
            base_vals.append(abs_ret[base_lo : base_hi + 1].mean())

    return {
        "pre_decision_abs_return_pct": float(np.mean(pre_vals)),
        "post_decision_abs_return_pct": float(np.mean(post_vals)),
        "baseline_30d_before_window_pct": float(np.mean(base_vals)),
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
    for y0, y1 in [(2014, 2016), (2022, 2023)]:
        ax.axvspan(pd.Timestamp(f"{y0}-01-01"), pd.Timestamp(f"{y1}-01-01"), color="red", alpha=0.06)
    ax.set_title("Условная волатильность USD/RUB, даты решений (оранжевые линии),\nкризисные годы 2014-15/2022 — розовая заливка")
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

    # --- Событийное исследование: наивный тест (для сравнения) ---
    naive = event_study_naive(df, cond_vol, cfg.EVENT_WINDOW_DAYS)
    print("\n=== T6a: наивный тест (плацебо по всей выборке) ===")
    print(pd.DataFrame([naive]).round(4).to_string(index=False))

    # --- Стратифицированный тест: все события / без кризисных лет ---
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

    # --- До/после решения: все события и отдельно без кризисных лет ---
    before_after_all = event_study_before_after(df, cfg.EVENT_WINDOW_DAYS)
    before_after_all["subset"] = "все события"
    before_after_noncrisis = event_study_before_after(
        df, cfg.EVENT_WINDOW_DAYS, restrict_years=set(df["year"].unique()) - CRISIS_YEARS
    )
    before_after_noncrisis["subset"] = "без 2014/2015/2022 (кризисные годы)"
    t6c = pd.DataFrame([before_after_all, before_after_noncrisis])
    t6c.to_csv(cfg.OUTPUT_TABLES / "T6c_before_after.csv", index=False)
    print("\n=== T6c: до/после решения, база за 30 дней до окна ===")
    print(t6c.round(4).to_string(index=False))

    pd.DataFrame([naive]).to_csv(cfg.OUTPUT_TABLES / "T6_event_study.csv", index=False)


if __name__ == "__main__":
    main()
