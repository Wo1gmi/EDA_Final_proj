"""Параметры исследования и пути к данным."""

import os
from pathlib import Path

__author__ = "Анастасия Казакова; Степан Селезнев; Светлана Калошкина"

ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
OUTPUT_TABLES = ROOT / "output" / "tables"
OUTPUT_FIGURES = ROOT / "output" / "figures"
for directory in (DATA_RAW, DATA_PROCESSED, OUTPUT_TABLES, OUTPUT_FIGURES):
    directory.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".matplotlib"))
SAMPLE_START = "01.01.2013"
SAMPLE_END = "23.09.2026"
MONTHLY_START = "2013-10-01"
MONTHLY_END = "2026-08-31"
CBR_KEYRATE_URL = "https://www.cbr.ru/hd_base/KeyRate/?UniDbQuery.Posted=True&UniDbQuery.From={date_from}&UniDbQuery.To={date_to}"
CBR_USDRUB_URL = "https://www.cbr.ru/scripts/XML_dynamic.asp?date_req1={date_from}&date_req2={date_to}&VAL_NM_RQ=R01235"
FRED_BRENT_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU"
RAW_KEYRATE_FILE = DATA_RAW / "keyrate_raw.csv"
RAW_USDRUB_FILE = DATA_RAW / "usdrub_raw.csv"
RAW_BRENT_FILE = DATA_RAW / "brent_raw.csv"
MONTHLY_PANEL_FILE = DATA_PROCESSED / "monthly_panel.parquet"
DAILY_RETURNS_FILE = DATA_PROCESSED / "daily_returns.parquet"
EVENT_CALENDAR_FILE = DATA_PROCESSED / "rate_change_calendar.csv"
SHOCK_DATE = "2022-02-28"
FX_MEASUREMENT_BREAK = "2024-06-13"
VOLATILE_TAIL_START = "2026-07-01"
VAR_MAX_LAG = 6
VAR_LAG = 2
GARCH_ORDER = (1, 1)
EVENT_WINDOW_DAYS = 5
