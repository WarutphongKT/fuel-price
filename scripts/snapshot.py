#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
สำรอง/กู้ประวัติราคาเป็น JSON ข้อความล้วน

ใช้เมื่อรันบน GitHub Actions ซึ่งดิสก์ไม่คงอยู่ระหว่างรอบ:
    python scripts/snapshot.py import data/history.json   # ก่อน fetch
    python scripts/snapshot.py export data/history.json   # หลัง report

รูปแบบ: อาร์เรย์ต่อแถว หนึ่งบรรทัดต่อหนึ่งรายการ เพื่อให้ git diff อ่านง่าย
และไม่บวมเหมือนไฟล์ SQLite (binary)
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fetch import connect

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "data" / "history.json"
TZ = timezone(timedelta(hours=7))
VERSION = 1

PRICE_COLS = ("province", "district", "effective_at", "product", "price", "fetched_at")
MARKET_COLS = ("date", "brent", "usdthb", "fetched_at")
NEWS_COLS = ("url", "title", "source", "published_at", "query", "fetched_at")

# (table, columns, order by, primary key)
TABLES = (
    ("price_change", PRICE_COLS, "province, district, effective_at, product",
     ("province", "district", "effective_at", "product")),
    ("market", MARKET_COLS, "date", ("date",)),
    ("news", NEWS_COLS, "published_at DESC, url", ("url",)),
)


def export_snapshot(conn, path):
    doc = {
        "version": VERSION,
        "exported_at": datetime.now(TZ).isoformat(timespec="seconds"),
    }
    for table, cols, order, _ in TABLES:
        rows = conn.execute(
            f"SELECT {', '.join(cols)} FROM {table} ORDER BY {order}"
        ).fetchall()
        doc[table] = [list(row) for row in rows]

    lines = ["{"]
    lines.append(f'  "version": {doc["version"]},')
    lines.append(f'  "exported_at": {json.dumps(doc["exported_at"])},')
    names = [name for name, _, _, _ in TABLES]
    for index, name in enumerate(names):
        rows = doc[name]
        tail = "," if index < len(names) - 1 else ""
        lines.append(f'  "{name}": [')
        for i, row in enumerate(rows):
            comma = "," if i < len(rows) - 1 else ""
            payload = json.dumps(row, ensure_ascii=False, separators=(",", ":"))
            lines.append(f"    {payload}{comma}")
        lines.append(f"  ]{tail}")
    lines.append("}")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    counts = ", ".join(f"{name} {len(doc[name])}" for name in names)
    print(f"บันทึก snapshot: {path} ({counts})")
    return doc


def import_snapshot(conn, path):
    if not path.exists():
        print(f"ไม่พบ snapshot ที่ {path} — เริ่มจากฐานข้อมูลว่าง")
        return 0

    doc = json.loads(path.read_text(encoding="utf-8"))
    version = doc.get("version")
    if version != VERSION:
        print(f"  ! snapshot version {version} ไม่ตรงกับ {VERSION} — อ่านเท่าที่เข้าใจ", file=sys.stderr)

    total = 0
    for table, cols, _, keys in TABLES:
        rows = doc.get(table) or []
        placeholders = ",".join("?" * len(cols))
        updates = ", ".join(
            f"{col} = excluded.{col}" for col in cols if col not in keys
        )
        sql = (
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({placeholders}) "
            f"ON CONFLICT({', '.join(keys)}) DO UPDATE SET {updates}"
        )
        for row in rows:
            if len(row) != len(cols):
                continue
            conn.execute(sql, row)
            total += 1
        print(f"  - {table}: {len(rows)} แถว")

    conn.commit()
    print(f"กู้ข้อมูลจาก snapshot แล้ว {total} แถว")
    return total


def main():
    parser = argparse.ArgumentParser(description="สำรอง/กู้ประวัติราคาเป็น JSON")
    parser.add_argument("action", choices=("export", "import"))
    parser.add_argument("path", nargs="?", default=str(DEFAULT_PATH))
    parser.add_argument("--db", help="ไฟล์ SQLite ที่ใช้ (ค่าเริ่มต้น data/prices.db)")
    args = parser.parse_args()

    path = Path(args.path)
    conn = connect(args.db)
    try:
        if args.action == "export":
            export_snapshot(conn, path)
        else:
            import_snapshot(conn, path)
    finally:
        conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
