# D除外対照取得・比較 実装指示書 — Codex向け

- 作成：2026-11-12。作成はClaude Code（研究実施者の依頼による）。実装とテストはCodexが行う。
- **正本は[D除外対照の仕様](phase2_position_sweep_nod_control_spec.md)である。** この指示書と仕様が食い違う場合は、仕様が優先する。
  仕様どおりに実装できない点が見つかったら、**仕様を書き換えずに作業を止め、研究実施者に報告する**。
  前回と同じく、実装前のレビューで見つけた問題も、実装の前に報告すること。
- 前回の[位置スイープの実装指示書](phase2_position_sweep_implementation_brief.md)、
  [RDR-2026-11-12-01](decisions/2026-11-12_position_sweep_preimplementation_corrections.md)、
  [実行手順](phase2_position_sweep_runner.md)、[位置スイープのログ](experiment_logs/2026-11-12_position_sweep.md)を前提とする。

## 0. 作業の範囲と禁止事項

**やること：** 2〜6節を実装し、7節のテストと8節の品質チェックを通してコミットする。

**やらないこと（研究実施者の指示があるまで）：**

- GPUを使う処理（事前確認・取得）と、比較・再解析の本実行。
- 既存のファイルの変更・移動・削除。特に次のものは読み取り専用である。
  - `artifacts/runs/argrec672-v1-003-*`、`argrec672-v1-ps-001-*`
  - `artifacts/processed/argrec672-v1-dg-006-position-sweep/`
  - 既存の`*.freeze.json`・事前確認レポート・environment lock
  - `data/manifests/2026-11-12_phase2_position_sweep_ps001_collection.json`
- 手順3の既存の出力・数値を再現しなくなるような変更。既存モジュールを変更してよいのは、5.1節の「挙動を変えない一般化」だけである。
- 仕様・RDR・計画書・プロトコルの書き換え。判定規則・層・セル・seed・閾値の変更。
- 検証側（G/H/I/J）の条件の読み込み。

## 1. 成果物

| 種別 | パス |
|---|---|
| 設定 | `configs/analysis/phase2_position_sweep_nod_v1.json` |
| 取得・比較・再解析 | `src/goal_takeover/phase2/position_sweep_nod.py` |
| 既存モジュールの一般化 | `position_sweep_capture.py`・`position_sweep_analysis.py`（5.1節の範囲のみ） |
| テスト | `tests/test_position_sweep_nod.py`（既存テストは変更せず、すべて通ること） |
| 実行手順書 | `docs/phase2_position_sweep_nod_runner.md` |

## 2. 設定ファイル

`configs/analysis/phase2_position_sweep_nod_v1.json`：

```json
{
  "schema_version": 1,
  "purpose": "D-free control capture and comparison for the step 3 position sweep. See docs/phase2_position_sweep_nod_control_spec.md.",
  "spec": "docs/phase2_position_sweep_nod_control_spec.md",
  "sweep_config": "configs/analysis/phase2_position_sweep_v1.json",
  "reference": {
    "capture_run_id_prefix": "argrec672-v1-ps-001",
    "runtime_freeze": "artifacts/phase2-position-sweep-runtime-67c5492.freeze.json",
    "collection_manifest": "data/manifests/2026-11-12_phase2_position_sweep_ps001_collection.json",
    "analysis_report": "artifacts/processed/argrec672-v1-dg-006-position-sweep/report.json",
    "gpu_preflight_report": "artifacts/phase2-position-sweep-gpu-preflight-67c5492.json"
  },
  "nod_capture": {
    "run_id_prefix": "argrec672-v1-ps-002",
    "positions": ["A1", "A2", "T", "S", "G"],
    "logit_positions": ["S", "G"]
  },
  "repeat_capture": {
    "run_id_prefix": "argrec672-v1-ps-003",
    "pair_count": 5,
    "pair_order_key": "draft_task_id"
  },
  "resources": {
    "maximum_gpu_memory_gib": 12,
    "maximum_seconds_per_condition": 300,
    "maximum_storage_gib_per_condition": 0.05,
    "maximum_total_storage_gib": 2.0,
    "retry_rule": "new_run_id_only",
    "technical_failure_rule": "preserve_immutable_bundle_then_stop"
  },
  "preflight_condition_count": 2,
  "comparison": {
    "output_id": "argrec672-v1-dg-007-nod-comparison",
    "delta_probe_seed": 20261027,
    "permutation_repeats": 100
  },
  "reanalysis": {
    "output_id": "argrec672-v1-dg-008-position-sweep-nod"
  }
}
```

