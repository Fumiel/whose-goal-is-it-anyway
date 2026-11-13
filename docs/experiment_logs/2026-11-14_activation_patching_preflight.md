# 活性化パッチングの実装・GPU事前確認（2026-11-14）

[仕様](../phase2_activation_patching_spec.md)、[実装指示書](../phase2_activation_patching_implementation_brief.md)、
[実行手順](../phase2_activation_patching_runner.md)、
[RDR-2026-11-14-03](../decisions/2026-11-14_patching_preimplementation_review_corrections.md)に従う。
研究実施者はコード実装からGPU事前確認までを指示し、本取得はまだ行わないよう明示した。

## 結果と現在のゲート

コード実装と合成テストは完了した。トークナイザ事前確認は全240条件で合格したが、
GPU事前確認は1条件目が**479.508秒**かかり、凍結予定の**300秒上限**を超えたため不合格で停止した。
自己置換・陽性対照・キャッシュ復元の一致と12 GiBメモリ上限は満たした。

先頭2条件と必要な追加donor4条件の正常計算を行った後、1条件目の90介入と正常再確認、追加の繰り返し確認を行った。
2条件目の介入確認には進んでいない。失敗レポートを新規ファイルとして保持した。
本取得のrun bundleは0件、runtime freeze・環境lockの新規作成と、パッチング解析・局所文言ベースラインの本実行は行っていない。
この記録は工学的な事前確認であり、介入効果やH2/H3に関する研究結果ではない。

## 実装と品質チェック

実装commit：`b1160c7`（`Implement train-only activation patching and preflight controls`）。
両事前確認はこのクリーンなcommitで実行した。

- `activation_hooks.py`に独立した`ResidualPatch`を追加。既存`ResidualCapture`は変更していない。
  出力をcloneして1位置だけを書き換え、captureフックより先に置換フックを登録する。
- `activation_patching.py`に入力・donorの照合、逐次採点、事前確認、freeze、明示的な本取得・解析コマンドを実装した。
  `local_wording_baseline.py`は既存`text_scores`を呼び、口座直前の窓だけを特徴とする。
- prefixは未使用logitsを抑えるため`logits_to_keep=1`、suffixは全18位置のlogitsを取得する。
  口座の残りは1tokenずつ採点し、`DynamicCache.crop()`で候補間・介入間にキャッシュを戻す。
- recipient先頭の専用helperを追加し、既存serializer・旧入力・旧run・freeze・manifestは変更していない。
- 既存の実装指示書はPython記述例の改行・空行だけをruffに合わせた。仕様の意味は変更していない。

品質チェックは以下のとおり成功した。

| 検査 | 結果 |
|---|---|
| 標準Pythonのunittest discover | 304件、成功（追加依存がない検査72件はskip） |
| compileall（src・tests） | 成功 |
| ruff check / format --check（全体） | 成功 |
| pytest | 304件成功、39 subtests成功 |
| git diff --check | 成功 |

新規27テストには、対・donorの整合性、口座token境界、正規化効果・破壊判定・対応づけ、
自己置換、キャッシュ復元、候補間の独立性、全語彙の陽性対照、異なるprefix長の対、
合成bundleの保存・再開・読み戻し・解析、第1パスの失敗保存、局所文言のfold分離を含む。
これらは小さい合成モデル・一時ディレクトリによる検査であり、本取得データではない。

## 実行と来歴

固定revisionのローカルキャッシュを使い、ネットワーク取得を避けて実行した。
GPU処理はCUDAへアクセスできる制限外環境で実行した。

```bash
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m goal_takeover.phase2.activation_patching tokenizer-preflight configs/analysis/phase2_activation_patching_v1.json
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m goal_takeover.phase2.activation_patching gpu-preflight configs/analysis/phase2_activation_patching_v1.json
```

環境：Python 3.12.3、torch 2.10.0+cu128、Transformers 4.57.6、bitsandbytes 0.50.2、CUDA 12.8、
NVIDIA GeForce RTX 5060 Ti。モデルは暫定Qwen3-8B int8、bfloat16、sdpaで、設定・revisionは既存freezeとの一致を確認した。

| 不変の事前確認レポート | 状態 | bytes | SHA-256 |
|---|---|---:|---|
| [tokenizer-preflight-b1160c7](../../artifacts/phase2-activation-patching-tokenizer-preflight-b1160c7.json) | passed | 123078 | `a0211bfecda063036505e154ab2919e5883c6a6b06702fc93ec2dd7305963cd9` |
| [gpu-preflight-b1160c7](../../artifacts/phase2-activation-patching-gpu-preflight-b1160c7.json) | failed | 70240 | `0e01241807921da10f1734450dc9a165c43a17549ecaa7a647e2b59418ad8bdd` |

トークナイザレポートには全240条件の元bundleのmanifest SHA-256と固定donor表を記録した。
GPUレポートには正常LD・delta・matched/crossの効果を記録していない。
凍結済み宣言全体の整合性検査では検証宣言192条件を読み、検証側run bundleの読み込みと分析利用は0件である。

## GPU測定の内訳

対象：`phase2_argrec672_015e0550742e5e29`（ID昇順の1条件目、元の正準run番号c368）。

| 項目 | 実測 |
|---|---:|
| 正常計算（第1パス） | 7.318秒 |
| 90介入と正常再確認（第2パス） | 472.191秒 |
| 上限判定対象の合計 | **479.508秒** |
| 追加のキャッシュ復元検査 | 11.046秒（上記と別） |
| 最大GPUメモリ | **9.494176 GiB** |
| self厳密一致 | **30/30セル** |
| G・層35の全語彙分布とdonorの一致 | **ビット一致** |
| 同じmatched介入を2回行った一致 | **ビット一致** |

上限チェックは条件の計算完了後に超過を検出し、2条件目の介入前に停止した。
GPUレポートは`condition time ceiling exceeded`を失敗理由として保存している。

第2パスはprefix 1回、18tokenのsuffix 91回、1token採点3,094回。
順伝播の実測時間はそれぞれ0.628秒、15.314秒、454.947秒で、1token採点の平均は約**0.147秒/回**だった。
bitsandbytesからbfloat16→float16変換の警告が行列演算ごとに大量に出た。
この測定は警告の出力処理を含み、その寄与と量子化カーネルの所要時間は切り分けていない。

計算経路の差として保存済みps-002と比べた108ベクトルは0件がビット一致、最大相対L2差は0.145930だった。
Gの4候補の数字の対数確率はビット一致せず、最大絶対差は0.5だった。
この比較は仕様どおり記録のみとし、不合格理由には用いていない。

## 時間見積もりの更新と次の制約

前回の約11〜21時間という予測で仮定した1token計算0.05〜0.09秒に対して、今回の実測は約0.147秒だった。
1条件の合計を240倍する単純外挿は**約31.97時間（約32時間）**となる。
これは1条件だけの工学測定による外挿で、全条件の完走時間や上限を保証しない。
現在の300秒上限では、この経路の本取得は開始可能な状態ではない。

時間上限を緩めたり、候補を一括採点へ戻したり、位置・層・donor・閾値を変えたりはしていない。
速度改善や上限の再検討は、この失敗記録を保持したうえで別途判断する。
追加のGPU確認・本取得を自動で起動しない。コードを変更する場合は新しいcommitと事前確認レポートを作る。
この記録のcommit後も、事前確認レポートが対象とする実装commitは`b1160c7`のままであり、
現在のHEADでのruntime freezeへ読み替えない。
