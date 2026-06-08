#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
quotes_real.json（抽出済み実データ）→ デモ用データ TACTI_DEMO を生成。
出力:
  demo_data.real.js   … 実データ（実在船名/サプライヤー/価格）※gitignore・公開しない
  demo_data.public.js … 匿名化版（公開GitHub Pages用）
  index.internal.html … index.html の実データ版コピー ※gitignore
schema:
  window.TACTI_DEMO = { mode, navigator[], suppliers{items[]}, dunning[], ocr{} }
"""
import os, re, json, copy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC  = os.path.join(ROOT, "data", "quotes_real.json")

def maker_of(supplier):
    return re.split(r"[ (,]", supplier.strip())[0].upper()

def clean_pname(n):
    # 部品名 先頭に紛れた品番トークン（数字を含む英数字）を除去
    n = re.sub(r"^\s*[A-Z0-9]*\d[A-Z0-9\-]*\s+(?=[A-Za-z])", "", n or "").strip()
    return n or (n if n else "PART")

def by_vessel(d, name):
    for r in d:
        if r.get("vessel") == name and r["lines"]:
            return r
    return None

def model_in(rec):
    m = re.search(r"(?:Model\s*No\.?|形\s*式)[:：]?\s*([A-Z0-9][A-Z0-9\-]{2,12})", rec.get("raw_excerpt",""), re.I)
    return m.group(1) if m else "—"

# ---------------- build (real) ----------------
def build(d):
    for r in d:                                   # 部品名から品番混入を除去（実版・公開版とも整う）
        for l in r["lines"]: l["name"] = clean_pname(l["name"])
    full = [r for r in d if r["lines"]]
    pool_suppliers = sorted(set(r["supplier"] for r in d))

    # --- Navigator: 実船×実部品 ---
    nav = []
    picks = [("BERGE KAIZAN", ["FUJI TRADING (SHANGHAI) CO. LTD.", "SANKO SANGYO"]),
             ("ESTEEM ENERGY", ["FUJI TRADING (MARINE) B.V.", "ISS MACHINERY SERVICES LIMITED"]),
             ("VITALITY DIVA", ["DAIHATSU INFINEARTH (ASIA PACIFIC) PTE. LTD", "SANKO SANGYO"]),
             ("ANDROMEDA SPIRIT", ["FUJI TRADING (SHANGHAI) CO. LTD.", "DAN MARINE GROUP LTD."])]
    for vessel, alts in picks:
        rec = by_vessel(d, vessel)
        if not rec: continue
        line0 = rec["lines"][0]
        part = line0["name"]
        maker = maker_of(rec["supplier"])
        model = model_in(rec)
        sups = [rec["supplier"]] + alts
        ev = []
        for l in rec["lines"][:2]:
            ev.append({"src":"q","id":rec.get("quote_no") or rec["file"][:18],
                       "detail":f"{vessel} / {rec.get('date') or '—'} ・ {l['name']} ・ PartNo {l['part_no'] or '—'} ・ {l['unit_price']}{rec.get('currency') or ''}（成約）"})
        ev.append({"src":"m","id":(line0["part_no"] or "P-—"),
                   "detail":f"商品マスタ ・ {part} ・ Maker: {maker}"+(f" ・ 型式 {model}" if model!='—' else "")})
        nav.append({
            "q": f"{vessel} の {part} の製造業者は？",
            "conf":"高", "maker": maker, "model": model, "suppliers": sups[:3],
            "say": f"同船舶 <b>{vessel}</b> ×「{part}」で過去見積に成約実績を確認。確信度 <b>高</b>。製造業者・型式を断定し、推奨サプライヤーをTOP3候補で提示します。",
            "ev": ev,
        })
    # 確信度=中 と 0件 を追加
    if nav:
        nav.append({
            "q": f"{picks[0][0]} の特殊バルブ（型式不明）の製造業者は？",
            "conf":"中", "maker":"要確認（候補あり）", "model":"—",
            "suppliers":[nav[0]["suppliers"][0], pool_suppliers[3] if len(pool_suppliers)>3 else "—"],
            "say":"型式が特定できず、成約実績も限定的のため確信度 <b>中</b>。候補を提示しますが、価格・適合は人によるご確認を推奨します。",
            "note":"確信度=中：根拠が限定的です。低確信時は同型船舶へ拡張（Q-N3）。最終採否は担当者がご判断ください。",
            "ev":[{"src":"m","id":"P-—","detail":"商品マスタ ・ 互換情報なし（要確認）"}],
        })
    nav.append({"q":"M/V SAKURA MARU の SPECIAL VALVE の製造業者は？", "conf":"なし", "none":True, "say":""})

    # --- 推奨: 実部品×実サプライヤー（同メーカー系を上位、他はsim/master） ---
    items = []
    rec = by_vessel(d, "BERGE KAIZAN")
    if rec:
        prime = rec["supplier"]
        items.append({"label": f"BERGE KAIZAN ／ {rec['lines'][0]['name']}（{maker_of(prime)} {model_in(rec)}）",
            "candidates":[
                {"name":prime,"rule":0.95,"sim":0.86,"master":1.0,"dealer":True,
                 "reason":f"同船舶 BERGE KAIZAN × 同部品で直近成約。{maker_of(prime)} 正規代理店。"},
                {"name":"FUJI TRADING (SHANGHAI) CO. LTD.","rule":0.42,"sim":0.80,"master":0.5,"dealer":False,
                 "reason":"同型船舶で同部品の成約実績（Embeddings類似度0.83）。"},
                {"name":"SANKO SANGYO","rule":0.55,"sim":0.52,"master":0.4,"dealer":False,
                 "reason":"同船舶で別部品の取扱実績あり。短納期。"},
                {"name":"DAN MARINE GROUP LTD.","rule":0.18,"sim":0.6,"master":0.35,"dealer":False,
                 "reason":"汎用流通。価格優位。"}]})
    rec2 = by_vessel(d, "ESTEEM ENERGY")
    if rec2:
        items.append({"label": f"ESTEEM ENERGY ／ {rec2['lines'][0]['name']}",
            "candidates":[
                {"name":rec2["supplier"],"rule":0.9,"sim":0.78,"master":0.9,"dealer":True,
                 "reason":"同船舶で直近成約。主要メーカー取扱い。"},
                {"name":"FUJI TRADING (MARINE) B.V.","rule":0.4,"sim":0.82,"master":0.55,"dealer":False,
                 "reason":"同型船舶で成約5回（類似度0.85）。"},
                {"name":"ISS MACHINERY SERVICES LIMITED","rule":0.5,"sim":0.55,"master":0.45,"dealer":False,
                 "reason":"近隣港・短納期で実績。"},
                {"name":"CAPE LINE LTD","rule":0.45,"sim":0.48,"master":0.3,"dealer":False,
                 "reason":"社外互換。価格最安。"}]})
    rec3 = by_vessel(d, "ANDROMEDA SPIRIT")
    if rec3:
        items.append({"label": f"ANDROMEDA SPIRIT ／ {rec3['lines'][0]['name']}（{maker_of(rec3['supplier'])}）",
            "candidates":[
                {"name":rec3["supplier"],"rule":0.88,"sim":0.75,"master":1.0,"dealer":True,
                 "reason":"同船舶で成約。正規代理店。"},
                {"name":"SANKO SANGYO","rule":0.55,"sim":0.6,"master":0.5,"dealer":False,"reason":"同型船舶で成約。在庫潤沢。"},
                {"name":"FUJI TRADING (SHANGHAI) CO. LTD.","rule":0.46,"sim":0.58,"master":0.4,"dealer":False,"reason":"近隣港・短納期。"},
                {"name":"DAN MARINE GROUP LTD.","rule":0.5,"sim":0.42,"master":0.28,"dealer":False,"reason":"社外互換品。"}]})
    suppliers = {"items": items}

    # --- 納期督促: 実(船/部品/サプライヤー)からPO合成（納期は督促デモ用に設定） ---
    def first_part(v):
        r=by_vessel(d,v); return (r["lines"][0]["name"], r["supplier"]) if r else ("PART","SUPPLIER")
    dun=[]
    rows_spec=[
      ("BERGE KAIZAN",1,1,"初回督促","s1","担当（田中）","yes"),
      ("ESTEEM ENERGY",3,3,"再督促(3営業日)","s3","担当（田中）","yes"),
      ("ANDROMEDA SPIRIT",8,7,"上長エスカ(7営業日)","s7","上長（佐藤）","yes"),
      ("VITALITY DIVA",-2,0,"—","s0","—","no"),
    ]
    for i,(v,days,bizd,stage,sc,to,judge) in enumerate(rows_spec):
        part,sup=first_part(v)
        due="2026/06/0%d"%(9 if days>=0 else 12)
        d_=("超過 %d 営業日"%bizd) if judge=="yes" else ""
        draft=(f"🚢 納期遅延通知（{stage}）\n案件: PO-2026-001{i+2} / {v} / {part}\n発注先: {sup}\n納期: {due}（→ 2026/06/10 現在）\n担当: 田中さん") if judge=="yes" else ""
        dun.append({"po":f"PO-2026-001{i+2}","ship":f"{v} / {part}","sup":sup,"due":due,
                    "days":days,"bizd":bizd,"stage":stage,"sc":sc,"to":to,"judge":judge,
                    "reason":("" if judge=="yes" else "納期内・回答済 → 督促不要"),"draft":draft})
    # 出荷済/保留 の2行（固定）
    dun.append({"po":"PO-2026-0016","ship":"ESTEEM EXPLORER / "+(first_part('ESTEEM EXPLORER')[0]),"sup":first_part('ESTEEM EXPLORER')[1],
                "due":"2026/06/01","days":9,"bizd":7,"stage":"出荷済","sc":"s0","to":"—","judge":"no","reason":"出荷済（連絡漏れ）→ ステータス更新依頼","draft":""})
    dun.append({"po":"PO-2026-0017","ship":"BERGE KAIZAN / "+first_part('BERGE KAIZAN')[0],"sup":first_part('BERGE KAIZAN')[1],
                "due":"2026/06/06","days":4,"bizd":2,"stage":"再督促 保留","sc":"s0","to":"担当（田中）","judge":"hold","reason":"前回督促から3営業日未経過 → 保留","draft":""})

    # --- OCR突合: BERGE KAIZAN DAIHATSU見積を実Vendor_Quoteに、RFQを派生 ---
    ocr={}
    qr=by_vessel(d,"BERGE KAIZAN")
    if qr:
        L=qr["lines"]
        cur=qr.get("currency") or "JPY"
        def money(x): return f"{x}{cur}"
        rows=[]
        # 1 一致
        rows.append({"ln":1,"read":f"{L[0]['name']} {L[0]['part_no']}","qty":f"{L[0]['qty']} EA","price":money(L[0]['amount']),"src":"P.1 行1",
            "cand":f"{L[0]['name']} / PartNo {L[0]['part_no']}","candNote":"品名・品番ともに一致","diff":["match","一致"],"conf":96,"status":"auto"})
        # 2 表記差異（品番の区切り）
        pn=L[1]['part_no']; pn_ocr=pn.replace("-"," ") if "-" in pn else pn+" "
        rows.append({"ln":2,"read":f"{L[1]['name']} {pn_ocr}","qty":f"{L[1]['qty']} EA","price":money(L[1]['amount']),"src":"P.1 行2",
            "cand":f"{L[1]['name']} / PartNo {pn}","candNote":"品番の区切り表記が相違。AI類似度で同一と判定（候補3件）","diff":["name","品番 表記差異"],"conf":79,"status":"check"})
        # 3 数量差異
        q=int(re.sub(r"\D","",L[2]['qty']) or "2")
        rows.append({"ln":3,"read":f"{L[2]['name']} {L[2]['part_no']}","qty":f"{q+1} EA","price":money(L[2]['amount']),"src":"P.2 行1",
            "cand":f"{L[2]['name']} / PartNo {L[2]['part_no']}","candNote":f"品番一致。数量が相違（依頼{q} / 見積{q+1}）","diff":["qty",f"数量差異 ({q}→{q+1})"],"conf":88,"status":"check"})
        # 4 新規（依頼外）
        ex=L[4] if len(L)>4 else L[-1]
        rows.append({"ln":4,"read":f"{ex['name']} {ex['part_no']}","qty":f"{ex['qty']} EA","price":money(ex['amount']),"src":"P.2 行4",
            "cand":"（依頼書に該当なし）","candNote":"見積書のみに存在＝サプライヤー提案の追加品。採否を確認","diff":["new","新規（依頼外）"],"conf":0,"status":"check"})
        # 5 欠落
        ms=L[3] if len(L)>3 else L[-1]
        rows.append({"ln":"—","read":"（見積書に記載なし）","qty":"—","price":"—","src":"—",
            "cand":f"{ms['name']} / {ms['qty']} EA（依頼書 行{ms['seq']}）","candNote":"依頼したが見積もられていない明細。再見積を依頼","diff":["miss","欠落（未見積）"],"conf":0,"status":"miss"})
        ocr={"rfqNo":"EN-2026-0418","rfqVessel":qr["vessel"],"rfqMeta":"主機まわり 5明細 ・ 依頼日 2026/06/01 ・ 希望納期 2026/06/20",
             "quoteNo":qr.get("quote_no") or "QT-7741","quoteSupplier":qr["supplier"],
             "quoteMeta":f"見積日 {qr.get('date') or '2026/06/07'} ・ 通貨 {cur} ・ {len(L)}明細 読取",
             "rows":rows}

    return {"mode":"real","navigator":nav,"suppliers":suppliers,"dunning":dun,"ocr":ocr,
            "meta":{"suppliers_total":len(pool_suppliers),"vessels":sorted(set(r['vessel'] for r in d if r['vessel']))}}

# ---------------- anonymize ----------------
def anonymize(demo, d):
    dd = copy.deepcopy(demo); dd["mode"]="public"
    def maskprice(s): return re.sub(r"\d[\d,]*\.?\d*", "■,■■■", s) if s else s
    # 品番のみマスク（英字+数字混在トークン）。純英字の部品名・型式語は残す。
    def maskpn(s):    return re.sub(r"\b(?=[A-Z0-9\-]*\d)(?=[A-Z0-9\-]*[A-Z])[A-Z0-9][A-Z0-9\-]{4,}\b", "PN-■■■", s) if s else s
    # 1) 価格・品番はフィールド個別でマスク
    for n in dd["navigator"]:
        for e in n.get("ev", []):
            e["detail"] = maskpn(maskprice(e.get("detail",""))); e["id"] = maskpn(maskprice(e.get("id","")))
    if dd["ocr"]:
        o = dd["ocr"]; o["quoteMeta"] = maskprice(o.get("quoteMeta",""))
        for r in o["rows"]:
            r["read"]     = maskpn(maskprice(r.get("read","")))
            r["price"]    = maskprice(r.get("price",""))
            r["cand"]     = maskpn(maskprice(r.get("cand","")))      # 全数字の品番も価格マスクで塞ぐ
            r["candNote"] = maskpn(maskprice(r.get("candNote","")))
    # 2) 実名（船名・サプライヤー・メーカー）は全体一括スイープで確実に置換
    vessels = sorted({v for v in dd["meta"]["vessels"] if v and v.lower() != "name" and len(v) >= 5},
                     key=len, reverse=True)
    suppliers = sorted({r["supplier"] for r in d if r.get("supplier")}, key=len, reverse=True)
    makers = sorted({maker_of(s) for s in suppliers if len(maker_of(s)) >= 4}, key=len, reverse=True)
    vmap = {v: "M/V VESSEL-%02d" % (i+1) for i, v in enumerate(sorted(vessels))}
    smap = {s: "サプライヤー%02d" % (i+1) for i, s in enumerate(sorted(suppliers))}
    s = json.dumps(dd, ensure_ascii=False)
    for name in suppliers:  s = s.replace(name, smap[name])     # 長い順：部分一致の取りこぼし防止
    for v in vessels:       s = s.replace(v, vmap[v])
    for mk in makers:       s = re.sub(r"\b" + re.escape(mk) + r"\b", "MAKER-X", s)
    dd = json.loads(s)
    dd["meta"]["vessels"] = sorted(vmap.values())
    return dd

def emit(path, demo, public=False):
    banner = "// 公開用・匿名化データ（実在船名/サプライヤー/価格はマスキング済）\n" if public else \
             "// 実データ（実在船名・サプライヤー・価格を含む）— 公開しないこと（.gitignore対象）\n"
    with open(path,"w") as f:
        f.write(banner+"window.TACTI_DEMO = "+json.dumps(demo, ensure_ascii=False, indent=1)+";\n")
    print("  ->", os.path.relpath(path, ROOT))

def main():
    d = json.load(open(SRC))
    real = build(d)
    pub  = anonymize(real, d)
    emit(os.path.join(ROOT,"data","demo_data.real.js"), real)
    emit(os.path.join(ROOT,"demo_data.public.js"), pub, public=True)
    # 実データ版HTML（gitignore）を index.html から生成
    idx = os.path.join(ROOT,"index.html")
    if os.path.exists(idx):
        html = open(idx).read().replace("demo_data.public.js","data/demo_data.real.js")
        open(os.path.join(ROOT,"index.internal.html"),"w").write(html)
        print("  -> index.internal.html（実データ版・gitignore）")
    print(f"=== 生成完了: navigator {len(real['navigator'])} / 推奨 {len(real['suppliers']['items'])}品目 / 督促 {len(real['dunning'])} / OCR {len(real['ocr'].get('rows',[]))}行 ===")

if __name__ == "__main__":
    main()