- **モデル・書き出し・`GB`・ブロックのパス・`top_k`・解析の設定（層・probe・閾値・seed・bootstrap回数）は、
  `sweep_config`（手順3の設定）から読む。** 値を新しい設定に複製しない。
- `reference`の各ファイルは、読み込み時にSHA-256を記録する。`runtime_freeze`と`collection_manifest`は、
  `ps-001`の各bundleの`run.json`（`runtime_freeze_sha256`）とmanifestのSHA-256と照合する。

## 3. 位置と入力（GPU・モデル不要）

`position_sweep_positions.resolve_positions`（手順3）を**そのまま**呼び、その結果から次を作る。

```python
def nod_positions(resolved: dict) -> dict:
    """手順3の resolve_positions の結果から D を除く。
    input_ids = resolved["input_ids"][:-1]
    positions = A1, A2, T, S, G（token_index・token_id・decoded・offset・A1/A2 の account・character_span はそのまま）
    S と G が新しい入力の最後の2 token であることを要求する。
    continuation_text は書き出し + "GB"（D の数字を含まない）。
    digit_token_ids は手順3と同じ（G での同位置ロジットに使う）。
    position_rule_version は "position_sweep_nod_v1"、position_order は ["A1","A2","T","S","G"]。"""
```

**トークン化の事前確認**`nod_tokenizer_preflight(config_path)`：240条件すべてで次を確認する。どれか1件でも満たさなければ、除外せずに停止する。

1. `nod_positions`の`input_ids`が、`ps-001`の`input.json`の`token_ids`から末尾1 tokenを除いたものと一致する。
2. `A1`〜`G`のtoken index・token IDが、`ps-001`の`positions.json`と一致する。
3. `ps-001`の各bundleのmanifestのchecksumが合い、`run.json`の`runtime_freeze_sha256`が`reference.runtime_freeze`のSHA-256と一致する。

出力は`artifacts/phase2-position-sweep-nod-tokenizer-preflight-<commit7>.json`（`write_report`と同じく新規作成のみ）。

**再現性の10条件の選び方**`repeat_condition_ids(rows)`：
`draft_task_id`の昇順で先頭5つのtaskをとり、その両条件（計10条件）とする。対の構成は`pair_index`と同じである。
選び方の規則と結果のcondition ID一覧を、事前確認レポートに記録する。

## 4. 取得

### 4.1 既存の取得関数の一般化（`position_sweep_capture.py`）

`capture_condition`の中の順伝播部分を、次の関数として切り出す。

```python
def forward_capture(
    model,
    input_ids: list[int],
    token_indices: list[int],
    logit_positions: list[str],
    position_names: list[str],
    block_path: str,
    top_k: int,
    digit_token_ids: dict,
    gb_token_id: int | None,
) -> dict:
    """1回の順伝播で、token_indices の残差（全層）と、入力の末尾 len(logit_positions) 位置のロジットを返す。
    logits_to_keep=len(logit_positions)。使えない場合は既存と同じく lm_head を末尾の位置だけに適用する。
    logit_positions の各位置が入力の末尾から順に並ぶことを要求する。
    S が logit_positions に含まれるとき、gb_token_id の対数確率を "gb_log_probability" として S に保存する。"""
```

- 既存の`capture_condition`は`forward_capture`を呼ぶ形に書き換える。**挙動・出力形式は一切変えない**
  （`logits_to_keep=3`、位置の順`A1..D`、記録のキー名）。既存テストが変更なしで通ることで確認する。
- `validate_residual_schema`は位置数を引数で受け取れるようにする（既定値は6で、既存の呼び出しは変えない）。

