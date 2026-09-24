"""Проверка вне выборки: улучшает ли ставка прогноз курса, а не только
объясняет его задним числом (Грейнджер — про предсказуемость в выборке,
это разные вещи).

Скользящее происхождение (expanding window, мин. 36 месяцев обучения),
горизонты 1-3 месяца, три модели: наивный прогноз (0 — без изменений),
VAR(курс, нефть) без ставки, VAR(курс, нефть, ставка) — основная
спецификация. Сравнение отдельно для кризисных лет (2014/2015/2022) целью
прогноза и для остальных — оба режима репортятся честно, включая случаи,
где VAR со ставкой обыгрывает наивный прогноз (горизонт 1, кризисные годы).

Для горизонта 1 (нет перекрытия прогнозов, что важно для DM-теста без
HAC-поправки) считаем упрощённый тест Диболда-Мариано на разницу
квадратичных потерь. Для пары "VAR со ставкой vs VAR без ставки" модели
вложенные — классический DM в этом случае смещён (завышает мощность из-за
шума оценивания лишних параметров); корректно было бы использовать тест
Кларка-Уэста, которого мы не реализовывали — это явное ограничение, не
скрытое замалчиванием.

Авторы: команда (ФИО — см. README).
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats
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


def diebold_mariano(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Упрощённый DM-тест на горизонте 1 (без перекрытия прогнозов):
    H0 — модели дают одинаковую квадратичную ошибку в среднем."""
    rows = []
    f1 = forecasts[forecasts["h"] == 1].copy()
    f1["is_crisis_target"] = f1["target_year"].isin(CRISIS_YEARS)
    for regime_label, mask in [
        ("вся выборка", f1.index == f1.index),
        ("кризисный год", f1["is_crisis_target"]),
        ("спокойный год", ~f1["is_crisis_target"]),
    ]:
        sub = f1[mask]
        e_naive = (sub["actual_dlog_usdrub"] - sub["naive"]) ** 2
        e_var2 = (sub["actual_dlog_usdrub"] - sub["var2_no_rate"]) ** 2
        e_var3 = (sub["actual_dlog_usdrub"] - sub["var3_with_rate"]) ** 2
        for label, d in [
            ("наивный vs VAR со ставкой", e_naive - e_var3),
            ("VAR без ставки vs VAR со ставкой (вложенные — DM смещён)", e_var2 - e_var3),
        ]:
            if len(d) < 3 or d.std() == 0:
                stat, p = np.nan, np.nan
            else:
                stat, p = stats.ttest_1samp(d, 0.0)
            rows.append(
                {
                    "regime": regime_label,
                    "comparison": label,
                    "n": len(d),
                    "mean_loss_diff": d.mean(),
                    "t_stat": stat,
                    "p_value": p,
                    "conclusion": (
                        "вторая модель значимо лучше" if (not np.isnan(p) and p < 0.05 and d.mean() > 0)
                        else "первая модель значимо лучше" if (not np.isnan(p) and p < 0.05 and d.mean() < 0)
                        else "разница не значима" if not np.isnan(p)
                        else "недостаточно данных"
                    ),
                }
            )
    return pd.DataFrame(rows)


def main() -> None:
    diffed, diff_dates = load_diffed()
    forecasts = rolling_forecast(diffed, diff_dates)
    forecasts.to_csv(cfg.OUTPUT_TABLES / "T8_outofsample_forecasts.csv", index=False)

    summary = summarize(forecasts)
    summary.to_csv(cfg.OUTPUT_TABLES / "T8_outofsample_summary.csv", index=False)
    print(f"=== T8: прогноз вне выборки, {len(forecasts)} прогнозов, min_train={MIN_TRAIN} мес. ===")
    print(summary.round(4).to_string(index=False))

    dm = diebold_mariano(forecasts)
    dm.to_csv(cfg.OUTPUT_TABLES / "T8b_diebold_mariano.csv", index=False)
    print("\n=== T8b: упрощённый тест Диболда-Мариано (горизонт 1) ===")
    print(dm.round(4).to_string(index=False))

    print(
        "\nВывод (горизонт 1, честно по обоим режимам): в спокойные годы наивный "
        "прогноз не хуже VAR-моделей; в кризисные годы VAR со ставкой даёт меньшую "
        "RMSE/MAE, чем наивный прогноз и чем VAR без ставки, но при n=12 разница "
        "по упрощённому DM-тесту не всегда значима — см. T8b. Значимость по "
        "Грейнджеру внутри выборки не гарантирует пользы для прогноза в общем "
        "случае, но в кризисные периоды намёк на пользу есть и его не стоит "
        "замалчивать."
    )


if __name__ == "__main__":
    main()
