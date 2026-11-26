#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ค่าคงที่และตัวจัดรูปแบบที่ใช้ร่วมกันระหว่าง report.py กับ theme.py"""

from datetime import timedelta, timezone

TZ = timezone(timedelta(hours=7))

THAI_MONTHS = [
    "มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน",
    "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม",
]
THAI_MONTHS_SHORT = [
    "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.",
    "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค.",
]
THAI_DAYS = ["จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์", "อาทิตย์"]
THAI_DAYS_SHORT = ["จ", "อ", "พ", "พฤ", "ศ", "ส", "อา"]


def thai_date(dt, short=False):
    months = THAI_MONTHS_SHORT if short else THAI_MONTHS
    year = dt.year + 543
    if short:
        year = year % 100
    return f"{dt.day} {months[dt.month - 1]} {year}"


def fmt_price(value):
    return f"{value:,.2f}"


def fmt_delta(value):
    if value is None:
        return "—"
    if abs(value) < 0.005:
        return "คงที่"
    return f"{value:+.2f}"


def delta_class(value):
    if value is None or abs(value) < 0.005:
        return "flat"
    return "up" if value > 0 else "down"


def delta_arrow(value):
    if value is None or abs(value) < 0.005:
        return "–"
    return "▲" if value > 0 else "▼"


def delta_word(value):
    if value is None or abs(value) < 0.005:
        return "ไม่เปลี่ยนแปลง"
    return "เพิ่มขึ้นจากครั้งก่อน" if value > 0 else "ลดลงจากครั้งก่อน"
