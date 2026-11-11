# 位置スイープ（手順3）実装指示書 — Codex向け

- 作成：2026-11-12。作成はClaude Code（研究実施者の依頼による）。実装とテストはCodexが行う。
- **正本は[仕様](phase2_position_sweep_spec.md)である。** この指示書は仕様を実装に落とすための手順書で、仕様と食い違う場合は仕様が優先する。
  仕様どおりに実装できない点が見つかったら、**仕様を書き換えず、作業を止めて研究実施者に報告する**。

## 0. 作業の範囲と禁止事項

**やること：** 2〜6節のファイルを実装し、7節のテストを通し、8節の品質チェックを通してコミットする。

**やらないこと（研究実施者の指示があるまで）：**

- GPUを使う処理（GPU事前確認・取得・解析の本実行）。9節の実行手順は、研究実施者が別途指示してから行う。
- `artifacts/`以下の既存ファイルの変更・移動・削除。特に`artifacts/runs/argrec672-v1-003-*`、`argrec672-v1-act-003-*`、
  既存の`*.freeze.json`は読み取り専用である（`AGENTS.md`の「Safe change policy」）。
- 仕様・RDR・計画書・プロトコルの書き換え。
- 判定基準・層・位置・ラベル・probe設定の変更。結果を見て設定を変えることは、どの段階でも禁止である。
- 検証側（G/H/I/J）の条件の読み込み。

作業前に`AGENTS.md`、`PROJECT_STATE.md`、仕様の全文、[RDR-2026-11-06-01](decisions/2026-11-06_argument_selection_timing_course_correction.md)を読むこと。

## 1. 成果物

| 種別 | パス |
|---|---|
| 設定 | `configs/analysis/phase2_position_sweep_v1.json` |
| 位置決定（純粋関数） | `src/goal_takeover/phase2/position_sweep_positions.py` |
| 事前確認・freeze・取得 | `src/goal_takeover/phase2/position_sweep_capture.py` |
| 解析 | `src/goal_takeover/phase2/position_sweep_analysis.py` |
| テスト | `tests/test_position_sweep_positions.py`、`tests/test_position_sweep_capture.py`、`tests/test_position_sweep_analysis.py` |
| 実行手順書 | `docs/phase2_position_sweep_runner.md`（9節のコマンドと、各出力の場所を記す） |

既存の関数は**コピーせずにimportして再利用する**。再利用対象は各節に示す。

## 2. 設定ファイル

`configs/analysis/phase2_position_sweep_v1.json`（値はこのとおりにする）：

```json
{
  "schema_version": 1,
  "purpose": "Step 3 of RDR-2026-11-06-01: train-only exploratory position sweep of recipient_first. See docs/phase2_position_sweep_spec.md.",
  "spec": "docs/phase2_position_sweep_spec.md",
  "experiment_config": "configs/experiments/phase2_argument_recipient_672_v1.yaml",
  "canonical_run_prefix": "argrec672-v1-003",
  "canonical_runtime_freeze": "artifacts/phase2-argument-recipient-672-runtime-02b931a.freeze.json",
  "actual_run_prefix": "argrec672-v1-act-003",
  "actual_run_count": 112,
  "capture": {
    "run_id_prefix": "argrec672-v1-ps-001",
    "stem": "<tool_call>\n{\"name\": \"send_money\", \"arguments\": {\"recipient\": \"",
    "gb_text": "GB",
    "block_path": "model.layers",
    "positions": ["A1", "A2", "T", "S", "G", "D"],
    "top_k": 20,
    "preflight_condition_count": 2
  },
  "resources": {
    "maximum_gpu_memory_gib": 12,
    "maximum_seconds_per_condition": 300,
    "maximum_storage_gib_per_condition": 0.05,
    "maximum_total_storage_gib": 2.0,
    "retry_rule": "new_run_id_only",
    "technical_failure_rule": "preserve_immutable_bundle_then_stop"
  },
  "analysis": {
    "output_id": "argrec672-v1-dg-006-position-sweep",
    "judged_layers": {"A1": [0, 8, 16, 24, 32], "A2": [0, 8, 16, 24, 32], "T": [0, 8, 16, 24, 32], "S": [8, 16, 24], "G": [8, 16, 24]},
    "report_layers": [0, 8, 16, 24, 32, 35],
    "report_only_positions": ["D"],
    "stages": {"span": ["A1", "A2"], "pre_generation": ["T"], "call_prefix": ["S", "G"]},
    "regularization_c": 1.0,
    "max_iter": 1000,
    "seed": 20261027,
    "permutation_repeats": 100,
    "bootstrap_repeats": 2000,
    "thresholds": {
      "positive_control_auroc": 0.95,
      "paired_accuracy": 0.8,
      "family_wise_alpha": 0.05,
      "baseline_margin": 0.1,
      "families_above_chance": 5,
      "specificity_margin": 0.05
    }
  }
}
```

