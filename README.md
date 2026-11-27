# ราคาน้ำมันรายวัน · อ.เมืองอำนาจเจริญ

ระบบสรุปราคาน้ำมันขายปลีกรายวัน พร้อมบอกว่ามีการปรับราคา (ขึ้น/ลง) วันไหน
อ้างอิงราคาของ **ปตท.OR** เฉพาะอำเภอที่อยู่จริง ไม่ใช่ราคากลางกรุงเทพฯ

**หน้าเว็บจริง:** https://warutphongkt.github.io/fuel-price/

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
scripts/fetch.py         ดึงราคา + ตลาดโลก + ข่าว -> data/prices.db
scripts/report.py        สร้าง reports/*.md, dashboard.html, ส่ง Telegram
scripts/theme.py         ชั้น view: HTML + CSS ของแดชบอร์ด
scripts/snapshot.py      สำรอง/กู้ประวัติราคาเป็น data/history.json
scripts/common.py        ตัวจัดรูปแบบวันที่/ตัวเลขภาษาไทย (ใช้ร่วมกัน)
scripts/serve.py         เปิด dashboard ให้มือถือดูในวง LAN
scripts/telegram_setup.py  ตั้งค่า Telegram อัตโนมัติ
.github/workflows/update.yml  อัปเดตหน้าเว็บอัตโนมัติบน GitHub (24 ชม.)
run.bat                  รันทั้งชุด (ใช้โดย Task Scheduler)
publish.bat              push dashboard.html + index.html + reports + history ขึ้น git
setup_schedule.ps1       ตั้ง/ลบ/ตรวจงานเวลา 06:00 และ 17:30
```

ไฟล์ที่ generate: `dashboard.html`, `index.html` (สำเนาสำหรับ static hosting), `reports/*.md`

`data/history.json` คือสำเนาประวัติราคาแบบข้อความล้วน (ไม่ใช่ SQLite) ใช้กู้ฐานข้อมูล
บนเครื่องใหม่หรือบน GitHub Actions ที่ดิสก์ไม่คงอยู่ระหว่างรอบ — `data/prices.db` ยังถูก ignore

## ใช้งาน

```powershell
python scripts\fetch.py          # ดึงข้อมูล (ครั้งแรกดึงย้อนหลังทั้งปี)
python scripts\report.py         # สร้างรายงาน + แดชบอร์ด
start dashboard.html             # เปิดดู
```

ย้ายเครื่อง / ตั้ง repo ใหม่ ให้กู้ประวัติก่อนดึงข้อมูล:

```powershell
python scripts\snapshot.py import data\history.json
python scripts\snapshot.py export data\history.json   # สำรองล่าสุด
```

หรือรันทั้งหมดในครั้งเดียวด้วย `run.bat` (fetch → report → export snapshot → publish)

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

## ให้ผู้อื่นดู (เลือกตามสถานการณ์)

### 1) ในบ้าน / วง Wi-Fi เดียวกัน — ง่ายสุด ไม่ต้องสมัครอะไร

```powershell
python scripts\serve.py            # พอร์ต 8765
```

เปิดให้คนอื่นที่ต่อ Wi-Fi เดียวกัน (ไม่ใช่ 4G) ที่ `http://<IP-เครื่องนี้>:8765/`
IP ดูได้จากข้อความที่สคริปต์พิมพ์ออกมา หรือ `ipconfig`

- ครั้งแรก Windows จะถาม firewall → ติ๊ก **Private networks** แล้ว Allow
- เครื่องนี้ต้องเปิดอยู่ และต้องไม่หลับ (ตั้ง Power & sleep = Never)
- ข้อดี: ข้อมูลสดทุกครั้งที่รีเฟรช · ข้อเสีย: ใช้ได้เฉพาะในบ้าน

### 2) ส่งไฟล์เดียว — เร็วสุด ใช้ได้ทุกที่

แนบ `dashboard.html` ทาง LINE/อีเมล ผู้รับเปิดในเบราว์เซอร์มือถือได้เลย
เพราะ CSS และข้อมูลฝังอยู่ในไฟล์เดียว (ฟอนต์โหลดจาก Google Fonts ถ้าออฟไลน์จะใช้ฟอนต์ในเครื่องแทน)

- ข้อดี: ไม่ต้องมีเซิร์ฟเวอร์ · ข้อเสีย: เป็นภาพนิ่ง ณ ตอนที่สร้าง ต้องส่งไฟล์ใหม่ทุกครั้ง

### 3) เว็บสาธารณะฟรี (GitHub Pages) + อัปเดตอัตโนมัติ 24 ชั่วโมง

ทำครั้งเดียว:

1. สร้าง repository แบบ public (เช่น `fuel-price`) แล้ว push โค้ดขึ้นไป
2. ไปที่ **Settings → Pages → Deploy from a branch → main / (root)**
3. เปิด `https://<ชื่อผู้ใช้>.github.io/fuel-price/`

`report.py` เขียนทั้ง `dashboard.html` และ `index.html` (เนื้อหาเดียวกัน) เพื่อให้ URL รากเปิดได้เลย

**อัปเดตเองจากเครื่อง (ไม่ต้องมี Actions):** `run.bat` เรียก `publish.bat` ให้อยู่แล้ว
ซึ่ง commit `dashboard.html` + `index.html` + `reports/` + `data/history.json` แล้ว push
(ถ้ายังไม่มี remote/upstream จะข้ามเอง ไม่ทำให้ scheduled task ล้ม)

**หรือให้ GitHub อัปเดตให้ตลอด 24 ชม. แม้คอมที่บ้านปิด:**
workflow `.github/workflows/update.yml` ตั้งเวลาไว้ 7 รอบ/วัน (เวลาไทย)
05:00 · 06:00 · 15:30 · 16:45 · 17:30 · 18:30 · 21:00
โดยกู้ประวัติจาก `data/history.json` → ดึงราคา/ข่าว → สร้างหน้าเว็บ → commit + push กลับเข้า `main`
เปิดใช้เพิ่มแค่:

1. **Settings → Secrets and variables → Actions → New repository secret** (ถ้าต้องการ Telegram)
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
2. แท็บ **Actions → Update fuel price dashboard → Run workflow** เพื่อทดสอบรอบแรก

ถ้าไม่ใส่ secret ระบบยังอัปเดตเว็บปกติ แค่ไม่ส่ง Telegram
(ปุ่ม `workflow_dispatch` มีไว้กดรันมือได้ตลอด)

- ข้อดี: ใครมีลิงก์ก็เปิดได้ ไม่ต้องเปิดคอม · ข้อเสีย: หน้าเว็บเป็นข้อมูลรอบล่าสุดที่ push ขึ้นไป
- ข้อควรรู้: หน้าเว็บแสดงชื่ออำเภอ/จังหวัด ถ้าไม่อยากให้คนนอกรู้ ให้แก้ `config.json` เป็นระดับจังหวัด

### 4) ให้คนนอกดูชั่วคราว โดยไม่ต้องมี GitHub

```powershell
winget install --id Cloudflare.cloudflared
python scripts\serve.py
cloudflared tunnel --url http://localhost:8765
```

จะได้ URL แบบ `https://xxx.trycloudflare.com` ใช้ได้จนกว่าจะปิดหน้าต่าง — เหมาะกับ "ส่งให้เพื่อนดูเดี๋ยวนี้"

## แดชบอร์ด

`dashboard.html` เป็นไฟล์เดียวจบ (CSS ฝังใน) เปิดด้วย `file://` ได้ ไม่ต้องต่อเน็ต
ยกเว้นฟอนต์ IBM Plex Sans Thai จาก Google Fonts (ถ้าออฟไลน์จะ fallback เป็น Leelawadee UI)

ส่วนบนสุดของหน้าเป็น **การ์ดคำแนะนำ** ที่ตอบว่า "ควรเติมคืนนี้หรือรอพรุ่งนี้" โดยเรียงลำดับความน่าเชื่อถือ:

1. ประกาศจริงของ ปตท.OR ที่มีผลพรุ่งนี้ (ขึ้น → เติมคืนนี้, ลง → รอพรุ่งนี้)
2. ข่าวล่วงหน้าจากสำนักข่าวไทยที่เชื่อถือได้ภายใน 24 ชม. (ข่าวต่างประเทศถูกกรองออก)
3. ช่วงเวลาเฝ้าระวัง 16:00–18:30 น. ที่ OR มักประกาศราคา
4. แรงกดดันจาก Brent + USD/THB
5. ถ้าไม่มีสัญญาณใด ๆ จะบอกว่าราคาทรงตัว เติมได้ตามปกติ

ถ้าระบบดึงข้อมูลไม่สำเร็จติดกันเกิน 18 ชั่วโมง จะมีแถบเตือน "ข้อมูลอาจเก่า" ด้านบนสุด
และยังมี `last_fetch_at` แยกจากเวลาที่ราคามีผลจริง เพื่อไม่ให้เข้าใจผิดว่าข้อมูลสด

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
- ระบบดึงข้อมูล 7 รอบ/วันบน GitHub Actions (หรือ 2 รอบ/วันถ้าใช้ Task Scheduler ในเครื่อง)
  และ 1 ครั้ง/เดือนสำหรับเดือนก่อน เพื่อไม่รบกวนเซิร์ฟเวอร์ต้นทาง