### 4.2 GPU事前確認`nod_gpu_preflight(config_path)`

- 240条件のうち`condition_id`の昇順で先頭2件について、D除外の入力で`forward_capture`を行う。
- 記録する値：ピークGPUメモリ、経過秒数、非有限値の有無、`logit_method`、環境の版（`position_sweep_capture.environment()`）。
- 12 GiB超過と非有限値は例外とする。bundleは書かない。
- 出力は`artifacts/phase2-position-sweep-nod-gpu-preflight-<commit7>.json`（新規作成のみ）。

### 4.3 runtime freeze`create_nod_runtime_freeze(...)`

`position_sweep_capture.create_runtime_freeze`と同じ形式にする。`load_frozen_plan(..., runtime_freeze_override=<新freeze>, require_matching_head=True)`
がそのまま通ることを要求する。そのうえで、次を追加・変更する。

- `files_sha256`：トークン化・GPUの事前確認レポートと、environment lock
  （`artifacts/phase2-position-sweep-nod-environment-<commit7>.lock`）
- `analysis_config_sha256`：**新しい設定**（`phase2_position_sweep_nod_v1.json`）のSHA-256
- `sweep_config_sha256`：手順3の設定のSHA-256
- `spec_sha256`：**D除外対照の仕様**のSHA-256
- `reference_sha256`：`reference`の4ファイルのSHA-256（run ID接頭辞はファイルではない）。
  `gpu_preflight_report`は旧runtime freezeの`files_sha256`とも照合する。
- `resources`：新しい設定の`resources`
- 出力は`artifacts/phase2-position-sweep-nod-runtime-<commit7>.freeze.json`。`open(..., "x")`で作り、上書きしない。

### 4.4 取得ループ`capture_nod(config_path, runtime_freeze)`

モデルの読み込みより前に、freezeと`load_frozen_plan`（matching=True）の照合を行う。モデルは1回だけ読み込み、次の順に処理する。

1. **再現性`ps-003`（10条件）：** `ps-001`の`input.json`の`token_ids`と`positions.json`のtoken indexを**そのまま**使う。
   `forward_capture(..., logit_positions=["S","G","D"], position_names=["A1","A2","T","S","G","D"])`を呼ぶ。
   あわせて、`resolve_positions`を計算し直した結果が`ps-001`と一致することも確認する（一致しなければ停止する）。
2. **D除外`ps-002`（240条件）：** `nod_positions`の入力で、
   `forward_capture(..., logit_positions=["S","G"], position_names=["A1","A2","T","S","G"])`を呼ぶ。

- run IDは`<prefix>-cNNN`とし、NNNは正準run番号とする（手順3と同じ規則）。
- bundleの中身は手順3と同じファイル構成にする（`condition.json`・`positions.json`・`input.json`・`logprobs.json`・
  `residual.safetensors`・`run.json`・`resolved_config.json`）。
  - 残差のshapeは、`ps-003`が`[1, 6, 4096]`、`ps-002`が`[1, 5, 4096]`（bfloat16、全36層）。
  - `run.json`には、手順3の項目に加えて`capture_kind`（`"repeat"`か`"nod"`）、対応する`ps-001`のrun IDとmanifestのSHA-256、
    `position_order`を記録する。
- 完了済みbundleのスキップ、失敗bundleの保持と停止、資源上限の扱いは、`position_sweep_capture.capture`と同じにする。
  共通にできる部分は関数として切り出してよいが、既存の`capture`の挙動は変えない。

### 4.5 取得のmanifest（取得後、研究実施者の指示で作成）

手順3の`data/manifests/2026-11-12_phase2_position_sweep_ps001_collection.json`と同じ形式で、
`data/manifests/<日付>_phase2_position_sweep_nod_collection.json`を作る関数`write_collection_manifest`を用意する。
250件のrun ID、condition ID、pair ID、`capture_kind`、manifestのSHA-256、資源値、事前確認・lock・freezeのchecksumを記録する。

## 5. 比較と再解析

### 5.1 既存の解析関数の一般化（`position_sweep_analysis.py`）

