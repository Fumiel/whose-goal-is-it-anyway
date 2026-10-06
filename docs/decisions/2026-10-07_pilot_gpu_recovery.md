---
decision_id: RDR-2026-10-07-02
date: 2026-10-07
status: accepted
phase: after_post_gate_exploratory_continuation_technical_stop
test_set_status: not_created_or_inspected
affected_files:
  - src/goal_takeover/pilot/services.py
  - src/goal_takeover/pilot/runner.py
  - src/goal_takeover/pilot/report.py
  - src/goal_takeover/cli.py
  - data/schemas/pilot_run.schema.json
  - configs/experiments/banking_pilot_technical_recovery_v1.json
  - docs/experimental_protocol.md
  - docs/pilot_runner.md
  - PROJECT_STATE.md
supersedes: RDR-2026-10-07-01
related_decisions:
  - RDR-2026-10-01-03
  - RDR-2026-10-02-01
---

# GPU資源停止後の探索的pilot収集を再開する

## 判断範囲

2026-10-07、先行18件のclean成功2/6とゲート不合格を維持した探索的継続は、
実行順19～50の32件を完了した後、51番の残差取得で12 GiB上限により停止した。
51番の初回runには3回のモデル出力があり、旧規則の「最初の出力前の外部中断」には
該当しない。本RDRは、この**一件の資源上限による技術的失敗**に限って新run ID
`c051-a2`で再取得し、その後に凍結順の52～90を収集する例外を決める。
元の`c051-a1`、全stage bundle、先行監査・報告、標本freezeを変更しない。
先行ゲート、12 GiB、300秒、保存上限、総量上限、sample、payload、モデル、decode、
位置・Attentionの定義、即停止規則を維持する。別の技術停止が起きた場合は再び止める。

## 根拠と工学的な確認

旧runの失敗時の正確なpeakは保存されていない。保存済みの51番の4つのprefixを
同じモデル・量子化・`sdpa`、同じ残差hookとlast-query attention経路で読み直す
工学的な測定では、キャッシュ解放なしの2,313 token残差取得で
`max_memory_reserved=12.25 GiB`、`max_memory_allocated=9.48 GiB`だった。
各forward前に未使用CUDAキャッシュを解放した測定では、4 prefixの残差と
attentionの全36層取得が完了し、最大予約量は11.06 GiBだった。
これはモデル生成を再実行せず、既存token列で測定した資源診断である。
詳細は[工学計測記録](../experiment_logs/2026-10-07_c051_gpu_cache_measurement.md)に残す。

したがって取得直前に`torch.cuda.empty_cache()`を呼ぶ。per-conditionのpeak統計は
初期化し直さず、割当量と予約量の大きい方で12 GiBを引き続き照合する。
上限超過時は両方のpeak byte数を失敗bundleへ記録する。これは未使用の予約blockの
解放であり、prefix、層、値の定義、位置、token ID、評価を変えない。
後続の軌跡が長く、なお12 GiBを超えたら元の即停止を適用する。

## 再開の来歴と解釈

再開前に先行から50番までの50完了、51番の`actual_capture`失敗・3出力、
52～90未実行、旧拡張stageの`technical_stop`、旧manifestと本RDRのchecksumを検証する。
新runtime freezeは修正code commitと全source/config/schema checksumを固定する。
51番の新runは旧run ID・旧manifest checksum・本RDRのauthorization checksumを
記録し、旧runは`technical_failure`として保持する。旧拡張stageに追記せず、
別のimmutable recovery stageに40条件の結果と停止状態を保存する。

再試行の理由は測定の資源問題に限る。旧runの行動結果に基づく選択ではないが、
旧runにはモデル出力が3回あるため、51番の新軌跡を独立な反復や旧軌跡の続きと
扱わない。行動結果が変わった場合は両試行を併記し、主要な集計では事前に宣言した
最終試行だけを一条件として数え、旧試行も感度確認と来歴に残す。全90件の集計は
先行ゲート不合格後・技術停止後に得た探索的資料である。

Research Questionと仮説は維持するが、技術停止後の再試行を伴うため、
行動頻度の解釈は限定する。成功率や内部状態の確証的推定には使用しない。
Phase 2、主モデル採用、確認的testへの移行はこの再開だけでは認めない。
確認的testは未作成・未実行・未閲覧である。
