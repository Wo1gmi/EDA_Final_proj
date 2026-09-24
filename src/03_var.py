"""VAR в разностях (основная спецификация) + VECM (альтернатива),
тест Грейнджера в обе стороны (с контролем на нефть и без), импульсные отклики.

Основная спецификация выбрана в `01_prepare.py` (`var_spec_decision.txt`):
данные не показывают устойчивой коинтеграции (ранг зависит от лага), поэтому
базовая модель — VAR(2) на первых разностях `key_rate, log(usdrub), log(brent)`.
VECM(k_ar_diff=1, rank=1) считается параллельно, а не как запасной план.

Авторы: команда (ФИО — см. README).
"""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.vector_ar.var_model import VAR
from statsmodels.tsa.vector_ar.vecm import VECM

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config as cfg

VARS = ["key_rate", "usdrub", "brent"]


def load_levels() -> pd.DataFrame:
    panel = pd.read_parquet(cfg.MONTHLY_PANEL_FILE)
    data = panel[VARS].copy()
    data["usdrub"] = np.log(data["usdrub"])
    data["brent"] = np.log(data["brent"])
    return data


def read_spec_decision() -> dict:
    text = cfg.DATA_PROCESSED.joinpath("var_spec_decision.txt").read_text(encoding="utf-8")
    spec, kd = None, 1
    for line in text.splitlines():
        if line.startswith("SPEC="):
            spec = line.split("=", 1)[1].strip()
        if line.startswith("KD="):
            kd = int(line.split("=", 1)[1].strip())
    return {"spec": spec, "kd": kd}


def lag_selection_table(levels: pd.DataFrame) -> pd.DataFrame:
    order = VAR(levels.values).select_order(cfg.VAR_MAX_LAG)
    rows = []
    for crit in ["aic", "bic", "hqic", "fpe"]:
        rows.append({"criterion": crit, "selected_lag": order.selected_orders[crit]})
    return pd.DataFrame(rows)


def fit_var_diff(levels: pd.DataFrame, lag: int, include_oil: bool = True):
    cols = VARS if include_oil else ["key_rate", "usdrub"]
    d = levels[cols].diff().dropna()
    model = VAR(d.values)
    results = model.fit(lag)
    return results, cols


def granger_row(results, cols: list, caused: str, causing: str, spec_label: str, control_label: str) -> dict:
    caused_idx = cols.index(caused)
    causing_idx = cols.index(causing)
    test = results.test_causality(caused=caused_idx, causing=[causing_idx], kind="f")
    return {
        "spec": spec_label,
        "control": control_label,
        "causing": causing,
        "caused": caused,
        "f_stat": test.test_statistic,
        "p_value": test.pvalue,
        "conclusion": "отвергаем H0 (есть предсказуемость)" if test.pvalue < 0.05 else "не отвергаем H0",
    }


def granger_row_vecm(vecm_results, caused: int, causing: int, caused_name: str, causing_name: str) -> dict:
    test = vecm_results.test_granger_causality(caused=caused, causing=causing)
    return {
        # kd=1 — тот самый лаг, который сам план признал произвольным (см. 0.5):
        # ранг коинтеграции при нём на границе критического значения, а при
        # data-driven лаге (kd=2) не подтверждается вовсе. Помечаем явно как
        # отвергнутую по данным альтернативу, а не равноправную спецификацию.
        "spec": "VECM (kd=1 — альтернатива, отвергнутая по данным, см. 01_prepare.py)",
        "control": "с нефтью (в системе)",
        "causing": causing_name,
        "caused": caused_name,
        "f_stat": test.test_statistic,
        "p_value": test.pvalue,
        "conclusion": "отвергаем H0 (есть предсказуемость)" if test.pvalue < 0.05 else "не отвергаем H0",
    }


