#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ชั้น view: สร้าง dashboard.html จาก ctx ที่ report.py เตรียมไว้

แนวทางดีไซน์ (บันทึกไว้เป็นสัญญา):
  - "ledger + station price board": กระดาษอุ่น อ่านกลางแดดได้ ตัวเลขเป็นพระเอก
  - accent เดียว (rust) ใช้เฉพาะลิงก์/โฟกัส/วันที่ปัจจุบัน
  - แดง/เขียวใช้เฉพาะ "ทิศทางราคา" และมีลูกศรกำกับเสมอ (ไม่พึ่งสีอย่างเดียว)
  - ไม่มี gradient, เงา, glass, emoji ใน chrome
  - radius: การ์ด 12 / ชิป 8 / pill 999
"""

import html
from datetime import date, timedelta

from common import (
    THAI_DAYS,
    THAI_DAYS_SHORT,
    THAI_MONTHS,
    delta_arrow,
    delta_class,
    delta_word,
    fmt_delta,
    fmt_price,
    thai_date,
)

CSS = """
:root{
  --paper:#faf8f4; --surface:#ffffff; --ink:#16181d; --muted:#6b6357;
  --line:#e4ded4; --line-strong:#d6cdbf;
  --accent:#b4441a; --accent-soft:#f6e7df;
  --up:#b42318; --up-bg:#fbeae8;
  --down:#067647; --down-bg:#e6f4ec;
  --flat:#6b6357; --flat-bg:#efebe3;
  --r-card:12px; --r-chip:8px;
  --maxw:1040px;
  color-scheme:light;
}
@media (prefers-color-scheme: dark){
  :root{
    --paper:#14120f; --surface:#1b1815; --ink:#f2ede4; --muted:#a79e8f;
    --line:#2e2a24; --line-strong:#3d372f;
    --accent:#e8834f; --accent-soft:#2a1d15;
    --up:#f97066; --up-bg:#2b1a18;
    --down:#47cd89; --down-bg:#12251b;
    --flat:#a79e8f; --flat-bg:#241f1a;
    color-scheme:dark;
  }
}
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
@media (prefers-reduced-motion: reduce){
  html{scroll-behavior:auto}
  *{transition:none !important;animation:none !important}
}
body{
  margin:0;background:var(--paper);color:var(--ink);
  font-family:"IBM Plex Sans Thai","Leelawadee UI","Noto Sans Thai",Tahoma,system-ui,sans-serif;
  font-size:15px;line-height:1.6;
  -webkit-font-smoothing:antialiased;
  font-variant-numeric:tabular-nums;
}
::selection{background:var(--accent-soft);color:var(--ink)}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:3px;
  touch-action:manipulation;-webkit-tap-highlight-color:var(--accent-soft)}
a:hover{text-decoration-thickness:2px}
a:focus-visible,button:focus-visible{outline:2px solid var(--accent);outline-offset:3px;border-radius:4px}
h2{text-wrap:balance}
.sr-only{
  position:absolute;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;
  clip:rect(0 0 0 0);white-space:nowrap;border:0;
}
[id]{scroll-margin-top:28px}
.skip{
  position:absolute;left:16px;top:-64px;z-index:10;background:var(--ink);color:var(--paper);
  padding:8px 14px;border-radius:var(--r-chip);text-decoration:none;transition:top .15s ease-out;
}
.skip:focus{top:12px}

.wrap{max-width:var(--maxw);margin:0 auto;padding:32px 20px 56px}
.masthead{
  display:flex;flex-wrap:wrap;gap:16px 24px;align-items:flex-end;justify-content:space-between;
  padding-bottom:20px;border-bottom:1px solid var(--line-strong);margin-bottom:24px;
}
.kicker{
  margin:0 0 6px;font-size:11.5px;font-weight:600;letter-spacing:.09em;color:var(--muted);
}
h1{
  margin:0;font-size:clamp(1.5rem,3.4vw,2rem);line-height:1.25;font-weight:700;
  letter-spacing:-.015em;text-wrap:balance;
}
h1 .place{color:var(--muted);font-weight:500}
.dateline{margin:6px 0 0;font-size:13px;color:var(--muted)}
.pills{display:flex;flex-wrap:wrap;gap:8px;align-items:center}
.pill{
  display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);
  border-radius:999px;padding:4px 11px;font-size:12px;color:var(--muted);
}

