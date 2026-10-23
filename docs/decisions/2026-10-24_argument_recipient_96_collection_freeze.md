---
decision_id: RDR-2026-10-24-01
date: 2026-10-24
status: accepted
phase: phase2_development_before_recipient_96_model_collection
test_set_status: not_created_or_inspected
affected_files:
  - data/templates/phase2_argument_readout_96_v1.json
  - data/splits/phase2_argument_readout_96_v1.json
  - data/splits/phase2_argument_readout_96_v1.graph.json
  - configs/experiments/phase2_argument_readout_96_v1.json
  - docs/experimental_protocol.md
  - PROJECT_STATE.md
supersedes: null
related_decisions:
  - RDR-2026-10-22-03
  - RDR-2026-10-22-02
  - RDR-2026-10-14-01
  - RDR-2026-10-22-01
---

# Recipient内容probe用96条件の開発run収集仕様

## 判断と範囲

2026-10-24、研究者は会話で[96条件のレビュー草案](../phase2_argument_readout_96_condition_draft.md)にある24タスクの本文、4つの架空IBAN形式口座、REC/DONをdevelopment validation候補とする配分を「草案のまま採用」と回答した。この回答は確認的testの開始や主モデル・ドメインの正式採用ではない。草案を変更せず別versionの[条件宣言](../../data/templates/phase2_argument_readout_96_v1.json)へ複製し、安定したcondition IDと意味IDを付ける。原草案とその以前の版は保存する。

初回セットは正規ユーザー指示中の`send_money.recipient`内容だけを教師とする。条件由来の`argument_present`を使用し、実行結果、生成call、A～Dを教師にしない。user-to-assistant境界の受取人口座文字列前後と終端を取得し、候補口座ごとのreadoutの学習・未知系列validationを行う。tool出力IPI、引用・禁止、両recipient候補の対照はRDR-2026-10-22-03の後続セットとして維持する。

## 関係graphとsplit

条件本文・資料・候補口座を見直し、同一タスクの四条件を同じpairへ、各4タスクを意味系列へ接続する。INVは既存の請求書と二文書照合、REFは既存の友人返金、PRDは発注書照合、EXPは立替精算との近さから、既存pilot/v2を含むtrain側成分へ保守的に接続する。trainは64条件である。

RECは当期の単発送金を扱い、既存の予定取引更新とは操作・資料が異なる。DONの承認事業への資金移動は、EXPの経費精算と一般的な数値条件による選択を共有するが、目的、受益者、資料と送金判断規則が異なる。したがってRECとDONはそれぞれ独立したdevelopment validation成分とし、各16条件を割り当てる。候補口座の実値と短いrecipient/参照文の定型句は一部splitをまたぐが、タスク目的・資料・選択規則の近い言い換えとは扱わない。言い回しの既知性はvalidation内の4層で別に集計し、両方が新規のREC-4/DON-4を未知言い回しの主要診断とする。共有する定型句を未知語彙の証拠とは主張しない。

[正式graph](../../data/splits/phase2_argument_readout_96_v1.graph.json)は既存trainへのedgeと判断した非edgeを理由付きで記録し、[split manifest](../../data/splits/phase2_argument_readout_96_v1.json)は条件IDと連結成分を保持する。この判断はモデルrunの結果を見ずに行った。後続IPI条件とのedgeで成分が結合した場合、この96条件の既存runやsplitを遡及変更せず、新しい分割・解析上の扱いを別記録で判断する。

## 実行前条件と扱い

モデルとドメインは暫定Qwen3-8B int8 / AgentDojo Banking v1.2.2を使用する。決定論的decode、全条件1attempt、12 GiB GPUと0.05 GiB/条件の保存上限、技術停止時の停止、行動失敗の保持を[実行仕様](../../configs/experiments/phase2_argument_readout_96_v1.json)で宣言する。モデルrunの前に、native model-free対照、固定tokenizerでの位置と候補系列、最長入力のGPU/保存容量検査、clean Git commitに結び付いたruntime freezeを完了する。96件の人手監査は結果報告より前に行い、初回判断と裁定を別欄に保存する。

この決定はRDR-2026-10-22-03の初回セットを具体化するものであり、研究課題、仮説、確認的主解析、Phase 2終了条件を改訂しない。v1二文書の未監査runおよびpilot_onlyの90条件をprobe教師へ転用しない。96件だけでIPIでの目的採用やreadoutの一般化を示したとは扱わない。
