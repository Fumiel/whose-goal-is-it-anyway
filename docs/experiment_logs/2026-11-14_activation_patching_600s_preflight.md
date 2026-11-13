# 600秒上限でのパッチング事前確認（2026-11-14）

[RDR-2026-11-14-04](../decisions/2026-11-14_patching_time_limit_revision.md)、
[仕様](../phase2_activation_patching_spec.md)と[実行手順](../phase2_activation_patching_runner.md)に従う。
研究実施者は、時間上限の変更をRDRに記録してコミットした後、GPU事前確認を再実行するよう指示した。
本取得は引き続き行わない。

## 結果

時間上限を1条件300秒から600秒へ変更し、改訂commit **`76e538a`** のクリーンな作業ツリーで、
トークナイザ事前確認とGPU事前確認を新規実行した。**両方とも合格**した。

| 対象 | 正準run番号 | 所要時間（2パス合計） | 最大GPUメモリ | self | 陽性対照 | キャッシュ復元 |
|---|---|---:|---:|---|---|---|
| `phase2_argrec672_015e0550742e5e29` | c368 | **457.875秒** | 9.494176 GiB | 30/30一致 | 全語彙分布ビット一致 | ビット一致 |
| `phase2_argrec672_01c86b60e6c4fe0e` | c144 | **455.198秒** | 9.749942 GiB | 30/30一致 | 全語彙分布ビット一致 | ビット一致 |

両条件とも600秒・12 GiBの上限内だった。旧300秒の失敗レポートはそのまま保持し、合格へ書き換えていない。
これは改訂後の運用条件での工学的合格であり、介入効果やH2/H3に関する研究結果ではない。
先頭2条件の合格は、全240条件の時間・メモリ上限を保証しない。

## 変更とコミットの順序

1. RDR-2026-11-14-04を作成し、パッチングの時間上限だけを600秒へ具体化した。
   観測した最大約480秒に25%の余裕を置いた値である。
2. 仕様・プロトコル第19節・実装指示書・実行手順・設定をそろえ、境界値テストを600秒で成功、600秒超で失敗するものへ更新した。
3. 品質チェックを通し、`76e538a`（`Raise exploratory patching time limit to 600 seconds under RDR-04`）へコミットした。
4. そのcommitでトークナイザ事前確認、GPU事前確認の順に実行した。実行中に追跡対象ファイルを変更していない。

設定の差分が`resources.maximum_seconds_per_condition: 300 -> 600`だけであることを確認した。
計算コードは変更していない。位置・層・donor・seed・逐次採点・科学的な判定閾値、GPU/容量上限は維持する。
元のpilot・672条件収集の上限や、既存freeze・runは変更していない。

品質チェックは標準Pythonのunittest 304件（72 skip）、compileall、ruff check、ruff format --check、
pytest 304件・39 subtests、git diff --checkが成功した。

## 実行方法と環境

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m goal_takeover.phase2.activation_patching tokenizer-preflight configs/analysis/phase2_activation_patching_v1.json
set -o noclobber
nohup setsid --wait env PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m goal_takeover.phase2.activation_patching gpu-preflight configs/analysis/phase2_activation_patching_v1.json > artifacts/phase2-activation-patching-gpu-preflight-76e538a.log 2>&1 < /dev/null
```

GPU処理はCUDAへアクセスできる制限外環境で実行した。SSH端末への出力を分離し、WSL側の新規ログへ保存した。
モデルとtokenizerは固定revisionのローカルキャッシュを使用した。
環境はPython 3.12.3、torch 2.10.0+cu128、Transformers 4.57.6、bitsandbytes 0.50.2、CUDA 12.8、RTX 5060 Ti。
暫定Qwen3-8B int8、bfloat16、sdpa、seed 20261027と逐次採点は従来どおりである。

トークナイザ確認は全240条件で合格した。GPUは先頭2条件と必要な追加donor4条件の正常計算を行い、
その後、各対象の90介入・正常再確認と追加の復元検査を行った。検証側の宣言192条件は整合性検査だけに読み、
検証run bundleの読み込みと分析利用は0件である。正常LD・delta・介入効果は集計・記録していない。

## 時間の内訳

| 項目 | 1条件目 | 2条件目 |
|---|---:|---:|
| donor正常計算 | 6.847秒 | 5.625秒 |
| 90介入と正常再確認 | 451.028秒 | 449.573秒 |
| 追加のキャッシュ復元検査（上記と別） | 10.479秒 | 10.406秒 |
| 1token順伝播の平均 | 0.140337秒 | 0.139885秒 |

新しいレポートは、長い方の所要時間を240倍した単純外挿として109,889.986秒、約**30.52時間**を記録した。
これは先頭2条件の工学測定からの見積もりで、全条件の完走時間の保証ではない。
型変換警告の出力と計測処理は従来どおり含まれ、速度改善を施した結果ではない。

## 不変の出力と未実行事項

| 出力 | 状態 | bytes | SHA-256 |
|---|---|---:|---|
| [tokenizer-preflight-76e538a](../../artifacts/phase2-activation-patching-tokenizer-preflight-76e538a.json) | passed | 123078 | `40db4c249024b3b980b89edac2539dfdadac43e459144cf7015d96dfb02a26ae` |
| [gpu-preflight-76e538a](../../artifacts/phase2-activation-patching-gpu-preflight-76e538a.json) | passed | 88119 | `9c67f2b6bfd981c5f004ea16c1823e9e8e402b44a7c4cba89e41c3b180e6908b` |
| [WSL側実行ログ](../../artifacts/phase2-activation-patching-gpu-preflight-76e538a.log) | 終了コード0 | 144157344 | `d42e32ca9daa26ef3b81aea48fa43738f2d02ab7bc9f26b3cb172ade80099aeb` |

[初回失敗](2026-11-14_activation_patching_preflight.md)と[再確認失敗](2026-11-14_activation_patching_preflight_recheck.md)のレポート・ログは保持した。
本取得のrun bundleは0件で、runtime freeze・環境lockの作成、パッチング解析、局所文言ベースラインの本実行は行っていない。
この事前確認はパッチング本取得の開始ではなく、2026-11-20の開始期限を満たしたとは扱わない。
将来のruntime freezeは実行commit`76e538a`と対応する必要があり、本記録を保存した後の別HEADへ読み替えない。