def build_t4(levels: pd.DataFrame, lag: int) -> pd.DataFrame:
    rows = []

    res_full, cols_full = fit_var_diff(levels, lag, include_oil=True)
    rows.append(granger_row(res_full, cols_full, "usdrub", "key_rate", "VAR-в-разностях (осн.)", "с нефтью в системе"))
    rows.append(granger_row(res_full, cols_full, "key_rate", "usdrub", "VAR-в-разностях (осн.)", "с нефтью в системе"))

    res_biv, cols_biv = fit_var_diff(levels, lag, include_oil=False)
    rows.append(granger_row(res_biv, cols_biv, "usdrub", "key_rate", "VAR-в-разностях (осн.)", "без нефти"))
    rows.append(granger_row(res_biv, cols_biv, "key_rate", "usdrub", "VAR-в-разностях (осн.)", "без нефти"))

    vecm = VECM(levels.values, k_ar_diff=1, coint_rank=1, deterministic="co").fit()
    rows.append(granger_row_vecm(vecm, caused=1, causing=0, caused_name="usdrub", causing_name="key_rate"))
    rows.append(granger_row_vecm(vecm, caused=0, causing=1, caused_name="key_rate", causing_name="usdrub"))

    return pd.DataFrame(rows)


def _orth_irf_per_pp(sample: np.ndarray, lag: int, impulse_idx: int, response_idx: int, periods: int) -> np.ndarray:
    """IRF ортогонализована по Холецкому, пересчитана на отклик к шоку 1 п.п.

    orth_irfs по умолчанию даёт отклик на шок в 1 стандартное отклонение
    структурной инновации. Для переменной, стоящей первой в порядке Холецкого
    (у нас — key_rate), это отклонение равно sqrt(sigma_u[0,0]) и не смешано
    с ковариацией остальных переменных, поэтому деление на него даёт именно
    отклик на 1 процентный пункт ставки. Для impulse не первого в порядке
    такое масштабирование было бы некорректно.
    """
    r = VAR(sample).fit(lag)
    irf = r.irf(periods)
    shock_sd = np.sqrt(r.sigma_u[impulse_idx, impulse_idx])
    return irf.orth_irfs[:, response_idx, impulse_idx] / shock_sd


def bootstrap_irf(
    results, cols: list, periods: int = 12, n_boot: int = 500, seed: int = 20260101
) -> pd.DataFrame:
    """Остаточный (recursive-design) бутстрап доверительных интервалов IRF:
    пересэмплируем остатки с возвращением, симулируем ряд по тем же
    коэффициентам VAR, переоцениваем модель и IRF на каждой реплике —
    вместо асимптотического интервала по умолчанию (см. фидбек P0-3.5:
    при 156 наблюдениях и выбросах 2014-15/2022 он, скорее всего, узкий)."""
    impulse_idx = cols.index("key_rate")
    response_idx = cols.index("usdrub")
    if impulse_idx != 0:
        raise RuntimeError("Масштабирование IRF на 1 п.п. верно только для impulse, стоящего первым в порядке.")

    intercept = results.intercept
    coefs = results.coefs  # (lag, k, k)
    resid = results.resid  # (T-lag, k)
    lag = results.k_ar
    k = results.neqs
    d = results.endog  # исходные (дифференцированные) данные, включая первые lag наблюдений
    T = d.shape[0]

    point = _orth_irf_per_pp(d, lag, impulse_idx, response_idx, periods)

    rng = np.random.default_rng(seed)
    paths = np.full((n_boot, periods + 1), np.nan)
    for b in range(n_boot):
        e_star = resid[rng.integers(0, resid.shape[0], size=T - lag)]
        y = np.zeros((T, k))
        y[:lag] = d[:lag]
        for t in range(lag, T):
            yt = intercept.copy()
            for l in range(lag):
                yt = yt + coefs[l] @ y[t - 1 - l]
            y[t] = yt + e_star[t - lag]
        try:
            paths[b] = _orth_irf_per_pp(y, lag, impulse_idx, response_idx, periods)
        except Exception:
            continue

    lo = np.nanpercentile(paths, 2.5, axis=0)
    hi = np.nanpercentile(paths, 97.5, axis=0)
    n_ok = int(np.isfinite(paths[:, 0]).sum())
    print(f"Бутстрап IRF: {n_ok}/{n_boot} реплик успешно (шок = 1 п.п., ставка первая в порядке Холецкого)")

    return pd.DataFrame(
        {
            "horizon": np.arange(periods + 1),
            "response_per_pp": point,
            "ci_lo": lo,
            "ci_hi": hi,
            "cum_response_per_pp": np.cumsum(point),
            "cum_ci_lo": np.cumsum(lo),
            "cum_ci_hi": np.cumsum(hi),
        }
    )


