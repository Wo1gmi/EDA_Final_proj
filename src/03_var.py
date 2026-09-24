"""Слой 1 плана: VAR в разностях (основная спецификация) + VECM (альтернатива),
тест Грейнджера в обе стороны (с контролем на нефть и без), импульсные отклики.

Основная спецификация выбрана на Э2 (`01_prepare.py`, `var_spec_decision.txt`):
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
        "spec": "VECM (kd=1, rank=1)",
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


def plot_irf(results, cols: list, periods: int = 12) -> None:
    irf = results.irf(periods)
    impulse_idx = cols.index("key_rate")
    response_idx = cols.index("usdrub")
    fig = irf.plot(
        orth=True,
        impulse=impulse_idx,
        response=response_idx,
        signif=0.05,
    )
    fig.set_size_inches(7.5, 5)
    if fig._suptitle is not None:
        fig.suptitle("")
    ax = fig.axes[0]
    ax.set_title(
        "Отклик Δlog(курс USD/RUB) на шок ставки в 1 п.п.\nVAR(2) в разностях, 95% доверительный интервал",
        fontsize=11,
    )
    ax.set_xlabel("Месяцы после шока")
    ax.set_ylabel("Отклик log-курса")
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

    plot_irf(res_full, cols_full)
    print(f"\nСохранено: {cfg.OUTPUT_FIGURES / 'R2_irf_rate_to_fx.png'}")


if __name__ == "__main__":
    main()