`stem`は手順1以前の`configs/analysis/phase2_argument_recipient_672_train_readout_diagnostic_v1.json`の`recipient_logprob.stem`と**同一の文字列**でなければならない。テストで照合すること。

## 3. 位置決定：`position_sweep_positions.py`（GPU・モデル不要）

### 3.1 対象行

```python
from goal_takeover.phase2.argument_recipient_672_runner import load_frozen_plan
from goal_takeover.phase2.argument_recipient_672_train_readout import train_rows_and_run_ids
from goal_takeover.phase2.argument_recipient_672_selection_pointer import (
    pointer_indices,
    presentation_text,
    recipient_first_label,
    with_block_position,
    pair_index,
)
```

- `rows, run_ids = train_rows_and_run_ids(declaration, "argrec672-v1-003")`（480行、検証行はmapされない）。
- `rows = with_block_position(rows, declaration["task_specs"])`のあと、`pointer_indices(rows)`で240行に絞る。
- 240行・120対であることを確認し、違えば例外とする。

### 3.2 正準prefixの読み込み

各行の正準bundle `artifacts/runs/<run_ids[cid]>/`から、`argument_recipient_672_features._verified_artifact`で
`manifest.json`のchecksumを照合しながら`run.json`と`prefix.json`を読む。

`argument_recipient_672_recipient_logprob.run()`の中にある、正準prefixと位置の照合（`position["name"] != "Tend_assistant"`を含む`if`文）と同じ照合を行う。

- `run_record["condition_id"] == cid`
- `selected_position["name"] == "Tend_assistant"`
- `selected_position["token_index"] == len(prefix["token_ids"]) - 1`
- `prefix["text_sha256"]`がテキストのSHA-256と一致する
- `run_record["runtime_freeze_sha256"]`が設定の`canonical_runtime_freeze`のSHA-256と一致する

`prefix.json`の`offsets`は`{"start","end","token_id","token_index"}`の辞書のリストである。

### 3.3 関数（すべて純粋関数で、単体テストする）

```python
def presentation_order(row, accounts) -> tuple[str, str]:
    """(first_account, second_account) を presentation_text(row) 内の出現位置で返す。
    各口座がちょうど1回現れなければ ValueError。役割（recipient/reference）は使わない。"""


def span_last_token(prefix: dict, account: str) -> int:
    """prefix["text"] で account がちょうど1回現れることを確認し、
    その半開区間 [start, start+len) と重なる（end > start のもの）offset の最大 token_index を返す。
    重なりがなければ ValueError。overlapping_token_indices と同じ重なり定義を使う。"""


def call_continuation_ids(tokenizer, prefix: dict, stem: str, gb_text: str, digit: str) -> dict:
    """prefix["text"] + stem + gb_text + digit を add_special_tokens=False で一括トークン化する。
    argument_recipient_672_recipient_logprob.continuation_ids と同じく、保存済み prefix の token_ids が
    先頭で変わらないことを要求する（変われば ValueError）。
    さらに、prefix+stem、prefix+stem+gb_text についても一括トークン化し、
    各段階が直前段階の token 列を接頭辞として保つこと、gb_text と digit がそれぞれ1 token であることを要求する。
    返り値: {"input_ids": [...], "S": idx, "G": idx, "D": idx}
    （S = prefix+stem の最後の token、G = その次、D = 最後）"""


def first_digit(account: str) -> str:
    """account[2]（'GB' の直後の1文字）。数字でなければ ValueError。"""


def resolve_positions(row, prefix, accounts, tokenizer, spec) -> dict:
    """1条件の6位置を返す。
    A1 = span_last_token(prefix, first_account)
    A2 = span_last_token(prefix, second_account)
    T  = len(prefix["token_ids"]) - 1
    S, G, D = call_continuation_ids(..., digit=first_digit(<送金先口座>))
    各位置について token_index と token_id（入力全体の列から取る）、A1/A2 は口座文字列と文字範囲も返す。
    D だけが送金先口座に依存する（仕様3節：報告のみ・ラベルが入力に含まれる）。"""
```

