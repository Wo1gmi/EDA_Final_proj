"""Скачивает три сырых ряда: ключевую ставку ЦБ РФ (HTML-таблица),
курс USD/RUB (XML) и цену нефти Brent (готовый CSV с FRED).

Идемпотентно: если файл уже скачан, повторно не тянет из сети.

Авторы: команда (ФИО — см. README).
"""

import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config as cfg

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; final-project-bot/1.0)"}


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def download_keyrate() -> None:
    if cfg.RAW_KEYRATE_FILE.exists():
        print(f"Уже скачано, пропускаю: {cfg.RAW_KEYRATE_FILE.relative_to(cfg.ROOT)}")
        return
    url = cfg.CBR_KEYRATE_URL.format(date_from=cfg.SAMPLE_START, date_to=cfg.SAMPLE_END)
    print(f"Скачиваю ключевую ставку: {url}")
    html = fetch(url)
    rows = re.findall(r"<tr[^>]*>.*?</tr>", html, re.S)
    lines = ["date,rate"]
    for row in rows:
        cells = re.findall(r"<td[^>]*>\s*([^<]+?)\s*</td>", row)
        if len(cells) == 2:
            date_s, rate_s = (c.strip() for c in cells)
            rate_s = rate_s.replace(",", ".")
            lines.append(f"{date_s},{rate_s}")
    if len(lines) < 2:
        raise RuntimeError(
            "Не нашёл ни одной строки таблицы ставки — верстка cbr.ru могла измениться."
        )
    cfg.RAW_KEYRATE_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Строк: {len(lines) - 1} -> {cfg.RAW_KEYRATE_FILE.relative_to(cfg.ROOT)}")


def download_usdrub() -> None:
    if cfg.RAW_USDRUB_FILE.exists():
        print(f"Уже скачано, пропускаю: {cfg.RAW_USDRUB_FILE.relative_to(cfg.ROOT)}")
        return
    url = cfg.CBR_USDRUB_URL.format(date_from=cfg.SAMPLE_START, date_to=cfg.SAMPLE_END)
    print(f"Скачиваю курс USD/RUB: {url}")
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    xml = resp.content.decode("windows-1251")
    records = re.findall(
        r'<Record Date="([\d.]+)"[^>]*><Nominal>(\d+)</Nominal><Value>([\d,]+)</Value>',
        xml,
    )
    if not records:
        raise RuntimeError("Не нашёл ни одной записи курса — проверить формат ответа ЦБ.")
    lines = ["date,nominal,value"]
    for date_s, nominal_s, value_s in records:
        lines.append(f"{date_s},{nominal_s},{value_s.replace(',', '.')}")
    cfg.RAW_USDRUB_FILE.write_text("\n".join(lines), encoding="utf-8")
    print(f"Строк: {len(lines) - 1} -> {cfg.RAW_USDRUB_FILE.relative_to(cfg.ROOT)}")


def download_brent() -> None:
    if cfg.RAW_BRENT_FILE.exists():
        print(f"Уже скачано, пропускаю: {cfg.RAW_BRENT_FILE.relative_to(cfg.ROOT)}")
        return
    print(f"Скачиваю Brent (FRED): {cfg.FRED_BRENT_URL}")
    csv_text = fetch(cfg.FRED_BRENT_URL)
    cfg.RAW_BRENT_FILE.write_text(csv_text, encoding="utf-8")
    n_lines = csv_text.count("\n")
    print(f"Строк: {n_lines} -> {cfg.RAW_BRENT_FILE.relative_to(cfg.ROOT)}")


def main() -> None:
    t0 = time.time()
    download_keyrate()
    download_usdrub()
    download_brent()
    print(f"Загрузка завершена за {time.time() - t0:.1f} с")


if __name__ == "__main__":
    main()
