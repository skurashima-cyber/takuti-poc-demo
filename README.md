# タクティ株式会社 — DC × Agentforce PoC デモ画面

船舶部品調達業務向け Agentforce エージェントの**仕様合意用モックアップ**です。Salesforce 実装前に、3テーマの体験イメージを顧客と合意するために使用します。**要件定義書 v0.1 準拠**。

👉 **公開URL（GitHub Pages・匿名化版）:** https://skurashima-cyber.github.io/takuti-poc-demo/

> 公開版は実見積59件を**匿名化**したデータ（船名・サプライヤー・価格・品番をマスキング）。
> 実データ版は `index.internal.html` ＋ `data/demo_data.real.js`（ローカル限定・非公開）。

- **① Navigator（船別・部品検索）**: 自然言語の問い合わせ → **製造業者／型式／推奨サプライヤーTOP3** を**確信度(高/中/低)＋根拠(過去見積 最大3件)**つきで回答。0件時は推測せず「該当なし・手動確認を」（ハルシネーション0）
- **② サプライヤー推奨**: **ルール0.5×類似0.3×マスタ0.2** のハイブリッド加重で推奨サプライヤーをランキング。重みスライダーで再計算、推奨理由(Reason__c)・採用/却下(手動承認)つき
- **③ 納期督促（Flow）**: PurchaseOrder__c を平日09:00監視。**+1営業日=担当へ初回／+3=再督促／+7=上長エスカ** の段階通知。Slack DM に[納期を更新する][サプライヤー連絡を記録する]を添付（過剰督促の抑止・再督促インターバル制御）

## 使い方
`index.html` をブラウザで開くだけ（単一ファイル・依存なし）。

## データモデル対応
RFQ__c / RFQ_Line__c（Part_Number__c, Maker__c, Match_Confidence__c, Vessel_Name__c …）/ Vendor_Quote__c に対応した画面イメージ。

> ⚠️ サンプルデータによるモックアップです。実データ（Mariapps）・Salesforce / Data Cloud とは未接続です。
> 精度KPI：TOP1 ≥ 70% / TOP3 ≥ 90%。入力例・期待出力・スコアはすべて仮置きで、実データ反映後に確定します。
> ※ OCR（見積書突合 / Apollo）は本PoCの Out of Scope です。
