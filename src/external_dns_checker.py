#!/usr/bin/env python3
"""
Dış DNS Kontrol & Puanlama Aracı
Network internship portfolio adaptation (sanitized)

Kullanım:
  python dns_checker_v2.py --excel dis_dns.xlsx
  python dns_checker_v2.py --excel dis_dns.xlsx --timeout 10 --workers 20
"""

import requests
import socket
import time
import argparse
import concurrent.futures
from datetime import datetime

try:
    from bs4 import BeautifulSoup
    BS4 = True
except ImportError:
    BS4 = False

try:
    import openpyxl
    from openpyxl.styles import PatternFill, Font, Alignment
    from openpyxl.utils import get_column_letter
    XLSX = True
except ImportError:
    print("openpyxl yüklü değil: pip install openpyxl"); exit(1)

# ── Terminal renkleri ──────────────────────────────────────────────────────
G="\033[92m"; R="\033[91m"; Y="\033[93m"; B="\033[94m"
M="\033[95m"; C="\033[96m"; W="\033[97m"; D="\033[2m"; RST="\033[0m"

# ── Puanlama ───────────────────────────────────────────────────────────────
def puan_hesapla(http_code, response_ms, login, status):
    """
    Puanlama kriterleri:
      100 → 200 OK + hızlı (<500ms)
       85 → 200 OK ama yavaş (500ms–2000ms)
       70 → 200 OK ama çok yavaş (>2000ms)
       60 → 301/302 Yönlendirme
       40 → 403 Kısıtlı (sunucu cevap veriyor)
       20 → 404 / 5xx
        0 → DNS hatası / bağlantı yok / timeout
    Bonus +10 → login/şifre ekranı tespit edildi
    """
    if http_code is None:
        return 0

    if http_code == 200:
        if response_ms is None:    base = 85
        elif response_ms < 500:    base = 100
        elif response_ms < 2000:   base = 85
        else:                      base = 70
    elif http_code in (301, 302, 303, 307, 308):
        base = 60
    elif http_code == 403:
        base = 40
    elif http_code == 404:
        base = 20
    elif http_code == 401:
        base = 50  # Auth required — sunucu var
    elif http_code and http_code >= 500:
        base = 20
    else:
        base = 30

    bonus = 10 if login else 0
    return min(100, base + bonus)

def puan_etiketi(puan):
    if puan >= 90:  return "🟢 Mükemmel"
    if puan >= 70:  return "🟡 İyi"
    if puan >= 50:  return "🟠 Orta"
    if puan >= 20:  return "🔴 Zayıf"
    return              "⛔ Erişilemiyor"

# ── Login tespiti ──────────────────────────────────────────────────────────
LOGIN_KW = [
    "password","şifre","parola","login","giriş","sign in",
    "kullanıcı adı","username","log in","oturum","authenticate",
    "passwd","giris","sifre","kullanici"
]

def login_tespit(html):
    if not html: return False, ""
    hl = html.lower()
    if BS4:
        try:
            soup = BeautifulSoup(html, "html.parser")
            if soup.find_all("input", {"type": "password"}):
                return True, "Şifre kutusu var"
            forms = soup.find_all("form")
            kw_hit = [k for k in LOGIN_KW if k in hl]
            if forms and kw_hit:
                return True, f"Form + '{kw_hit[0]}'"
        except: pass
    if 'type="password"' in hl or "type='password'" in hl:
        return True, "Şifre kutusu var"
    kw_hit = [k for k in LOGIN_KW if k in hl]
    if len(kw_hit) >= 2:
        return True, f"Keyword: {kw_hit[0]}, {kw_hit[1]}"
    return False, ""

# ── DNS çözümleme ──────────────────────────────────────────────────────────
def dns_coz(url):
    host = url.replace("https://","").replace("http://","").split("/")[0].split(":")[0]
    try:
        ip = socket.gethostbyname(host)
        return True, ip
    except: return False, "DNS çözümlenemedi"

# ── Tek URL kontrolü ───────────────────────────────────────────────────────
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 Chrome/124 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.9",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8"
}

