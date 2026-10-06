# 2026-10-07 post-gate探索的継続の技術的停止

## 来歴と実行範囲

[RDR-2026-10-07-01](../decisions/2026-10-07_banking_pilot_post_gate_exploratory_continuation.md)
に従い、先行18条件のclean成功2/6・元のゲート不合格を保持したまま、
`banking-pilot-001`の実行順19～90を探索的に収集開始した。
実行code commitは`b7df23f41b47b0eae529ebe261d46d41ab29701c`、
新runtime freezeは`artifacts/pilot-runtime-continuation.freeze.json`
（SHA-256 `1fce5812b554586c7887b2b925680c37ec28793345150614bfdb77bc794bea5b`）。
元のsample freeze、先行run、監査票、先行報告は変更していない。

## 停止した箇所

新規33条件を試行し、実行順19～50の32件が`completed`、51番
`banking-pilot-001-c051-a1`が`technical_failure`となった。
51番の失敗stageは`actual_capture`で、記録された例外は
`oom_or_resource_limit: peak GPU memory exceeds frozen ceiling`。
この条件は3回のモデル出力後に停止し、最後に完了したstageは`actual_generation`。
4番目の実軌跡prefixは2,313 tokenである。失敗bundleに保存された直前までの
GPU peakは11.664 GiBだが、**上限超過を検出した瞬間のpeak値は保存されていない**。
したがって超過幅を推測しない。

runnerは技術的即停止を実行し、`banking-pilot-001-expansion-status`の不変stage bundleに
`technical_stop`を記録した。全90条件の状態は`completed` 50、
`technical_failure` 1、`not_run` 39である。51番はモデル出力後の失敗なので、
元の「最初のモデル出力前の外部インフラ中断」に限る再試行例外に該当しない。
現行RDRとruntime freezeの下で自動再試行・再開はしない。

`load_records`による51 bundleのmanifest checksum照合は成功した。
現時点の機械集計は`artifacts/pilot-expansion-partial-report-2026-10-07.json`に保存したが、
拡張分の人手監査は未完了であり、この集計を最終研究結果と扱わない。
元の先行ゲートは引き続き不合格、Phase 2移行も未許可である。

## 次の判断に必要な事項

残り39件の実行と51番の再取得には、技術的停止後の収集範囲、再試行規則、
GPU資源上限、実行codeとruntime freezeの新versionを別RDRで決める必要がある。
資源上限の変更または工学的なメモリ削減を採る場合も、旧failure bundleを保持し、
新run IDから来歴をたどれるようにする。確認的testは未作成・未実行・未閲覧である。
