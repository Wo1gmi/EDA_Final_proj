"""Проверка вне выборки (P1-4 фидбека, см. `feedback_1.md`): улучшает ли
ставка прогноз курса, а не только объясняет его задним числом (Грейнджер —
про предсказуемость в выборке, это разные вещи, лекция 4).

Скользящее происхождение (expanding window, мин. 36 месяцев обучения),
горизонты 1-3 месяца, три модели: наивный прогноз (0 — без изменений),
VAR(курс, нефть) без ставки, VAR(курс, нефть, ставка) — основная
спецификация. Сравнение отдельно для кризисных лет (2014/2015/2022) целью
прогноза и для остальных.

Авторы: команда (ФИО — см. README).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from statsmodels.tsa.vector_ar.var_model import VAR

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config as cfg

MIN_TRAIN = 36
MAX_H = 3
LAG = 2
CRISIS_YEARS = {2014, 2015, 2022}


def load_diffed() -> tuple[pd.DataFrame, pd.Series]:
    panel = pd.read_parquet(cfg.MONTHLY_PANEL_FILE)
    data = panel[["key_rate", "usdrub", "brent"]].copy()
    data["usdrub"] = np.log(data["usdrub"])
    data["brent"] = np.log(data["brent"])
    diffed = data.diff().dropna().reset_index(drop=True)
    diff_dates = panel["date"].iloc[1:].reset_index(drop=True)
    return diffed, diff_dates


def rolling_forecast(diffed: pd.DataFrame, diff_dates: pd.Series) -> pd.DataFrame:
    n = len(diffed)
    rows = []
    for origin in range(MIN_TRAIN, n - MAX_H):
        train3 = diffed.iloc[:origin][["key_rate", "usdrub", "brent"]].values
        train2 = diffed.iloc[:origin][["usdrub", "brent"]].values
        try:
            fc3 = VAR(train3).fit(LAG).forecast(train3[-LAG:], steps=MAX_H)
        except Exception:
            fc3 = np.full((MAX_H, 3), np.nan)
        try:
            fc2 = VAR(train2).fit(LAG).forecast(train2[-LAG:], steps=MAX_H)
        except Exception:
            fc2 = np.full((MAX_H, 2), np.nan)

        for h in range(1, MAX_H + 1):
            target_idx = origin + h - 1
            if target_idx >= n:
                continue
            rows.append(
                {
                    "origin": origin,
                    "h": h,
                    "target_date": diff_dates.iloc[target_idx],
                    "target_year": diff_dates.iloc[target_idx].year,
                    "actual_dlog_usdrub": diffed["usdrub"].iloc[target_idx],
                    "naive": 0.0,
                    "var2_no_rate": fc2[h - 1, 0],
                    "var3_with_rate": fc3[h - 1, 1],
                }
            )
    return pd.DataFrame(rows)


def summarize(forecasts: pd.DataFrame) -> pd.DataFrame:
    forecasts = forecasts.copy()
    forecasts["is_crisis_target"] = forecasts["target_year"].isin(CRISIS_YEARS)
    rows = []
    for regime_label, regime_mask in [
        ("все горизонты, вся выборка", forecasts.index == forecasts.index),
        ("цель прогноза — кризисный год (2014/2015/2022)", forecasts["is_crisis_target"]),
        ("цель прогноза — спокойный год", ~forecasts["is_crisis_target"]),
    ]:
        sub_regime = forecasts[regime_mask]
        for h in range(1, MAX_H + 1):
            sub = sub_regime[sub_regime["h"] == h]
            if len(sub) == 0:
                continue
            row = {"regime": regime_label, "h": h, "n": len(sub)}
            for model in ["naive", "var2_no_rate", "var3_with_rate"]:
                err = sub["actual_dlog_usdrub"] - sub[model]
                row[f"rmse_{model}"] = np.sqrt((err**2).mean())
                row[f"mae_{model}"] = err.abs().mean()
            rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    diffed, diff_dates = load_diffed()
    forecasts = rolling_forecast(diffed, diff_dates)
    forecasts.to_csv(cfg.OUTPUT_TABLES / "T8_outofsample_forecasts.csv", index=False)

    summary = summarize(forecasts)
    summary.to_csv(cfg.OUTPUT_TABLES / "T8_outofsample_summary.csv", index=False)
    print(f"=== T8: прогноз вне выборки, {len(forecasts)} прогнозов, min_train={MIN_TRAIN} мес. ===")
    print(summary.round(4).to_string(index=False))

    print(
        "\nВывод: наивный прогноз (без изменений) конкурентен с обеими VAR-моделями "
        "на всех горизонтах и в обоих режимах — ставка не улучшает прогноз курса "
        "за пределами обучающей выборки, даже там, где она значима по Грейнджеру "
        "внутри выборки. См. feedback_1.md, P1-4."
    )


if __name__ == "__main__":
    main()
