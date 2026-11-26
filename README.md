# ราคาน้ำมันรายวัน · อ.เมืองอำนาจเจริญ

ระบบสรุปราคาน้ำมันขายปลีกรายวัน พร้อมบอกว่ามีการปรับราคา (ขึ้น/ลง) วันไหน
อ้างอิงราคาของ **ปตท.OR** เฉพาะอำเภอที่อยู่จริง ไม่ใช่ราคากลางกรุงเทพฯ

## แหล่งข้อมูล (ตรวจสอบได้)

| ข้อมูล | แหล่ง | ความน่าเชื่อถือ |
|---|---|---|
| ราคาขายปลีก ปตท. | [pttor.com/th/oil_price](https://www.pttor.com/th/oil_price) — ใช้ endpoint เดียวกับหน้าเว็บ (`fetch_regional_oil_prices`) | **ทางการ** (บริษัท ปตท.OR จำกัด มหาชน) |
| ข่าวประกาศล่วงหน้า | Google News RSS (`ราคาน้ำมันพรุ่งนี้`) กรองเฉพาะสำนักข่าวไทย | ข่าวประชาสัมพันธ์ — ใช้ยืนยันซ้ำกับระบบ OR |
| Brent crude | Yahoo Finance `BZ=F` | ตลาดล่วงหน้า NYMEX |
| USD/THB | [api.frankfurter.app](https://api.frankfurter.app/) | อ้างอิงอัตราของ ECB |

ทุกครั้งที่ดึงข้อมูลจะบันทึกแหล่ง + จำนวนแถวลงตาราง `fetch_log` ในฐานข้อมูล

## ข้อเท็จจริงเรื่อง "วันไหนราคาจะขึ้น"

ไม่มีการประกาศล่วงหน้าหลายวัน ปตท.OR ประกาศช่วง **16:00–18:00 น.** มีผล **05:00 น. ของวันถัดไป**
(บางครั้งปรับกลางวัน เช่น 13:00 น.) ตารางราคาบนเว็บ OR จะอัปเดต **ตอน 05:00 ของวันที่มีผล** เท่านั้น
ระบบจึงรายงาน 4 ชั้น:

1. **ประกาศล่าสุด** — ถ้ามีแถวราคาที่มีผลพรุ่งนี้ จะแจ้งทันที
2. **ข่าวประกาศล่วงหน้า** — พาดหัวจากสำนักข่าวไทย (Google News) เช่น "ราคาน้ำมันพรุ่งนี้ 27 พ.ย. ดีเซลปรับขึ้น 50 สตางค์" ใช้ตัดสินใจเติมน้ำมันคืนนี้
3. **ปฏิทินย้อนหลัง** — วันที่ขึ้น/ลงในเดือนนี้ + สถิติวันในสัปดาห์
4. **แรงกดดันตลาด** — Brent + ค่าเงิน 5 วัน (เป็นตัวชี้ทิศทาง ไม่ใช่คำพยากรณ์)

## โครงสร้าง

```
config.json              ตั้งค่าจังหวัด/อำเภอ/ผลิตภัณฑ์
config.local.json        Telegram token (สร้างอัตโนมัติ, ไม่ขึ้น git)
scripts/fetch.py         ดึงราคา + ตลาดโลก -> data/prices.db
scripts/report.py        สร้าง reports/*.md, dashboard.html, ส่ง Telegram
scripts/theme.py         ชั้น view: HTML + CSS ของแดชบอร์ด
scripts/common.py        ตัวจัดรูปแบบวันที่/ตัวเลขภาษาไทย (ใช้ร่วมกัน)
scripts/serve.py         เปิด dashboard ให้มือถือดูในวง LAN
scripts/telegram_setup.py  ตั้งค่า Telegram อัตโนมัติ
run.bat                  รันทั้งชุด (ใช้โดย Task Scheduler)
setup_schedule.ps1       ตั้ง/ลบ/ตรวจงานเวลา 06:00 และ 17:30
```

## ใช้งาน

```powershell
python scripts\fetch.py          # ดึงข้อมูล (ครั้งแรกดึงย้อนหลังทั้งปี)
python scripts\report.py         # สร้างรายงาน + แดชบอร์ด
start dashboard.html             # เปิดดู
```

ตั้งเวลาให้รันเองทุกวัน:

```powershell
powershell -ExecutionPolicy Bypass -File .\setup_schedule.ps1
powershell -ExecutionPolicy Bypass -File .\setup_schedule.ps1 -Status
powershell -ExecutionPolicy Bypass -File .\setup_schedule.ps1 -Remove
```

## เปิด Telegram (ทำครั้งเดียว)

1. คุยกับ **@BotFather** → `/newbot` → คัดลอก token
2. ส่งข้อความ `/start` ไปที่บอทที่สร้าง
3. `python scripts\telegram_setup.py --token "123456:AA..."`

ระบบจะส่งสรุปให้ทุกวัน 06:00 (ราคาที่ใช้จริงวันนี้) และ 17:30 (ประกาศของพรุ่งนี้)

## แดชบอร์ด

`dashboard.html` เป็นไฟล์เดียวจบ (CSS ฝังใน) เปิดด้วย `file://` ได้ ไม่ต้องต่อเน็ต
ยกเว้นฟอนต์ IBM Plex Sans Thai จาก Google Fonts (ถ้าออฟไลน์จะ fallback เป็น Leelawadee UI)

หลักการออกแบบที่ใช้ตัดสินใจทุกจุด:

- **ledger + station price board** — กระดาษอุ่น อ่านกลางแดดได้ ตัวเลขเป็นพระเอก ไม่มี gradient/เงา/glass
- **accent เดียว (rust)** ใช้เฉพาะลิงก์ โฟกัส และกรอบ "วันนี้" — ไม่ใช้ประดับ
- **แดง/เขียวใช้เฉพาะทิศทางราคา** และมีลูกศร ▲▼ กำกับเสมอ (ไม่พึ่งสีอย่างเดียว)
- เส้นคั่นเป็น hairline 1px ไม่มี zebra stripe, ตัวเลข tabular-nums, ตารางยุบเป็นการ์ดบนมือถือ
- รองรับ dark mode ตามระบบ, `prefers-reduced-motion`, skip link, `:focus-visible`
- คอนทราสต์ทุกคู่ที่ใช้จริง ≥ 4.5:1 (ข้อความหลัก 16.7:1)

ตรวจภาพด้วย Edge headless:

```powershell
& "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe" --headless=new --disable-gpu `
  --screenshot="$PWD\design\shot.png" --window-size=1280,2800 "file:///$($PWD.Path.Replace('\','/'))/dashboard.html"
```

หมายเหตุ: Chromium จำกัดความกว้างหน้าต่างขั้นต่ำ ~500px ถ้าต้องการภาพมือถือ 390px
ให้ใช้ `design/frame-mobile.html` (iframe 390px) แล้วแคปเจอร์ที่ความกว้าง 500px

## ข้อจำกัดที่ควรรู้

- ราคาแต่ละอำเภอต่างกันจริง (ค่าขนส่ง) — ถ้าย้ายบ้านให้แก้ `config.json`
- ราคา OR ไม่รวมภาษีบำรุงท้องที่ (ถ้ามี)
- ข้อมูลย้อนหลังของ OR ก่อน มี.ค. 2569 มีไม่ครบ สถิติจึงเริ่มตั้งแต่ต้นปีตามข้อมูลที่มี
- ผลิตภัณฑ์ที่เลิกจำหน่ายจะค้างราคาเดิม — แดชบอร์ดจะแสดง "ไม่ปรับมา N วัน" ให้เห็น
- ระบบดึงข้อมูล 2 ครั้ง/วัน (และ 1 ครั้ง/เดือน สำหรับเดือนก่อน) เพื่อไม่รบกวนเซิร์ฟเวอร์ต้นทาง
