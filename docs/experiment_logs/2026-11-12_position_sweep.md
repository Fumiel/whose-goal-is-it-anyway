# 位置スイープ・手順3（2026-11-12）

[固定仕様](../phase2_position_sweep_spec.md)、[実行手順](../phase2_position_sweep_runner.md)、
[RDR-2026-11-06-01](../decisions/2026-11-06_argument_selection_timing_course_correction.md)と
[実装前修正](../decisions/2026-11-12_position_sweep_preimplementation_corrections.md)に従う。
研究実施者がGPU事前確認・取得・解析本実行を指示した。結果閲覧後のtrainのみの探索的診断であり、
独立検証、確認的test、選択時点の因果的な証明として扱わない。

## 事前確認

取得commitは`67c5492f4eb188277fb56678cbd8664f254be15f`、作業ツリーはクリーン。
同commitの新規レポートを`artifacts/phase2-position-sweep-*-67c5492.*`に保存した。

- トークン化：240条件すべてでprefix不変、GBと数字の1 token分割、S/G共通、口座露出回数、提示順と対内口座の一致を確認。
  Sのtoken IDは330（` "`）、Gは5381（`GB`）。検証行の読み込みは0。
- 書き出し：112件すべてにsend_moneyを含む生成があり、112/112が指定文字列に一致。不一致率0。
  生成テキストだけを確認し、条件・成否・評価結果は読んでいない。
- GPU：先頭2条件で非有限値なし。最大9.253327 GiBで12 GiB上限内。
  `logits_to_keep=3`による取得を確認。
- 環境：Python 3.12.3、torch 2.10.0+cu128、Transformers 4.57.6、bitsandbytes 0.50.2、
  CUDA 12.8、NVIDIA GeForce RTX 5060 Ti。制限環境内ではCUDAが見えず、制限外で利用可能だった。
  GPU処理は制限外で行った。

T残差の正準キャプチャとの差は次のとおり。仕様9節のとおり停止条件にせず、差を記録して取得した。
差は小さいとは扱わず、Tを手順1の独立な再現とも扱わない。

| 条件ID | 層別最大絶対差の最大 | 層別相対L2差の最大 | GPU GiB | 秒（モデル読込後） |
|---|---:|---:|---:|---:|
| phase2_argrec672_015e0550742e5e29 | 10.0 | 0.149533 | 9.252274 | 2.007958 |
| phase2_argrec672_01c86b60e6c4fe0e | 40.0 | 0.164676 | 9.253327 | 0.794772 |

各36層の値はGPU事前確認レポートに保存した。入力の延長とint8の数値計算を伴う再測定である。
bitsandbytesはbfloat16入力を内部でfloat16へcastする警告を出したが、非有限値・技術失敗はなかった。
ローカル実装にはsequenceを行に展開した後の外れ値列処理があり、後続tokenを含む一括計算の
量子化処理が早い位置の値に影響し得る点も解釈上の留保とする。
今回の事前確認だけではT差の原因や、送金先の数字Dが先行位置に与える影響を特定していない。
注意maskの因果性だけから、int8一括計算の先行位置が後続入力に完全に不変とは断定しない。
設定変更や追加GPU比較は行っていない。

## Runtime freezeと取得

環境lockは`artifacts/phase2-position-sweep-environment-67c5492.lock`に新規作成した。
新freezeは`artifacts/phase2-position-sweep-runtime-67c5492.freeze.json`。
既存freeze・既存runは変更していない。

[取得manifest](../../data/manifests/2026-11-12_phase2_position_sweep_ps001_collection.json)に
240件すべてのrun ID、条件ID、pair ID、正準manifestと新manifestのSHA-256、資源値を記録した。
同じmanifestは事前確認・環境lock・runtime freezeのchecksumも保持する。

- 240条件・120対、全件completed。技術失敗0、自動再試行0。
- 検証側の条件・残差の読み込み0。
- 全artifactのchecksum、条件の一致、正準prefixのchecksum、入力token列のchecksumとprefix不変を照合。
- 全36層、`[1,6,4096]`、bfloat16、全値有限、位置順A1/A2/T/S/G/Dを照合。
- 合計432,515,414 bytes（約432.5 MB）。総量2 GiB、各条件0.05 GiBの上限内。
- 最大GPUメモリ9.268343 GiB。1条件の最大16.755459秒（初回のモデル読込を含む）。
- 取得照合完了は2026-11-11 17:25:47 UTC（2026-11-12 JST）。

## 解析前の記録

このログと取得manifestを別commitに保存してから、固定設定の解析を一度実行する。
解析コード・設定・仕様は取得commitから変更していない。
BLASの3環境変数を1に固定し、取得時runtime freezeを参照する。
位置ごとのp値は42判定セル全体の最大統計量で補正する。
この段階ではprobe fit・p値計算・R判定は未実行である。
