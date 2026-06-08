#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
タクティ 見積書サンプル59件 → 構造化JSON 抽出。
HTML / XLSX / PDF の混在を best-effort でパースし、
  supplier(=ファイル名) / vessel / imo / quote_no / date / currency / lines[] / raw_excerpt / status
を data/quotes_real.json に出力する（実データ＝gitignore対象）。
"""
import os, re, sys, json, glob, subprocess, zipfile
from html import unescape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ZIP  = os.path.expanduser("~/Downloads/見積書サンプル59件.zip")
RAW  = os.path.join(ROOT, "data", "_raw")
OUT  = os.path.join(ROOT, "data", "quotes_real.json")

def unzip():
    os.makedirs(RAW, exist_ok=True)
    # plain unzip（このmacOSではUTF-8名で正しく展開される）
    subprocess.run(["unzip", "-o", "-q", ZIP, "-d", RAW], check=False)

def list_files():
    fs = []
    for dirpath, _, names in os.walk(RAW):
        for n in names:
            if n.startswith("._"): continue
            if os.path.splitext(n)[1].lower() in (".pdf", ".html", ".htm", ".xlsx"):
                fs.append(os.path.join(dirpath, n))
    return sorted(fs)

def supplier_from_name(fn):
    base = os.path.splitext(os.path.basename(fn))[0]
    # 先頭の連番を除去  "3 YANMAR" -> "YANMAR"
    return re.sub(r"^\s*\d+\s*[\.\-_)]?\s*", "", base).strip()

# ---------- テキスト取得 ----------
def text_from_pdf(fn):
    try:
        r = subprocess.run(["pdftotext", "-layout", "-enc", "UTF-8", fn, "-"],
                           capture_output=True, timeout=60)
        t = r.stdout.decode("utf-8", "ignore")
    except Exception:
        t = ""
    if len(t.strip()) >= 200:           # テキスト層あり
        return t
    return text_from_pdf_ocr(fn) or t    # スキャンPDF → OCR

def text_from_pdf_ocr(fn):
    """スキャンPDFを pdftoppm で画像化し tesseract(eng+jpn) でOCR。"""
    if not (_has("pdftoppm") and _has("tesseract")):
        return ""
    import tempfile, glob as _glob
    out = []
    with tempfile.TemporaryDirectory() as tmp:
        base = os.path.join(tmp, "p")
        subprocess.run(["pdftoppm", "-r", "300", "-png", fn, base], check=False, timeout=180)
        for img in sorted(_glob.glob(base + "*.png"))[:6]:   # 最大6ページ
            try:
                r = subprocess.run(["tesseract", img, "-", "-l", "eng+jpn", "--psm", "6"],
                                   capture_output=True, timeout=120)
                out.append(r.stdout.decode("utf-8", "ignore"))
            except Exception:
                pass
    return "\n".join(out)

_WHICH = {}
def _has(cmd):
    if cmd not in _WHICH:
        _WHICH[cmd] = subprocess.run(["which", cmd], capture_output=True).returncode == 0
    return _WHICH[cmd]

def text_from_html(fn):
    raw = open(fn, "rb").read().decode("utf-8", "ignore")
    raw = re.sub(r"(?is)<style.*?</style>", " ", raw)
    raw = re.sub(r"(?is)<script.*?</script>", " ", raw)
    raw = re.sub(r"(?is)<[^>]+>", " ", raw)
    raw = unescape(raw).replace("\xa0", " ")
    return re.sub(r"[ \t]+", " ", raw)

def text_from_xlsx(fn):
    import openpyxl
    wb = openpyxl.load_workbook(fn, read_only=True, data_only=True)
    rows = []
    for ws in wb.worksheets:
        for row in ws.iter_rows(values_only=True):
            cells = [("" if c is None else str(c)).strip() for c in row]
            if any(cells):
                rows.append("\t".join(cells))
    wb.close()
    return "\n".join(rows)

# ---------- ヘッダ抽出 ----------
BUYER = re.compile(r"TACT[YI]|タクティ|MESSRS", re.I)
def _clean_vessel(v):
    v = re.split(r"\s{2,}|IMO|HULL|代\s*価|Delivery|EXW|/\s*\d{3,}|形\s*式|機\s*番", v)[0]
    v = v.strip(" .,-/：:")
    if not v or v.isdigit() or len(v) < 3: return None
    if BUYER.search(v): return None            # 買い手(タクティ)の誤ラベルを除外
    return v
def find_vessel(t):
    for pat in [r"機場\s*／?\s*船名\s*[:：]\s*([^\n]{3,40})",
                r"船名\s*[:：]\s*([^\n]{3,40})",
                r"Subject\s*[:：]\s*([A-Z0-9][^\n]{2,40})",
                r"VESSEL[\s:：/]*([A-Z0-9][A-Z0-9 .&'\-/]{2,40})",
                r"\bM[./ ]?V[./ ]?\s+([A-Z][A-Z0-9 .&'\-]{2,40})"]:
        m = re.search(pat, t, re.I)
        if m:
            v = _clean_vessel(m.group(1))
            if v: return v
    return None

def find_imo(t):
    m = re.search(r"IMO[\s:.#]*([0-9]{7})", t, re.I)
    return m.group(1) if m else None

def find_quote_no(t):
    for pat in [r"(?:QUOTATION|QUOTE|QUOT\.?|REF\.?|OFFER)\s*(?:NO\.?|NUMBER|#)?\s*[:：]?\s*([A-Z0-9][A-Z0-9\-/]{4,25})",
                r"\b([A-Z]{2,4}\d{2,4}[A-Z]{0,3}-?\d{3,6})\b"]:
        m = re.search(pat, t, re.I)
        if m: return m.group(1).strip()
    return None

def find_date(t):
    m = re.search(r"\b(\d{1,2}\s+[A-Z][a-z]{2,8},?\s+20\d{2})\b", t)        # 28 Apr, 2026
    if m: return m.group(1)
    m = re.search(r"\b(20\d{2}[-/.]\d{1,2}[-/.]\d{1,2})\b", t)
    if m: return m.group(1)
    m = re.search(r"\b(\d{1,2}[-/.]\d{1,2}[-/.]20\d{2})\b", t)
    return m.group(1) if m else None

def find_currency(t):
    for c in ["USD", "JPY", "EUR", "SGD", "GBP"]:
        if re.search(r"\b"+c+r"\b", t): return c
    if "¥" in t or "円" in t: return "JPY"
    if "$" in t: return "USD"
    return None

# ---------- 明細抽出（best-effort） ----------
UNIT = r"(EA|PC|PCS|SET|SETS|NO|NOS|PR|PRS|M|KG|L|UNIT)"
def _num(s):
    s = re.sub(r"[¥$,＼\s]", "", s or "")
    try: return float(s) if s else 0.0
    except ValueError: return 0.0
def _extract_pn(name):
    pm = re.search(r"(?:PART\s*NO[.:]*\s*|P/?N[.:]*\s*)([A-Z0-9][A-Z0-9\-]{3,20})", name, re.I)
    if not pm: pm = re.search(r"\b([A-Z]{1,3}\d{5,}|[A-Z0-9]{2,}-[A-Z0-9-]{3,})\b", name)
    return pm.group(1) if pm else ""
def _clean_name(name):
    return re.sub(r"\s*(ADD\.?\s*(REMARKS|PART NO|DWG NO|MATERIAL).*$)", "", name, flags=re.I).strip(" .,:*")
def _validate(qty, up, amt):
    # 金額 ≈ 数量×単価 で誤検出を排除（端数±2%許容）
    try:
        q, u, a = _num(qty), _num(up), _num(amt)
        if a <= 0 or u <= 0: return False
        return abs(q*u - a) <= max(1.0, a*0.02)
    except Exception:
        return False

def find_lines(t):
    lines, seen = [], set()
    for ln in t.splitlines():
        s = ln.strip()
        if len(s) < 6: continue
        rec = None
        # P1: 英語 "1 VALVE SEAT GASKET ... A00002071 2 EA 26.07 52.14 STK"
        m = re.match(r"^(\d{1,3})\s+(.{3,80}?)\s+(\d{1,5})\s+"+UNIT+r"\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)", s, re.I)
        if m and _validate(m.group(3), m.group(5), m.group(6)):
            nm = _clean_name(m.group(2))
            rec = {"seq": int(m.group(1)), "name": nm[:70], "part_no": _extract_pn(m.group(2)),
                   "qty": m.group(3), "unit": m.group(4).upper(), "unit_price": m.group(5), "amount": m.group(6)}
        if not rec:
            # P2: DAIHATSU等 "001 06548-030 GASKET:T/C INLET 2 5500 11000 [0.3]"  (seq 部品No 品名 数量 単価 金額 [重量])
            m = re.match(r"^\*?\s*(\d{1,3})[:：]?\s+([A-Z0-9][A-Z0-9\-./]{4,})\s+(.+?)\s+(\d{1,4})\s+([\d,]+\.?\d*)\s+([\d,]+\.?\d*)(?:\s+[\d.]+)?$", s)
            if m and _validate(m.group(4), m.group(5), m.group(6)):
                rec = {"seq": int(m.group(1)), "name": _clean_name(m.group(3))[:70], "part_no": m.group(2),
                       "qty": m.group(4), "unit": "", "unit_price": m.group(5), "amount": m.group(6)}
        if not rec:
            # P3: 汎用（KITASAKA/MITSUI/ISS等）"seq … 数量 単価 金額"。末尾3数値を 金額≈数量×単価 で検証。
            #     ¥/$/カンマ/末尾の KG・STK・重量 を許容。
            m = re.match(r"^\*?\s*(\d{1,3})[:：.]?\s+(.+?)\s+(\d{1,4})\s+([¥$＼]?[\d,]+(?:\.\d+)?)\s+([¥$＼]?[\d,]+(?:\.\d+)?)\s*(?:KG|STK|EA|PCS?|[\d.]+)?\s*$", s, re.I)
            if m and _validate(m.group(3), m.group(4), m.group(5)):
                nm = _clean_name(m.group(2))
                rec = {"seq": int(m.group(1)), "name": nm[:70], "part_no": _extract_pn(m.group(2)),
                       "qty": m.group(3), "unit": "", "unit_price": re.sub(r"[¥$＼]","",m.group(4)),
                       "amount": re.sub(r"[¥$＼]","",m.group(5))}
        if rec:
            key = (rec["name"], rec["amount"])
            if key in seen: continue
            seen.add(key); lines.append(rec)
            if len(lines) >= 40: break
    return lines

def main():
    if not os.path.exists(ZIP):
        print("ZIP not found:", ZIP); sys.exit(1)
    unzip()
    files = list_files()
    out = []
    stats = {"full": 0, "header_only": 0, "failed": 0, "ocr_needed": 0}
    for fn in files:
        ext = os.path.splitext(fn)[1].lower()
        try:
            if ext == ".pdf":  t = text_from_pdf(fn)
            elif ext in (".html", ".htm"): t = text_from_html(fn)
            else: t = text_from_xlsx(fn)
        except Exception as e:
            t = ""
        rec = {
            "file": os.path.basename(fn),
            "type": ext.lstrip("."),
            "supplier": supplier_from_name(fn),
            "vessel": find_vessel(t),
            "imo": find_imo(t),
            "quote_no": find_quote_no(t),
            "date": find_date(t),
            "currency": find_currency(t),
            "lines": find_lines(t),
            "text_len": len(t),
            "raw_excerpt": re.sub(r"\s+", " ", t)[:600],
        }
        if rec["lines"]: rec["status"] = "full"; stats["full"] += 1
        elif rec["text_len"] > 200: rec["status"] = "header_only"; stats["header_only"] += 1
        else: rec["status"] = "ocr_needed"; stats.setdefault("ocr_needed", 0); stats["ocr_needed"] += 1
        out.append(rec)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(out, open(OUT, "w"), ensure_ascii=False, indent=1)

    # ---- レポート ----
    nv = sum(1 for r in out if r["vessel"])
    nl = sum(len(r["lines"]) for r in out)
    print(f"=== 抽出結果: {len(out)} ファイル ===")
    print(f" 明細あり(full): {stats['full']}  ヘッダのみ: {stats['header_only']}  OCR要: {stats['ocr_needed']}")
    print(f" 船名取得: {nv}/{len(out)}   明細行 合計: {nl}")
    print(f" 出力: {OUT}")
    print("\n--- サプライヤー × 船名 × 明細数（先頭25件）---")
    for r in out[:25]:
        print(f"  [{r['status'][:4]:4}] {r['supplier'][:34]:34} | 船:{(r['vessel'] or '-')[:22]:22} | 明細:{len(r['lines'])}")

if __name__ == "__main__":
    main()
