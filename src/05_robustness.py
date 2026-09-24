"""Проверки устойчивости (Э6 плана): альтернативный лаг, подпериоды
до/после 2022, альтернативный порядок переменных в IRF, полный период
против периода без волатильного хвоста 2026 года. Всё сводится в Т7.

Ничего здесь не заменяет основную спецификацию из `03_var.py` — задача
этого скрипта показать, меняются ли содержательные выводы (знак и
значимость Грейнджера, знак пика IRF), а не выбрать "лучшую" версию.

Авторы: команда (ФИО — см. README).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.vector_ar.var_model import VAR

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config as cfg

VARS = ["key_rate", "usdrub", "brent"]


def load_levels(exclude_tail: bool = False) -> pd.DataFrame:
    panel = pd.read_parquet(cfg.MONTHLY_PANEL_FILE)
    if exclude_tail:
        panel = panel[~panel["volatile_tail"]]
    data = panel[VARS].copy()
    data["usdrub"] = np.log(data["usdrub"])
    data["brent"] = np.log(data["brent"])
    return data.reset_index(drop=True)


def granger_pvalues(levels: pd.DataFrame, lag: int) -> dict:
    d = levels.diff().dropna()
    if len(d) <= lag * len(VARS) + 5:
        return {"rate_to_fx_p": np.nan, "fx_to_rate_p": np.nan, "n_obs": len(d)}
    res = VAR(d.values).fit(lag)
    c1 = res.test_causality(caused=1, causing=[0], kind="f")
    c2 = res.test_causality(caused=0, causing=[1], kind="f")
    return {"rate_to_fx_p": c1.pvalue, "fx_to_rate_p": c2.pvalue, "n_obs": len(d)}


def irf_peak(levels: pd.DataFrame, lag: int, ordering: list) -> dict:
    d = levels[ordering].diff().dropna()
    res = VAR(d.values).fit(lag)
    irf = res.irf(12)
    impulse_idx = ordering.index("key_rate")
    response_idx = ordering.index("usdrub")
    path = irf.orth_irfs[:, response_idx, impulse_idx]
    peak_idx = int(np.argmax(np.abs(path)))
    return {"peak_horizon": peak_idx, "peak_value": path[peak_idx], "sign": "+" if path[peak_idx] > 0 else "-"}


def main() -> None:
    rows = []

    levels_full = load_levels(exclude_tail=False)
    levels_no_tail = load_levels(exclude_tail=True)
    principal_lag = 2

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

    # 2. Подпериоды до/после структурного слома 2022
    for label, sub in [
        ("до 28.02.2022", levels_full[pd.read_parquet(cfg.MONTHLY_PANEL_FILE)["date"] < cfg.SHOCK_DATE].reset_index(drop=True)),
        ("после 28.02.2022", levels_full[pd.read_parquet(cfg.MONTHLY_PANEL_FILE)["date"] >= cfg.SHOCK_DATE].reset_index(drop=True)),
    ]:
        g = granger_pvalues(sub, principal_lag)
        rows.append(
            {
                "check": "подпериод (структурный слом 2022)",
                "variant": label,
                "n_obs": g["n_obs"],
                "rate_to_fx_p": g["rate_to_fx_p"],
                "fx_to_rate_p": g["fx_to_rate_p"],
                "conclusion": "оба направления значимы (p<0.05)"
                if (not np.isnan(g["rate_to_fx_p"])) and g["rate_to_fx_p"] < 0.05 and g["fx_to_rate_p"] < 0.05
                else "не всё значимо / мало наблюдений",
            }
        )

    # 3. Полный период против периода без волатильного хвоста 2026 года
    for label, lv in [("полный период (основной)", levels_full), ("без хвоста 07-09.2026", levels_no_tail)]:
        g = granger_pvalues(lv, principal_lag)
        rows.append(
            {
                "check": "хвост выборки (0.8)",
                "variant": label,
                "n_obs": g["n_obs"],
                "rate_to_fx_p": g["rate_to_fx_p"],
                "fx_to_rate_p": g["fx_to_rate_p"],
                "conclusion": "оба направления значимы (p<0.05)"
                if g["rate_to_fx_p"] < 0.05 and g["fx_to_rate_p"] < 0.05
                else "результат меняется",
            }
        )

    t7 = pd.DataFrame(rows)
    t7.to_csv(cfg.OUTPUT_TABLES / "T7_robustness.csv", index=False)
    print("=== T7: робастность (Грейнджер по проверкам) ===")
    print(t7.round(4).to_string(index=False))

    # 4. Альтернативный порядок переменных в IRF (ортогонализация Холецкого)
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
    print("\n=== T7b: чувствительность IRF к порядку переменных ===")
    print(t7_irf.round(4).to_string(index=False))

    # Свод по коинтеграции — уже посчитан на Э2, здесь просто цитируем файл
    spec_text = cfg.DATA_PROCESSED.joinpath("var_spec_decision.txt").read_text(encoding="utf-8")
    print("\n=== Напоминание Э2: чувствительность ранга коинтеграции к лагу ===")
    print(spec_text)


if __name__ == "__main__":
    main()
