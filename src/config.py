"""Константы проекта. Дата отсечки, источники, параметры моделей — всё здесь,
чтобы проверяющий мог поменять любое значение и перезапустить пайплайн.

Авторы: команда (ФИО — см. README).
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUT_TABLES = ROOT / "output" / "tables"
OUTPUT_FIGURES = ROOT / "output" / "figures"

for _dir in (DATA_RAW, DATA_PROCESSED, OUTPUT_TABLES, OUTPUT_FIGURES):
    _dir.mkdir(parents=True, exist_ok=True)

# --- Период разведки (см. plan_keyrate.md, раздел 0) ---
# Начало — момент, когда ключевая ставка стала основным инструментом ЦБ РФ.
SAMPLE_START = "01.01.2013"
# Конец — фиксируем на дату последней проверки данных, не "сегодня":
# иначе повторный прогон в другой день даст другую выборку.
SAMPLE_END = "23.09.2026"

# --- Источники данных ---
CBR_KEYRATE_URL = (
    "https://www.cbr.ru/hd_base/KeyRate/"
    "?UniDbQuery.Posted=True&UniDbQuery.From={date_from}&UniDbQuery.To={date_to}"
)
CBR_USDRUB_URL = (
    "https://www.cbr.ru/scripts/XML_dynamic.asp"
    "?date_req1={date_from}&date_req2={date_to}&VAL_NM_RQ=R01235"
)
FRED_BRENT_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU"

RAW_KEYRATE_FILE = DATA_RAW / "keyrate_raw.csv"
RAW_USDRUB_FILE = DATA_RAW / "usdrub_raw.csv"
RAW_BRENT_FILE = DATA_RAW / "brent_raw.csv"

MONTHLY_PANEL_FILE = DATA_PROCESSED / "monthly_panel.parquet"
DAILY_RETURNS_FILE = DATA_PROCESSED / "daily_returns.parquet"

# --- Структурный слом (см. plan_keyrate.md, п. 0.4) ---
SHOCK_DATE = "2022-02-28"  # экстренное повышение ставки 9.5% -> 20%

# --- Хвост выборки: НЕ обрезаем в основной спецификации (см. plan_keyrate.md, п. 0.8 и раздел 7) ---
# Дата, после которой начинается волатильный, неустоявшийся эпизод нефти.
# Используется только для параллельной проверки устойчивости, не для обрезки основной модели.
VOLATILE_TAIL_START = "2026-07-01"

# --- Параметры моделей ---
VAR_MAX_LAG = 6
GARCH_ORDER = (1, 1)
EVENT_WINDOW_DAYS = 5  # +/- торговых дней вокруг даты решения по ставке