.hero{display:grid;grid-template-columns:1.65fr 1fr;gap:18px;margin-bottom:18px}
@media (max-width:820px){.hero{grid-template-columns:1fr}}
.card{
  background:var(--surface);border:1px solid var(--line);border-radius:var(--r-card);
  padding:20px 22px;
}
.card + .card{margin-top:0}
.hero-main .eyebrow{
  margin:0;font-size:12.5px;font-weight:600;letter-spacing:.04em;color:var(--muted);
}
.hero-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:2px 0 0}
.hero-head h2{margin:0;font-size:1.05rem;font-weight:600}
.hero-price{display:flex;align-items:baseline;gap:10px;margin:6px 0 2px}
.hero-price .num{
  font-size:clamp(2.9rem,7vw,4rem);line-height:1.02;font-weight:700;letter-spacing:-.035em;
}
.hero-price .unit{font-size:13px;color:var(--muted)}
.hero-note{margin:4px 0 0;font-size:12.5px;color:var(--muted)}
.hero-chart{margin-top:14px;border-top:1px solid var(--line);padding-top:12px}
.hero-chart .cap{display:flex;justify-content:space-between;font-size:11.5px;color:var(--muted);margin-bottom:4px}
.spark{display:block;width:100%;height:88px;color:var(--muted)}
.spark-dot{fill:var(--ink)}

.chip{
  display:inline-flex;align-items:center;gap:4px;border-radius:var(--r-chip);
  padding:2px 8px;font-size:12.5px;font-weight:600;font-variant-numeric:tabular-nums;
  white-space:nowrap;
}
.chip.up{background:var(--up-bg);color:var(--up)}
.chip.down{background:var(--down-bg);color:var(--down)}
.chip.flat{background:var(--flat-bg);color:var(--flat)}

.tomorrow h2{margin:0;font-size:.95rem;font-weight:600;color:var(--muted)}
.tomorrow .status{margin:6px 0 0;font-size:1.3rem;font-weight:700;letter-spacing:-.01em}
.tomorrow .note{margin:8px 0 0;font-size:12.5px;color:var(--muted)}
.tomorrow .list{margin:8px 0 0;padding:0;list-style:none;font-size:13px}
.tomorrow .list li{display:flex;justify-content:space-between;gap:12px;padding:3px 0}
.tomorrow .more{margin:12px 0 0;font-size:13px}

.panel{
  background:var(--surface);border:1px solid var(--line);border-radius:var(--r-card);
  padding:18px 20px;margin-bottom:18px;
}
.panel-head{
  display:flex;flex-wrap:wrap;gap:4px 12px;align-items:baseline;justify-content:space-between;
  margin-bottom:10px;
}
.panel-head h2{margin:0;font-size:1rem;font-weight:600}
.hint{margin:0;font-size:12px;color:var(--muted)}

