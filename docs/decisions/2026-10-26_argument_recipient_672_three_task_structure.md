---
decision_id: RDR-2026-10-26-06
date: 2026-10-26
status: accepted
phase: phase2_argument_recipient_672_task_text_draft
test_set_status: not_created_or_inspected
affected_files:
  - src/goal_takeover/datasets/argument_recipient_672_draft.py
  - data/templates/phase2_argument_recipient_672_draft.json
  - tests/test_argument_recipient_672_draft.py
  - docs/phase2_argument_recipient_672_task_text_draft.md
  - docs/experimental_protocol.md
  - docs/decisions/README.md
  - PROJECT_STATE.md
supersedes: RDR-2026-10-26-05
related_decisions:
  - RDR-2026-10-26-01
  - RDR-2026-10-26-02
  - RDR-2026-10-26-03
  - RDR-2026-10-26-04
---

# 672条件の3タスク構造と文型規模の採用、タスク本文草案の生成

## 判断と部分改訂の範囲

2026-10-26、研究実施者はタスク本文の実装に先立ち、[改訂版草案v1](../phase2_argument_recipient_672_review_draft_v1.md)のうちRDR-2026-10-26-05で採否未決だった次の点を採用した。

1. **規模と構造（v1 §4）**: 学習40系列・検証16系列、各系列3タスク・各タスク4条件、学習480＋検証192＝672条件。学習曲線は8系列・96条件のバッチ（v1 §5.3のB1～B5）で累積96～480条件とする。金額・件名・日付は資料または指示に明記し、計算を要求しない。Uシリーズは3タスクを`U0`・`UN`・`UI`とし、候補以外の名前・IDを0・1・2個置く。Dシリーズは`D1`・`D1M`（複数項目の資料から指示で指定した項目の口座）・`D2`（請求書と支払先登録簿の照合）とする。
2. **言い回しの規模（v1 §9の文型部分）**: recipient文と参照文を、ユーザー指示用・資料用それぞれ学習16種類＋検証専用8種類とする。参照文の語義は自分の支払元口座、照合台帳、過去の取引記録上の自分の口座、明細・領収書の保管口座の4種とし、「別件の受取口座」型は使わない。

`supersedes`は、RDR-2026-10-26-05が上記2点を未採用とした箇所と、RDR-2026-10-26-01の「25＋10系列×各5タスク＝500＋200条件、100条件刻み」の規模・刻みだけを部分改訂する。RDR-01の未知系列AUROC 0.80基準と主指標、RDR-02～04の5規則・4条件・露出後ラベル・混合曲線、RDR-03の交差方針、RDR-05のファミリー分離・旧REC/DON算入・LLM監査方針は維持する。

v1の表の不整合（F3がファミリー表ではD、バッチ表ではU）は、各バッチをU5・D3に保つため**F3をUシリーズ**とした。

## 生成した草案と未採用・未凍結の事項

研究実施者の依頼で、Claude Code（claude-opus-5-5）が全56系列・168タスク・672条件の英語本文、資料、条件由来ラベル、正規`send_money`、露出境界を[生成コード](../../src/goal_takeover/datasets/argument_recipient_672_draft.py)で作成し、[レビュー草案JSON](../../data/templates/phase2_argument_recipient_672_draft.json)と[説明文書](../phase2_argument_recipient_672_task_text_draft.md)を置いた。題材・支払先名・金額・指示文は架空であり、**研究実施者のレビュー前の草案**である。

次は引き続き未採用または未凍結である: `role_swap_auc`主指標、教師強制prefixと実走行標本の二系統取得、取得位置、段階0、ファミリー除外CV、検証のモニタリング／留保配分、日程・停止規則、関係graph、split manifest、native evaluator登録、model-free・tokenizer preflight、LLM監査仕様、runtime。現行`argument_probe`は資料由来の正例を露出検査で扱えないため、Dシリーズのfit前に拡張と合成fixture検査が要る。

## 根拠、時点と限界

3タスク構造は、5タスクの変動が金額計算に偏りprobeラベルと無関係だったというクロスチェック指摘（v1 §1・§4）による。40＋16系列に5タスクを当てると1120条件となりRDR-01の枠を超えるため、研究実施者は3タスク構造を選んだ。判断は旧96条件の結果閲覧後、確認的test未作成・未閲覧の時点の開発上の設計変更であり、性能改善の実証ではない。候補口座ごとの正例・参照例数は各バッチと検証で均衡させたが、source別には最大6条件の差がある。系列名56とファミリー10は題材候補であり、独立成分数は関係graph監査後に数える。旧96条件の宣言・run・audit・probe結果は変更しない。