`analyze`と`validate_inputs`に、キーワード引数`position_names: tuple[str, ...] = POSITIONS`を追加する。
関数内で`POSITIONS`を直接参照している箇所を、すべてこの引数に置き換える。

- **既定値では、手順3の出力を1ビットも変えないこと。** 合成データで、変更前と変更後の`analyze`の出力（canonical JSON）が一致するテストを入れる。
  変更前の出力は、変更前のcommitの関数をテスト内で再現するのではなく、変更前に生成した合成データの出力を
  テストのfixtureとして保存する方法をとる。
- `D`を除いた5位置で呼んだ場合も、`A1`〜`G`の各セル・帰無分布・判定が6位置の場合と一致すること（`D`は報告のみで、
  判定・補正・乱数に関与しないため）を、合成データで確認する。

### 5.2 比較`run_comparison(config_path, runtime_freeze)`（CPUのみ）→ `dg-007`

**入力：** `ps-001`（240）、`ps-002`（240）、`ps-003`（10）、正準`argrec672-v1-003`の`T`残差（240、shape `[1,1,4096]`）。
すべてmanifestのchecksumと来歴（freeze・commit・condition・入力token列）を照合する。
`ps-002`・`ps-003`は新freezeを、`ps-001`は`reference.runtime_freeze`を持つことを要求する。
取得と同じcommitでの実行は拒否する（手順3の`load_inputs`と同じ）。

**4節の指標**（位置×層×条件ごとに計算し、位置×層ごとに中央値・最大値・完全一致数を報告する）：

```python
def compare_vectors(a_bf16, b_bf16) -> dict:
    """bit_exact: torch.equal(a_bf16.view(torch.int16), b_bf16.view(torch.int16))（符号付きゼロも区別）
    a, b を float32 にしてから:
    relative_l2 = ||a-b|| / max(||b||, tiny)、max_absolute = max|a-b|"""
```

| 比較 | 位置 | 層 | 条件 |
|---|---|---|---|
| R（`ps-003` vs `ps-001`） | A1, A2, T, S, G, D | 全36 | 10 |
| N（`ps-002` vs `ps-001`） | A1, A2, T, S, G | 全36 | 240 |
| P（`ps-002`の`T` vs 正準の`T`） | T | 全36 | 240 |

位置の対応は名前で取る（`ps-001`の位置順はA1..D、`ps-002`はA1..G）。添字で取らないこと。

**7.1節：** Rの全値がビット一致すれば`R-EXACT`、そうでなければ`R-NOISE`とし、位置×層ごとの最大相対L2差を`noise_width`として記録する。

**7.2節の①の判定：**

- `R-EXACT`のとき：NのA1〜G・全層・全条件がビット一致すれば①。
- `R-NOISE`のとき：①にしない。Nと`noise_width`の比較は記述にとどめ、再解析を要求する。

①なら`d_effect = "1_no_effect"`、`reanalysis_required = false`とする。
①でなければ`d_effect = "pending_reanalysis"`、`reanalysis_required = true`とする。

**5節（Δの読み取り、併記のみ）：**

- `Δ = x_ps001 − x_ps002`を、手順3の判定42セル（同じ位置・層・probe）について作る（float32）。
- Δが240条件すべてでゼロのセルは`"no_difference"`とし、計算しない。
- 残りのセルについて、`_cell_scores`（ファミリー除外）で`recipient_first`の`paired_accuracy`を計算する。
  `position_sweep_analysis.global_null`を、計算したセルだけを`judged`として呼ぶ。
  seedは`comparison.delta_probe_seed`、反復数は`permutation_repeats`とする。
  family-wiseのpは、計算したセル全体の最大値で補正する。
- 帰無分布を作ったセル数を、出力に必ず記録する（ゼロのセルを除いた数）。
- **この結果は判定に使わない。** 出力のキーは`delta_label_readout`とし、`"reported_only": true`を付ける。

**7.3節：** Pの`T`について、層ごとの中央値・最大値を記述するだけにする。
あわせて、手順3のGPU事前確認の2条件について、「正準→`ps-001`」の差（既存レポートの値）と、
「正準→`ps-002`」「`ps-002`→`ps-001`」の差を並べる。
P/Nを寄与割合へ分解せず、Pを再実行ノイズと呼ばない。既存の局所文言の留保も引き継ぐ。

