#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
สร้างรายงานราคาน้ำมันรายวัน (Markdown + dashboard.html) และส่งเข้า Telegram

อ่านข้อมูลจาก data/prices.db ที่ scripts/fetch.py ดึงมาจาก:
  - ปตท.OR ราคาขายปลีกภูมิภาค (ทางการ)  https://www.pttor.com/th/oil_price
  - Brent (Yahoo Finance) และ USD/THB (Frankfurter / อ้างอิง ECB)
"""

import html
import json
import os
import sqlite3
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config.json"
LOCAL_CONFIG_PATH = ROOT / "config.local.json"
DB_PATH = ROOT / "data" / "prices.db"
REPORT_DIR = ROOT / "reports"
DASHBOARD_PATH = ROOT / "dashboard.html"

TZ = timezone(timedelta(hours=7))
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ThaiFuelPriceTracker/1.0"

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


# ---------------------------------------------------------------- helpers
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
    return timeline, events, market


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

    timeline, events, market = load_data(conn, province, district)
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
    snapshot_date = snapshot_at.date()

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
        if ref is not None:
            delta = ref["delta"]
        else:
            delta = sum(e["delta"] for e in day_events)
        if abs(delta) < 0.005:
            continue
        day_direction[day] = 1 if delta > 0 else -1

    weekday_stats = {i: {"up": 0, "down": 0} for i in range(7)}
    for day, direction in day_direction.items():
        weekday_stats[day.weekday()]["up" if direction > 0 else "down"] += 1

    product_stats = {}
    for event in events:
        bucket = product_stats.setdefault(event["product"], {"up": 0, "down": 0})
        bucket["up" if event["delta"] > 0 else "down"] += 1

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

    # ---- ราคาอ้างอิงย้อนหลัง (ใช้ใน dashboard)
    ref_history = timeline.get(reference, [])

    brent, fx = market_summary(market)
    pressure_class, pressure_label = pressure_text(brent, fx)

    return {
        "config": config,
        "province": province,
        "district": district,
        "reference": reference,
        "now": now,
        "today": today,
        "tomorrow": tomorrow,
        "snapshot_at": snapshot_at,
        "snapshot_date": snapshot_date,
        "cards": cards,
        "events": events,
        "tomorrow_events": tomorrow_events,
        "today_events": today_events,
        "by_date": by_date,
        "day_direction": day_direction,
        "weekday_stats": weekday_stats,
        "product_stats": product_stats,
        "calendar": calendar,
        "ref_history": ref_history,
        "brent": brent,
        "fx": fx,
        "pressure_class": pressure_class,
        "pressure_label": pressure_label,
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

    # ---- เดือนนี้
    month_events = [
        e for e in ctx["events"] if e["at"].year == ctx["today"].year and e["at"].month == ctx["today"].month
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

    # ---- สถิติวันในสัปดาห์
    add("## วันในสัปดาห์ที่มักปรับราคา")
    add("")
    add(f"นับเฉพาะวันที่มีการเปลี่ยนราคา **{ctx['reference']}** (หรือผลิตภัณฑ์อื่นหากอ้างอิงไม่เปลี่ยน) ตั้งแต่ต้นปี")
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

    # ---- ตลาดโลก
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
    add(f"**การอ่านแนวโน้ม:** {ctx['pressure_label']} — เป็นเพียงตัวชี้วัดทิศทางจากราคาตลาดโลก "
        "ไม่ใช่คำพยากรณ์ว่าวันใดราคาจะขึ้นหรือลง")
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


# ---------------------------------------------------------------- dashboard
CSS = """
:root{
  --bg:#0a0f1c; --card:#121b2e; --card2:#0f1727; --line:rgba(255,255,255,.08);
  --text:#e8eefc; --muted:#93a4c3; --accent:#38bdf8;
  --up:#f87171; --upbg:rgba(248,113,113,.14);
  --down:#4ade80; --downbg:rgba(74,222,128,.14);
  --flat:#94a3b8; --flatbg:rgba(148,163,184,.12);
}
*{box-sizing:border-box}
body{
  margin:0;padding:20px 16px 48px;background:
  radial-gradient(1200px 600px at 15% -10%,rgba(56,189,248,.16),transparent 60%),
  radial-gradient(900px 500px at 100% 0%,rgba(168,85,247,.12),transparent 55%),var(--bg);
  color:var(--text);font-family:"Sarabun","Noto Sans Thai",system-ui,-apple-system,"Segoe UI",sans-serif;
  -webkit-font-smoothing:antialiased;line-height:1.5;
}
.wrap{max-width:1080px;margin:0 auto}
header.top{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end;justify-content:space-between;margin-bottom:18px}
h1{font-size:clamp(1.4rem,3.4vw,2rem);margin:0;font-weight:700;letter-spacing:-.02em}
.sub{color:var(--muted);font-size:.92rem;margin-top:4px}
.badge{display:inline-flex;align-items:center;gap:6px;background:rgba(56,189,248,.12);color:#7dd3fc;
  border:1px solid rgba(56,189,248,.3);padding:5px 11px;border-radius:999px;font-size:.78rem;white-space:nowrap}
