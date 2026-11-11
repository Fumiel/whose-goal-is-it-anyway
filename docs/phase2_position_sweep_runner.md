# 手順3：位置スイープの実行手順

正本は[仕様](phase2_position_sweep_spec.md)と[実装指示書](phase2_position_sweep_implementation_brief.md)。
2026-11-12の[実装前修正](decisions/2026-11-12_position_sweep_preimplementation_corrections.md)を反映する。
この文書は実行許可ではない。実装・合成CPUテストのみ完了した段階では、以下を実行しない。
研究実施者の別途指示後、リポジトリ直下・クリーンなcommitで実行する。

## 事前確認と取得（同じcommit）

全パスはリポジトリ相対。絶対パス・`..`・リポジトリ外へのsymlinkを拒否する。
`<commit7>`は取得コードの現在のHEADの先頭7文字へ置き換える。

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_positions tokenizer-preflight configs/analysis/phase2_position_sweep_v1.json
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_positions stem-preflight configs/analysis/phase2_position_sweep_v1.json
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_capture gpu-preflight configs/analysis/phase2_position_sweep_v1.json
.venv/bin/python -m pip freeze > artifacts/phase2-position-sweep-environment-<commit7>.lock
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_capture freeze configs/analysis/phase2_position_sweep_v1.json --tokenizer-report artifacts/phase2-position-sweep-tokenizer-preflight-<commit7>.json --stem-report artifacts/phase2-position-sweep-stem-preflight-<commit7>.json --gpu-report artifacts/phase2-position-sweep-gpu-preflight-<commit7>.json --environment-lock artifacts/phase2-position-sweep-environment-<commit7>.lock
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_capture capture configs/analysis/phase2_position_sweep_v1.json --runtime-freeze artifacts/phase2-position-sweep-runtime-<commit7>.freeze.json
```

environment lockの作成時は`set -o noclobber`を設定し、既存ファイルを上書きしない。
3つの事前確認レポートとruntime freezeは上記の`artifacts/phase2-position-sweep-*`に新規作成のみ。
トークン化は240条件すべてを検査する。GPU事前確認は先頭2条件のT残差差、非有限値、メモリ、時間、環境版を記録する。
T残差の差とstemの不一致率は停止条件ではない。事前確認の結果を研究実施者の指示に従ってログに記録する。

`generations.json`は辞書のリストで、各要素は`prefix_id`・`boundary`・`raw_text`・`kind`・`tool_calls`を持つ。
stem確認では112件の`raw_text`だけを照合し、条件・成否・評価結果は読まない。
これは仕様9節で指定された112件の形式確認であり、probe用の検証行を読み込む処理ではない。

取得出力は`artifacts/runs/argrec672-v1-ps-001-cNNN/`の240 bundle。
NNNは元の正準run番号。全36層のblock出力をbfloat16・`[1,6,4096]`で保存し、順序はA1/A2/T/S/G/D。
ロジットはTransformers 4.57.6のローカルQwen3ソースで確認した`logits_to_keep=3`を使用する。
未対応モデルではbackboneの最終hidden stateの末尾3位置にだけlm_headを適用する。
本モデルのGPU動作確認は、別途GPU事前確認を実行した際に記録する。

完了済みbundleは全artifactのchecksumと来歴を確認してスキップする。
技術失敗・資源超過は小さい不変failure bundleを保持して停止する。失敗IDで自動再試行しない。
再試行には新しいrun ID接頭辞・設定と、それに対応する新しいcommit・事前確認・freezeを用意する。
既存freezeや既存bundleは変更しない。

## 解析（取得と別のcommit）

取得完了後、研究実施者の指示によるログの追記などをコミットし、作業ツリーをクリーンにする。
取得時のruntime freezeを参照し、現在のHEADとの一致だけは要求しない。freeze内のchecksumは引き続き照合する。
解析コードの変更は一度の解析に先立って確定する。実行後の再解析は別出力ID・別仕様とする。

```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_analysis configs/analysis/phase2_position_sweep_v1.json --runtime-freeze artifacts/phase2-position-sweep-runtime-<commit7>.freeze.json
```

エントリポイントもnumpy・sklearnのimport前に上記3変数を未設定の場合のみ1に設定する。
既に別の値が設定されている環境では、上記コマンドで明示する。
進捗は標準エラーへ出力する。判定42セル全体で帰無最大値を計算する。

出力は`artifacts/processed/argrec672-v1-dg-006-position-sweep/report.json`とchecksum manifest。
既存出力があればfit前に停止する。検証条件の残差は読まず、`validation_rows_loaded: 0`を記録する。
結果は既存結果閲覧後のtrainのみの探索的診断で、独立検証や因果的な選択時点の証明とは扱わない。
小さい要約（`results/`）と実験ログ（`docs/experiment_logs/`）は本実行後に研究実施者の指示で作成する。

## 合成テストと仕様の対応

- `test_position_sweep_positions.py`：仕様3・9・12節（提示順、offset、連結、tokenizer検査、stem）。
- `test_position_sweep_capture.py`：仕様9・10・12節（CPU合成モデル、shape、確率、freeze互換性、不変保存・再開・失敗）。
- `test_position_sweep_analysis.py`：仕様4〜8・12節（信号回復、位置ベースライン、全体補正、logitの向き、規則0〜6、リーク・欠測・再現性）。

合成テストの結果は研究結果ではない。

## 実装ファイルと検証記録（2026-11-12、工学確認のみ）

| 作成・変更 | ファイル | 内容 |
|---|---|---|
| 新規 | `configs/analysis/phase2_position_sweep_v1.json` | 指定された値を固定 |
| 新規 | `src/goal_takeover/phase2/position_sweep_positions.py` | 位置決定、tokenizer・stem確認、入力の照合 |
| 新規 | `src/goal_takeover/phase2/position_sweep_capture.py` | CPUで試験可能な取得、GPU事前確認、freeze、不変保存・再開 |
| 新規 | `src/goal_takeover/phase2/position_sweep_analysis.py` | fold内fit、42セル全体補正、対照、ロジット比較、仮説対応づけ |
| 新規 | `tests/test_position_sweep_positions.py` | 上記の位置決定テスト |
| 新規 | `tests/test_position_sweep_capture.py` | 上記の取得・freeze・保存テスト |
| 新規 | `tests/test_position_sweep_analysis.py` | 上記の解析・合成bundle読み込みテスト |
| 新規 | `docs/phase2_position_sweep_runner.md` | 本書 |
| 変更 | `src/goal_takeover/phase2/argument_recipient_672_runner.py` | runtime照合を挙動を変えずに関数化し、新freezeとの互換性を合成入力で検証 |
| 変更 | `src/goal_takeover/storage/run_writer.py` | manifestを含む正確な保存容量を公開前に算出 |
| 変更 | `PROJECT_STATE.md` | 実装完了・未実行を記録 |
| 変更 | `docs/phase2_position_sweep_implementation_brief.md` | ruffの全文書チェックに合わせたコードブロックの書式のみ調整 |

実装上の補足：技術失敗時は、OOMなどで残差が取得できない場合にも保存できるよう、
来歴・条件・例外を含む小さいfailure bundleを保存する。正常取得ではモデルの層数とhidden sizeも記録し、
解析時にbundle間の一致を検査する。入力token列のchecksumは既存の`canonical_json_bytes`によるJSON表現のSHA-256である。

最終検証：

- `PYTHONPATH=src python3 -m unittest discover -s tests`：262件、成功（研究用依存関係がない標準Pythonでは53件skip）。
- `python3 -m compileall -q src tests`：成功。
- `.venv/bin/ruff check .`：`All checks passed!`。
- `.venv/bin/ruff format --check .`：`278 files already formatted`。
- スレッド数を1に設定した`.venv/bin/pytest`：`262 passed in 27.60s`。
- 新規3テストファイル：`22 passed, 4 subtests passed`。

初回のpytestでは新しい合成fixtureの`tokenizer_revision`不足により4サブケースが
`KeyError: 'tokenizer_revision'`で失敗した。fixtureに版情報を補い、上記の全件検証を再実行して成功した。
研究用モデルのGPU順伝播、事前確認レポートの作成、runtime freezeの作成、240条件の取得・解析は実行していない。