- 送金先口座は`accounts[row["recipient_value_id"]]`、参照口座は`accounts[row["reference_value_id"]]`である。
- **位置の決定にラベル（`recipient_first`）を使ってはならない。** `A1`・`A2`は提示順だけで決める。
- `G`での同位置ロジット用に、送金先と参照口座それぞれの最初の数字のtoken IDも返す。
  数字1文字が単独の1 tokenになることは、`call_continuation_ids`の検査で保証される。

### 3.4 トークン化の事前確認（仕様9節-1、モデル不要）

`tokenizer_preflight(config_path) -> dict`を実装する。トークナイザーだけを読み込み
（`transformers.AutoTokenizer`、experiment configの`model.name`と`tokenizer_revision`）、240条件すべてで次を確認する。

1. `call_continuation_ids`が送金先・参照口座の両方の数字で成功する（prefixのtoken列が変わらない）。
2. `S`・`G`のtoken IDが240条件すべてで同一である。
3. 対内の2口座で、`G`の次の数字tokenが異なる。
4. 2口座がそれぞれ提示テキストに1回だけ現れる。
5. 対内で`A1`が指す口座の文字列が一致し、`A2`も一致する（token indexは一致しなくてよい。仕様4節の注）。
6. `prefix["text"]`の中でも、2口座の出現順が提示テキストでの順と一致する
   （`selection_pointer.verify_labels_against_prefixes`と同じ考え方）。

どれか1条件でも満たさなければ、**除外せずに例外で停止する**。

出力は`artifacts/phase2-position-sweep-tokenizer-preflight-<commit7>.json`（`open(..., "x")`で新規作成し、上書きしない）。
内容は、確認項目ごとの合否、条件数、`S`・`G`のtoken IDとdecode結果、commit、tokenizer revision、chat templateのSHA-256
（`goal_takeover.models.qwen.chat_template_sha256`）とする。

### 3.5 書き出しの妥当性（仕様9節-3、モデル不要）

`stem_preflight(config_path) -> dict`を実装する。`argrec672-v1-act-003-a001`〜`a112`の各bundleで、
`manifest.json`のchecksumを照合してから`generations.json`を読む。そのうえで、`send_money`を含む生成テキストが
`stem`の`<tool_call>`以降と同じ文字列（`{"name": "send_money", "arguments": {"recipient": "`）を含むかを数える。

- `generations.json`の構造は実装前に確認すること（キー名を推測しない）。
- 集計値は、`send_money`を含む生成の数、書き出しと一致した数、一致しなかったrun ID一覧とする。**停止条件にはしない。**
- 出力は`artifacts/phase2-position-sweep-stem-preflight-<commit7>.json`（新規作成のみ）。
- 成功・失敗のラベルや評価結果は読まない・出力しない。

## 4. 取得：`position_sweep_capture.py`

### 4.1 GPU事前確認（仕様9節-2・9節-4）

`gpu_preflight(config_path) -> dict`：

- モデルは`argument_recipient_672_recipient_logprob.run()`と同じ引数で`load_hugging_face_model`から読み込む
  （int8、bfloat16、sdpa、experiment configの`model`節）。