table.prices,table.recent{width:100%;border-collapse:collapse;font-size:13.5px}
table.prices th,table.recent th{
  text-align:left;font-size:11.5px;font-weight:600;color:var(--muted);
  padding:0 6px 8px;border-bottom:1px solid var(--line-strong);white-space:nowrap;
}
table.prices td,table.recent td{padding:9px 6px;border-bottom:1px solid var(--line);vertical-align:middle}
table.prices tr:last-child td,table.recent tr:last-child td{border-bottom:none}
.num{text-align:right;font-variant-numeric:tabular-nums}
.c-name{font-weight:500}
.c-price{text-align:right;font-weight:600;white-space:nowrap}
.c-delta{text-align:right;white-space:nowrap}
.c-spark{width:132px;text-align:right}
.c-when{text-align:right;color:var(--muted);font-size:12.5px;white-space:nowrap}
.c-spark svg{display:block;width:120px;height:26px;margin-left:auto}
@media (max-width:720px){
  table.prices thead,table.recent thead{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0)}
  table.prices tr,table.recent tr{
    display:grid;grid-template-columns:minmax(0,1fr) auto;grid-template-areas:"name price" "when delta";
    gap:1px 12px;padding:11px 2px;border-bottom:1px solid var(--line);
  }
  table.prices tr:last-child,table.recent tr:last-child{border-bottom:none}
  table.prices td,table.recent td{padding:0;border:none}
  .c-name{grid-area:name}
  .c-price{grid-area:price;font-size:15px}
  .c-delta{grid-area:delta}
  .c-when{grid-area:when;text-align:left;font-size:12px}
  .c-spark{display:none}
}

.duo{display:grid;grid-template-columns:1.12fr .88fr;gap:18px}
@media (max-width:820px){.duo{grid-template-columns:1fr}}
.duo .panel{margin-bottom:18px}

table.cal{width:100%;border-collapse:separate;border-spacing:3px;table-layout:fixed}
table.cal th{font-size:11px;font-weight:600;color:var(--muted);padding:0 0 4px;text-align:center}
table.cal td{
  height:42px;border:1px solid var(--line);border-radius:var(--r-chip);
  text-align:center;vertical-align:middle;font-size:12.5px;position:relative;
}
table.cal td.empty{border-color:transparent}
table.cal td.up{background:var(--up-bg);border-color:var(--up-bg)}
table.cal td.down{background:var(--down-bg);border-color:var(--down-bg)}
table.cal td.mixed{background:var(--flat-bg);border-color:var(--flat-bg)}
table.cal td.today{outline:2px solid var(--accent);outline-offset:-2px;font-weight:700}
.cal-num{display:block;line-height:1.1}
.cal-mark{display:block;font-size:9px;line-height:1;letter-spacing:1px;color:var(--muted)}
td.up .cal-mark{color:var(--up)}
td.down .cal-mark{color:var(--down)}
.legend{margin:10px 0 0;font-size:11.5px;color:var(--muted)}

.wd{display:grid;grid-template-columns:auto 1fr auto;gap:10px;align-items:center;padding:4px 0;font-size:13px}
.wd .bar{display:flex;height:6px;border-radius:999px;overflow:hidden;background:var(--flat-bg)}
.wd .bar i{display:block;height:100%}
.wd .bar .u{background:var(--up)}
.wd .bar .d{background:var(--down)}
.wd .count{font-size:12px;color:var(--muted);white-space:nowrap;text-align:right}
.wd .count .u{color:var(--up)}
.wd .count .d{color:var(--down)}
.summary{
  margin:14px 0 0;padding-top:11px;border-top:1px solid var(--line);
  font-size:12.5px;font-weight:600;color:var(--ink);line-height:1.7;
}
.summary span{display:block}

.news{list-style:none;margin:0;padding:0}
.news li{padding:10px 0;border-bottom:1px solid var(--line)}
.news li:last-child{border-bottom:none;padding-bottom:0}
.news a{color:var(--ink);text-decoration:underline;text-decoration-color:var(--line-strong);
  text-decoration-thickness:1px;text-underline-offset:3px;font-weight:500;font-size:14px}
.news a:hover{text-decoration-color:var(--accent);text-decoration-thickness:2px}
.news .meta{margin:3px 0 0;font-size:11.5px;color:var(--muted)}
.news .tag{
  display:inline-block;border:1px solid var(--accent);color:var(--accent);
  border-radius:999px;padding:0 8px;font-size:10.5px;font-weight:600;margin-left:6px;
  vertical-align:1px;
}

