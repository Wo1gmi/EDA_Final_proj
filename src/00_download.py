"""Скачивает три сырых ряда: ключевую ставку ЦБ РФ (HTML-таблица),
курс USD/RUB (XML) и цену нефти Brent (готовый CSV с FRED).

Идемпотентно: если файл уже скачан, повторно не тянет из сети.

Авторы: команда (ФИО — см. README).
"""

import hashlib
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import config as cfg

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; final-project-bot/1.0)"}

# Контрольные суммы на момент нашего прогона (P2-4 фидбека): CBR отдаёт
# "живую" выгрузку по диапазону дат, и хотя даты в SAMPLE_END зафиксированы
# в прошлом, теоретическая правка истории источником не исключена. Если
# хеш при повторном скачивании не совпадёт — это сигнал сверить числа
# заново, а не тихо продолжать с другими данными.
EXPECTED_SHA256 = {
    "keyrate_raw.csv": "e1e56132781b1477437a7857e56f772e56b77b056e78f92be71b8e4a72f1076f",
    "usdrub_raw.csv": "0edc56f497a383258ecc14691028e6612d81ff9c35a83784c6749429541d0f40",
    "brent_raw.csv": "fc3ab55170885e666085c1bdcb9ecf864826055d6370b305c6f8cb1b3e34edd0",
}


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.text


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


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


def write_checksums() -> None:
    lines = []
    for f in [cfg.RAW_KEYRATE_FILE, cfg.RAW_USDRUB_FILE, cfg.RAW_BRENT_FILE]:
        digest = sha256_of(f)
        lines.append(f"{digest}  {f.name}")
        expected = EXPECTED_SHA256.get(f.name)
        if expected and expected != digest:
            print(
                f"ВНИМАНИЕ: хеш {f.name} не совпадает с зафиксированным при первом прогоне "
                f"({expected[:12]}... vs {digest[:12]}...) — источник мог обновить историю, "
                "сверить числа заново."
            )
    checksums_path = cfg.DATA_RAW / "checksums.txt"
    checksums_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nКонтрольные суммы записаны в {checksums_path.relative_to(cfg.ROOT)}:")
    print("\n".join(lines))


def main() -> None:
    t0 = time.time()
    download_keyrate()
    download_usdrub()
    download_brent()
    write_checksums()
    print(f"\nЗагрузка завершена за {time.time() - t0:.1f} с")


if __name__ == "__main__":
    main()