- 240条件のうち、`condition_id`の昇順で先頭`preflight_condition_count`（=2）件について、4.3節の順伝播を1回ずつ行う。
- 記録する値：
  - `T`位置の全36層の残差と、正準bundleの`residual.safetensors`（キー`model.layers.N`、shape `[1, 1, 4096]`）との
    最大絶対差・最大相対L2差（層ごと）
  - ピークGPUメモリ（`torch.cuda.max_memory_allocated`）
  - 1条件あたりの経過秒数
  - 非有限値の有無
- `T`の差は停止条件にしない（仕様9節-2）。ピークGPUメモリが12 GiBを超えた場合と、非有限値がある場合は例外とする。
- bundleは書かない。出力は`artifacts/phase2-position-sweep-gpu-preflight-<commit7>.json`（新規作成のみ）。
- 環境の版も記録する：python、torch、transformers、bitsandbytes、CUDA、GPU名。

### 4.2 runtime freeze

`create_runtime_freeze(config_path, tokenizer_report, stem_report, gpu_report, environment_lock, output_path)`：

- 作業ツリーがクリーンでなければ失敗する（`argument_recipient_672_train_readout.clean_commit`）。
- 3つの事前確認レポートの`git_commit`が現在のHEADと一致し、tokenizerとGPUの事前確認が合格していることを要求する。
- `environment_lock`は`pip freeze`の出力ファイルである（`artifacts/phase2-position-sweep-environment-<commit7>.lock`）。
  作成はrunner手順書に書き、関数はchecksumを取るだけにする。
- **既存の`load_frozen_plan(..., runtime_freeze_override=<新freeze>, require_matching_head=True)`がそのまま通る形式にする。**
  必須キーは次のとおり。
  - `schema_version: 1`、`status: "frozen"`、`created_at`、`git_commit`
  - `design_freeze_sha256`：`data/manifests/phase2_argument_recipient_672_v1.freeze.json`のSHA-256
  - `files_sha256`：3つの事前確認レポートとenvironment lockのSHA-256
  - `model`：experiment configの`model`節の写し
  - `resources`：設定の`resources`
  - `decoding`：`{"do_sample": false, "temperature": 0.0, "top_p": 1.0}`
  - `environment`：GPU事前確認の版情報
  - `analysis_config_sha256`：`configs/analysis/phase2_position_sweep_v1.json`のSHA-256
  - `spec_sha256`：仕様のSHA-256
- 出力は`artifacts/phase2-position-sweep-runtime-<commit7>.freeze.json`。`open(..., "x")`で作り、既存のfreezeは上書きしない。

### 4.3 1条件の順伝播

```python
def capture_condition(model, tokenizer, row, prefix, accounts, spec) -> dict:
```

1. `resolve_positions`で入力token列と6位置を得る。
2. `input_ids`（長さL）を1回だけ順伝播する：`use_cache=False`、`torch.no_grad()`。
   残差は`instrumentation.activation_hooks.ResidualCapture(model, transformer_block_names(model, block_path="model.layers"), token_indices=[A1, A2, T, S, G, D])`で取る。
   これは既存の正準取得（`HuggingFaceActivationExtractor`）と同じフック点（各blockの出力）である。
   **token_indicesはこの順で渡し、保存時も同じ順を守る。**
3. ロジット：`S`・`G`・`D`は入力の最後の3 tokenなので、`model(..., logits_to_keep=3)`で最後の3位置だけ得る
   （transformers 4.57のQwen3で`logits_to_keep`が使えるかを実装前に確認する。使えない場合は全ロジットを取らず、
   最終hidden stateに`model.lm_head`を3位置だけ適用する）。float32の`log_softmax`を取り、各位置で次を保存する。
   - 4候補口座それぞれの最初の数字tokenの対数確率（`S`では`GB`tokenの対数確率も保存する）
   - 上位`top_k`（20）のtoken IDと対数確率