def url_kontrol(url, timeout=8):
    if not url or not str(url).strip():
        return {"url": url, "status": "BOŞ", "http_code": None,
                "ms": None, "ip": "", "login": False,
                "login_neden": "", "yonlendirme": "", "hata": "Boş URL",
                "puan": 0, "etiket": "⛔ Erişilemiyor"}

    url = str(url).strip()
    if not url.startswith(("http://","https://")):
        url = "http://" + url

    dns_ok, ip = dns_coz(url)
    if not dns_ok:
        return {"url": url, "status": "DNS Hatası", "http_code": None,
                "ms": None, "ip": "", "login": False,
                "login_neden": "", "yonlendirme": "", "hata": ip,
                "puan": 0, "etiket": "⛔ Erişilemiyor"}

    sonuc = {"url": url, "status": "", "http_code": None,
             "ms": None, "ip": ip, "login": False,
             "login_neden": "", "yonlendirme": "", "hata": ""}

    def dene(u):
        t0 = time.time()
        r = requests.get(u, timeout=timeout, headers=HEADERS,
                         verify=True, allow_redirects=True)
        return r, int((time.time()-t0)*1000)

    try:
        resp, ms = dene(url)
        sonuc["http_code"] = resp.status_code
        sonuc["ms"] = ms
        if resp.url != url:
            sonuc["yonlendirme"] = resp.url

        # Durum metni
        kod = resp.status_code
        if   kod == 200: sonuc["status"] = "Açık"
        elif kod in (301,302,303,307,308): sonuc["status"] = "Yönlendirme"
        elif kod == 401: sonuc["status"] = "Giriş Gerekli (401)"
        elif kod == 403: sonuc["status"] = "Kısıtlı (403)"
        elif kod == 404: sonuc["status"] = "Bulunamadı (404)"
        elif kod >= 500: sonuc["status"] = f"Sunucu Hatası ({kod})"
        else:            sonuc["status"] = f"HTTP {kod}"

        # Login tespiti
        if kod in (200,301,302,303,307,308,401):
            try:
                login, neden = login_tespit(resp.text[:60000])
                sonuc["login"] = login
                sonuc["login_neden"] = neden
            except: pass

    except requests.exceptions.SSLError:
        sonuc["status"] = "TLS Sertifika Hatası"
        sonuc["hata"] = "TLS doğrulaması başarısız; HTTP'ye düşürülmedi"

    except requests.exceptions.ConnectionError:
        sonuc["status"] = "Bağlantı Hatası"
        sonuc["hata"]   = "Bağlantı reddedildi"
    except requests.exceptions.Timeout:
        sonuc["status"] = "Zaman Aşımı"
        sonuc["hata"]   = f">{timeout}s cevap gelmedi"
    except Exception as e:
        sonuc["status"] = "Hata"; sonuc["hata"] = str(e)[:80]

    sonuc["puan"]   = puan_hesapla(sonuc["http_code"], sonuc["ms"],
                                    sonuc["login"], sonuc["status"])
    sonuc["etiket"] = puan_etiketi(sonuc["puan"])
    return sonuc

# ── Terminal çıktısı ───────────────────────────────────────────────────────
def terminal_yaz(r, idx, toplam):
    st = r["status"]; kod = r["http_code"]
    ms = r["ms"];     puan = r["puan"]
    login = r["login"]; hata = r["hata"]

    if   "Açık" in st:          renk = G
    elif "Yönlendirme" in st:   renk = Y
    elif "DNS" in st:           renk = M
    elif "Zaman" in st:         renk = Y
    else:                       renk = R

    num   = f"{D}[{idx:>3}/{toplam}]{RST}"
    url_s = r["url"][:52].ljust(52)
    st_s  = f"{renk}{st:<22}{RST}"
    kod_s = f"{B}{kod}{RST}" if kod else "   -"
    ms_s  = f"{ms:>5}ms" if ms else "     -"
    puan_s= f"{W}{puan:>3}p{RST}"
    l_s   = f" {M}🔐{RST}" if login else ""
    e_s   = f" {D}→ {hata[:40]}{RST}" if hata and puan==0 else ""
    print(f"{num} {url_s} {st_s} {kod_s} {ms_s} {puan_s}{l_s}{e_s}")