def plot_irf(irf_table: pd.DataFrame) -> None:
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(7.5, 7), sharex=True)

    ax1.plot(irf_table["horizon"], irf_table["response_per_pp"], color="steelblue", lw=2)
    ax1.fill_between(irf_table["horizon"], irf_table["ci_lo"], irf_table["ci_hi"], color="steelblue", alpha=0.2)
    ax1.axhline(0, color="black", lw=0.7)
    ax1.set_ylabel("Отклик log-курса за месяц")
    ax1.set_title(
        "Отклик курса USD/RUB на шок ставки в 1 п.п.\n"
        "VAR(2) в разностях, 95% бутстрап-CI (500 реплик, ставка первая в порядке Холецкого)",
        fontsize=10,
    )

    ax2.plot(irf_table["horizon"], irf_table["cum_response_per_pp"], color="darkorange", lw=2)
    ax2.fill_between(irf_table["horizon"], irf_table["cum_ci_lo"], irf_table["cum_ci_hi"], color="darkorange", alpha=0.2)
    ax2.axhline(0, color="black", lw=0.7)
    ax2.set_ylabel("Накопленный отклик log-курса")
    ax2.set_xlabel("Месяцы после шока")
    ax2.set_title("Накопленный эффект (сумма отклика по горизонтам)", fontsize=11)

    fig.tight_layout()
    fig.savefig(cfg.OUTPUT_FIGURES / "R2_irf_rate_to_fx.png", dpi=150)
    plt.close(fig)


def main() -> None:
    levels = load_levels()
    decision = read_spec_decision()
    lag = decision["kd"]
    print(f"Основная спецификация: {decision['spec']}, лаг (k_ar_diff)={lag}")

    t3_lag = lag_selection_table(levels)
    t3_lag.to_csv(cfg.OUTPUT_TABLES / "T3_lag_selection.csv", index=False)
    print("\n=== T3: выбор лага VAR (по уровням) ===")
    print(t3_lag.to_string(index=False))

    res_full, cols_full = fit_var_diff(levels, lag, include_oil=True)
    print(f"\nМодель стабильна: {res_full.is_stable()}")
    whiteness = res_full.test_whiteness(nlags=12)
    print(f"Тест на автокорреляцию остатков (whiteness, 12 лагов): p={whiteness.pvalue:.3f}")
    with open(cfg.OUTPUT_TABLES / "T3_diagnostics.txt", "w", encoding="utf-8") as f:
        f.write(f"is_stable={res_full.is_stable()}\n")
        f.write(f"whiteness_stat={whiteness.test_statistic:.3f}\n")
        f.write(f"whiteness_pvalue={whiteness.pvalue:.4f}\n")

    t4 = build_t4(levels, lag)
    t4.to_csv(cfg.OUTPUT_TABLES / "T4_granger.csv", index=False)
    print("\n=== T4: тест Грейнджера ===")
    print(t4.round(4).to_string(index=False))

    irf_table = bootstrap_irf(res_full, cols_full, periods=12, n_boot=500)
    irf_table.to_csv(cfg.OUTPUT_TABLES / "T3c_irf_bootstrap.csv", index=False)
    plot_irf(irf_table)
    print("\n=== T3c: IRF (шок 1 п.п.), бутстрап-CI ===")
    print(irf_table.round(4).to_string(index=False))
    print(f"\nСохранено: {cfg.OUTPUT_FIGURES / 'R2_irf_rate_to_fx.png'}")


if __name__ == "__main__":
    main()