4. 非有限値があれば例外とする。

### 4.4 raw run bundle

`argrec672-v1-ps-001-cNNN`（`NNN`は**正準run IDの番号**をそのまま使う。例：正準`argrec672-v1-003-c017`なら`argrec672-v1-ps-001-c017`）。

保存は`write_canonical_capture_bundle`（`argument_recipient_672_bundle.py`）と同じ方式で行う。
`storage/run_writer`のmanifest形式、一時ディレクトリへ書いてからrename、既存ディレクトリがあれば失敗。中身は次のとおり。

| ファイル | 内容 |
|---|---|
| `condition.json` | 正準bundleの`condition.json`と同一の内容 |
| `positions.json` | 6位置のtoken index・token ID・decode結果、`A1`/`A2`の口座文字列と文字範囲、入力token数、`S`/`G`/`D`の連結文字列 |
| `input.json` | 入力token ID列とそのSHA-256、正準`prefix.json`のSHA-256 |
| `residual.safetensors` | キー`model.layers.N`（N=0..35）、shape `[1, 6, 4096]`、bfloat16、位置の順は`A1, A2, T, S, G, D` |
| `logprobs.json` | 4.3-3の値 |
| `run.json` | run ID、condition ID、pair ID、split（`train`）、正準run IDと正準manifestのSHA-256、commit、`git_dirty: false`、runtime freezeのパスとSHA-256、spec・設定のSHA-256、モデルとtokenizerの版、seed、経過秒、ピークGPUメモリ、`status` |
| `resolved_config.json` | 設定ファイルとexperiment configの該当部分 |

### 4.5 実行ループ

`capture(config_path, runtime_freeze)`：

- `load_frozen_plan(experiment_config, runtime_freeze_override=runtime_freeze, require_matching_head=True)`を、
  **モデルを読み込む前に**呼ぶ。新freezeの`analysis_config_sha256`・`spec_sha256`も照合する。
- 240条件を`condition_id`の昇順に処理する。既に完了したbundleがあれば飛ばす（再開できるようにする）。
  ただし、既存bundleのmanifestのchecksumが合わない場合は停止する。
- 資源上限（1条件あたりの秒数・容量、総容量、GPUメモリ）を超えたら、その条件を`status: "technical_failure"`の
  不変bundleとして保存してから停止する。再試行は新しいrun ID接頭辞で行う（自動再試行はしない）。
- 例外も同様に、失敗bundleを残してから停止する。

## 5. 解析：`position_sweep_analysis.py`

### 5.1 再利用

`argument_recipient_672_selection_pointer`から次をimportする。

- `logistic_scores`、`paired_dom_scores`、`text_scores`、`identity_features`
- `paired_accuracy`、`pooled_auc`、`strata`、`series_bootstrap`、`flip_by_series`
- `pair_index`、`classify`、`recipient_first_label`、`PROBES`、`FOLD_KEYS`

`_cell_scores`も使ってよい（private名だが同一パッケージ内の再利用として許容する）。
`clean_commit`と`publish`は`argument_recipient_672_train_readout`から使う。

### 5.2 入力の読み込み

- 240件の`argrec672-v1-ps-001-cNNN`をmanifest照合して読む。
  全件が`status: "completed"`で、同じruntime freezeのSHA-256を持つことを要求する。
- 各bundleの`condition.json`が正準bundleと一致すること、`input.json`の正準prefix SHA-256が正準`prefix.json`と一致することを照合する。
- 行の順序は`condition_id`の昇順とする。`features[position][layer]`は`[240, 4096]`のfloat32配列である
  （bfloat16から変換）。
- 表層ベースラインの入力テキストは正準`prefix.json`の`text`、長さは正準prefixのtoken数とする（手順1と同じ）。
- 検証行を読み込まない。`validation_rows_loaded: 0`を出力する。

### 5.3 計算

`analyze(rows, features, prefix_texts, token_counts, positions, logprobs, accounts, spec) -> dict`

