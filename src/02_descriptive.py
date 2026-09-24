"""Описание исходных рядов и график их динамики."""

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config as cfg


def load_raw():
    import importlib
    prepare = importlib.import_module("src.01_prepare")
    key = prepare.load_keyrate().rename(columns={"key_rate": "rate"})
    return key, prepare.load_usdrub(), prepare.load_brent()


def build_t1(key: pd.DataFrame, usd: pd.DataFrame, brent: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, df, col in [("key_rate", key, "rate"), ("usdrub", usd, "usdrub"), ("brent", brent, "brent")]:
        rows.append(
            {
                "series": name,
                "n_obs": len(df),
                "date_min": df["date"].min().date(),
                "date_max": df["date"].max().date(),
                "value_min": df[col].min(),
                "value_max": df[col].max(),
                "value_mean": df[col].mean(),
            }
        )
    return pd.DataFrame(rows)


def plot_r1(key: pd.DataFrame, usd: pd.DataFrame, brent: pd.DataFrame) -> None:
    changes = key.sort_values("date").reset_index(drop=True)
    change_dates = changes.loc[changes["rate"].diff() != 0, "date"].iloc[1:]

    fig, axes = plt.subplots(3, 1, figsize=(9, 8), sharex=True)

    axes[0].plot(key["date"], key["rate"], color="darkred", lw=1)
    axes[0].set_ylabel("Ключевая ставка, %")
    for d in change_dates:
        axes[0].axvline(d, color="gray", lw=0.2, alpha=0.4)

    axes[1].plot(usd["date"], usd["usdrub"], color="steelblue", lw=0.8)
    axes[1].set_ylabel("USD/RUB, ₽")

    axes[2].plot(brent["date"], brent["brent"], color="darkgreen", lw=0.8)
    axes[2].set_ylabel("Brent, $/баррель")
    axes[2].set_xlabel("Дата")

    fig.suptitle("Ключевая ставка, курс USD/RUB и цена Brent, 2013-2026\n(серые линии - даты вступления изменений ставки в силу)")
    fig.tight_layout()
    fig.savefig(cfg.OUTPUT_FIGURES / "R1_three_series.png", dpi=150)
    plt.close(fig)


def main() -> None:
    key, usd, brent = load_raw()

    t1 = build_t1(key, usd, brent)
    t1.to_csv(cfg.OUTPUT_TABLES / "T1_sample.csv", index=False)
    print("=== T1: описание выборки ===")
    print(t1.round(2).to_string(index=False))

    plot_r1(key, usd, brent)
    print(f"\nСохранено: {cfg.OUTPUT_FIGURES / 'R1_three_series.png'}")


if __name__ == "__main__":
    main()
