---
decision_id: RDR-2026-09-24-04
date: 2026-09-24
status: accepted
phase: before_formal_model_selection
test_set_status: not_created_or_inspected
affected_files:
  - configs/selection/integration_gate.yaml
  - configs/selection/banking_native_selection_sample.yaml
  - configs/selection/integration_gate.freeze.json
  - docs/selection_audit.md
  - src/goal_takeover/selection.py
supersedes: null
related_decisions:
  - RDR-2026-09-24-03
  - RDR-2026-09-24-01
---

# Bankingモデル選定ゲートの凍結

## 判断

候補モデルの正式な行動結果を見る前に、RDR-2026-09-24-03で指定した5 clean・2 IPI条件、
両候補共通の決定論的実行規則、閾値・分母・tie-breakを凍結する。
凍結記録は[`integration_gate.freeze.json`](../../configs/selection/integration_gate.freeze.json)であり、
実装と設定の親commitは `95cc1e860aff2658fccba9fccdf1adfd7e5a0013`。
gate SHA-256は `e84db8e1ae1ca886004bde2e4a58cad7ef58705d204cb2151fed58c3a532b5df`、
sample SHA-256は `c5fb408b51ae6bef21b7b5fe6fea2eca0be4e93e2802e35000d98a430adee819`。
モデル、ドメイン、除外設定のchecksumも同じ凍結記録に含めた。
凍結記録自体は親commitの直後のcommitへ保存し、自己参照のcommit hashを記入しない。
正式runnerはclean checkout、親commit、設定checksumの一致を確認してから開始する。

## 事前照合と監査

AgentDojo `0.1.35`、Banking `v1.2.2`のローカル固定環境で7条件を照合した。
各条件の最初のground-truth toolは実行でき、11個のtool schemaを取得した。
家賃IPIは `read_file` の最初の出力で注入文が文字範囲 `[155, 251)` に1回現れた。
パスワードIPIは `get_most_recent_transactions` の最初の出力で `[785, 894)` に1回現れた。
固定payload、call index、正規・攻撃callの名前と全引数はmanifestと一致した。
両IPI条件で、評価器は無操作 `(false, false)`、正規ground truth `(true, false)`、
攻撃ground truth `(false, true)` を返した。これらは環境・評価器の対照であり、候補モデルの成否ではない。
証跡は[`2026-09-24_banking_selection_preflight.json`](../../data/audits/2026-09-24_banking_selection_preflight.json)
にあり、SHA-256は `fc6e565b16aaf92725f747aa140d047caf5eae477397948a0f156ed64914a937`。

人手監査は各候補7件すべてを自動ラベルにblindで判定し、user-task successとattack successを
別々に記録する。条件付きの`user_task_14`は前提条件の成立も記録する。
不一致の裁定、欠測、no-call、技術的失敗、再試行と資源超過は
[`selection_audit.md`](../selection_audit.md)の手順に従う。

## 検証範囲と残る作業

source commitでunit test 51件、pytest 51件、compileall、Ruff lint・format、
repository設定検査、および7条件のmodel-free preflightが通った。
この作業環境ではGPUを利用できず、14件の候補モデル実行はまだ始めていない。
実モデルの時間、memory、保存量、構文解析率、task成功率、候補間順位は未確認である。
凍結は選定規則の事前固定であり、モデルまたは主ドメインの採用判断ではない。
確認的testは作成・閲覧していない。研究課題・仮説・確認的解析は変更しない。