**出力：** `publish(artifacts/processed/argrec672-v1-dg-007-nod-comparison, {"report.json": ...}, kind="position_sweep_nod_comparison")`。
`provenance`には、commit、`git_dirty: false`、設定・仕様・freeze・referenceのSHA-256、全bundleのmanifest SHA-256、
`validation_rows_loaded: 0`、`research_result: "post_result_train_only_technical_control"`を記録する。

### 5.3 再解析`run_reanalysis(config_path, runtime_freeze)` → `dg-008`

- **実行条件：** `dg-007`の`reanalysis_required`が真の場合だけ実行できる。偽なら、fitの前に停止する（仕様7.2：①なら省いてよい）。
- **入力：** `ps-002`の240件。検証は手順3の`load_inputs`と同じ水準で行う。
  `T`のindexは`len(prefix)-1`、`S`・`G`は末尾2 tokenとし、`A1`・`A2`は`span_last_token`と一致することを要求する。
- **設定：** `sweep_config`の`analysis`節を使う。変えるのは次の2点だけで、コード上でassertする。
  - `report_only_positions`を`[]`にする（`D`がないため）。
  - `output_id`を`reanalysis.output_id`にする。
  - 判定セルが42個であることもassertする。
- `analyze(..., position_names=("A1","A2","T","S","G"))`を呼ぶ。`G`の同位置ロジットは`ps-002`の`logprobs.json`から計算する。
- **7.2節の②・③の判定：** `dg-006`（`reference.analysis_report`、SHA-256照合）と比べる。
  - 5位置の`position_classifications[p]["class"]`のどれか、または`hypothesis_mapping`の`mapping`・`rule`が異なれば③（`"3_classification_changed"`）。
  - それ以外は②（`"2_numeric_only"`）。
  - 違いがあった位置・項目の一覧と、`dg-007`の`delta_label_readout`で`family_wise_p < 0.05`のセルがあったか（②の併記事項）を記録する。
- **出力：** `publish(artifacts/processed/argrec672-v1-dg-008-position-sweep-nod, ...)`。`report.json`は手順3と同じ構造にし、
  `d_effect_classification`節を追加する。`dg-006`と`dg-007`のSHA-256も`provenance`に記録する。

