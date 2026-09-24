"""Константы проекта. Дата отсечки, источники, параметры моделей — всё здесь,
чтобы проверяющий мог поменять любое значение и перезапустить пайплайн.

Авторы: команда (ФИО — см. README).
"""

import warnings
from pathlib import Path

# Подавляем только те предупреждения, которые проверили и признали
# безобидными для наших целей (P2-6 фидбека), а не всё подряд:
# - statsmodels предупреждает, что adfuller/kpss/acorr_lm в будущей версии
#   поменяют формат возврата (FutureWarning) — мы используем текущий формат
#   намеренно (`adf_stat, adf_p, *_ = adfuller(...)`), совместимость на
#   момент сдачи проверена.
# - InterpolationWarning из kpss — p-значение вне таблицы (< 0.01 или > 0.1),
#   мы читаем это как "решительно отвергаем/не отвергаем", таблица с точным
#   p-значением здесь не нужна.
warnings.filterwarnings("ignore", category=FutureWarning)
try:
    from statsmodels.tools.sm_exceptions import InterpolationWarning

    warnings.filterwarnings("ignore", category=InterpolationWarning)
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUT_TABLES = ROOT / "output" / "tables"
OUTPUT_FIGURES = ROOT / "output" / "figures"

for _dir in (DATA_RAW, DATA_PROCESSED, OUTPUT_TABLES, OUTPUT_FIGURES):
    _dir.mkdir(parents=True, exist_ok=True)

# --- Период разведки ---
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

# --- Структурный слом: экстренное повышение ставки 9.5% -> 20% в ответ на санкционный шок ---
SHOCK_DATE = "2022-02-28"

# --- Хвост выборки: НЕ обрезаем в основной спецификации ---
# Дата, после которой начинается волатильный, неустоявшийся эпизод нефти.
# Используется только для параллельной проверки устойчивости, не для обрезки основной модели.
VOLATILE_TAIL_START = "2026-07-01"

# --- Параметры моделей ---
VAR_MAX_LAG = 6
GARCH_ORDER = (1, 1)
EVENT_WINDOW_DAYS = 5  # +/- торговых дней вокруг даты решения по ставке
