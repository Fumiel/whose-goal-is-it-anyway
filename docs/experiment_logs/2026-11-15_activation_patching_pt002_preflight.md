# pt-002前のパッチング事前確認（2026-11-15）

[RDR-2026-11-15-01](../decisions/2026-11-15_patching_capture_recovery_and_retry.md)の段階Aにあたる記録。
研究実施者の指示「mainと統合してから事前確認を行う」に従い、作業ブランチを`main`へ統合した。
統合後のclean commit **`0b99c17`**（`0b99c178ba374489f99fdd6d634add0ff465bd77`）で、
トークナイザ事前確認とGPU事前確認を新規レポートへ実行した。**両方とも合格**した。

これは工学的な合格であり、介入効果やH2/H3に関する研究結果ではない。
正常LD・delta・介入効果は集計・閲覧していない。runtime freeze、環境lock、`pt-002`本取得はまだ行っていない。

## 統合

`patching-capture-diagnostics`（`1de1e04`停止調査、`8ababec`診断記録とログ制限、`e5b5508` RDR-2026-11-15-01と再試行経路）を、
`main`（`bee8d53`、600秒での事前確認記録）へ`--no-ff`で統合した。衝突はなかった。
マージコミットでは、PROJECT_STATEの「未統合」とする一文だけを更新した。
統合後の品質チェックはunittest 313件、compileall、ruff check、ruff format --check、pytest 313件・39 subtestsがすべて成功した。

## 結果

| 対象 | 正準run番号 | 2パス合計 | donor正常計算 | 介入と再確認 | 1token順伝播の平均 | 最大GPUメモリ | self | 陽性対照 | キャッシュ復元 |
|---|---|---:|---:|---:|---:|---:|---|---|---|
| `phase2_argrec672_015e0550742e5e29` | c368 | **422.480秒** | 6.368秒 | 416.111秒 | 129.4 ms | 9.494176 GiB | 30/30一致 | ビット一致 | ビット一致 |
| `phase2_argrec672_01c86b60e6c4fe0e` | c144 | **419.369秒** | 5.238秒 | 414.130秒 | 128.8 ms | 9.749942 GiB | 30/30一致 | ビット一致 | ビット一致 |

donor群別の時間はmatched・self・crossとも約136〜137秒でそろっていた。
追加のキャッシュ復元検査は上記とは別に9.727秒・9.694秒、追加donor4条件の正常計算は各5.1〜5.2秒だった。
トークナイザ事前確認は全240条件で合格した。

## 観察項目（合否には使わない）

| 項目 | `76e538a`（2026-11-14） | `0b99c17`（今回） |
|---|---:|---:|
| 2パス合計 | 457.875秒 / 455.198秒 | 422.480秒 / 419.369秒（約7.8%短縮） |
| 1token順伝播の平均 | 140.3 ms / 139.9 ms | 129.4 ms / 128.8 ms |
| 実行ログ | 144,157,344 bytes | 917 bytes、6行 |

- ログ制限：型変換メッセージは1回だけ出力され、1,695,959回を抑制した。
- ホスト記録（介入段階の開始時・終了時）：MemAvailable 8.74〜8.77 GiB、swap使用量0、
  パッチング用PythonのVmRSS 2.02 GiB（2条件で変化なし）、memory pressureの`some avg60`は0.29以下。
- 新レポートの単純外挿（長い方×240）は101,395秒、約**28.2時間**。全条件の完走時間の保証ではない。

時間の短縮は、ログ制限の導入と環境の再起動のあとに観察された。
どちらの寄与かは分離していないため、短縮の原因をどちらかに断定しない。
`pt-001`本取得の約508秒との差（約17%）も、同じ理由で原因を確定しない。
最大値422.5秒は600秒上限の約70%で、RDR-2026-11-15-01の監視基準570秒とも十分に離れている。

## 実行方法

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m goal_takeover.phase2.activation_patching tokenizer-preflight configs/analysis/phase2_activation_patching_v1.json
set -o noclobber
nohup setsid --wait env PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m goal_takeover.phase2.activation_patching gpu-preflight configs/analysis/phase2_activation_patching_v1.json > artifacts/phase2-activation-patching-gpu-preflight-0b99c17.log 2>&1 < /dev/null
```

GPU事前確認は端末から切り離し、WSL側の新規ログへ保存した。終了コードは0。
実行中に追跡対象のファイルを変更していない。
環境はRTX 5060 Ti（開始前のGPU使用量993 MiB・利用率0%）、Windows・Mac再起動後のWSLで、
開始前のMemAvailableは約10.3 GiB、swap使用量0だった。

## 出力

| 出力 | 状態 | bytes | SHA-256 |
|---|---|---:|---|
| [tokenizer-preflight-0b99c17](../../artifacts/phase2-activation-patching-tokenizer-preflight-0b99c17.json) | passed | 123078 | `aa6774ce3d374a293be96f7afb96e689cafb1e925f736a4d62efca88c41c2b63` |
| [gpu-preflight-0b99c17](../../artifacts/phase2-activation-patching-gpu-preflight-0b99c17.json) | passed | 93053 | `a2f52c7beb5bd08f28b1290eaac75b24b57fffd0ebedc8c1259ef2866764da24` |
| [WSL側実行ログ](../../artifacts/phase2-activation-patching-gpu-preflight-0b99c17.log) | 終了コード0 | 917 | `9aad2e6b4bfbe55fecdb6ba9d05f07d614bdea8c49685f4a42486ac8a007fa63` |

レポートが記録した設定・仕様のSHA-256は、analysis config `b1490f50c938cdaccda523c9eea2c4220086ddce9b1431dd4e5b2aa4f8198ed2`、
spec `64ac4f67345fbffc66e09fde351319b21035fa863d082ed6e851cc8449a6fc16`。
旧事前確認レポート・`pt-001`の49 bundle・旧freezeは変更していない。

## 次の手順（未実施）

RDR-2026-11-15-01の実行順序3・4にあたる。研究実施者の指示を受けてから行う。

1. 同じcommit `0b99c17`で環境lockを新規作成し、runtime freezeを作成する。
   このログを保存するcommitは別のHEADになるため、freezeは`0b99c17`のcheckoutで作る。
2. `pt-002`本取得を起動し、最初の20件を監視する。
