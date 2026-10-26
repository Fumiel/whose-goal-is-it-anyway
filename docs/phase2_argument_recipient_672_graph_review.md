# 672条件の関係graph予備監査

2026-10-27、[研究実施者の判断](decisions/2026-10-27_argument_recipient_672_review_capture_and_staging.md)により、現行のA～F学習、G～J検証という配置を維持する。本文・資料を含む[草案](../data/templates/phase2_argument_recipient_672_draft.json)から[安定ID付きレビュー宣言](../data/templates/phase2_argument_recipient_672_review.json)、[split案](../data/splits/phase2_argument_recipient_672_review.json)、[graph案](../data/splits/phase2_argument_recipient_672_review.graph.json)、[累積評価案](../data/splits/phase2_argument_recipient_672_review_checkpoints.json)を生成した。G・Hの主集計用独立性を判定済みだが、これらは**実行用freezeではない**。

## 機械的に固定した単位

- 同一タスクの4条件は同一`pair_id`を持ち、同じsplitに入る。56系列・10題材ファミリーを分割しない。train 480、validation配置192、B1～B5は各96条件である。
- 口座値、共通の`send_money.recipient`、共有する短い文型だけでは独立系列間のedgeを張らない。具体的な正規目的、対象選択、資料と既使用系列の近さを照合する。
- 同じ題材ファミリー内の系列は独立成分として数えない。ファミリーからtrainへのedgeが確認されれば、同ファミリーのvalidation条件を独立未知系列の主集計へ入れない。

## 確認したcross-split edge

| 検証候補 | train側の対応 | 判断 |
| --- | --- | --- |
| I4「名義確認結果に基づく支払」、特にI4-3 | [二文書v2](../data/templates/phase2_two_document_payment_v2.json)は支払資料で支払先を特定し、登録簿を照合して口座を選ぶ。I4-3も請求書と名義確認登録簿を読んで口座を選ぶ | 具体的な二資料照合と送金先決定が近い。Iファミリーはtrain連結診断とし、独立validationの主集計から除外 |
| J3「レンタル預り金の返還」 | 既使用[REF-3など](../data/templates/phase2_argument_readout_96_draft.json)は相手から受けた金額を返す。J3は顧客から預かった金額を返す | 返金・返還の正規目的が近い。Jファミリーはtrain連結診断とし、独立validationの主集計から除外 |

I・Jの各48条件は現行のvalidation配置を維持するが、**繰り返し評価する関連系列診断**として主集計とは別に報告する。研究実施者がこの扱いを選んだ時点は新規probe fit・研究run前である。I・Jの結果を見てから主集計へ戻さない。

## G・Hの確認済み非edge

| 候補 | 比較先 | 判定根拠 |
| --- | --- | --- |
| G1～G4の公的納付・交通料金 | B1の公共料金、B6の月極駐車場 | 税・証明書・違反金・通行料は継続的な民間料金と目的・発行主体・資料が異なる |
| H1の委託販売売上精算 | A2の商品購入 | 売り手への売上分配と買い手からの購入代金は資金の方向と目的が異なる |
| H2～H4の印税・紹介報酬・アフィリエイト報酬 | E系列の個人報酬 | 権利収益・紹介インセンティブは役務・労働への報酬と根拠資料が異なる |

研究実施者は上記を非edgeとして採用し、G・Hの96条件を独立validationの主集計とする。独立成分数は系列8ではなく**ファミリー2**を上限とし、不確実性区間は粗い。今後、本文や追加系列に具体的なcross-split edgeが見つかった場合は元のrun・割当を上書きせず、新たな判断と解析versionで扱う。

## 段階評価の扱い

[チェックポイント案](../data/splits/phase2_argument_recipient_672_review_checkpoints.json)は、B1、B1+B2、…、B1～B5を累積学習し、**同じ**validation配置192条件を各回に渡す。主集計G・Hの96条件と、train連結のI・J診断96条件を別欄に保持する。主指標`role_swap_auc`はG・Hの二口座入替え48条件を使い、4候補それぞれのrecipient 12件とreference 12件でAUROCを求めて等重み平均する。いずれかの候補scoreが欠ける段階は部分平均を出さず、主指標を未定義として欠測を報告する。従来のlexical-present指標は副指標とする。同一validationを5回見るため到達時点と最大値は適応的な開発結果であり、未閲覧の最終確認とは呼ばない。層・正則化・停止規則は最初のfit前に別仕様で固定する。
主曲線のtrainは新規B1～B5の条件だけとし、旧96条件は含めない。旧REC/DONを使う場合は別の補助解析に分ける。
B1のtrain内で8系列のleave-one-series-out CVを行い、旧96条件と同じ6層×3個のCから系列外`role_swap_auc`が最大の1組を選ぶ。同点時は列挙順の早い層、小さいCの順とする。この組をB1～B5で固定し、G・Hの値で選び直さない。
