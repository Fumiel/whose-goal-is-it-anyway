# 活性化パッチングGPU事前確認の再実行（2026-11-14）

[前回の記録](2026-11-14_activation_patching_preflight.md)と
[実行手順](../phase2_activation_patching_runner.md)に続く、研究実施者の指示による再確認である。
研究実施者から「前回の実行中にMacとWSLとのSSH接続が切れており、それが長時間化の理由ではないか」と連絡があり、
同じコードと設定で事前確認を再実行した。本取得は引き続き行わない。

## 結果

トークナイザ事前確認は全240条件で再び合格した。
GPU事前確認は端末から切り離し、標準出力・標準エラーをWSL側の新規ファイルへ保存して再実行したが、
1条件目に**447.285秒**かかり、**300秒上限を再び超えたため不合格で停止**した。
前回より32.223秒（6.72%）短かったものの、時間超過は再現した。

| 項目（同じ1条件目） | 前回 | 今回 |
|---|---:|---:|
| 正常計算と90介入・再確認の合計 | 479.508秒 | **447.285秒** |
| 正常計算（第1パス） | 7.318秒 | 6.634秒 |
| 90介入と正常再確認（第2パス） | 472.191秒 | 440.651秒 |
| 1token順伝播の平均 | 0.147042秒 | 0.137091秒 |
| 最大GPUメモリ | 9.494176 GiB | 9.494176 GiB |
| self厳密一致 | 30/30 | 30/30 |
| G最終層の全語彙分布とdonorの一致 | ビット一致 | ビット一致 |
| キャッシュ復元の繰り返し | ビット一致 | ビット一致 |

対象はID昇順の`phase2_argrec672_015e0550742e5e29`（正準run番号c368）。
必要な正常計算を済ませ、1条件目の90介入・正常再確認と追加の復元検査を完了後、
時間上限超過を検出して停止した。追加の復元検査10.272秒は、表の上限判定対象とは別である。
2条件目の介入確認と本取得には進んでいない。

## 接続・出力の扱いと比較の限界

- 前回の接続断は研究実施者からの申告として記録する。接続断の正確な時刻と計算停止時間を追跡する記録は、今回の比較にはない。
- 今回は`nohup`と`setsid --wait`を使い、stdinを`/dev/null`、stdout/stderrをWSL側の新規ログへ向けた。
  モデルの計算内容・層・位置・donor・seed・採点方式・上限は変更していない。
- 端末への出力を分離した今回も300秒を超えたため、**SSH切断だけが前回の時間超過の原因だったとは確認できない**。
  これだけで前回の切断に影響がなかったことまで断定しない。
- 出力先の変更と接続状況を同時に変えた比較であり、32.223秒の差をSSH切断だけの寄与とはみなさない。
  bitsandbytesの型変換警告は抑制せず、そのファイル出力処理も測定に含まれる。GPUカーネルとCPU処理の寄与は未分離である。

## 実行commitと手順

再実行commitは`a332ee0`（前回の記録commit）で、クリーンな作業ツリーで実行した。
`git diff b1160c7 a332ee0 -- src configs`が空であることを確認した。コードや設定を修正してからの再実験ではない。

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m goal_takeover.phase2.activation_patching tokenizer-preflight configs/analysis/phase2_activation_patching_v1.json
set -o noclobber
nohup setsid --wait env PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m goal_takeover.phase2.activation_patching gpu-preflight configs/analysis/phase2_activation_patching_v1.json > artifacts/phase2-activation-patching-gpu-preflight-a332ee0.log 2>&1 < /dev/null
```

GPUはCUDAへアクセスできる制限外環境で実行した。環境は前回と同じPython 3.12.3、torch 2.10.0+cu128、
Transformers 4.57.6、bitsandbytes 0.50.2、CUDA 12.8、RTX 5060 Tiだった。
参照元のSHA-256も前回と一致した。今回保存した陽性対照の全語彙分布checksumと参照残差との差の指標も、前回の記録と一致した。
正常LD・delta・介入効果は集計・記録していない。

## 不変の出力

| 出力 | 状態 | bytes | SHA-256 |
|---|---|---:|---|
| [tokenizer-preflight-a332ee0](../../artifacts/phase2-activation-patching-tokenizer-preflight-a332ee0.json) | passed | 123078 | `1d3690f38e66fff212c4b45fc71ee63920d775383f6a05a6f01e2013715a10f5` |
| [gpu-preflight-a332ee0](../../artifacts/phase2-activation-patching-gpu-preflight-a332ee0.json) | failed | 70238 | `a43a0fb52ecabd2c8425d29d8df0f94e59e25a4399d0855a20e48de44e8901e1` |
| [WSL側の実行ログ](../../artifacts/phase2-activation-patching-gpu-preflight-a332ee0.log) | 終了コード1 | 74393269 | `185de973f5982eaefaf9e6d257af137bb8827bb6061d774ba38cac892abbb10d` |

前回のGPU失敗レポートのSHA-256は引き続き`0e01241807921da10f1734450dc9a165c43a17549ecaa7a647e2b59418ad8bdd`で、上書きしていない。
新しい出力も以後は読み取り専用の記録として保持する。

今回の時間を240条件へ単純外挿すると約29.82時間（約30時間）となる。1条件だけの工学測定による外挿で、
全条件の完走時間の保証ではない。現在の300秒上限は満たしておらず、設定の変更や本取得の起動はしていない。
この記録によってH2/H3の研究結果や、パッチング開始期限の達成を主張しない。
