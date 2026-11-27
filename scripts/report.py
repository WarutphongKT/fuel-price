#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
สร้างรายงานราคาน้ำมันรายวัน (Markdown + dashboard.html) และส่งเข้า Telegram

อ่านข้อมูลจาก data/prices.db ที่ scripts/fetch.py ดึงมาจาก:
  - ปตท.OR ราคาขายปลีกภูมิภาค (ทางการ)  https://www.pttor.com/th/oil_price
  - Brent (Yahoo Finance) และ USD/THB (Frankfurter / อ้างอิง ECB)

ชั้น view (HTML/CSS) อยู่ใน scripts/theme.py
"""

import html
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import theme
from common import (
    THAI_DAYS,
    THAI_MONTHS,
    THAI_MONTHS_SHORT,
    TZ,
    fmt_delta,
    fmt_price,
    thai_date,
)

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
LOCAL_CONFIG_PATH = ROOT / "config.local.json"
DB_PATH = ROOT / "data" / "prices.db"
REPORT_DIR = ROOT / "reports"
DASHBOARD_PATH = ROOT / "dashboard.html"
INDEX_PATH = ROOT / "index.html"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ThaiFuelPriceTracker/1.0"

# สำนักข่าวไทยที่เชื่อถือได้สำหรับข่าวราคาน้ำมันในประเทศ
CREDIBLE_HINTS = (
    "thairath", "bangkokbiznews", "prachachat", "kaohoon", "infoquest",
    "posttoday", "thansettakij", "matichon", "krungthep", "manager",
    "baseeconomic", "efinance", "pptv", "nation", "tnn", "springnews",
    "amarintv", "ch7", "ch3", "workpoint", "sanook", "moneyandbanking",
)

# ข่าวราคาน้ำมันของประเทศเพื่อนบ้าน ไม่ใช้เป็นสัญญาณเตือนราคาในไทย
FOREIGN_HINTS = (
    "vietnam", "lao", "laos", "china", "malaysia", "cambodia", "myanmar",
    "philippines", "indonesia", "ลาว", "เวียดนาม", "กัมพูชา", "มาเลเซีย",
    "เมียนมา", "ฟิลิปปินส์", "อินโดนีเซีย", "จีน", "ต่างประเทศ",
)


def load_config():
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    local = {}
    if LOCAL_CONFIG_PATH.exists():
        try:
            local = json.loads(LOCAL_CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            local = {}
    return config, local


# ---------------------------------------------------------------- data
def load_data(conn, province, district):
    rows = conn.execute(
        """
        SELECT effective_at, product, price FROM price_change
        WHERE province = ? AND district = ?
        ORDER BY effective_at ASC, product ASC
        """,
        (province, district),
    ).fetchall()

    timeline = {}
    events = []
    for eff_iso, product, price in rows:
        try:
            eff = datetime.fromisoformat(eff_iso)
        except ValueError:
            continue
        if eff.tzinfo is None:
            eff = eff.replace(tzinfo=TZ)
        price = float(price)
        history = timeline.setdefault(product, [])
        prev = history[-1][1] if history else None
        history.append((eff, price))
        if prev is not None and abs(price - prev) > 0.004:
            events.append(
                {
                    "at": eff,
                    "product": product,
                    "price": price,
                    "delta": round(price - prev, 2),
                }
            )

    market = conn.execute(
        "SELECT date, brent, usdthb FROM market ORDER BY date ASC"
    ).fetchall()

    news_cutoff = (datetime.now(TZ) - timedelta(days=4)).isoformat(timespec="minutes")
    news_rows = conn.execute(
        """
        SELECT title, source, url, published_at FROM news
        WHERE published_at >= ? ORDER BY published_at DESC LIMIT 6
        """,
        (news_cutoff,),
    ).fetchall()
    news = [
        {
            "title": title,
            "source": source,
            "url": url,
            "published": datetime.fromisoformat(published_at),
        }
        for title, source, url, published_at in news_rows
    ]
    return timeline, events, market, news


def market_summary(market):
    brent = [(d, v) for d, v, _ in market if v is not None]
    fx = [(d, v) for d, _, v in market if v is not None]

    def summarize(series, label, unit):
        if not series:
            return None
        latest_day, latest = series[-1]
        base = series[-6][1] if len(series) >= 6 else series[0][1]
        change = latest - base
        pct = (change / base * 100) if base else 0.0
        return {
            "label": label,
            "unit": unit,
            "value": latest,
            "day": latest_day,
            "change": change,
            "pct": pct,
            "days": min(5, len(series) - 1) or 0,
        }

    return summarize(brent, "Brent", "USD/บาร์เรล"), summarize(fx, "USD/THB", "บาท")


def pressure_text(brent, fx):
    score = 0.0
    if brent:
        score += brent["pct"] * 0.7
    if fx:
        score += fx["pct"] * 0.3
    if score >= 1.5:
        return "up", "แรงกดดันขาขึ้นชัดเจน"
    if score >= 0.5:
        return "up", "เอียงขึ้น"
    if score <= -1.5:
        return "down", "แรงกดดันขาลงชัดเจน"
    if score <= -0.5:
        return "down", "เอียงลง"
    return "flat", "ทรงตัว"


# ---------------------------------------------------------------- context
def build_context(conn, config):
    province = config["province"]
    district = config["district"]
    reference = config.get("reference_product", "ดีเซล B7")
    now = datetime.now(TZ)
    today = now.date()
    tomorrow = today + timedelta(days=1)

    timeline, events, market, news = load_data(conn, province, district)
    if not timeline:
        raise SystemExit("ยังไม่มีข้อมูลในฐานข้อมูล — รัน scripts/fetch.py ก่อน")

    latest_by_product = {p: hist[-1] for p, hist in timeline.items()}
    last_event_by_product = {}
    for event in events:
        last_event_by_product[event["product"]] = event

    # เรียงผลิตภัณฑ์: ตาม config ก่อน แล้วต่อด้วยที่เหลือ
    order = [p for p in config.get("display_products", []) if p in timeline]
    order += [p for p in timeline if p not in order]

    snapshot_at = max(dt for dt, _ in latest_by_product.values())
    last_fetch_row = conn.execute(
        "SELECT MAX(fetched_at) FROM price_change WHERE province=? AND district=?",
        (province, district),
    ).fetchone()
    last_fetch_at = snapshot_at
    if last_fetch_row and last_fetch_row[0]:
        try:
            last_fetch_at = datetime.fromisoformat(last_fetch_row[0])
        except ValueError:
            pass

    cards = []
    for product in order:
        price_at, price = latest_by_product[product]
        event = last_event_by_product.get(product)
        delta = event["delta"] if event else None
        delta_at = event["at"] if event else price_at
        history = [(dt, v) for dt, v in timeline[product] if dt >= snapshot_at - timedelta(days=120)]
        cards.append(
            {
                "product": product,
                "price": price,
                "delta": delta,
                "delta_at": delta_at,
                "price_at": price_at,
                "history": history,
            }
        )

    tomorrow_events = [e for e in events if e["at"].date() == tomorrow]
    today_events = [e for e in events if e["at"].date() == today]

    # ---- สถิติ: ทิศทางรายวัน + วันในสัปดาห์
    by_date = {}
    for event in events:
        by_date.setdefault(event["at"].date(), []).append(event)

    day_direction = {}
    for day, day_events in by_date.items():
        ref = next((e for e in day_events if e["product"] == reference), None)
        delta = ref["delta"] if ref is not None else sum(e["delta"] for e in day_events)
        if abs(delta) < 0.005:
            continue
        day_direction[day] = 1 if delta > 0 else -1

    weekday_stats = {i: {"up": 0, "down": 0} for i in range(7)}
    for day, direction in day_direction.items():
        weekday_stats[day.weekday()]["up" if direction > 0 else "down"] += 1

    # ---- ปฏิทินเดือนปัจจุบัน
    calendar = {}
    for day, day_events in by_date.items():
        if day.year != today.year or day.month != today.month:
            continue
        ups = sum(1 for e in day_events if e["delta"] > 0)
        downs = sum(1 for e in day_events if e["delta"] < 0)
        direction = "mixed" if ups and downs else ("up" if ups else "down")
        calendar[day.day] = {
            "direction": direction,
            "events": sorted(day_events, key=lambda e: -abs(e["delta"])),
        }

    brent, fx = market_summary(market)
    pressure_class, pressure_label = pressure_text(brent, fx)

    tomorrow_tag = f"{tomorrow.day} {THAI_MONTHS_SHORT[tomorrow.month - 1]}"
    for item in news:
        item["for_tomorrow"] = tomorrow_tag in item["title"]
        source_key = (item["source"] or "").lower()
        item["credible"] = any(hint in source_key for hint in CREDIBLE_HINTS)
        item["foreign"] = any(hint in source_key for hint in FOREIGN_HINTS)
        item["score"] = (
            (4 if "พรุ่งนี้" in item["title"] else 0)
            + (2 if item["for_tomorrow"] else 0)
            + (2 if item["credible"] else 0)
            + (1 if "ราคาน้ำมัน" in item["title"] else 0)
        )

    relevant_keywords = (
        "พรุ่งนี้", "วันนี้", "ดีเซล", "แก๊สโซฮอล์", "ปรับขึ้น", "ปรับลง", "สตางค์",
    )
    relevant = [
        item
        for item in news
        if "ราคาน้ำมัน" in item["title"]
        and any(keyword in item["title"] for keyword in relevant_keywords)
    ]
    news = relevant or news
    news.sort(key=lambda x: (x["score"], x["published"]), reverse=True)
    news = news[:5]

    advice = compute_advice(
        tomorrow_events, news, now, pressure_class, pressure_label, brent, tomorrow
    )

    # ข้อมูลสำหรับกราฟเลือกดูรายประเภท (ส่งให้ JS วาดกราฟ)
    series = {
        product: [[dt.date().isoformat(), value] for dt, value in sorted(history)]
        for product, history in timeline.items()
    }

    return {
        "config": config,
        "province": province,
        "district": district,
        "reference": reference,
        "now": now,
        "today": today,
        "tomorrow": tomorrow,
        "snapshot_at": snapshot_at,
        "last_fetch_at": last_fetch_at,
        "cards": cards,
        "events": events,
        "tomorrow_events": tomorrow_events,
        "today_events": today_events,
        "by_date": by_date,
        "day_direction": day_direction,
        "weekday_stats": weekday_stats,
        "calendar": calendar,
        "brent": brent,
        "fx": fx,
        "pressure_class": pressure_class,
        "pressure_label": pressure_label,
        "news": news,
        "advice": advice,
        "series": series,
    }


def compute_advice(
    tomorrow_events, news, now, pressure_class, pressure_label, brent, tomorrow
):
    """
    คำนวณคำแนะนำด่วนเพื่อป้องกันการเติมน้ำมันแพง:
      1) ทางการ ปตท.OR ยืนยันราคาพรุ่งนี้แล้ว (ปรับขึ้น -> รีบเติมคืนนี้ / ปรับลง -> รอเติมพรุ่งนี้)
      2) สัญญาณข่าวประกาศล่วงหน้า (หากยังไม่มีในระบบทางการ)
      3) ช่วงเวลาเฝ้าระวัง 16:00-18:30 น.
      4) แรงกดดันตลาดโลก (Brent/USDTHB)
      5) สถานะปกติ
    """
    if tomorrow_events:
        ups = [e for e in tomorrow_events if e["delta"] > 0]
        downs = [e for e in tomorrow_events if e["delta"] < 0]
        if ups and not downs:
            max_up = max(e["delta"] for e in ups)
            items_str = ", ".join(f"{e['product']} +{e['delta']:.2f}" for e in sorted(ups, key=lambda x: -x["delta"]))
            return {
                "theme": "up",
                "badge": "🚨 แนะนำ: เติมน้ำมันคืนนี้ก่อน 05:00 น.!",
                "title": f"พรุ่งนี้ราคาปรับขึ้นสูงสุด +{max_up:.2f} บาท/ลิตร",
                "action": "รีบเติมให้เต็มถังคืนนี้ก่อน 05:00 น. เพื่อประหยัดเงินและหลีกเลี่ยงราคาใหม่ที่แพงขึ้น",
                "detail": f"รายการปรับขึ้น: {items_str} (มีผลพรุ่งนี้ 05:00 น.)",
            }
        elif downs and not ups:
            max_down = min(e["delta"] for e in downs)
            items_str = ", ".join(f"{e['product']} {e['delta']:.2f}" for e in sorted(downs, key=lambda x: x["delta"]))
            return {
                "theme": "down",
                "badge": "🟢 แนะนำ: อย่าเพิ่งเติม! รอเติมพรุ่งนี้หลัง 05:00 น.",
                "title": f"พรุ่งนี้ราคาปรับลดลงสูงสุด {abs(max_down):.2f} บาท/ลิตร",
                "action": "ชะลอการเติมไว้ก่อน รอไปเติมพรุ่งนี้หลัง 05:00 น. จะได้ราคาน้ำมันที่ถูกลงอย่างแน่นอน",
                "detail": f"รายการปรับลด: {items_str} (มีผลพรุ่งนี้ 05:00 น.)",
            }
        elif ups and downs:
            up_str = ", ".join(f"{e['product']} +{e['delta']:.2f}" for e in ups)
            down_str = ", ".join(f"{e['product']} {e['delta']:.2f}" for e in downs)
            return {
                "theme": "warn",
                "badge": "⚠️ แนะนำ: ตรวจสอบกลุ่มน้ำมันของคุณก่อนเติม",
                "title": "พรุ่งนี้มีทั้งกลุ่มที่ปรับขึ้นและปรับลดราคา",
                "action": f"กลุ่มที่ขึ้น ({up_str}) ให้เติมคืนนี้ก่อน 05:00 น. / กลุ่มที่ลด ({down_str}) ให้รอเติมพรุ่งนี้หลัง 05:00 น.",
                "detail": "ราคาปรับเปลี่ยนไม่เท่ากันในแต่ละกลุ่มน้ำมัน ตรวจสอบชนิดที่รถของคุณใช้ก่อนเติม",
            }

    # ตรวจสอบข่าวล่วงหน้าภายใน 24 ชม. (เฉพาะสำนักข่าวไทยที่เชื่อถือได้ และเป็นข่าวของพรุ่งนี้จริง)
    fuel_words = ("ราคาน้ำมัน", "ดีเซล", "แก๊สโซฮอล์", "เบนซิน", "E20", "E85", "B7", "B20")
    tomorrow_tag = f"{tomorrow.day} {THAI_MONTHS_SHORT[tomorrow.month - 1]}"
    for item in news:
        published = item["published"]
        if (now - published).total_seconds() > 86400:
            continue
        if not item.get("credible") or item.get("foreign"):
            continue
        t = item["title"]
        if not any(w in t for w in fuel_words):
            continue

        # ต้องเป็นข่าวที่พูดถึงราคาของ "พรุ่งนี้" อย่างชัดเจน
        if "พรุ่งนี้" not in t and tomorrow_tag not in t:
            continue

        # วันที่ที่ข่าวหมายถึง: ปกติคือวันถัดจากวันที่เผยแพร่ แต่ถ้าระบุวันพรุ่งนี้ชัดเจนให้ใช้วันพรุ่งนี้
        target = published.date() + timedelta(days=1)
        if tomorrow_tag in t:
            target = tomorrow
        if target == now.date():
            if now.hour >= 5:
                continue  # ราคาใหม่มีผลไปแล้ว ข่าวนี้ใช้เตือนไม่ได้
            when = "เช้านี้ก่อน 05:00 น."
        elif target == tomorrow:
            when = "คืนนี้ก่อน 05:00 น."
        else:
            continue

        ups = any(w in t for w in ("ปรับขึ้น", "ขยับขึ้น", "ขึ้นราคา", "พุ่งขึ้น"))
        downs = any(w in t for w in ("ปรับลด", "ขยับลง", "ปรับลง", "ลดราคา"))
        if ups == downs:
            continue
        if ups:
            return {
                "theme": "up",
                "badge": "📢 สัญญาณข่าวเตือน: มีแนวโน้มปรับขึ้นราคา",
                "title": "สำนักข่าวรายงานแนวโน้มปรับขึ้นราคาน้ำมัน",
                "action": f"หากระดับน้ำมันในถังเหลือน้อย แนะนำให้แวะเติม{when}เพื่อป้องกันการเสียเงินแพงขึ้น",
                "detail": f"ตามรายงาน: \"{t}\" ({item.get('source') or 'สำนักข่าว'}) — รอระบบทางการ ปตท.OR ยืนยัน",
            }
        return {
            "theme": "down",
            "badge": "📢 สัญญาณข่าวแจ้ง: มีแนวโน้มปรับลดราคา",
            "title": "สำนักข่าวรายงานแนวโน้มปรับลดราคาน้ำมัน",
            "action": "หากน้ำมันยังไม่หมดถัง แนะนำให้ชะลอการเติมเพื่อรอราคาใหม่ที่ถูกลง",
            "detail": f"ตามรายงาน: \"{t}\" ({item.get('source') or 'สำนักข่าว'}) — รอระบบทางการ ปตท.OR ยืนยัน",
        }

    # ช่วงเวลาจับตาประกาศรอบเย็น (16:00 - 18:30 น.)
    if 16 <= now.hour <= 18:
        return {
            "theme": "warn",
            "badge": "🔍 เฝ้าระวังประกาศราคา (16:00 - 18:30 น.)",
            "title": "ปตท.OR มักจะประกาศราคาน้ำมันของวันพรุ่งนี้ในช่วงเวลานี้",
            "action": "ระบบกำลังติดตามการประกาศให้อัตโนมัติ หากมีการแจ้งปรับราคาจะอัปเดตคำแนะนำทันที",
            "detail": "ประกาศช่วงเย็นจะมีผลบังคับใช้ในเวลา 05:00 น. ของวันถัดไป",
        }

    # ตลาดโลก
    brent_val = f"{brent['value']:.2f} USD ({brent['pct']:+.2f}%)" if brent else ""
    if pressure_class == "up":
        return {
            "theme": "warn",
            "badge": "📊 ตลาดโลกส่งสัญญาณแรงกดดันขาขึ้น",
            "title": f"ราคาน้ำมันดิบโลกและค่าเงินเอียงขึ้น ({pressure_label})",
            "action": "ต้นทุนน้ำมันตลาดโลกมีทิศทางสูงขึ้น มีความเสี่ยงที่ราคาขายปลีกอาจปรับขึ้นใน 1-3 วันนี้ ไม่ควรปล่อยให้น้ำมันแห้งถัง",
            "detail": f"Brent: {brent_val} · การปรับราคาขึ้นอยู่กับกองทุนน้ำมันฯ และค่าการตลาด",
        }
    elif pressure_class == "down":
        return {
            "theme": "down",
            "badge": "📊 ตลาดโลกส่งสัญญาณแรงกดดันขาลง",
            "title": f"ราคาน้ำมันดิบโลกและค่าเงินเอียงลง ({pressure_label})",
            "action": "ต้นทุนตลาดโลกปรับตัวลดลง มีโอกาสที่ราคาขายปลีกจะทรงตัวหรือปรับลดลงได้",
            "detail": f"Brent: {brent_val} · ติดตามประกาศของ ปตท.OR รอบถัดไป",
        }

    return {
        "theme": "neutral",
        "badge": "✔️ ราคาน้ำมันยังทรงตัว",
        "title": "ยังไม่มีสัญญาณการปรับราคาในขณะนี้",
        "action": "สามารถเติมน้ำมันได้ตามการใช้งานปกติ ณ ราคาปัจจุบัน",
        "detail": "ระบบจะตรวจสอบและอัปเดตราคาจาก ปตท.OR อัตโนมัติทุกวันตลอด 24 ชั่วโมง",
    }


# ---------------------------------------------------------------- markdown
def render_markdown(ctx):
    lines = []
    add = lines.append
    snapshot_at = ctx["snapshot_at"]
    add(f"# ราคาน้ำมัน {ctx['district']} — {thai_date(ctx['today'])}")
    add("")
    add(
        f"> ราคา ณ **{thai_date(snapshot_at, short=True)} "
        f"{snapshot_at:%H:%M} น.** · แหล่งข้อมูล: ปตท.OR (ราคาขายปลีกภูมิภาค) "
        f"· ดึงข้อมูลเมื่อ {ctx['now']:%d/%m/%Y %H:%M} น."
    )
    add("")

    advice = ctx.get("advice")
    if advice:
        add(f"## {advice['badge']}")
        add(f"**{advice['title']}**")
        add(f"- **คำแนะนำ:** {advice['action']}")
        add(f"- **รายละเอียด:** {advice['detail']}")
        add("")

    add("## ราคาปัจจุบัน")
    add("")
    add("| ผลิตภัณฑ์ | ราคา (บาท/ลิตร) | เปลี่ยนครั้งล่าสุด | มีผลเมื่อ |")
    add("|---|---:|---:|---|")
    for card in ctx["cards"]:
        add(
            f"| {card['product']} | {fmt_price(card['price'])} | "
            f"{fmt_delta(card['delta'])} | {thai_date(card['delta_at'], short=True)} "
            f"{card['delta_at']:%H:%M} |"
        )
    add("")
    add("*ราคาของ ปตท.OR ไม่รวมภาษีบำรุงท้องที่ (ถ้ามี) — ราคาแต่ละอำเภอต่างกันตามค่าขนส่ง*")
    add("")

    add(f"## ประกาศสำหรับวันพรุ่งนี้ ({thai_date(ctx['tomorrow'])})")
    add("")
    if ctx["tomorrow_events"]:
        add("**มีการประกาศปรับราคาแล้ว**")
        add("")
        add("| ผลิตภัณฑ์ | ราคาใหม่ | เปลี่ยน |")
        add("|---|---:|---:|")
        for event in ctx["tomorrow_events"]:
            add(
                f"| {event['product']} | {fmt_price(event['price'])} | "
                f"{fmt_delta(event['delta'])} |"
            )
    else:
        add(
            "ยังไม่มีการประกาศราคาของพรุ่งนี้ในระบบ ปตท.OR "
            "(ปกติประกาศช่วง 16:00–18:00 น. มีผล 05:00 น. ของวันถัดไป)"
        )
    add("")

    if ctx["news"]:
        add("## ข่าวประกาศล่าสุดจากสำนักข่าว")
        add("")
        add("*เป็นข่าวประชาสัมพันธ์ล่วงหน้า ยังไม่ใช่ข้อมูลยืนยันจากระบบ ปตท.OR*")
        add("")
        for item in ctx["news"][:5]:
            flag = " 🔔" if item["for_tomorrow"] else ""
            source = f" — {item['source']}" if item["source"] else ""
            add(
                f"- **{thai_date(item['published'], short=True)} {item['published']:%H:%M}**{flag} "
                f"[{item['title']}]({item['url']}){source}"
            )
        add("")

    if ctx["today_events"]:
        add(f"## ปรับราคาวันนี้ ({thai_date(ctx['today'])})")
        add("")
        add("| ผลิตภัณฑ์ | ราคาใหม่ | เปลี่ยน |")
        add("|---|---:|---:|")
        for event in ctx["today_events"]:
            add(
                f"| {event['product']} | {fmt_price(event['price'])} | "
                f"{fmt_delta(event['delta'])} |"
            )
        add("")

    month_events = [
        e for e in ctx["events"]
        if e["at"].year == ctx["today"].year and e["at"].month == ctx["today"].month
    ]
    dates = sorted({e["at"].date() for e in month_events})
    add(f"## ภาพรวมเดือน{THAI_MONTHS[ctx['today'].month - 1]} {ctx['today'].year + 543}")
    add("")
    if dates:
        add(f"ปรับราคา {len(dates)} วัน: " + ", ".join(str(d.day) for d in dates))
        add("")
        add("| วันที่ | ผลิตภัณฑ์ที่เปลี่ยน |")
        add("|---|---|")
        for day in dates:
            parts = []
            for event in sorted(
                [e for e in month_events if e["at"].date() == day],
                key=lambda e: -abs(e["delta"]),
            ):
                parts.append(f"{event['product']} {fmt_delta(event['delta'])}")
            add(f"| {day.day} {THAI_MONTHS_SHORT[day.month - 1]} | {', '.join(parts)} |")
    else:
        add("เดือนนี้ยังไม่มีการปรับราคา")
    add("")

    add("## วันในสัปดาห์ที่มักปรับราคา")
    add("")
    add(
        f"นับเฉพาะวันที่มีการเปลี่ยนราคา **{ctx['reference']}** "
        "(หรือผลิตภัณฑ์อื่นหากอ้างอิงไม่เปลี่ยน) ตั้งแต่ต้นปี"
    )
    add("")
    add("| วัน | ขึ้น | ลง | รวม |")
    add("|---|---:|---:|---:|")
    total_up = total_down = 0
    for index in range(7):
        stat = ctx["weekday_stats"][index]
        total_up += stat["up"]
        total_down += stat["down"]
        add(f"| {THAI_DAYS[index]} | {stat['up']} | {stat['down']} | {stat['up'] + stat['down']} |")
    add(f"| **รวม** | **{total_up}** | **{total_down}** | **{total_up + total_down}** |")
    add("")

    add("## ปัจจัยตลาดโลก (5 วันทำการล่าสุด)")
    add("")
    for item in (ctx["brent"], ctx["fx"]):
        if not item:
            continue
        add(
            f"- **{item['label']}**: {item['value']:,.2f} {item['unit']} "
            f"({fmt_delta(round(item['change'], 2))}, {item['pct']:+.2f}%)"
        )
    add("")
    add(
        f"**การอ่านแนวโน้ม:** {ctx['pressure_label']} — เป็นเพียงตัวชี้วัดทิศทางจากราคาตลาดโลก "
        "ไม่ใช่คำพยากรณ์ว่าวันใดราคาจะขึ้นหรือลง"
    )
    add("")

    add("## แหล่งข้อมูล")
    add("")
    add("- ราคาขายปลีกภูมิภาค ปตท.OR: https://www.pttor.com/th/oil_price (ทางการ)")
    add("- Brent crude front-month: https://finance.yahoo.com/quote/BZ=F")
    add("- อัตราแลกเปลี่ยน USD/THB: https://api.frankfurter.app/ (อ้างอิง ECB)")
    add("")
    add("---")
    add("สร้างโดยสคริปต์อัตโนมัติ · ตรวจสอบราคาหน้าสถานีก่อนเติมน้ำมันทุกครั้ง")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- telegram
def send_telegram(ctx, config, local):
    if not config.get("telegram", {}).get("enabled", True):
        print("Telegram: ปิดใช้งานใน config")
        return False

    token = os.environ.get("TELEGRAM_BOT_TOKEN") or local.get("telegram_bot_token")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or local.get("telegram_chat_id")
    if not token or not chat_id:
        print("Telegram: ยังไม่มี token/chat_id (สร้าง config.local.json) — ข้ามการส่ง")
        return False

    lines = [
        f"<b>📅 ราคาน้ำมัน {html.escape(ctx['district'])}</b>",
        f"{thai_date(ctx['today'])} · ราคา ณ {ctx['snapshot_at']:%H:%M} น.",
        "",
    ]
    advice = ctx.get("advice")
    if advice:
        lines.append(f"<b>{html.escape(advice['badge'])}</b>")
        lines.append(f"💡 {html.escape(advice['action'])}")
        lines.append("")
    for card in ctx["cards"][:6]:
        delta = card["delta"]
        arrow = "▲" if delta and delta > 0 else "▼" if delta and delta < 0 else "—"
        change = f"{arrow}{abs(delta):.2f}" if delta and abs(delta) > 0.004 else "—"
        lines.append(f"{card['product']}: <b>{fmt_price(card['price'])}</b> {change}")

    lines.append("")
    if ctx["tomorrow_events"]:
        parts = [
            f"{e['product']} {fmt_delta(e['delta'])}"
            for e in sorted(ctx["tomorrow_events"], key=lambda e: -abs(e["delta"]))
        ]
        lines.append(f"🔔 <b>พรุ่งนี้ ({thai_date(ctx['tomorrow'], short=True)}) ปรับราคา</b>")
        lines.append(html.escape(" · ".join(parts)))
    else:
        lines.append(f"🔔 พรุ่งนี้ ({thai_date(ctx['tomorrow'], short=True)}): ยังไม่ประกาศ")

    if ctx["news"]:
        top = ctx["news"][0]
        headline = top["title"]
        if len(headline) > 120:
            headline = headline[:117] + "..."
        lines.append("")
        lines.append(f"📰 {html.escape(headline)}")
        meta = f"{thai_date(top['published'], short=True)} {top['published']:%H:%M}"
        if top["source"]:
            meta += f" · {top['source']}"
        lines.append(f"<i>{html.escape(meta)}</i>")

    month_dates = sorted(
        {
            e["at"].date()
            for e in ctx["events"]
            if e["at"].year == ctx["today"].year and e["at"].month == ctx["today"].month
        }
    )
    if month_dates:
        lines.append("")
        lines.append(
            f"📊 เดือนนี้ปรับ {len(month_dates)} วัน: "
            + ", ".join(str(d.day) for d in month_dates)
        )

    if ctx["brent"]:
        lines.append(
            f"🛢 Brent {ctx['brent']['value']:,.2f} ({ctx['brent']['pct']:+.2f}% 5 วัน) · "
            f"{ctx['pressure_label']}"
        )

    text = "\n".join(lines)
    payload = json.dumps(
        {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    ).encode("utf-8")
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        if body.get("ok"):
            print("Telegram: ส่งสำเร็จ")
            return True
        print(f"Telegram: ตอบกลับผิดพลาด {body}")
    except Exception as exc:  # noqa: BLE001
        print(f"Telegram: ส่งไม่สำเร็จ — {exc}", file=sys.stderr)
    return False


# ---------------------------------------------------------------- main
def main():
    config, local = load_config()
    if not DB_PATH.exists():
        raise SystemExit("ยังไม่มี data/prices.db — รัน scripts/fetch.py ก่อน")

    conn = sqlite3.connect(DB_PATH)
    ctx = build_context(conn, config)
    conn.close()

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / f"{ctx['today'].isoformat()}.md"
    report_path.write_text(render_markdown(ctx), encoding="utf-8")

    DASHBOARD_PATH.write_text(theme.render_html(ctx), encoding="utf-8")
    # สำเนาสำหรับ static hosting (GitHub Pages ใช้ index.html ที่ root)
    INDEX_PATH.write_bytes(DASHBOARD_PATH.read_bytes())

    print(f"รายงาน: {report_path.relative_to(ROOT)}")
    print(f"แดชบอร์ด: {DASHBOARD_PATH.relative_to(ROOT)}")
    send_telegram(ctx, config, local)
    return 0


if __name__ == "__main__":
    sys.exit(main())