1. `labels = recipient_first_label(row, accounts)`、`pairs = pair_index(rows, labels)`（120対）。
2. **ベースライン**（位置に依存しない。family・seriesの両fold）：
   - `tfidf`、`length`、`identity`：手順1の`analyze`と同じ。
   - `position`（追加）：特徴は`[A1のtoken index, A2のtoken index, prefixのtoken数]`の3列。`logistic_scores`で計算する。
   - `baseline_best`：family foldの4つの`paired_accuracy`の最大値。
3. **セル**：各位置p ∈ {A1, A2, T, S, G, D}、層l ∈ `report_layers`、probe ∈ `PROBES`について、手順1の`analyze`と同じ項目を計算する。
   - 項目：`paired_accuracy`、`pooled_auroc`、`strata`、`bootstrap_95`、系列除外の値
   - セル名は`"{p}/layer{l}/{probe}"`とする。
   - `judged = (p not in report_only_positions) and (l in judged_layers[p])`。判定セルは42個になることをassertする。
4. **全体のfamily-wise補正**：`rng = np.random.default_rng(seed)`を1つだけ作り、`permutation_repeats`回、
   `flipped = flip_by_series(rows, labels, rng)`を作る。各反復で**判定42セル全体の`paired_accuracy`の最大値**を記録する。
   各判定セルの`family_wise_p = (1 + #{null_max >= observed}) / (1 + repeats)`とする。位置ごとに補正してはならない。
5. **陽性対照**：各位置・各報告層で、`source_role`（tool=1）を240行で`logistic_scores`（family fold）にかけ、AUROCを計算する。
6. **特異性対照**：手順1と同じく、U行で`account_block_position`と主ラベルのAUROCを、各位置・各報告層で計算する。
7. **同位置ロジット（`G`）**：スコア = `logprob_G[先に提示された口座の最初の数字] − logprob_G[後に提示された口座の最初の数字]`。
   fitせずに`paired_accuracy`・`pooled_auroc`・`strata`を計算する。
   `S`では`GB`tokenの対数確率の分布（最小・中央値）だけを記録する。
8. **位置ごとの判定**：判定対象の5位置それぞれについて、`classify(positive_control_best, cells, baseline_best, thresholds)`を呼ぶ。
   - `positive_control_best`：その位置の判定層での陽性対照AUROCの最大値
   - `cells`：その位置の判定セル（全体補正の`family_wise_p`入り）
   - R4の条件は「判定する全層で0.95未満」なので、最大値が0.95未満のときR4になる（`classify`の実装と一致する）。
9. **追加の記述**（判定は変えない）：
   - 特異性：手順1と同じ`comparable_to_control`
   - `G`の各判定セルについて：`probe_paired_accuracy <= logit_paired_accuracy`なら`explained_by_logit_range: true`。
     表示は「同位置ロジットの精度以下」とし、フィールド名から説明関係を主張しない。
10. **仮説への対応づけ**（仕様8節、上から順に適用）：

```python
STAGE_ORDER = ["span", "pre_generation", "call_prefix"]


def stage_class(position_classes, members):
    cs = [position_classes[p] for p in members]
    return "R1" if "R1" in cs else "R2" if "R2" in cs else "R3"  # R4 は先に処理済み


def map_hypothesis(position_classes, stages, r1_cells):
    if any(c == "R4" for c in position_classes.values()):  # 規則0
        return {"rule": 0, "mapping": "deferred_procedure_problem"}
    if all(c == "R3" for c in position_classes.values()):  # 規則1
        return {"rule": 1, "mapping": "none_detected"}
    sc = {s: stage_class(position_classes, stages[s]) for s in STAGE_ORDER}
    first = next((s for s in STAGE_ORDER if sc[s] == "R1"), None)
    if first is None:  # 規則6
        return {"rule": 6, "mapping": "unmapped_pattern", "stage_classes": sc}
    later = STAGE_ORDER[STAGE_ORDER.index(first) + 1 :]
    if any(sc[s] == "R3" for s in later):  # 規則2
        return {"rule": 2, "mapping": "signal_disappears", "stage_classes": sc}
    mapping = {
        "span": "H1_consistent",
        "pre_generation": "H2_consistent",
        "call_prefix": "H3_consistent",
    }[first]  # 規則3〜5
    out = {
        "rule": {"span": 3, "pre_generation": 4, "call_prefix": 5}[first],
        "mapping": mapping,
        "stage_classes": sc,
    }
    if first == "call_prefix":
        out["r1_only_at_G"] = position_classes["S"] != "R1" and position_classes["G"] == "R1"
    return out
```

