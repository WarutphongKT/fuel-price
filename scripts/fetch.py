#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ดึงราคาน้ำมันขายปลีก ปตท.OR รายอำเภอ (แหล่งทางการ) + ราคาตลาดโลก แล้วเก็บลง SQLite

แหล่งข้อมูล:
  1) ปตท.OR  ราคาขายปลีกภูมิภาค  https://www.pttor.com/th/oil_price
     (endpoint เดียวกับที่หน้าเว็บเรียก: admin-ajax.php action=fetch_regional_oil_prices)
  2) Brent crude (front month)    Yahoo Finance  BZ=F
  3) USD/THB                      Frankfurter (อ้างอิงธนาคารกลางยุโรป)

ใช้เฉพาะ standard library ไม่ต้อง pip install
"""

import argparse
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
DB_PATH = ROOT / "data" / "prices.db"

TZ = timezone(timedelta(hours=7))  # Asia/Bangkok
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ThaiFuelPriceTracker/1.0 (personal use)"

OR_ENDPOINT = "https://www.pttor.com/wp-admin/admin-ajax.php"
BRENT_URL = "https://query1.finance.yahoo.com/v8/finance/chart/BZ=F?range=1mo&interval=1d"
FX_URL = "https://api.frankfurter.app/{start}..?from=USD&to=THB"

# ชื่อผลิตภัณฑ์ที่ OR ส่งมา -> ชื่อที่ใช้แสดงในรายงาน
PRODUCT_LABELS = {
    "ดีเซล": "ดีเซล B7",
    "ดีเซล B20": "ดีเซล B20",
    "ดีเซลพรีเมียม": "ดีเซลพรีเมียม",
    "เบนซิน": "เบนซิน 95",
    "เบนซินแก๊สโซฮอล์ 95": "แก๊สโซฮอล์ 95",
    "เบนซินแก๊สโซฮอล์ 91": "แก๊สโซฮอล์ 91",
    "เบนซินแก๊สโซฮอล์ E20": "แก๊สโซฮอล์ E20",
    "เบนซินแก๊สโซฮอล์ E85": "แก๊สโซฮอล์ E85",
    "Super Power GSH95": "SP GSH95",
    "Super Power Diesel": "SP Diesel",
    "Super Power X99": "SP X99",
    "ก๊าซ NGV": "NGV",
}


# ---------------------------------------------------------------- http utils
def http_request(url, form=None, timeout=40):
    headers = {"User-Agent": UA, "Accept": "application/json, text/plain, */*"}
    body = None
    if form is not None:
        body = urllib.parse.urlencode(form, encoding="utf-8").encode("utf-8")
        headers.update(
            {
                "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.pttor.com/th/oil_price",
            }
        )
    req = urllib.request.Request(url, data=body, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read()
    return raw.decode("utf-8", errors="replace")


def get_json(url, form=None, label="request"):
    last = None
    for attempt in range(3):
        try:
            return json.loads(http_request(url, form))
        except Exception as exc:  # noqa: BLE001 - ต้องทน network ล่มชั่วคราว
            last = exc
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"{label} ล้มเหลว: {last}")


# ---------------------------------------------------------------- database
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS price_change (
            province     TEXT NOT NULL,
            district     TEXT NOT NULL,
            effective_at TEXT NOT NULL,
            product      TEXT NOT NULL,
            price        REAL NOT NULL,
            fetched_at   TEXT NOT NULL,
            PRIMARY KEY (province, district, effective_at, product)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS market (
            date       TEXT PRIMARY KEY,
            brent      REAL,
            usdthb     REAL,
            fetched_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS fetch_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            source     TEXT NOT NULL,
            detail     TEXT,
            rows       INTEGER,
            fetched_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def log_fetch(conn, source, detail, rows):
    conn.execute(
        "INSERT INTO fetch_log (source, detail, rows, fetched_at) VALUES (?,?,?,?)",
        (source, detail, rows, datetime.now(TZ).isoformat(timespec="seconds")),
    )


# ---------------------------------------------------------------- OR retail
def fetch_or_month(province, district, month, year_be):
    payload = {
        "action": "fetch_regional_oil_prices",
        "province": province,
        "district": district,
        "month": month,
        "year": year_be,
    }
    data = get_json(OR_ENDPOINT, payload, label=f"OR {month}/{year_be}")
    if not data.get("success"):
        raise RuntimeError(f"OR ตอบ success=false ({month}/{year_be})")
    rows = (data.get("data") or {}).get("rows") or []
    return rows


def save_or_rows(conn, rows, province, district, now_iso):
    saved = 0
    for row in rows:
        raw_dt = row.get("priceDate")
        if not raw_dt:
            continue
        try:
            eff = datetime.fromisoformat(raw_dt)
        except ValueError:
            continue
        if eff.tzinfo is None:
            eff = eff.replace(tzinfo=TZ)
        eff_iso = eff.isoformat(timespec="minutes")
        for item in row.get("priceData") or []:
            raw_name = str(item.get("OilTypeId", "")).strip()
            if not raw_name:
                continue
            product = PRODUCT_LABELS.get(raw_name, raw_name)
            try:
                price = float(item.get("Price"))
            except (TypeError, ValueError):
                continue
            conn.execute(
                """
                INSERT INTO price_change
                    (province, district, effective_at, product, price, fetched_at)
                VALUES (?,?,?,?,?,?)
                ON CONFLICT(province, district, effective_at, product)
                DO UPDATE SET price = excluded.price, fetched_at = excluded.fetched_at
                """,
                (province, district, eff_iso, product, price, now_iso),
            )
            saved += 1
    return saved


def months_to_fetch(conn, province, district, full):
    today = datetime.now(TZ).date()
    if not full:
        have = conn.execute(
            "SELECT COUNT(*) FROM price_change WHERE province=? AND district=?",
            (province, district),
        ).fetchone()[0]
        if have == 0:
            full = True
    if full:
        return [(m, today.year + 543) for m in range(1, today.month + 1)]

    out = []
    y, m = today.year, today.month
    for _ in range(2):  # เดือนปัจจุบัน + เดือนก่อน (เผื่อข้อมูลย้อนหลังปลายเดือน)
        out.append((m, y + 543))
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    return out


# ---------------------------------------------------------------- market data
def fetch_brent():
    data = get_json(BRENT_URL, label="Brent")
    result = (data.get("chart") or {}).get("result") or []
    if not result:
        raise RuntimeError("Brent: ไม่มีข้อมูล")
    res = result[0]
    stamps = res.get("timestamp") or []
    closes = ((res.get("indicators") or {}).get("quote") or [{}])[0].get("close") or []
    out = []
    for ts, close in zip(stamps, closes):
        if close is None:
            continue
        day = datetime.fromtimestamp(ts, TZ).date().isoformat()
        out.append((day, float(close)))
    return out


def fetch_fx():
    start = (datetime.now(TZ).date() - timedelta(days=14)).isoformat()
    data = get_json(FX_URL.format(start=start), label="USD/THB")
    rates = data.get("rates") or {}
    return [(day, float(v["THB"])) for day, v in rates.items() if "THB" in v]


def save_market(conn, now_iso):
    brent_rows = fetch_brent()
    for day, price in brent_rows:
        conn.execute(
            """
            INSERT INTO market (date, brent, usdthb, fetched_at) VALUES (?,?,NULL,?)
            ON CONFLICT(date) DO UPDATE SET brent = excluded.brent, fetched_at = excluded.fetched_at
            """,
            (day, price, now_iso),
        )
    fx_rows = fetch_fx()
    for day, rate in fx_rows:
        conn.execute(
            """
            INSERT INTO market (date, brent, usdthb, fetched_at) VALUES (?,NULL,?,?)
            ON CONFLICT(date) DO UPDATE SET usdthb = excluded.usdthb, fetched_at = excluded.fetched_at
            """,
            (day, rate, now_iso),
        )
    return len(brent_rows), len(fx_rows)


# ---------------------------------------------------------------- main
def main():
    parser = argparse.ArgumentParser(description="ดึงราคาน้ำมันรายวัน (ปตท.OR)")
    parser.add_argument("--full", action="store_true", help="ดึงย้อนหลังทุกเดือนของปีนี้")
    parser.add_argument("--skip-market", action="store_true", help="ข้ามข้อมูลตลาดโลก")
    args = parser.parse_args()

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    province = config["province"]
    district = config["district"]

    now = datetime.now(TZ)
    now_iso = now.isoformat(timespec="seconds")
    conn = connect()

    total = 0
    for month, year_be in months_to_fetch(conn, province, district, args.full):
        try:
            rows = fetch_or_month(province, district, month, year_be)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {month:02d}/{year_be}: {exc}", file=sys.stderr)
            continue
        saved = save_or_rows(conn, rows, province, district, now_iso)
        total += saved
        print(f"  - {month:02d}/{year_be}: {len(rows)} แถวที่ราคาเปลี่ยน ({saved} รายการ)")
        log_fetch(conn, "pttor_or", f"{province}/{district} {month:02d}/{year_be}", len(rows))
        time.sleep(0.6)  # สุภาพต่อเซิร์ฟเวอร์

    if not args.skip_market:
        try:
            brent_n, fx_n = save_market(conn, now_iso)
            print(f"  - ตลาดโลก: Brent {brent_n} วัน, USD/THB {fx_n} วัน")
            log_fetch(conn, "market", "Brent + USD/THB", brent_n + fx_n)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! ตลาดโลก: {exc}", file=sys.stderr)

    conn.commit()
    latest = conn.execute(
        "SELECT effective_at FROM price_change WHERE province=? AND district=? "
        "ORDER BY effective_at DESC LIMIT 1",
        (province, district),
    ).fetchone()
    conn.close()

    print(f"บันทึกแล้ว {total} รายการ | ราคาล่าสุด: {latest[0] if latest else '-'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