# ── Excel güncelle ─────────────────────────────────────────────────────────
# Hücre renkleri
FILL = {
    "yesil":  PatternFill("solid", fgColor="C6EFCE"),
    "sari":   PatternFill("solid", fgColor="FFEB9C"),
    "turuncu":PatternFill("solid", fgColor="FFD580"),
    "kirmizi":PatternFill("solid", fgColor="FFC7CE"),
    "mor":    PatternFill("solid", fgColor="E2CFFF"),
    "gri":    PatternFill("solid", fgColor="D9D9D9"),
    "header": PatternFill("solid", fgColor="1F3864"),
}
BOLD_WHITE = Font(bold=True, color="FFFFFF", size=11)
BOLD       = Font(bold=True)
CENTER     = Alignment(horizontal="center", vertical="center")

def fill_renk(puan):
    if puan >= 90:  return FILL["yesil"]
    if puan >= 70:  return FILL["sari"]
    if puan >= 50:  return FILL["turuncu"]
    if puan >= 20:  return FILL["kirmizi"]
    return FILL["gri"]

def excel_guncelle(excel_yolu, sonuclar, cikti_yolu):
    """
    Orijinal Excel'i okur, C ve D sütunlarını doldurur,
    sağına puan sütunları ekler, Özet sayfası oluşturur.
    """
    wb = openpyxl.load_workbook(excel_yolu)
    ws = wb.active

    # Başlık satırını oku — sütun indekslerini bul
    # Mevcut: A=ZONE, B=Dış DNS, C=SİTE AÇILIYOR MU?, D=PAROLA EKRANI VAR MI?
    # Yeni eklenecek: E=HTTP Kodu, F=Yanıt(ms), G=IP, H=Puan, I=Değerlendirme, J=Hata/Not

    # Başlık satırı (1. satır) güncelle
    yeni_basliklar = {
        3: "SİTE AÇILIYOR MU?",
        4: "PAROLA EKRANI VAR MI?",
        5: "HTTP Kodu",
        6: "Yanıt (ms)",
        7: "IP Adresi",
        8: "PUAN (/100)",
        9: "DEĞERLENDİRME",
        10:"Yönlendirme URL",
        11:"Hata / Not",
        12:"Kontrol Zamanı"
    }
    for col, baslik in yeni_basliklar.items():
        c = ws.cell(row=1, column=col, value=baslik)
        c.fill = FILL["header"]
        c.font = BOLD_WHITE
        c.alignment = CENTER

    ws.row_dimensions[1].height = 22

    # Sonuçları URL'ye göre eşleştir
    url_sonuc = {r["url"]: r for r in sonuclar}
    # http:// prefix'siz de eşleş
    url_sonuc_sade = {}
    for r in sonuclar:
        sade = r["url"].replace("http://","").replace("https://","").rstrip("/")
        url_sonuc_sade[sade] = r

    zaman = datetime.now().strftime("%d.%m.%Y %H:%M")

    for row_i in range(2, ws.max_row + 1):
        dis_dns_cell = ws.cell(row=row_i, column=2).value
        if not dis_dns_cell:
            continue

        dis_dns = str(dis_dns_cell).strip()
        # Eşleştir
        r = (url_sonuc.get("http://"+dis_dns) or
             url_sonuc.get("https://"+dis_dns) or
             url_sonuc_sade.get(dis_dns))

        if not r:
            continue

        puan   = r["puan"]
        etiket = r["etiket"]
        login  = r["login"]
        fill   = fill_renk(puan)

        # C — Site açılıyor mu?
        aciliyor = "EVET ✓" if r["http_code"] and r["http_code"] < 400 else \
                   "KISITLI" if r["http_code"] == 403 else \
                   "HAYIR ✗" if not r["http_code"] else f"HTTP {r['http_code']}"
        ws.cell(row=row_i, column=3, value=aciliyor)

        # D — Parola ekranı
        ws.cell(row=row_i, column=4,
                value=("EVET ✓ — " + r["login_neden"]) if login else "Hayır")

        # E — HTTP Kodu
        ws.cell(row=row_i, column=5, value=r["http_code"])

        # F — Yanıt ms
        ws.cell(row=row_i, column=6, value=r["ms"])

        # G — IP
        ws.cell(row=row_i, column=7, value=r["ip"])

        # H — Puan
        puan_cell = ws.cell(row=row_i, column=8, value=puan)
        puan_cell.font = BOLD
        puan_cell.alignment = CENTER

        # I — Değerlendirme
        ws.cell(row=row_i, column=9, value=etiket)

        # J — Yönlendirme
        ws.cell(row=row_i, column=10, value=r.get("yonlendirme",""))

        # K — Hata notu
        ws.cell(row=row_i, column=11, value=r.get("hata",""))

        # L — Zaman
        ws.cell(row=row_i, column=12, value=zaman)

        # Satır rengi (C:L arası)
        for col in range(3, 13):
            ws.cell(row=row_i, column=col).fill = fill

    # Sütun genişlikleri
    genislikler = {1:25, 2:35, 3:16, 4:28, 5:10, 6:12,
                   7:18, 8:12, 9:18, 10:40, 11:35, 12:18}
    for col, w in genislikler.items():
        ws.column_dimensions[get_column_letter(col)].width = w

    ws.freeze_panes = "C2"

    # ── ÖZET SAYFASI ──────────────────────────────────────────────────────
    if "ÖZET" in wb.sheetnames:
        del wb["ÖZET"]
    ws2 = wb.create_sheet("ÖZET")

    toplam   = len(sonuclar)
    mukemmel = sum(1 for r in sonuclar if r["puan"] >= 90)
    iyi      = sum(1 for r in sonuclar if 70 <= r["puan"] < 90)
    orta     = sum(1 for r in sonuclar if 50 <= r["puan"] < 70)
    zayif    = sum(1 for r in sonuclar if 20 <= r["puan"] < 50)
    erisile  = sum(1 for r in sonuclar if r["puan"] < 20)
    login_c  = sum(1 for r in sonuclar if r["login"])
    dns_fail = sum(1 for r in sonuclar if r["status"] == "DNS Hatası")
    timeout_c= sum(1 for r in sonuclar if "Zaman" in r["status"])
    ort_ms   = int(sum(r["ms"] for r in sonuclar if r["ms"]) /
                   max(1, sum(1 for r in sonuclar if r["ms"])))
    ort_puan = int(sum(r["puan"] for r in sonuclar) / max(1, toplam))

    ozet_baslik = [["External DNS Monitoring Report", ""],
                   ["Oluşturulma", zaman],
                   ["",""],
                   ["ALAN", "DEĞER"],
                   ["Toplam URL Kontrol Edildi", toplam],
                   ["🟢 Mükemmel (90-100p)", mukemmel],
                   ["🟡 İyi (70-89p)", iyi],
                   ["🟠 Orta (50-69p)", orta],
                   ["🔴 Zayıf (20-49p)", zayif],
                   ["⛔ Erişilemiyor (0-19p)", erisile],
                   ["",""],
                   ["🔐 Login Sayfası Tespit Edilen", login_c],
                   ["DNS Çözülemeyen", dns_fail],
                   ["Zaman Aşımı", timeout_c],
                   ["",""],
                   ["Ortalama Puan", f"{ort_puan}/100"],
                   ["Ortalama Yanıt Süresi", f"{ort_ms}ms"],
                   ["",""],
                   ["PUAN TABLOSU",""],
                   ["100p",  "200 OK + <500ms"],
                   ["85p",   "200 OK + 500ms-2sn"],
                   ["70p",   "200 OK + >2sn"],
                   ["60p",   "Yönlendirme (3xx)"],
                   ["50p",   "Giriş Gerekli (401)"],
                   ["40p",   "Kısıtlı (403)"],
                   ["20p",   "404 / 5xx"],
                   ["0p",    "DNS Hatası / Timeout"],
                   ["+10p",  "Login sayfası tespit bonus"],
    ]

    ozet_renkler = {
        0: FILL["header"],  # Başlık
        3: FILL["header"],  # ALAN/DEĞER başlık
    }
    ozet_font = {
        0: BOLD_WHITE,
        3: BOLD_WHITE,
    }

    for i, (a, b) in enumerate(ozet_baslik, 1):
        ca = ws2.cell(row=i, column=1, value=a)
        cb = ws2.cell(row=i, column=2, value=b)
        if i-1 in ozet_renkler:
            ca.fill = ozet_renkler[i-1]; cb.fill = ozet_renkler[i-1]
            ca.font = ozet_font[i-1];    cb.font = ozet_font[i-1]
        if i == 1:
            ca.font = Font(bold=True, size=14, color="1F3864")

    # Puan satırlarını renklendir
    puan_satirlari = {5:("yesil",None), 6:("yesil",None),
                      7:("sari",None),  8:("turuncu",None),
                      9:("kirmizi",None),10:("gri",None)}
    for satir, (renk, _) in puan_satirlari.items():
        for col in [1,2]:
            ws2.cell(row=satir, column=col).fill = FILL[renk]

    ws2.column_dimensions["A"].width = 35
    ws2.column_dimensions["B"].width = 30
    ws2.freeze_panes = "A2"

    wb.save(cikti_yolu)
    print(f"\n{G}✓ Excel kaydedildi → {cikti_yolu}{RST}")