.banner{border-radius:16px;padding:16px 18px;margin-bottom:18px;border:1px solid var(--line);background:var(--card)}
.banner.up{border-color:rgba(248,113,113,.45);background:linear-gradient(180deg,rgba(248,113,113,.16),rgba(248,113,113,.04))}
.banner.down{border-color:rgba(74,222,128,.45);background:linear-gradient(180deg,rgba(74,222,128,.16),rgba(74,222,128,.04))}
.banner.flat{border-color:var(--line)}
.banner h2{margin:0 0 6px;font-size:1.05rem}
.banner p{margin:0;color:var(--muted);font-size:.9rem}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(215px,1fr));gap:12px;margin-bottom:22px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:14px 16px;position:relative;overflow:hidden}
.card .name{font-size:.86rem;color:var(--muted);display:flex;justify-content:space-between;gap:8px}
.card .price{font-size:1.9rem;font-weight:700;letter-spacing:-.03em;margin:6px 0 2px;font-variant-numeric:tabular-nums}
.card .price small{font-size:.8rem;font-weight:400;color:var(--muted);margin-left:4px}
.chip{display:inline-block;padding:2px 9px;border-radius:999px;font-size:.8rem;font-weight:600;font-variant-numeric:tabular-nums}
.chip.up{background:var(--upbg);color:var(--up)}
.chip.down{background:var(--downbg);color:var(--down)}
.chip.flat{background:var(--flatbg);color:var(--flat)}
.spark{width:100%;height:40px;margin-top:8px;display:block;opacity:.95}
.cols{display:grid;grid-template-columns:1.15fr .85fr;gap:14px;margin-bottom:22px}
@media(max-width:820px){.cols{grid-template-columns:1fr}}
.panel{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:16px}
.panel h3{margin:0 0 12px;font-size:1rem}
table.cal{width:100%;border-collapse:separate;border-spacing:4px;table-layout:fixed}
table.cal th{font-size:.72rem;color:var(--muted);font-weight:600;padding-bottom:2px}
table.cal td{height:44px;border-radius:10px;background:var(--card2);border:1px solid transparent;
  text-align:center;font-size:.8rem;position:relative;font-variant-numeric:tabular-nums}