.mkt{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:0}
.mkt .box{padding:0 18px;border-left:1px solid var(--line)}
.mkt .box:first-child{padding-left:0;border-left:none}
@media (max-width:640px){
  .mkt{grid-template-columns:1fr;gap:14px}
  .mkt .box{padding:0;border-left:none;border-top:1px solid var(--line);padding-top:12px}
  .mkt .box:first-child{border-top:none;padding-top:0}
}
.mkt .k{margin:0;font-size:11.5px;color:var(--muted)}
.mkt .v{display:flex;align-items:baseline;gap:8px;margin:3px 0 0;font-size:1.35rem;font-weight:700;letter-spacing:-.02em}
.mkt .sub{margin:2px 0 0;font-size:11.5px;color:var(--muted)}

footer{
  margin-top:28px;padding-top:16px;border-top:1px solid var(--line);
  font-size:12px;color:var(--muted);line-height:1.7;
}
footer p{margin:0 0 4px}
@media print{
  .skip,.pills{display:none}
  body{background:#fff;color:#000}
  .card,.panel{border-color:#ccc}
}
"""


# ---------------------------------------------------------------- atoms
def chip(delta, label=None):
    cls = delta_class(delta)
    if label is not None:
        return f'<span class="chip {cls}">{html.escape(label)}</span>'
    if cls == "flat":
        return '<span class="chip flat">คงที่<span class="sr-only"> ไม่เปลี่ยนแปลง</span></span>'
    word = "เพิ่มขึ้น" if delta > 0 else "ลดลง"
    visible = f'<span aria-hidden="true">{delta_arrow(delta)} {abs(delta):.2f}</span>'
    sr = f'<span class="sr-only">{word} {abs(delta):.2f} บาท</span>'
    return f'<span class="chip {cls}">{visible}{sr}</span>'


def sparkline(values, height=88, width=560, stroke_width=2):
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
    color = "currentColor"
    poly = " ".join(points)
    last_x, last_y = points[-1].split(",")
    return (
        f'<svg class="spark" viewBox="0 0 {width} {height}" preserveAspectRatio="none" '
        f'aria-hidden="true" focusable="false">'
        f'<polyline points="{poly}" fill="none" stroke="{color}" stroke-width="{stroke_width}" '
        f'vector-effect="non-scaling-stroke" stroke-linejoin="round" stroke-linecap="round"/>'
        f'<circle class="spark-dot" cx="{last_x}" cy="{last_y}" r="2.6"/>'
        "</svg>"
    )


# ---------------------------------------------------------------- sections
def render_hero(ctx):
    reference = next(
        (card for card in ctx["cards"] if card["product"] == ctx["reference"]),
        ctx["cards"][0],
    )
    values = [value for _, value in reference["history"]]
    low = min(values) if values else reference["price"]
    high = max(values) if values else reference["price"]
    effective = f"{thai_date(reference['delta_at'], short=True)} {reference['delta_at']:%H:%M} น."

    if ctx["tomorrow_events"]:
        ups = [e for e in ctx["tomorrow_events"] if e["delta"] > 0]
        downs = [e for e in ctx["tomorrow_events"] if e["delta"] < 0]
        if ups and downs:
            status = "ปรับขึ้นและลง"
        elif ups:
            status = "ปรับขึ้น"
        else:
            status = "ปรับลง"
        items = "".join(
            f"<li><span>{html.escape(e['product'])}</span>{chip(e['delta'])}</li>"
            for e in sorted(ctx["tomorrow_events"], key=lambda e: -abs(e["delta"]))[:4]
        )
        aside_body = f'<ul class="list">{items}</ul>'
        note = "ประกาศโดย ปตท.OR · มีผล 05:00 น."
    else:
        status = "ยังไม่ประกาศ"
        note = "ปตท.OR ประกาศช่วง 16:00–18:00 น. มีผล 05:00 น. ของวันถัดไป"
        if ctx["today_events"]:
            today_items = " · ".join(
                f"{e['product']} {fmt_delta(e['delta'])}"
                for e in sorted(ctx["today_events"], key=lambda e: -abs(e["delta"]))[:3]
            )
            aside_body = f'<p class="note">วันนี้ปรับแล้ว: {html.escape(today_items)}</p>'
        else:
            aside_body = ""

    return f"""
<section class="hero" aria-label="ราคาหลักและประกาศพรุ่งนี้">
  <div class="card hero-main">
    <p class="eyebrow">ราคาอ้างอิงหลัก</p>
    <div class="hero-head">
      <h2 id="hero-title">{html.escape(reference['product'])}</h2>
      {chip(reference['delta'])}
    </div>
    <p class="hero-price">
      <span class="num">{fmt_price(reference['price'])}</span>
      <span class="unit">บาท/ลิตร</span>
    </p>
    <p class="hero-note">มีผล {effective} · {delta_word(reference['delta'])}</p>
    <div class="hero-chart">
      <div class="cap"><span>แนวโน้ม 120 วัน</span><span>{low:,.2f} – {high:,.2f}</span></div>
      {sparkline(values)}
    </div>
  </div>
  <aside class="card tomorrow" aria-labelledby="tomorrow-title">
    <h2 id="tomorrow-title">พรุ่งนี้ · {thai_date(ctx['tomorrow'], short=True)}</h2>
    <p class="status">{status}</p>
    <p class="note">{note}</p>
    {aside_body}
    <p class="more"><a href="#news">ดูข่าวประกาศล่าสุด</a></p>
  </aside>
</section>
"""


def render_prices(ctx):
    rows = []
    for card in ctx["cards"]:
        values = [value for _, value in card["history"]]
        spark = sparkline(values, height=26, width=120, stroke_width=1.6) if len(values) > 1 else ""
        when = f"{thai_date(card['delta_at'], short=True)} {card['delta_at']:%H:%M}"
        stale_days = (ctx["snapshot_at"] - card["delta_at"]).days
        stale = f'<span class="sr-only">ไม่มีการปรับมา {stale_days} วัน</span>' if stale_days > 45 else ""
        rows.append(
            "<tr>"
            f'<td class="c-name">{html.escape(card["product"])}</td>'
            f'<td class="c-price">{fmt_price(card["price"])}</td>'
            f'<td class="c-delta">{chip(card["delta"])}</td>'
            f'<td class="c-spark" aria-hidden="true">{spark}</td>'
            f'<td class="c-when">{when}{stale}</td>'
            "</tr>"
        )
    return f"""
<section class="panel" aria-labelledby="prices-title">
  <div class="panel-head">
    <h2 id="prices-title">ราคาทั้งหมด</h2>
    <p class="hint">{len(ctx['cards'])} ผลิตภัณฑ์ · บาท/ลิตร · ราคา ณ {thai_date(ctx['snapshot_at'], short=True)} {ctx['snapshot_at']:%H:%M} น.</p>
  </div>
  <table class="prices">
    <caption class="sr-only">ราคาน้ำมันขายปลีก ปตท.OR ที่ {html.escape(ctx['district'])}</caption>
    <thead>
      <tr>
        <th scope="col">ผลิตภัณฑ์</th>
        <th scope="col" class="c-price">ราคา</th>
        <th scope="col" class="c-delta">เปลี่ยน</th>
        <th scope="col" class="c-spark">แนวโน้ม 120 วัน</th>
        <th scope="col" class="c-when">มีผลเมื่อ</th>
      </tr>
    </thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
  <p class="hint" style="margin-top:10px">ราคา ปตท.OR ไม่รวมภาษีบำรุงท้องที่ (ถ้ามี) · ราคาแต่ละอำเภอต่างกันตามค่าขนส่ง</p>
</section>
"""


def render_calendar(ctx):
    today = ctx["today"]
    first = today.replace(day=1)
    next_month = (first.replace(day=28) + timedelta(days=4)).replace(day=1)
    total_days = (next_month - timedelta(days=1)).day
    leading = first.weekday()

    cells = ["<tr>"]
    for _ in range(leading):
        cells.append('<td class="empty"></td>')
    column = leading
    for day in range(1, total_days + 1):
        info = ctx["calendar"].get(day)
        classes = []
        mark = ""
        sr = ""
        if info:
            classes.append(info["direction"])
            ups = sum(1 for e in info["events"] if e["delta"] > 0)
            downs = sum(1 for e in info["events"] if e["delta"] < 0)
            mark = ('<span class="cal-mark" aria-hidden="true">'
                    + ("▲" if ups and not downs else "▼" if downs and not ups else "▲▼")
                    + "</span>")
            parts = [f"ปรับขึ้น {ups} รายการ" if ups else "", f"ปรับลง {downs} รายการ" if downs else ""]
            sr = f'<span class="sr-only">{day} {thai_date(today.replace(day=day), short=True)} {" ".join(p for p in parts if p)}</span>'
        if day == today.day:
            classes.append("today")
        cells.append(
            f'<td class="{" ".join(classes)}">'
            f'<span class="cal-num">{day}</span>{mark}{sr}</td>'
        )
        column += 1
        if column % 7 == 0 and day != total_days:
            cells.append("</tr><tr>")
    while column % 7 != 0:
        cells.append('<td class="empty"></td>')
        column += 1
    cells.append("</tr>")

    head = "".join(f'<th scope="col">{name}</th>' for name in THAI_DAYS_SHORT)
    cal_count = len(ctx["calendar"])
    cal_note = f"ปรับ {cal_count} วัน" if cal_count else "ยังไม่ปรับ"
    return f"""
<section class="panel" aria-labelledby="cal-title">
  <div class="panel-head">
    <h2 id="cal-title">ปฏิทินปรับราคา</h2>
    <p class="hint">{THAI_MONTHS[today.month - 1]} {today.year + 543} · {cal_note}</p>
  </div>
  <table class="cal">
    <caption class="sr-only">วันที่มีการปรับราคาน้ำมันในเดือน{THAI_MONTHS[today.month - 1]} {today.year + 543}</caption>
    <thead><tr>{head}</tr></thead>
    <tbody>{''.join(cells)}</tbody>
  </table>
  <p class="legend">▲ ปรับขึ้น · ▼ ปรับลง · ▲▼ ขึ้นและลงวันเดียวกัน · กรอบสี = วันนี้</p>
</section>
"""


def render_weekday(ctx):
    stats = ctx["weekday_stats"]
    peak = max((s["up"] + s["down"] for s in stats.values()), default=0) or 1
    rows = []
    total_up = total_down = 0
    for index in range(7):
        stat = stats[index]
        total = stat["up"] + stat["down"]
        total_up += stat["up"]
        total_down += stat["down"]
        up_pct = stat["up"] / peak * 100
        down_pct = stat["down"] / peak * 100
        if total:
            counts = (
                f'<span aria-hidden="true"><span class="u">▲{stat["up"]}</span> '
                f'<span class="d">▼{stat["down"]}</span></span>'
                f'<span class="sr-only">ขึ้น {stat["up"]} ลง {stat["down"]}</span>'
            )
        else:
            counts = '<span aria-hidden="true">—</span><span class="sr-only">ไม่มีการปรับ</span>'
        rows.append(
            '<div class="wd">'
            f"<span>{THAI_DAYS[index]}</span>"
            f'<span class="bar" aria-hidden="true"><i class="u" style="width:{up_pct:.1f}%"></i>'
            f'<i class="d" style="width:{down_pct:.1f}%"></i></span>'
            f'<span class="count">{counts}</span>'
            "</div>"
        )
    total_days = total_up + total_down
    top_index = max(range(7), key=lambda i: stats[i]["up"] + stats[i]["down"])
    top_total = stats[top_index]["up"] + stats[top_index]["down"]
    quiet = [THAI_DAYS[i] for i in range(7) if stats[i]["up"] + stats[i]["down"] == 0]
    summary = f"<span>รวม {total_days} วัน · ขึ้น {total_up} · ลง {total_down}</span>"
    if top_total:
        second = f"บ่อยสุด {THAI_DAYS[top_index]} ({top_total} วัน)"
        if quiet:
            second += f" · ไม่เคยปรับวัน{', '.join(quiet)}"
        summary += f"<span>{second}</span>"
    return f"""
<section class="panel" aria-labelledby="wd-title">
  <div class="panel-head">
    <h2 id="wd-title">วันในสัปดาห์ที่มักปรับ</h2>
    <p class="hint">ตั้งแต่ต้นปี {ctx['today'].year + 543}</p>
  </div>
  {''.join(rows)}
  <p class="summary">{summary}</p>
  <p class="hint" style="margin-top:6px">นับเฉพาะวันที่มีการเปลี่ยนราคา {html.escape(ctx['reference'])}
    (หรือผลิตภัณฑ์อื่นหากตัวอ้างอิงไม่เปลี่ยน)</p>
</section>
"""


def render_news(ctx):
    if not ctx["news"]:
        return """
<section class="panel" id="news" aria-labelledby="news-title">
  <div class="panel-head"><h2 id="news-title">ข่าวประกาศล่วงหน้า</h2></div>
  <p class="hint">ยังไม่มีข่าวในช่วง 4 วันที่ผ่านมา — ระบบจะอัปเดตในรอบถัดไป</p>
</section>
"""
    items = []
    for item in ctx["news"][:5]:
        tag = '<span class="tag">ประกาศพรุ่งนี้</span>' if item["for_tomorrow"] else ""
        meta = f"{thai_date(item['published'], short=True)} {item['published']:%H:%M}"
        if item["source"]:
            meta += f" · {item['source']}"
        items.append(
            f'<li><a href="{html.escape(item["url"])}" target="_blank" rel="noopener">'
            f'{html.escape(item["title"])}<span class="sr-only"> (เปิดในแท็บใหม่)</span></a>{tag}'
            f'<p class="meta">{html.escape(meta)}</p></li>'
        )
    return f"""
<section class="panel" id="news" aria-labelledby="news-title">
  <div class="panel-head">
    <h2 id="news-title">ข่าวประกาศล่วงหน้า</h2>
    <p class="hint">Google News · สำนักข่าวไทย</p>
  </div>
  <ul class="news">{''.join(items)}</ul>
  <p class="hint" style="margin-top:12px">เป็นข่าวประชาสัมพันธ์ ยังไม่ใช่ข้อมูลยืนยันจากระบบ ปตท.OR —
    ตรวจราคาจริงอีกครั้งก่อนเติม</p>
</section>
"""


def render_market(ctx):
    boxes = []
    for item, label, unit in (
        (ctx["brent"], "Brent · 5 วันทำการ", "USD/บาร์เรล"),
        (ctx["fx"], "USD/THB · 5 วันทำการ", "บาท/ดอลลาร์"),
    ):
        if not item:
            continue
        pct_label = f"{item['pct']:+.2f}%"
        day = item["day"]
        if isinstance(day, str):
            try:
                day = date.fromisoformat(day)
            except ValueError:
                pass
        day_label = thai_date(day, short=True) if isinstance(day, date) else day
        boxes.append(
            '<div class="box">'
            f'<p class="k">{label}</p>'
            f'<p class="v">{item["value"]:,.2f}{chip(item["pct"], pct_label)}</p>'
            f'<p class="sub">{unit} · {day_label}</p>'
            "</div>"
        )
    boxes.append(
        '<div class="box">'
        '<p class="k">แรงกดดันราคา</p>'
        f'<p class="v">{html.escape(ctx["pressure_label"])}</p>'
        '<p class="sub">จาก Brent + ค่าเงิน · ไม่ใช่คำพยากรณ์</p>'
        "</div>"
    )
    return f"""
<section class="panel" aria-labelledby="mkt-title">
  <div class="panel-head">
    <h2 id="mkt-title">ปัจจัยตลาดโลก</h2>
    <p class="hint">เทียบ 5 วันทำการล่าสุด</p>
  </div>
  <div class="mkt">{''.join(boxes)}</div>
</section>
"""


def render_recent(ctx, limit=8):
    rows = []
    for event in sorted(ctx["events"], key=lambda e: e["at"], reverse=True)[:limit]:
        rows.append(
            "<tr>"
            f'<td class="c-when" style="text-align:left">{thai_date(event["at"], short=True)} {event["at"]:%H:%M}</td>'
            f'<td class="c-name">{html.escape(event["product"])}</td>'
            f'<td class="c-price">{fmt_price(event["price"])}</td>'
            f'<td class="c-delta">{chip(event["delta"])}</td>'
            "</tr>"
        )
    return f"""
<section class="panel" aria-labelledby="recent-title">
  <div class="panel-head">
    <h2 id="recent-title">เปลี่ยนแปลงล่าสุด</h2>
    <p class="hint">{len(ctx['events'])} ครั้งตั้งแต่ต้นปี</p>
  </div>
  <table class="recent">
    <caption class="sr-only">รายการปรับราคาล่าสุด</caption>
    <thead><tr>
      <th scope="col">วันเวลา</th>
      <th scope="col">ผลิตภัณฑ์</th>
      <th scope="col" class="c-price">ราคา</th>
      <th scope="col" class="c-delta">เปลี่ยน</th>
    </tr></thead>
    <tbody>{''.join(rows)}</tbody>
  </table>
</section>
"""


def render_html(ctx):
    snapshot = ctx["snapshot_at"]
    return f"""<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#faf8f4" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#14120f" media="(prefers-color-scheme: dark)">
<meta name="description" content="ราคาน้ำมันขายปลีกรายวัน {html.escape(ctx['district'])} จากข้อมูลทางการ ปตท.OR">
<title>ราคาน้ำมัน {html.escape(ctx['district'])} · {thai_date(ctx['today'], short=True)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans+Thai:wght@400;500;600;700&display=swap">
<style>{CSS}</style>
</head>
<body>
<a class="skip" href="#main">ข้ามไปที่เนื้อหา</a>
<div class="wrap">
  <header class="masthead">
    <div>
      <p class="kicker">ปตท.OR · ราคาขายปลีกภูมิภาค</p>
      <h1>ราคาน้ำมัน <span class="place">· {html.escape(ctx['district'])}</span></h1>
      <p class="dateline">{thai_date(ctx['today'])} · ราคา ณ {thai_date(snapshot, short=True)} {snapshot:%H:%M} น.</p>
    </div>
    <div class="pills">
      <span class="pill">จ.{html.escape(ctx['province'])}</span>
      <span class="pill">อัปเดต {ctx['now']:%H:%M} น.</span>
    </div>
  </header>

  <main id="main">
    {render_hero(ctx)}
    {render_prices(ctx)}
    <div class="duo">
      {render_calendar(ctx)}
      {render_weekday(ctx)}
    </div>
    {render_news(ctx)}
    {render_market(ctx)}
    {render_recent(ctx)}
  </main>

  <footer>
    <p>แหล่งข้อมูล: <a href="https://www.pttor.com/th/oil_price">ราคาขายปลีกภูมิภาค ปตท.OR</a> (ทางการ) ·
      <a href="https://finance.yahoo.com/quote/BZ=F">Brent</a> ·
      <a href="https://api.frankfurter.app/">USD/THB (อ้างอิง ECB)</a></p>
    <p>ราคา ปตท.OR ไม่รวมภาษีบำรุงท้องที่ (ถ้ามี) · ราคาแต่ละอำเภอต่างกันตามค่าขนส่ง ·
      ตรวจสอบราคาหน้าสถานีก่อนเติมน้ำมันทุกครั้ง</p>
    <p>สร้างอัตโนมัติเมื่อ {ctx['now']:%d/%m/%Y %H:%M} น. · ตัวเลขทั้งหมดเป็นข้อมูลจริงจากฐานข้อมูล ไม่ใช่ตัวอย่าง</p>
  </footer>
</div>
</body>
</html>
"""
