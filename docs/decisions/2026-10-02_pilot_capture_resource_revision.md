---
decision_id: RDR-2026-10-02-01
date: 2026-10-02
status: accepted
phase: before_exploratory_pilot
test_set_status: not_created_or_inspected
affected_files:
  - configs/experiments/banking_pilot_detail_v1.yaml
  - docs/experimental_protocol.md
  - docs/banking_pilot_v1.md
  - docs/pilot_runner.md
  - PROJECT_STATE.md
supersedes: RDR-2026-10-01-03
related_decisions:
  - RDR-2026-09-22-01
  - RDR-2026-10-01-02
---

# PilotのAttention・詳細保存を実測に合わせて分離する

## 判断と部分改訂の範囲

2026-10-02、実行前のGPU/native計測後、研究実施者がAttention取得と詳細保存の
資源問題を解決する方針を承認した。`supersedes`はRDR-2026-10-01-03の
**固定prefix診断における内部状態保存と、詳細保存を各conditionの0.05 GiB枠へ
含める部分だけ**を改訂する。90条件のID・payload・順序、先行18、停止・移行規則、
通常conditionの300秒・GPU12 GiB・0.05 GiB、通常4.5 GiB・最大9 GiB、
test除外とnative/厳密判定は維持する。旧標本freezeとraw runは変更しない。

1. 通常pilotではQwen3の`sdpa`を維持し、`Tend_assistant`の最後のqueryから
   user goal・IPI・tool metadata範囲へのAttentionを各層・headで再計算・集約する。
   全token間の行列は通常生成しない。短い同一forward passで`eager`の
   last-query重みと照合し、全層・有限値・mask・prefix ID・GPU上限を確認する。
2. 先行12 IPIの固定prefix診断では、直列化済みprefix、token位置、候補系列全体の
   採点と整合を保存する。残差とAttentionは固定prefix診断では取得しない。
   実軌跡での残差・Attention取得は維持し、診断のスコアや成功件数を実軌跡へ混ぜない。
3. 通常pilotのIPI windowは左右16 tokenとし、`protocol_offsets_v1`を用いる。
   `full_sequence_condition_ids`と`full_sequence_attention_condition_ids`は空リストとする。
   通常の範囲集約Attentionと全層の選択位置・IPI window残差は保存する。
4. 全sequence・全層残差は、通常runを上書きせず、事前指定の四つの**固定prefix診断**から
   別のimmutable derived bundleへ取得する。条件は
   `banking_pilot_v1_4fb7f8324a191b52`、
   `banking_pilot_v1_4bcd2e89355ab958`、
   `banking_pilot_v1_0ec8e0587c4a88e7`、
   `banking_pilot_v1_196e79c78200e3c1`で、四task系列の先行IPI各一件である。
   選択は行動結果に依存しない。source bundleのchecksum、prefix ID、token列、
   model/tokenizer revisionと実行codeを検証し、source scopeを明記する。
   source prefixが欠けた場合は欠測として残し、別条件で置換しない。
   固定prefix詳細値を実軌跡の測定として扱わない。
5. 派生した全sequence残差には、通常runとは別に一取得1.5 GiB、四取得合計6 GiB、
   GPU12 GiB、各取得300秒の上限を置く。完全Attention行列の初回pilot保存は0件とし、
   通常の範囲集約値を優先する。後に完全行列が必要なら、目的・subset・資源・
   test閲覧状況を別RDRに記録する。

## 実測根拠

[2026-10-02の最初の計測](../experiment_logs/2026-10-02_pilot_preflight_measurements.md)では、
現行`sdpa`はweightsを返さず、`eager`の1,307 token集約passはGPU peak 13.39 GiBで
12 GiB上限を超えた。実prefix2,082 tokenの全層・全sequence残差は約585.6 MiBで、
通常条件の51.2 MiBに入らない。完全Attentionは372 tokenでも304.1 MiBだった。

修正した最後のqueryの計算は、同一`eager` forward passの全36層との比較で
重みの最大絶対差が`3.1e-5`だった。別passの`sdpa`/`eager`最終出力は量子化を含む
計算方式により異なったため、照合は同一passでも行う。実native固定prefix2,082 tokenで
左右16・32の通常取得はともに12 GiB以内だった。実モデルのcapture・採点と、
行動だけをscriptした一条件の工学bundleは、左右16で約37.85 MiB、46.76秒、
GPU peak 11.20 GiBだった。工学bundleの行動・marginは研究結果に使用しない。
詳細な測定値と検証の限界は別の実行前計測記録へ残す。

## 研究への影響と開始前gate

Research Question、仮説、主回帰、独立group、主モデルの暫定扱いは変更しない。
Attentionは引き続き補助的測定であり、重みだけから因果性を主張しない。
全sequence詳細値は固定prefix診断の探索・位置検証に限定し、実軌跡へ代用しない。
通常pilotの保存上限と詳細取得の保存上限を区別し、両方に来歴・checksumを付ける。

判断はpilotの新規モデル行動結果と確認的testを見ていない時点で行った。
pilot開始前には、Attention実装の全層検証、詳細派生経路のimmutable検証、
通常bundleの資源再計測、task 14の人手審査、cleanな実行commitと別runtime freezeを
完了する。モデル行動により条件を入れ替えたり、失敗runを上書きしたりしない。
