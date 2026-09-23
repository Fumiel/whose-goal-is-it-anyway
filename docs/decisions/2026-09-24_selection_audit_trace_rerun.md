---
decision_id: RDR-2026-09-24-05
date: 2026-09-24
status: accepted
phase: after_first_model_selection_execution_before_rerun
test_set_status: not_created_or_inspected
affected_files:
  - src/goal_takeover/selection.py
  - data/schemas/run.schema.json
  - docs/selection_audit.md
  - configs/selection/integration_gate.freeze.json
supersedes: RDR-2026-09-24-04
related_decisions:
  - RDR-2026-09-24-03
---

# 最終回答・生出力の欠落を補い、両候補を再実行する

## 発見と判断

初回選定run `banking-selection-20260924-001` は14 bundleを完了し、raw manifestの
checksum、設定、token位置、activation、系列採点に不整合はなかった。しかし
`messages.json`は最終assistant回答の直前で終わり、生成ステップの生出力も保存していなかった。
`user_task_7`は回答文を評価するため、保存された環境状態だけから自動判定を独立に
確認できない。14件のblind人手監査も完了していない。
証拠と検証範囲は[初回run監査](../experiment_logs/2026-09-24_banking_selection_first_run_audit.md)に記録する。

これは事前指定の監査を不可能にする保存上の欠陥である。初回runを編集・削除せず、
修正版runnerから**両モデルへ同じ7条件を新規run IDで再実行**する。
監査が済むまで初回runの選定判定は確定しない。

## 修正範囲と観測済み情報

修正は、測定用生成の生出力を`measurement_output.json`へ、実行loopの各生出力・
停止理由・評価器へ渡した最終回答を`model_output.json`へ保存し、最終回答がある場合は
`messages.json`末尾にも追加する。集計時にはこれらとprefixの対応を確認し、欠けたbundleを
監査完了扱いにしない。従来のrun schemaが選定用`metrics`とboundary token項目を
許さなかったため、実際の保存形式に合わせてschemaを補正した。

初回runの自動判定では8Bのclean成功3/5、4Bのclean成功2/5を既に見た。
この観測は欠陥の発見と監査不能性の説明にのみ用い、条件、閾値、分母、モデル候補、
decoding、tie-break、採用基準の変更には使っていない。保存修正は生成・評価器・
研究仮説を変更しない。確認的testは作成・閲覧していない。

## 再凍結

修正版runner、schema、テスト、監査手順、初回runの小型manifestを含む親commitは
`3e168324054bfe4d2ba907999bd78daec3fa2aa5`。新しい
[`integration_gate.freeze.json`](../../configs/selection/integration_gate.freeze.json)
にこのcommitを記録し、直後のcommitとして保存する。gate SHA-256
`e84db8e1ae1ca886004bde2e4a58cad7ef58705d204cb2151fed58c3a532b5df`、
sample SHA-256 `c5fb408b51ae6bef21b7b5fe6fea2eca0be4e93e2802e35000d98a430adee819`
は初回凍結から変わらない。モデル・ドメイン・除外設定のchecksumも変わらない。

親commitでunit test 54件、pytest 54件、compileall、Ruff lint・format、
設定検査、7条件preflightが通った。初回14件のrun recordは修正版schemaで検証を通った。
修正版でのGPU上の14件再実行とblind人手監査はこれから行う。