# ── Ana program ────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel",   required=True, help="Kaynak Excel (dis_dns.xlsx)")
    ap.add_argument("--output",  default="external_dns_results.xlsx")
    ap.add_argument("--timeout", type=int, default=8)
    ap.add_argument("--workers", type=int, default=15)
    args = ap.parse_args()

    # URL'leri oku
    wb  = openpyxl.load_workbook(args.excel, read_only=True, data_only=True)
    ws  = wb.active
    urls = []
    for i, row in enumerate(ws.iter_rows(values_only=True), 1):
        if i == 1: continue
        d = row[1] if len(row) > 1 else None
        if d and str(d).strip():
            urls.append(str(d).strip())

    print(f"""
{B}╔══════════════════════════════════════════════════════╗
║  External DNS Monitoring Tool v2            ║
║  {len(urls)} URL  |  {args.workers} paralel  |  timeout {args.timeout}s        ║
╚══════════════════════════════════════════════════════╝{RST}
Başlıyor... {datetime.now().strftime('%H:%M:%S')}
    """)

    print(f"{D}{'─'*95}{RST}")
    print(f"{'#':>8}  {'URL':<52} {'DURUM':<22} {'KOD':<6} {'SÜRE':>6} {'PUAN':>5}{RST}")
    print(f"{D}{'─'*95}{RST}")

    sonuclar = [None] * len(urls)

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        fm = {ex.submit(url_kontrol, u, args.timeout): i for i, u in enumerate(urls)}
        tamamlanan = 0
        for future in concurrent.futures.as_completed(fm):
            i = fm[future]
            try:
                r = future.result()
            except Exception as e:
                u = urls[i]
                r = {"url": u if u.startswith("http") else "http://"+u,
                     "status": "Hata", "http_code": None, "ms": None,
                     "ip": "", "login": False, "login_neden": "",
                     "yonlendirme": "", "hata": str(e)[:80],
                     "puan": 0, "etiket": "⛔ Erişilemiyor"}
            sonuclar[i] = r
            tamamlanan += 1
            terminal_yaz(r, tamamlanan, len(urls))

    # Özet
    toplam  = len(sonuclar)
    acik    = sum(1 for r in sonuclar if r["puan"] >= 60)
    login_c = sum(1 for r in sonuclar if r["login"])
    ort_p   = int(sum(r["puan"] for r in sonuclar) / max(1,toplam))
    ort_ms  = int(sum(r["ms"] for r in sonuclar if r["ms"]) /
                  max(1, sum(1 for r in sonuclar if r["ms"])))

    print(f"\n{B}{'═'*55}{RST}")
    print(f"{W}  ÖZET  |  {datetime.now().strftime('%H:%M:%S')}{RST}")
    print(f"{B}{'─'*55}{RST}")
    print(f"  Toplam kontrol      : {W}{toplam}{RST}")
    print(f"  {G}Erişilebilir (≥60p) : {acik}{RST}")
    print(f"  {M}Login sayfası       : {login_c}{RST}")
    print(f"  Ortalama puan       : {W}{ort_p}/100{RST}")
    print(f"  Ortalama yanıt      : {W}{ort_ms}ms{RST}")
    print(f"{B}{'═'*55}{RST}")

    excel_guncelle(args.excel, sonuclar, args.output)

if __name__ == "__main__":
    main()