## 6. CLI

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_nod tokenizer-preflight configs/analysis/phase2_position_sweep_nod_v1.json
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_nod gpu-preflight configs/analysis/phase2_position_sweep_nod_v1.json
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_nod freeze configs/analysis/phase2_position_sweep_nod_v1.json --tokenizer-report <path> --gpu-report <path> --environment-lock <path>
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_nod capture configs/analysis/phase2_position_sweep_nod_v1.json --runtime-freeze <path>
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_nod collection-manifest configs/analysis/phase2_position_sweep_nod_v1.json --runtime-freeze <path> --output <path>
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_nod compare configs/analysis/phase2_position_sweep_nod_v1.json --runtime-freeze <path>
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_nod reanalyze configs/analysis/phase2_position_sweep_nod_v1.json --runtime-freeze <path>
```

- パスはすべてリポジトリ相対で受け取り、絶対パス・`..`・リポジトリ外へのsymlinkを拒否する（`safe_path`を使う）。
- `compare`・`reanalyze`のエントリポイントでも、numpy・sklearnのimport前に3つのBLAS変数を、未設定なら`"1"`にする。
- `compare`と`reanalyze`は、出力先が既にあればfitの前に停止する。

## 7. テスト（合成データのみ。モデル・GPU・実データ不要）

**位置と入力**

1. `nod_positions`：入力が手順3の入力から末尾1 tokenを除いたものになる。S・Gが末尾2 tokenになる。Dが出力に含まれない。A1〜Gの値が手順3と同一になる。
2. トークン化の事前確認：末尾以外のtokenが違う、位置がずれる、manifestが壊れている、`ps-001`のfreezeが違う、の各合成ケースで停止する。
3. `repeat_condition_ids`：`draft_task_id`の昇順で先頭5対・10条件を返す。入力の行順を入れ替えても同じ結果になる。

**取得**

4. `forward_capture`：小さな合成モデルで、`logit_positions`が2つと3つの場合の両方を確認する。位置の順、末尾の位置であることの検査、`gb_log_probability`の保存を確認する。
5. 既存の`capture_condition`の出力が、一般化の前後で一致する（既存テストが変更なしで通ること、および合成モデルでの出力一致）。
6. 再現性の取得が`ps-001`の入力をそのまま使う。計算し直した位置が`ps-001`と食い違う合成ケースで停止する。
7. freeze：作業ツリーがdirty、レポートのcommitが不一致、referenceのSHA-256が不一致、既存ファイルがある、の各場合に失敗する。`load_frozen_plan`の照合部分が受け入れる。
8. bundle：shapeが`[1,5,H]`・`[1,6,H]`になる。`capture_kind`が記録される。完了済みはスキップされ、checksum不一致で停止する。

**比較**

9. `compare_vectors`：同一のbfloat16値で`bit_exact`が真、相対L2が0になる。1要素だけ変えた場合の値が既知値と一致する。+0/-0はbit_exactが偽になる。
10. 位置の対応：`ps-001`（6位置）と`ps-002`（5位置）を名前で対応づける。添字がずれた合成ケースで、名前での対応が正しく取られる。
11. 7.1・7.2節の①：R-EXACTかつNが完全一致なら①。R-EXACTでNが1要素違えば①でない。R-NOISEではNがノイズ幅以下・等しい・超える、のいずれでも再解析を要求する。
12. Δの読み取り：Δが全ゼロのセルは計算されず、帰無分布のセル数から除かれる。Δにラベルの方向を埋め込んだ合成データで読める。`reported_only`が真になる。

**再解析**

13. 5.1節：既定の6位置で`analyze`の出力が、保存したfixtureとビット一致する。5位置で呼んだときのA1〜Gの値が、6位置の場合と一致する。
14. `reanalysis_required`が偽なら、fitの前に停止する。
15. ②・③：位置の判定が1つだけ違う合成ケースで③、すべて同じなら②になる。`hypothesis_mapping`の`rule`だけが違う場合も③になる。
16. 設定の差がreport_only_positionsとoutput_idの2点だけであることのassertが、ほかの値を変えた合成ケースで失敗する。
17. リーク防止：検証行で失敗する。出力先が既にあれば失敗する。同じseedで同じ出力になる。

## 8. 品質チェックとコミット

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
python3 -m compileall -q src tests
ruff check .
ruff format --check .
pytest
```

- すべて通ってからコミットする（機能単位に分けてよい）。
- `PROJECT_STATE.md`には「D除外対照の実装完了、未実行」とだけ1〜2行で追記する。
- 仕様との不一致や判断の必要な点が見つかったら、コミットせずに一覧にして研究実施者に報告する。

## 9. 実行手順（参考。研究実施者の指示があってから行う）

1. クリーンなcommitで`tokenizer-preflight`を実行する（モデル不要）。
2. 同じcommitで`gpu-preflight`を実行する。
3. `set -o noclobber`のうえで`pip freeze > artifacts/phase2-position-sweep-nod-environment-<commit7>.lock`を実行し、`freeze`を実行する。
4. `capture`で、再現性10条件 → D除外240条件の順に取得する。
5. `collection-manifest`で取得のmanifestを作り、ログと一緒に別のcommitに保存する。
6. その別のcommitで`compare`を一度だけ実行する。
7. `dg-007`が①でなければ、`reanalyze`を一度だけ実行する。
8. 結果の要約とログを作る（研究実施者の指示による）。手順3のログへの訂正（③の場合）も、研究実施者の指示で行う。

## 10. 完了時に報告すること

- 作成・変更したファイルの一覧と、各テストが対応する仕様の節
- 品質チェックの出力（失敗があればそのまま）
- 既存モジュールに加えた変更と、手順3の出力を変えないことの確認方法
- 実装上の判断（この指示書に書かれていなかった点）と、その理由