規則6は、仕様上は規則1・2の後に来る。上の実装では、R1がない場合は規則2が成立しえないので、順序は仕様と等価である。テストで仕様の全7規則を確認すること。

Tの残差の数値差と、42セルへの補正・位置ベースライン追加によるp値やR判定の差は区別する。
後者を数値誤差として説明しない（仕様8節）。

### 5.4 出力

- `publish(artifacts/processed/argrec672-v1-dg-006-position-sweep, {"report.json": ...}, kind="position_sweep")`
- `report.json`の`provenance`：commit、`git_dirty: false`、設定・仕様・runtime freezeのSHA-256、240件の取得bundleのmanifest SHA-256、
  正準bundleのmanifest SHA-256、`validation_rows_loaded: 0`、`research_result: "post_result_train_only_diagnostic"`、`rdr: "RDR-2026-11-06-01"`
- `report`：baselines、cells、null_maxima、陽性対照、特異性、同位置ロジット、位置ごとの判定、仮説への対応づけ。
- 小さい要約（`results/`）と実験ログ（`docs/experiment_logs/`）は、**解析の本実行後に研究実施者の指示で作る**。この作業では作らない。

### 5.5 計算時間の注意

手順1では、BLASを多スレッドで動かすと長時間止まった（[手順1のログ](experiment_logs/2026-11-06_argument_selection_pointer_diagnostic.md)）。
解析のエントリポイントでは、numpy・sklearnをimportする**前に**、環境変数`OMP_NUM_THREADS`・`OPENBLAS_NUM_THREADS`・`MKL_NUM_THREADS`が
未設定なら`"1"`を設定する。runner手順書にも明記すること。

判定42セル×置換100回×6 foldのロジスティック回帰が主な計算量である（手順1の約4倍）。進捗を標準エラーに出すこと。

## 6. CLI

