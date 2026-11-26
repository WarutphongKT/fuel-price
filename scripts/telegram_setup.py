#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ตั้งค่า Telegram แบบอัตโนมัติ: หา chat_id จากข้อความล่าสุดที่ส่งหาบอท แล้วทดสอบส่ง

ขั้นตอน:
  1) คุยกับ @BotFather -> /newbot -> คัดลอก token
  2) ส่งข้อความอะไรก็ได้ (เช่น /start) ไปที่บอทที่สร้าง
  3) รัน:  python scripts/telegram_setup.py --token "123456:AA..."
"""

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCAL_CONFIG_PATH = ROOT / "config.local.json"
UA = "Mozilla/5.0 ThaiFuelPriceTracker/1.0"


def api(token, method, payload=None):
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload).encode("utf-8") if payload else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": UA},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main():
    parser = argparse.ArgumentParser(description="ตั้งค่า Telegram bot สำหรับรายงานราคาน้ำมัน")
    parser.add_argument("--token", help="Bot token จาก @BotFather")
    args = parser.parse_args()

    token = args.token
    if not token:
        token = input("วาง Bot token: ").strip()
    if not token or ":" not in token:
        raise SystemExit("token ไม่ถูกต้อง (ต้องมีรูปแบบ ตัวเลข:ตัวอักษร)")

    try:
        updates = api(token, "getUpdates")
    except Exception as exc:  # noqa: BLE001
        raise SystemExit(f"เรียก Telegram ไม่สำเร็จ: {exc}")

    if not updates.get("ok"):
        raise SystemExit(f"Telegram ตอบกลับผิดพลาด: {updates}")

    chat_id = None
    for item in reversed(updates.get("result") or []):
        message = item.get("message") or item.get("edited_message") or {}
        chat = message.get("chat") or {}
        if chat.get("id") is not None:
            chat_id = str(chat["id"])
            break

    if chat_id is None:
        raise SystemExit(
            "ยังไม่พบข้อความถึงบอท — เปิด Telegram ค้นหาบอทของคุณ กด Start/ส่งข้อความ 1 ครั้ง แล้วรันใหม่"
        )

    local = {}
    if LOCAL_CONFIG_PATH.exists():
        try:
            local = json.loads(LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            local = {}
    local["telegram_bot_token"] = token
    local["telegram_chat_id"] = chat_id
    LOCAL_CONFIG_PATH.write_text(
        json.dumps(local, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    result = api(
        token,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": "✅ เชื่อมต่อสำเร็จ! ระบบจะส่งสรุปราคาน้ำมันให้ทุกวัน 06:00 และ 17:30 น.",
        },
    )
    if result.get("ok"):
        print(f"บันทึก config.local.json แล้ว (chat_id={chat_id}) และส่งข้อความทดสอบสำเร็จ")
    else:
        print(f"บันทึกแล้ว แต่ส่งข้อความทดสอบไม่สำเร็จ: {result}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