table.cal td.empty{background:transparent}
table.cal td.today{outline:2px solid var(--accent);outline-offset:-2px}
table.cal td.up{background:var(--upbg);border-color:rgba(248,113,113,.35);color:#fecaca}
table.cal td.down{background:var(--downbg);border-color:rgba(74,222,128,.35);color:#bbf7d0}
table.cal td.mixed{background:rgba(250,204,21,.14);border-color:rgba(250,204,21,.35);color:#fde68a}
table.cal td .dot{position:absolute;bottom:5px;left:50%;transform:translateX(-50%);width:4px;height:4px;border-radius:50%;background:currentColor;opacity:.9}
.wd{display:grid;grid-template-columns:auto 1fr auto;gap:8px;align-items:center;margin-bottom:7px;font-size:.85rem}
.wd .bar{height:8px;border-radius:999px;background:rgba(255,255,255,.06);overflow:hidden;display:flex}
.wd .bar i{display:block;height:100%}
.wd .bar i.u{background:var(--up)}
.wd .bar i.d{background:var(--down)}
.wd .n{color:var(--muted);font-variant-numeric:tabular-nums;font-size:.8rem}
table.list{width:100%;border-collapse:collapse;font-size:.86rem}
table.list th{text-align:left;color:var(--muted);font-weight:600;font-size:.76rem;padding:6px 4px;border-bottom:1px solid var(--line)}
table.list td{padding:7px 4px;border-bottom:1px solid rgba(255,255,255,.05);font-variant-numeric:tabular-nums}
table.list td:last-child,table.list th:last-child{text-align:right}
.mkt{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}
.mkt .box{background:var(--card2);border:1px solid var(--line);border-radius:12px;padding:12px 14px}
.mkt .box .k{font-size:.78rem;color:var(--muted)}
.mkt .box .v{font-size:1.25rem;font-weight:700;margin-top:3px;font-variant-numeric:tabular-nums}
footer{margin-top:26px;color:var(--muted);font-size:.78rem;line-height:1.7}
footer a{color:#7dd3fc;text-decoration:none}
.note{color:var(--muted);font-size:.78rem;margin-top:8px}
"""


def sparkline_svg(values, delta=None, width=220, height=40):
    if not values:
        return ""
    pad = 3.0
    lo, hi = min(values), max(values)
    span = (hi - lo) or 1.0
    count = len(values)
    points = []
    for index, value in enumerate(values):
        x = pad + (width - 2 * pad) * (index / (count - 1) if count > 1 else 0.5)
        y = height - pad - (height - 2 * pad) * ((value - lo) / span)
        points.append(f"{x:.1f},{y:.1f}")
    if delta is None:
        delta = values[-1] - values[0]
    if delta > 0.004:
        color = "#f87171"
    elif delta < -0.004:
        color = "#4ade80"
    else:
        color = "#94a3b8"
    poly = " ".join(points)
    last_x, last_y = points[-1].split(",")
    return (
        f'<svg class="spark" viewBox="0 0 {width} {height}" preserveAspectRatio="none" aria-hidden="true">'
        f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="2" '
        f'stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle cx="{last_x}" cy="{last_y}" r="2.6" fill="{color}"/>'
        "</svg>"
    )


def render_calendar(ctx):
    today = ctx["today"]
    first = today.replace(day=1)
    days_in_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)
    total_days = days_in_month.day
    leading = first.weekday()

    cells = ["<tr>"]
    for _ in range(leading):
        cells.append('<td class="empty"></td>')
    column = leading
    for day in range(1, total_days + 1):
        info = ctx["calendar"].get(day)
        classes = []
        title = ""
        if info:
            classes.append(info["direction"])
            title = " · ".join(
                f"{e['product']} {fmt_delta(e['delta'])}" for e in info["events"][:4]
            )
        if day == today.day:
            classes.append("today")
        dot = '<span class="dot"></span>' if info else ""
        cells.append(
            f'<td class="{" ".join(classes)}" title="{html.escape(title)}">{day}{dot}</td>'
        )
        column += 1
        if column % 7 == 0 and day != total_days:
            cells.append("</tr><tr>")
    while column % 7 != 0:
        cells.append('<td class="empty"></td>')
        column += 1
    cells.append("</tr>")

    head = "".join(f"<th>{name}</th>" for name in THAI_DAYS_SHORT)
    return (
        f'<table class="cal"><thead><tr>{head}</tr></thead>'
        f'<tbody>{"".join(cells)}</tbody></table>'
        f'<p class="note">แดง = ปรับขึ้น · เขียว = ปรับลง · เหลือง = ขึ้นและลงในวันเดียว '
        f'(วางเมาส์/กดค้างเพื่อดูรายละเอียด)</p>'
    )


def render_weekday_stats(ctx):
    stats = ctx["weekday_stats"]
    peak = max((s["up"] + s["down"] for s in stats.values()), default=0) or 1
    rows = []
    for index in range(7):
        stat = stats[index]
        total = stat["up"] + stat["down"]
        up_pct = stat["up"] / peak * 100
        down_pct = stat["down"] / peak * 100
        rows.append(
            '<div class="wd">'
            f"<span>{THAI_DAYS[index]}</span>"
            f'<span class="bar"><i class="u" style="width:{up_pct:.1f}%"></i>'
            f'<i class="d" style="width:{down_pct:.1f}%"></i></span>'
            f'<span class="n">{total} ครั้ง</span>'
            "</div>"
        )
    return "".join(rows)


def render_recent(ctx, limit=8):
    rows = []
    for event in sorted(ctx["events"], key=lambda e: e["at"], reverse=True)[:limit]:
        cls = delta_class(event["delta"])
        rows.append(
            "<tr>"
            f"<td>{thai_date(event['at'], short=True)} {event['at']:%H:%M}</td>"
            f"<td>{event['product']}</td>"
            f"<td>{fmt_price(event['price'])}</td>"
            f'<td><span class="chip {cls}">{fmt_delta(event["delta"])}</span></td>'
            "</tr>"
        )
    return "".join(rows)


def render_cards(ctx):
    out = []
    for card in ctx["cards"]:
        cls = delta_class(card["delta"])
        values = [value for _, value in card["history"]]
        spark = sparkline_svg(values, card["delta"]) if len(values) > 1 else ""
        when = (
            f"{thai_date(card['delta_at'], short=True)} {card['delta_at']:%H:%M}"
            if card["delta"] is not None
            else "ไม่เปลี่ยนแปลง"
        )
        stale_days = (ctx["snapshot_at"] - card["delta_at"]).days
        stale = f" · ไม่ปรับมา {stale_days} วัน" if stale_days > 45 else ""
        out.append(
            '<div class="card">'
            f'<div class="name"><span>{card["product"]}</span>'
            f'<span class="chip {cls}">{fmt_delta(card["delta"])}</span></div>'
            f'<div class="price">{fmt_price(card["price"])}<small>บาท/ลิตร</small></div>'
            f'<div class="name" style="font-size:.75rem">มีผล {when}{stale}</div>'
            f"{spark}"
            "</div>"
        )
    return "".join(out)


def render_banner(ctx):
    if ctx["tomorrow_events"]:
        ups = [e for e in ctx["tomorrow_events"] if e["delta"] > 0]
        downs = [e for e in ctx["tomorrow_events"] if e["delta"] < 0]
        cls = "up" if len(ups) >= len(downs) else "down"
        parts = [
            f"{e['product']} {fmt_delta(e['delta'])}"
            for e in sorted(ctx["tomorrow_events"], key=lambda e: -abs(e["delta"]))
        ]
        return (
            f'<div class="banner {cls}"><h2>🔔 พรุ่งนี้ ({thai_date(ctx["tomorrow"], short=True)}) '
            f'มีการปรับราคา</h2><p>{html.escape(" · ".join(parts))}</p></div>'
        )
    if ctx["today_events"]:
        parts = [
            f"{e['product']} {fmt_delta(e['delta'])}"
            for e in sorted(ctx["today_events"], key=lambda e: -abs(e["delta"]))
        ]
        return (
            '<div class="banner flat"><h2>📌 วันนี้มีการปรับราคาแล้ว</h2>'
            f'<p>{html.escape(" · ".join(parts))}</p></div>'
        )
    return (
        '<div class="banner flat"><h2>🔔 พรุ่งนี้ยังไม่มีการประกาศ</h2>'
        "<p>ปตท.OR ประกาศราคาใหม่ช่วง 16:00–18:00 น. มีผล 05:00 น. ของวันถัดไป "
        "ระบบจะอัปเดตให้อัตโนมัติเมื่อมีประกาศ</p></div>"
    )


def render_html(ctx):
    brent, fx = ctx["brent"], ctx["fx"]
    market_boxes = []
    if brent:
        market_boxes.append(
            '<div class="box"><div class="k">Brent (5 วัน)</div>'
            f'<div class="v">{brent["value"]:,.2f} <span class="chip {delta_class(brent["pct"])}">'
            f'{brent["pct"]:+.2f}%</span></div>'
            f'<div class="k">USD/บาร์เรล · {brent["day"]}</div></div>'
        )
    if fx:
        market_boxes.append(
            '<div class="box"><div class="k">USD/THB (5 วัน)</div>'
            f'<div class="v">{fx["value"]:,.2f} <span class="chip {delta_class(fx["pct"])}">'
            f'{fx["pct"]:+.2f}%</span></div>'
            f'<div class="k">บาท/ดอลลาร์ · {fx["day"]}</div></div>'
        )
    market_boxes.append(
        '<div class="box"><div class="k">แรงกดดันราคา</div>'
        f'<div class="v">{html.escape(ctx["pressure_label"])}</div>'
        '<div class="k">จาก Brent + ค่าเงิน · ไม่ใช่คำพยากรณ์</div></div>'
    )

    snapshot = ctx["snapshot_at"]
    return f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ราคาน้ำมัน {html.escape(ctx['district'])} — {thai_date(ctx['today'], short=True)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header class="top">
  <div>
    <h1>ราคาน้ำมัน · {html.escape(ctx['district'])}</h1>
    <div class="sub">จ.{html.escape(ctx['province'])} · {thai_date(ctx['today'])} ·
      ราคา ณ {thai_date(snapshot, short=True)} {snapshot:%H:%M} น.</div>
  </div>
  <span class="badge">● ข้อมูลทางการ ปตท.OR</span>
</header>
{render_banner(ctx)}
<div class="grid">{render_cards(ctx)}</div>
<div class="cols">
  <div class="panel">
    <h3>ปฏิทินปรับราคา {THAI_MONTHS[ctx['today'].month - 1]} {ctx['today'].year + 543}</h3>
    {render_calendar(ctx)}
  </div>
  <div class="panel">
    <h3>วันในสัปดาห์ที่มักปรับราคา</h3>
    {render_weekday_stats(ctx)}
    <p class="note">นับจากวันที่มีการเปลี่ยนราคา {html.escape(ctx['reference'])} ตั้งแต่ต้นปี</p>
  </div>
</div>
<div class="panel" style="margin-bottom:22px">
  <h3>ปัจจัยตลาดโลก</h3>
  <div class="mkt">{''.join(market_boxes)}</div>
</div>
<div class="panel">
  <h3>เปลี่ยนแปลงล่าสุด</h3>
  <table class="list">
    <thead><tr><th>วันเวลา</th><th>ผลิตภัณฑ์</th><th>ราคา</th><th>เปลี่ยน</th></tr></thead>
    <tbody>{render_recent(ctx)}</tbody>
  </table>
</div>
<footer>
  แหล่งข้อมูล: <a href="https://www.pttor.com/th/oil_price">ราคาขายปลีกภูมิภาค ปตท.OR</a> (ทางการ) ·
  <a href="https://finance.yahoo.com/quote/BZ=F">Brent</a> ·
  <a href="https://api.frankfurter.app/">USD/THB (อ้างอิง ECB)</a><br>
  ราคาของ OR ไม่รวมภาษีบำรุงท้องที่ (ถ้ามี) · ราคาแต่ละอำเภอต่างกันตามค่าขนส่ง ·
  ตรวจสอบราคาหน้าสถานีก่อนเติมน้ำมันทุกครั้ง<br>
  สร้างอัตโนมัติเมื่อ {ctx['now']:%d/%m/%Y %H:%M} น.
</footer>
</div>
</body>
</html>
"""


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

    DASHBOARD_PATH.write_text(render_html(ctx), encoding="utf-8")

    print(f"รายงาน: {report_path.relative_to(ROOT)}")
    print(f"แดชบอร์ด: {DASHBOARD_PATH.relative_to(ROOT)}")
    send_telegram(ctx, config, local)
    return 0


if __name__ == "__main__":
    sys.exit(main())