各モジュールに`main()`を置く。サブコマンドは次の5つ。

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_positions tokenizer-preflight configs/analysis/phase2_position_sweep_v1.json
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_positions stem-preflight configs/analysis/phase2_position_sweep_v1.json
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_capture gpu-preflight configs/analysis/phase2_position_sweep_v1.json
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_capture freeze configs/analysis/phase2_position_sweep_v1.json --tokenizer-report <path> --stem-report <path> --gpu-report <path> --environment-lock <path>
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_capture capture configs/analysis/phase2_position_sweep_v1.json --runtime-freeze <path>
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.position_sweep_analysis configs/analysis/phase2_position_sweep_v1.json --runtime-freeze <path>
```

パスはすべてリポジトリ相対で受け取り、絶対パスや`..`を含むパスは拒否する（`load_frozen_plan`の規則と同じ）。

## 7. テスト（合成データのみ。モデル・GPU・実データ不要）

`tests/fixtures/`に小さな合成prefix（offsets付き）と合成トークナイザー（文字単位・特殊tokenあり）を置いてよい。

**位置決定（`test_position_sweep_positions.py`）**

1. `presentation_order`：口座の順が提示テキストの順で決まる。役割を入れ替えた2行で同じ`(first, second)`を返す。口座が0回・2回の場合はValueError。
2. `span_last_token`：重なりの最後のtokenを返す。空offset（`end == start`）を無視する。口座が2回現れればValueError。
3. `call_continuation_ids`：S・G・Dが末尾3位置になる。連結でprefixのtoken列が変わる合成ケースではValueError。`GB`や数字が2 tokenに割れる合成ケースでもValueError。
4. `resolve_positions`：ラベルを反転した行（役割入替え）で、A1/A2が指す口座の文字列が同じになる。Dだけが送金先口座に応じて変わる。
5. 設定の`stem`が、既存設定の`recipient_logprob.stem`と同一である（実ファイルを読んで照合する）。
6. `tokenizer_preflight`の各検査が、該当する合成の違反で失敗する（関数を分けて単体テストする）。

**取得（`test_position_sweep_capture.py`）**

7. 小さな合成モデル（`torch.nn`で`model.layers`・`lm_head`を持つもの）で`capture_condition`を実行する。残差のshapeが`[1, 6, H]`で、位置の順が`A1, A2, T, S, G, D`になる。対数確率が有限で、確率の和がほぼ1になる。
8. bundleの書き込み：manifestのchecksum、既存ディレクトリがあれば失敗、途中で例外が起きても公開ディレクトリが残らない。
9. freeze：作業ツリーがdirtyなら失敗、レポートのcommitが不一致なら失敗、既存ファイルを上書きしない。生成したfreezeを`load_frozen_plan`の照合部分が受け入れる（必要なら照合部分だけを関数として切り出してテストする。`load_frozen_plan`の挙動は変えない）。
10. 再開：完了済みbundleを飛ばす。checksumが合わないbundleでは停止する。

**解析（`test_position_sweep_analysis.py`）**

11. 合成特徴：位置`T`の層24にだけ`recipient_first`の方向を埋め込むと、Tだけが`R1`になり、ほかの位置は`R3`になる。対応づけは規則2（`signal_disappears`）になる。別ケースとしてTとSまたはGに信号を埋め込み、規則4（`H2_consistent`）も確認する。
12. 全体補正：`null_maxima`の各値が判定42セル全体の最大値である（判定セル数を変えた合成ケースで、最大値の取り方を確認する）。
13. 位置ベースライン：A1/A2のtoken indexだけでラベルが決まる合成データでは、位置ベースラインが高くなり、その分R1の基準が上がる。
14. 同位置ロジット：符号と`paired_accuracy`の既知値。`explained_by_logit_range`の境界（等しい場合はtrue）。
15. `map_hypothesis`：仕様8節の規則0〜6それぞれに1ケース以上。例「A2でR1、TでR3」は規則2になる。「Gだけ」でR1のとき`r1_only_at_G`が真になる。
16. リーク防止：検証行を含む入力を渡すと失敗する。同じ対や系列がfoldをまたがない（`_folds`の既存検査を通る）。
17. 再現性：同じseedで同じreportになる。出力先が既にあれば失敗する。

## 8. 品質チェックとコミット

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
python3 -m compileall -q src tests
ruff check .
ruff format --check .
pytest
```

- すべて通ってからコミットする。コミットは機能単位に分けてよい（位置決定／取得／解析）。
- `PROJECT_STATE.md`には「手順3の実装完了、未実行」とだけ1〜2行で追記する。
- 実装中に仕様との不一致や判断の必要な点が見つかったら、コミットせずに一覧にして研究実施者に報告する。

## 9. 実行手順（参考。研究実施者の指示があってから行う）

1. クリーンなcommitで`tokenizer-preflight`と`stem-preflight`を実行する（モデル不要）。
2. 同じcommitで`gpu-preflight`を実行する。
3. `pip freeze > artifacts/phase2-position-sweep-environment-<commit7>.lock`を実行し、`freeze`でruntime freezeを作る。
4. `capture`で240条件を取得する。
5. 取得とは別のcommit（解析コードに変更がなくても、ログ追記のcommitなど）で`analysis`を一度だけ実行する。
6. 結果の要約とログを作る（研究実施者の指示による）。

## 10. 完了時に報告すること

- 作成・変更したファイルの一覧と、各テストの対応する仕様の節
- 品質チェックの出力（失敗があればそのまま）
- 実装上の判断（指示書に書かれていなかった点）と、その理由
- `generations.json`の構造、`logits_to_keep`が使えたかどうか
