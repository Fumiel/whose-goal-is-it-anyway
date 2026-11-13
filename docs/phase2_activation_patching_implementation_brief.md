# 探索的活性化パッチング 実装指示書 — Codex向け

- 作成：2026-11-14。作成はClaude Code（研究実施者の依頼による）。実装とテストはCodexが行う。
- 同日のCodexレビューによる修正を研究実施者がすべて採用した。本書は[RDR-2026-11-14-03](decisions/2026-11-14_patching_preimplementation_review_corrections.md)を反映した実装前の指示であり、実装・実験は未実行。
- **正本は[パッチング仕様](phase2_activation_patching_spec.md)である。** この指示書と仕様が食い違う場合は、仕様が優先する。
  仕様どおりに実装できない点が見つかったら、**仕様を書き換えずに作業を止め、研究実施者に報告する**。
  実装前のレビューで見つけた問題も、実装の前に報告すること。
- 前提とする資料：[RDR-2026-11-14-01](decisions/2026-11-14_h1_scope_and_patching_focus.md)、
  [D除外対照の仕様](phase2_position_sweep_nod_control_spec.md)、[D除外対照の実装指示書](phase2_position_sweep_nod_control_implementation_brief.md)、
  [D除外対照のログ](experiment_logs/2026-11-12_position_sweep_nod_control.md)、[位置スイープの実行手順](phase2_position_sweep_runner.md)。
- **日程：** 仕様第9節により、本取得は**2026-11-20 23:59（JST）までに起動**しなければならない。
  事前確認とfreezeに1日かかるので、実装・テスト・コミットは**2026-11-18中**を目標とする。
  間に合わない見込みになったら、その時点で研究実施者に報告する。

## 0. 作業の範囲と禁止事項

**やること：** 2〜7節を実装し、8節のテストと9節の品質チェックを通してコミットする。

**やらないこと（研究実施者の指示があるまで）：**

- GPUを使う処理（事前確認・取得）、パッチング解析と局所文言ベースラインの本実行。
- 下記の明示的な例外以外の既存ファイルの変更・移動・削除。特に次のものは読み取り専用である。
  - `artifacts/runs/argrec672-v1-003-*`、`argrec672-v1-ps-001-*`、`argrec672-v1-ps-002-*`、`argrec672-v1-ps-003-*`
  - `artifacts/processed/argrec672-v1-dg-006-*`、`dg-007-*`、`dg-008-*`
  - 既存の`*.freeze.json`・事前確認レポート・environment lock・収集manifest
- 既存モジュールの挙動を変える変更。例外は`activation_hooks.py`への独立した`ResidualPatch`クラスの追加だけとし、既存の`ResidualCapture`・関数は変更しない。
  `PROJECT_STATE.md`への実装状況の追記も9節の範囲で許可する。共通化のための既存コードの変更は、変更前に報告する。
- 仕様・RDR・計画書・プロトコルの書き換え。位置・層・移し替え元・閾値・seedの変更。
- 検証側（G/H/I/J）のrun bundle・入力・残差・スコアの読み込みと、取得・donor選択・fit・評価への使用。
  凍結済み宣言全体の整合性検査だけは3.1節の例外とし、読み込みと利用件数を別記する。
- `A1`・`A2`への介入（仕様第14節）。

## 1. 成果物

| 種別 | パス |
|---|---|
| 設定 | `configs/analysis/phase2_activation_patching_v1.json` |
| 書き換えフック | `src/goal_takeover/instrumentation/activation_hooks.py`に新しいクラス`ResidualPatch`を**追加**する（既存の`ResidualCapture`は変更しない） |
| 取得・解析 | `src/goal_takeover/phase2/activation_patching.py` |
| 局所文言ベースライン | `src/goal_takeover/phase2/local_wording_baseline.py` |
| テスト | `tests/test_activation_patching.py`、`tests/test_local_wording_baseline.py`（既存テストは変更せず、すべて通ること） |
| 実行手順書 | `docs/phase2_activation_patching_runner.md` |

## 2. 設定ファイル

`configs/analysis/phase2_activation_patching_v1.json`：

```json
{
  "schema_version": 1,
  "purpose": "Exploratory train-only activation patching at T/S/G. See docs/phase2_activation_patching_spec.md.",
  "spec": "docs/phase2_activation_patching_spec.md",
  "sweep_config": "configs/analysis/phase2_position_sweep_v1.json",
  "nod_config": "configs/analysis/phase2_position_sweep_nod_v1.json",
  "reference": {
    "input_run_id_prefix": "argrec672-v1-ps-002",
    "runtime_freeze": "artifacts/phase2-position-sweep-nod-runtime-0aa063a.freeze.json",
    "collection_manifest": "data/manifests/2026-11-12_phase2_position_sweep_nod_collection.json",
    "candidate_report": "artifacts/processed/argrec672-v1-dg-008-position-sweep-nod/report.json"
  },
  "patching": {
    "run_id_prefix": "argrec672-v1-pt-001",
    "positions": ["T", "S", "G"],
    "layers": [0, 4, 8, 12, 16, 20, 24, 28, 32, 35],
    "donor_kinds": ["matched", "self", "cross"],
    "replacement": "full_residual_block_output",
    "candidate_scoring": "cached_token_by_token",
    "serialization": "patching_recipient_first_v1",
    "seed": 20261027,
    "top_k": 20
  },
  "analysis": {
    "output_id": "argrec672-v1-dg-009-patching",
    "delta_minimum_nats": 1.0,
    "bootstrap_repeats": 2000,
    "bootstrap_seed": 20261027,
    "strong": {
      "mean_minimum": 0.50,
      "interval_lower_minimum": 0.25,
      "direction_mean_minimum": 0.25,
      "family_positive_minimum": 5,
      "source_roles_positive": ["user", "tool"]
    },
    "disrupt_log_mass_threshold": -0.6931471805599453,
    "disrupt_stem_log_likelihood_threshold": -0.6931471805599453,
    "middle_layer_maximum": 24,
    "late_layer_minimum": 28,
    "positive_control": {
      "position": "G",
      "layer": 35,
      "target": "full_vocabulary_next_token_log_probs",
      "comparison": "bitwise_donor_clean"
    },
    "cross_half_ratio": 0.5
  },
  "local_wording": {
    "output_id": "argrec672-v1-dg-010-local-wording-baseline",
    "positions": ["A1", "A2"],
    "window_characters": [32, 64, 128],
    "ngram_range": [2, 5],
    "regularization_c": 1.0,
    "max_iter": 1000,
    "seed": 20261027
  },
  "resources": {
    "maximum_gpu_memory_gib": 12,
    "maximum_seconds_per_condition": 300,
    "maximum_storage_gib_per_condition": 0.05,
    "maximum_total_storage_gib": 2.0,
    "retry_rule": "new_run_id_only",
    "technical_failure_rule": "preserve_immutable_bundle_then_stop"
  },
  "preflight_condition_count": 2
}
```

- **モデル・書き出し・`GB`・ブロックのパス・トークナイザ・口座の値は、`sweep_config`（手順3の設定）と`position_sweep_positions.context()`から読む。** 新しい設定に複製しない。
- `reference`の各ファイルは、読み込み時にSHA-256を記録する。`ps-002`の各bundleの`run.json`の`runtime_freeze_sha256`が`reference.runtime_freeze`のSHA-256と一致し、
  各bundleのmanifestのSHA-256が`reference.collection_manifest`の記録と一致することを要求する。
- 読み込み時に、`layers`がすべて`0..35`の範囲にあること、`positions`が`T`・`S`・`G`だけであることをassertする。
- `candidate_scoring`・`serialization`・陽性対照の比較方式が本書の固定値と一致することも要求する。

## 3. 入力と対の構成（GPU・モデル不要）

### 3.1 行・ラベル・対

- 行は`position_sweep_positions.context(Path(sweep_config), ...)`の240行をそのまま使う。
- この既存helperは`load_frozen_plan()`で検証側も含む宣言全体を読み、整合性を検査してから訓練側を抽出する。
  この検査だけは許可し、それ以降は訓練側240行以外を処理関数へ渡さない。検証側のrun bundleは開かない。
  全コマンドの来歴に`full_declaration_loaded_for_integrity: true`、`validation_declaration_rows_loaded: 192`、
  `validation_run_bundles_loaded: 0`、`validation_rows_used: 0`を記録する。
  今回の新出力では、意味の曖昧な`validation_rows_loaded`を使わない。宣言内の件数も実際に検査する。
- ラベルは`recipient_first_label(row, accounts)`、対は`pair_index(rows, labels)`（どちらも`argument_recipient_672_selection_pointer`）を使う。
- 先の口座・後の口座は`position_sweep_positions.presentation_order(row, accounts)`で決める。
- 各条件の入力は、`ps-002`の`input.json`のtoken列と`positions.json`の位置を、checksumを照合して読む（`position_sweep_positions.verify_manifest`・`verified_json`）。
  `T`・`S`・`G`のtoken indexとtoken IDは`ps-002`の値を使い、`T`が`len(prefix) - 1`、`S`・`G`が入力の末尾2 tokenであることをassertする。

### 3.2 口座の残り

既存の`serialize_qwen_tool_call()`は`sort_keys=True`で引数名を並べるため、`amount`などが`recipient`より先になり、
位置スイープで固定したrecipient先頭の書き出しと一致しない。既存serializerの出力・呼出し元は変更しない。
この用途に限り、新しい`activation_patching.py`内に次のhelperを作ることを明示的に許可する。

```python
def patching_call_text(sweep: dict, row: dict, account: str) -> str:
    """形式IDは patching_recipient_first_v1。
    expected_send_money の name == 'send_money' を検査する。
    引数はrecipientを先頭にし、その値だけをaccountへ置き換え、残りは名前の昇順で全件を保持する。
    外側のキー順はname、argumentsとし、JSONはensure_ascii=False、sort_keys=False、
    separators=(', ', ': ')。囲みは '<tool_call>\n' と '\n</tool_call><|im_end|>'。
    全体が sweep['capture']['stem'] + account で始まることを要求する。
    JSONを戻して、候補口座以外の引数・値が元の宣言と完全に一致することを確認する。"""
```

完全な呼出しはトークン境界確認専用で、モデルの入力には含めない。書き出しと口座の後に続く引数を作る際に、
既存serializerからrecipient以後だけを切り出してはならない（recipientより前の引数を失うため）。

```python
def account_remainder_ids(
    tokenizer, sweep: dict, row: dict, account: str, *, prefix: dict
) -> list[int]:
    """ps-002と同じ正準prefixにpatching_call_text()の完全な呼出しを連結してトークン化する。
    prefix + 書き出し + 'GB' の保存済みtoken列の直後から、口座文字列の最後の文字を含むtokenまでを返す。
    prefixは呼出し側が検証済みの訓練側bundleから読み取り専用で取得して渡し、参照元とchecksumを記録する。
    同じprefix + 書き出し + 口座だけのtoken化でも、残りのtoken列が一致することを要求する。
    次の場合は例外とする（仕様第8節の事前確認1）：
    - prefix + 書き出し + 'GB' のtoken列が変わる
    - 口座の最後の文字を含む token が、口座の後の文字（'"' など）も含む（境界が token の途中にある）
    - 完全な呼出しの該当部分と、口座までのtoken列が一致しない。"""
```

- `patching_call_text()`は新しい実験用の形式であり、既存の正準serializerと同一の文字列とは称さない。
  文字範囲・token offsetで切り出し、閉じ引用符と後続引数は採点しない。形式IDと完全な文字列のSHA-256を位置記録に保存する。

### 3.3 移し替え元の対応表

```python
def donor_table(rows: list[dict], labels, pairs, accounts) -> dict[str, dict]:
    """移し替え先の condition_id -> {"matched": donor_id, "self": 自分の id, "cross": donor_id}。
    matched：対の相手。
    cross：family_id が移し替え先と異なり、recipient_first が matched の移し替え元と同じで、
           presentation_order(row, accounts) が移し替え先と完全に同じ（先の口座・後の口座の文字列の組）条件。
           候補を draft_condition_id の昇順に並べ、
           int(sha256(移し替え先の draft_condition_id の UTF-8).hexdigest(), 16) % 候補数 の番目を選ぶ。
    候補が0件の移し替え先があれば例外とする。ラベル以外の結果（実走行・LD・残差）は使わない。"""
```

- この表は事前確認レポートとrun bundleの両方に保存する。

## 4. 書き換えフック`ResidualPatch`

```python
class ResidualPatch:
    """指定した1つの module（transformer block）の出力のうち、1つの系列位置のベクトルを置き換える。
    with ResidualPatch(model, module_name, sequence_index, vector): model(...)
    - 置き換えは in-place ではなく、出力テンソルを複製して該当位置だけ代入した新しいテンソルを返す。
    - 出力が tuple なら第0要素だけを置き換え、残りの要素と型を保つ。テンソルならテンソルを返す。
    - vector の dtype・device・shape [hidden] が出力と一致しなければ例外とする（暗黙のキャストをしない）。
    - フックが呼ばれた回数を数え、1回でなければ __exit__ で例外とする。
    - sequence_index は、その forward 呼び出しの入力内の添字である（キャッシュ済み部分を含まない）。"""
```

- 既存の`ResidualCapture`と同時に使えること（同じblockに両方のフックを付けたとき、取得されるのは書き換え**後**の値であること）をテストする。
  フックの登録順に依存するので、取得側を後に登録するか、明示的に順序を保証する方法をとる。採った方法を報告する。

## 5. 取得

### 5.1 計算経路（仕様第7節）

1条件（移し替え先）あたりの処理は次のとおりである。

```python
def prefix_cache(model, input_ids, t_index):
    """input_ids[:t_index] を use_cache=True で一度だけ順伝播し、キャッシュを返す。フックは付けない。"""


def run_suffix(model, cache, input_ids, t_index, g_index, patch=None, capture_names=None):
    """cache に続けて input_ids[t_index : g_index + 1]（18 token）を順伝播する。
    patch が None でなければ (module_name, 位置名, vector) で、ResidualPatch を付ける。
    sequence_index は 位置の token_index - t_index（T=0、S=16、G=17）。
    capture_names が与えられれば、T・S・G の全36層の block 出力を ResidualCapture で取る（正常計算のみ）。
    18 位置すべての logits を返す（logits_to_keep は使わない）。"""


def score_candidates(model, cache, g_logits, remainders: dict[str, list[int]], g_length):
    """候補（先の口座、後の口座の順に固定）ごとに：
    1つ目の token の対数確率は G の logits から取る。
    2つ目以降は直前のtokenを1個だけ入力して、その出力から取る（フックなし、入力shapeは常に[1,1]）。
    長さmの候補はm-1回の追加forwardで採点し、未採点の後続tokenを一括入力しない。
    最後の候補tokenそのもののforwardは不要。候補間のバッチ化や共通部分の計算省略もしない。
    各候補の後に cache を g_length（= g_index + 1）へ戻す。
    token 別の対数確率、その和、を返す。"""
```

- 各計算の後、キャッシュを`t_index`の長さへ戻す（`DynamicCache.crop`など）。戻した後の長さをassertする。
  使った方法と、`transformers`の版での動作を報告する。戻せない場合は、prefixのキャッシュを計算ごとに複製する方法でもよい（その場合はGPUメモリを測る）。
- 対数確率は`torch.log_softmax(logits.float(), dim=-1)`で計算する（手順3と同じ）。
- 記録する値（正常計算と各介入）：
  - 候補ごとの口座の残りのtoken別対数確率とその和、`LD = 先 − 後`
  - `G`の先頭数字の対数確率（4候補の数字。手順3の`digit_token_ids`と同じ）と、先 − 後の差、上位20 token
  - `G`の全語彙の次token対数確率分布（`float32`）のshape・dtype・バイト列のSHA-256。全分布は実行中の比較に使い、bundleにはchecksumと比較記録だけを保存する
  - 書き出しの尤度：`T`を書き換えた場合は`T+1`〜`G`の17 tokenの対数確率の和、`S`を書き換えた場合は`G`の対数確率。正常計算では両方を記録する
  - 候補の確率質量：`logsumexp(先の和, 後の和)`
  - 個別の破壊フラグ：候補質量の変化または`T/S`の書き出し尤度の変化が各閾値未満なら理由付きで記録する。`G`の書き出しの変化はnullとする

- 陽性対照は`G`・層35の`matched`で、書き換え後の`G`の**全語彙**の次token対数確率分布をdonorの正常分布と比較する。
  全240条件についてビット一致を要求し、双方のSHA-256・shape・dtype・一致フラグ・最大絶対差を記録する。
  分布の元バイト列をCPUへ移してハッシュ化し、比較前に丸めない。`self`・再確認にも同じ分布checksumを用いる。
  口座全体のP-STRONGは陽性対照の条件にしない。`torch.equal`やJSONの数値の`==`だけを厳密ビット比較の代用にせず、
  tensorは元バイト列、保存するスカラーは明示した浮動小数点型のバイト列で比較する（+0と-0も区別する）。

### 5.2 取得の順序`capture_patching(config_path, runtime_freeze)`

モデルの読み込みより前に、freezeと`load_frozen_plan`（`require_matching_head=True`）の照合を行う。モデルは1回だけ読み込む。

1. **正常計算と移し替え元のベクトル（240条件）：** 条件ごとに`prefix_cache`・`run_suffix`（取得あり）・`score_candidates`を行う。
   `T`・`S`・`G`×10層のblock出力を、**モデルの出力のdtypeのまま**GPUかCPUのメモリに保持する（約59 MB）。
   dtypeを記録し、bfloat16でなければ停止して報告する（bundleへの保存はbfloat16で行うため）。
   正常計算のスコアと`G`の分布checksumも保持する。全36層の正常残差は後のbundle作成用にCPUへ保持し、
   全240件の`G`の全語彙分布もビット比較が終わるまでCPUへ保持する（float32で約0.15 GB）。GPUに全分布を常駐させない。
2. **介入（240条件）：** 条件ごとに`prefix_cache`を作り直し、`donor_table`に従って
   `matched` 30セル → `self` 30セル → `cross` 30セル の順に`run_suffix`（書き換えあり）と`score_candidates`を行う。
   あわせて、その条件の正常計算を同じキャッシュでもう一度行い、手順1の正常計算とビット一致することを確認する（一致しなければ停止する）。
   `G`・層35の`matched`では手順1のdonorの正常分布の元バイト列と直接比較し、checksumも照合して陽性対照の記録を作る。
3. 1条件につき1つのbundleを書く。run IDは`<prefix>-cNNN`（NNNは正準run番号、手順3と同じ規則）。

- 完了済みbundleのスキップ、技術的失敗のbundleの保持と停止、資源上限の扱い（GPUメモリ・1条件の秒数・容量）は、`position_sweep_nod.capture_nod`と同じにする。
  完了済みbundleをスキップして再開する場合でも、手順1の正常計算は240条件すべてやり直す（移し替え元のベクトルをbundleから読み戻さない）。
- 第1パスでの失敗もその条件の新しい不変bundleに`failure_stage: donor_clean`を記録して停止する。
  第2パスは`failure_stage: interventions`とする。1条件の時間は第1パスの正常計算と第2パスの介入・再確認の合計で判定し、
  それぞれの経過秒数、prefix・18token・1token順伝播の回数と時間を別記する。GPUメモリ上限は第1パスにも適用する。
  本取得全体の予測は仕様9.1節に従い、事前確認の実測で更新する。300秒上限を暗黙に緩めない。

### 5.3 bundleの内容

`ImmutableRunWriter`を使い、次のファイルを作る。

| ファイル | 内容 |
|---|---|
| `condition.json` | 条件の宣言（手順3と同じ） |
| `input.json` | `ps-002`のtoken列と、そのSHA-256・`ps-002`のrun ID・manifest SHA-256 |
| `positions.json` | `T`・`S`・`G`のtoken index・token ID・decoded、`t_index`、`g_index`、先の口座・後の口座とその残りのtoken列、形式ID・境界確認用の完全な呼出しのSHA-256 |
| `donors.json` | この条件の`donor_table`の行 |
| `results.json` | 正常計算と91件（`matched`・`self`・`cross`各30、正常計算の再確認1）の5.1節の値・全語彙分布のchecksum・個別破壊フラグ。各介入に移し替え元のcondition ID・run ID・位置・層・module名・ベクトルのSHA-256を付け、陽性対照の比較記録も含める |
| `clean_residual.safetensors` | 正常計算の`T`・`S`・`G`の全36層（bfloat16、shape `[1,3,4096]`） |
| `patch_vectors.safetensors` | `matched`・`cross`で書き込んだ60本のベクトル（bfloat16）。`self`は正常計算と同じなので保存しない |
| `run.json`・`resolved_config.json` | commit、`git_dirty`、freezeのSHA-256、モデル・トークナイザの版、seed、計算経路の設定（キャッシュの戻し方を含む）、経過秒数、ピークGPUメモリ、状態 |

## 6. 事前確認・freeze・CLI

### 6.1 トークン化の事前確認`patching_tokenizer_preflight`（モデル不要）

仕様第8節の1を240条件すべてで確認する。

- `T`より後の17 tokenが全条件で同一であること。
- 3.2節の口座の残りが、全条件の両候補で作れること。
- 対内の2口座で、口座の残りの最初のtokenが異なること。
- `donor_table`が240条件すべてで作れること。

あわせて`ps-002`の入力・位置・manifest・freezeを照合する。1件でも満たさなければ、除外せずに停止する。
出力は`artifacts/phase2-activation-patching-tokenizer-preflight-<commit7>.json`（新規作成のみ）。

### 6.2 GPU事前確認`patching_gpu_preflight`

`condition_id`の昇順で先頭2件について、次を行う。bundleは書かない。

1. **経路の比較（仕様8.2、停止しない）：** 正常計算の`T`・`S`・`G`の全36層と`G`の先頭数字の対数確率を、`ps-002`の保存値と比べる。
   ビット一致の数と最大相対L2差を記録する（`position_sweep_nod.compare_vectors`を使う）。
2. **`self`の一致（仕様8.3、停止する）：** 30セルすべての`self`の結果が、正常計算とビット単位で一致すること。
3. **キャッシュの復元（仕様8.4、停止する）：** 同じ`matched`の介入（`T`・層24）を2回続けて行い、結果がビット単位で一致すること。
4. **資源（仕様8.5）：** ピークGPUメモリが12 GiB以下であること。第1パス・全90介入・再確認を含む1条件の時間が300秒以下であること。
   donorの正常値を得るために必要な訓練側条件も正常計算だけ行い、追加条件のID・時間を別記する。
   1token・18tokenの順伝播の回数・時間、prefix計算・比較・I/O等の時間を分け、全240条件の取得時間を外挿する。
   preflightの繰り返し比較用の追加計算は、本取得1条件の時間見積もりと区別する。
5. **陽性対照（仕様8.6、停止する）：** `G`・層35の`matched`の全語彙の次token対数確率分布がdonorの正常分布とビット一致すること。

`matched`と`cross`の介入効果（`LD`など）は、この段階では**計算しても記録しない**。陽性対照の分布比較については、shape・dtype・checksum・一致フラグ・最大絶対差だけ記録してよい。
仕様第8節の「正常計算の`LD`と`Δ`は事前確認では集計しない」に従い、正常計算の`LD`も記録しない（`self`との一致はビット比較の結果だけを記録する）。
出力は`artifacts/phase2-activation-patching-gpu-preflight-<commit7>.json`（新規作成のみ）。

### 6.3 runtime freeze`create_patching_runtime_freeze`

`position_sweep_nod.create_nod_runtime_freeze`と同じ形式にし、`load_frozen_plan(..., runtime_freeze_override=<新freeze>, require_matching_head=True)`がそのまま通ることを要求する。
`analysis_config_sha256`は新しい設定、`spec_sha256`はパッチング仕様のSHA-256とする。
`files_sha256`には2つの事前確認レポートとenvironment lock（`artifacts/phase2-activation-patching-environment-<commit7>.lock`）を入れる。
`reference_sha256`には`reference`の3ファイルを入れる。出力は`artifacts/phase2-activation-patching-runtime-<commit7>.freeze.json`。`open(..., "x")`で作り、上書きしない。

### 6.4 収集manifest

`position_sweep_nod.write_collection_manifest`と同じ形式で、`data/manifests/<日付>_phase2_activation_patching_collection.json`を作る関数を用意する。

### 6.5 CLI

```bash
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.activation_patching tokenizer-preflight configs/analysis/phase2_activation_patching_v1.json
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.activation_patching gpu-preflight configs/analysis/phase2_activation_patching_v1.json
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.activation_patching freeze configs/analysis/phase2_activation_patching_v1.json --tokenizer-report <path> --gpu-report <path> --environment-lock <path>
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.activation_patching capture configs/analysis/phase2_activation_patching_v1.json --runtime-freeze <path>
PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.activation_patching collection-manifest configs/analysis/phase2_activation_patching_v1.json --runtime-freeze <path> --output <path>
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.activation_patching analyze configs/analysis/phase2_activation_patching_v1.json --runtime-freeze <path>
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 PYTHONPATH=src .venv/bin/python -m goal_takeover.phase2.local_wording_baseline run configs/analysis/phase2_activation_patching_v1.json
```

- パスはすべてリポジトリ相対で受け取り、`safe_path`で検査する。
- `analyze`と`local_wording_baseline run`は、numpy・sklearnのimport前に3つのBLAS変数を、未設定なら`"1"`にする。出力先が既にあれば、計算の前に停止する。
- `analyze`は、取得と同じcommitでの実行を拒否する（手順3・D除外対照と同じ）。

## 7. 解析

### 7.1 パッチング解析`analyze` → `dg-009`（CPUのみ）

**入力：** `pt-001`の240件。manifestのchecksum、freeze、commit、condition、入力token列、`donors.json`を照合する。検証行があれば停止する。

**手順の健全性（仕様6.2）：** 最初に確認し、結果を`health`節に記録する。

- `self`の全240条件×30セルが正常計算とビット一致すること（`results.json`の値で比較する）。
- 正常計算の再確認（5.2節の2）が全条件で一致していること。
- `G`・層35の全240件で、全語彙分布のchecksumがdonorの正常計算と一致し、実行中のビット比較も合格していること。
  SHA-256だけでなく、保存されたshape・dtype・対応するcondition IDと比較記録も照合する。

**指標（仕様第5節）：**

```python
def pair_effects(clean_ld: dict, patched_ld: dict, pairs, labels, delta_minimum) -> dict:
    """対 (x, y)（labels[x]=1, labels[y]=0）ごとに：
    delta = LD_clean(x) - LD_clean(y)
    delta < delta_minimum なら除外（除外理由 "small_or_reversed_delta" と、両方向の LD の生の変化を記録）
    NE(x→y) = (LD_patched(y←x) - LD_clean(y)) / delta
    NE(y→x) = (LD_clean(x) - LD_patched(x←y)) / delta
    NE_pair = (NE(x→y) + NE(y→x)) / 2。値は切り詰めない。"""
```

- `cross`も同じ式で、移し替え先の対の`delta`を分母にする（`patched_ld`に`cross`の値を入れる）。
- 副指標：donor符号一致率（書き換え後の`LD`の符号が移し替え元の正常`LD`の符号と一致する割合。どちらかが0なら不一致として数える）、
  先頭数字のロジット差、候補の確率質量の変化（書き換え後 − 正常）、書き出しの尤度の変化。
- 各実行の破壊フラグと理由を再計算して照合し、件数・割合を報告する。フラグによる追加除外は行わず、個別の成功例としては扱わない。

**セルの判定（仕様6.1、`matched`のみ、上から順に）：**

- `P-DISRUPT`：除外していない対の`matched`の全実行（2方向）で、候補の確率質量の変化の中央値が`disrupt_log_mass_threshold`未満、
  **または**`T/S`の書き出しの尤度の変化の中央値が`disrupt_stem_log_likelihood_threshold`未満。どちらの理由かも記録する。
  `G`の書き出しの変化はnullであり、この分岐を適用しない。閾値ちょうどは破壊にしない。
- `P-STRONG`：`NE_pair`の平均 ≥ 0.50、bootstrap 95%区間の下限 ≥ 0.25、方向ごとの平均（`NE(x→y)`の平均、`NE(y→x)`の平均）がともに ≥ 0.25、
  6ファミリー中5以上でファミリーの`NE_pair`平均 > 0、`source_role`のuser・toolの両方で平均 > 0。
- `P-PARTIAL`：区間の下限 > 0。
- `P-NONE`：それ以外。
- bootstrap：対象の対を`semantic_series_id`でまとめ、系列を復元抽出する（`bootstrap_repeats`回、`bootstrap_seed`）。各回の`NE_pair`平均の2.5・97.5パーセンタイルをとる。
  既存の`series_bootstrap`は対内正解率用なので、同じ再標本化の方法で平均用の関数を新しく書く。
- 除外後の対が0件のセルは判定せず、`"undefined"`とする。

**陽性対照（仕様6.2）：** `G`・層35の`matched`とdonor正常計算の全語彙の次token対数確率分布のビット一致。
`P-STRONG`の有無とは独立に、分母で除外した対も含めた全240件を確認する。

**仮説への対応づけ（仕様6.3、上から順に）：**

```python
def map_patching(
    cells: dict, health_ok: bool, positive_ok: bool, middle_max=24, late_min=28
) -> dict:
    """L*(p) = その位置で P-STRONG となる最も浅い層（なければ None）。
    0: not health_ok or not positive_ok、または対象対0件で全セルundefined -> "held"
    1: L*(T) <= middle_max -> "H2_consistent"
    2: L*(S) <= middle_max or L*(G) <= middle_max -> "H3_consistent"
       説明は「Tの中間層では強効果基準に達せず、S/Gの中間層では達した」。Tの部分効果を否定しない。
    3: どれかの位置で L*(p) >= late_min -> "late_layer_only_no_mapping"
    4: P-STRONG がどこにもない -> "no_strong_single_site_effect"
    rule 番号、各位置の L*、根拠のセルを返す。
    規則1・2の場合、根拠のセルについて cross の NE_pair 平均 / matched の NE_pair 平均 >= cross_half_ratio なら
    "same_accounts_order_cross_context_ge_half" を、そうでなければ "selected_cross_context_lt_half" を併記する。
    cross自身がP-DISRUPT相当なら比率だけを示し "cross_disrupted_interpretation_held" とする（判定は変えない）。
    提示順と口座identityの識別、文脈の必要性、選択が初めて決まる時点の証明とは記述しない。"""
```

- 規則0〜4で全ケースが尽くされる（仕様第17節の修正後）。どれにも当たらない組合せが見つかった場合は例外とし、報告する。
- `L*`がNoneの場合を先に検査し、数値との比較は行わない。手順確認に合格して全セルにP-STRONGがなければ規則4に到達する。
  分母で全対が除外されて全セルundefinedの場合は「強効果なし」とせず、`mapping: held`、`reason: no_eligible_pairs`とする。
  深層のみを対応づけに使わないのは事前の範囲制限であり、「T/Sの深層もGの出力を直接置き換える」とは説明しない。

**出力：** `publish(artifacts/processed/argrec672-v1-dg-009-patching, {"report.json": ...}, kind="activation_patching")`。

- 30セルの判定と全統計（平均、区間、方向別、ファミリー別、`source_role`別、副指標・両中央値・破壊フラグ）、`cross`の同じ統計、除外した対の一覧、`health`、陽性対照、対応づけ。
- `provenance`：commit、`git_dirty: false`、設定・仕様・freeze・referenceのSHA-256、全bundleのmanifest SHA-256、
  3.1節の宣言読み込み・検証bundle読み込み・検証行利用の別々の項目、`research_result: "post_result_train_only_exploratory_intervention"`。

### 7.2 局所文言ベースライン`local_wording_baseline run` → `dg-010`（CPUのみ、GPU・モデル不要）

仕様第11節による。

- 行・ラベル・対は3.1節と同じ。テキストは`argument_recipient_672_selection_pointer.presentation_text(row)`、口座は`presentation_order(row, accounts)`で決める。
- 特徴：各位置の口座が提示テキストで始まる文字位置の直前N文字（先頭が足りなければテキストの先頭から）。口座文字列自体は含めない。
- モデル：`TfidfVectorizer(analyzer="char", ngram_range=(2, 5))` + ロジスティック回帰（L2、C=1.0、`max_iter`=1000、seed 20261027）。
  既存の`text_scores`と同じ構成であり、テキストを差し替えて**`text_scores`を呼ぶ**ことで実装できるはずである。呼べない場合は理由を報告する。
- fold：ファミリー除外（6 fold、主）と系列除外（40 fold、比較）。指標は`paired_accuracy`。
- 出力：`publish(artifacts/processed/argrec672-v1-dg-010-local-wording-baseline, ...)`。位置×N×foldの対内正解率、各条件で使った窓の文字範囲、
  `provenance`（3.1節の宣言読み込みと検証側未使用の項目、`research_result: "formal_record_of_post_result_informal_check"`）。
- このコマンドは手順3・D除外対照の判定を変更しない。値を比べて上書きする処理を入れない。

## 8. テスト（合成データのみ。モデル・GPU・実データ不要）

**入力と対**

1. `account_remainder_ids`：境界がtokenの途中にある合成トークナイザで例外になる。正常な場合に書き出し + `GB`の後の正しいtoken列を返す。
   `patching_call_text`はrecipient先頭・他の引数名昇順・全引数保持・候補口座以外の値の一致を満たす。既存serializerの出力が不変であることも確認する。
2. `donor_table`：`cross`が別ファミリー・同じラベル・同じ口座の組から決定的に選ばれる。同じファミリー、異なる口座の組、異なるラベルが選ばれない。行順を入れ替えても同じ結果になる。候補0件で例外になる。
3. `T`・`S`・`G`の位置：prefix長が対内で異なる合成例でも、末尾からの位置で同じtokenを指す。

**フックと計算経路**（小さな合成のdecoder-onlyモデル。実モデルは使わない）

4. `ResidualPatch`：`self`の書き換えで出力がビット一致する。別のベクトルを書き込むと、指定した位置より前の出力が変わらず、
   その位置の値が変わる。後続attention blockがある合成例では後の位置への伝播も確かめる。
   最終block出力の置換が他の位置や既存KVを自動的に置き換えるとは期待しない。
   dtype・shapeの不一致で例外になる。tuple出力とテンソル出力の両方を扱える。呼び出し回数が1回でなければ例外になる。
5. `ResidualPatch`と`ResidualCapture`を同じblockに付けたとき、取得されるのが書き換え後の値である。
6. キャッシュ：`prefix_cache` + `run_suffix`の結果が、全系列を一度に順伝播した場合の対応する位置と（合成モデルのfloat32で）許容誤差内で一致する。戻した後に同じ計算を2回行うとビット一致する。
7. `score_candidates`：1つ目のtokenの対数確率がGのlogitsから取られる。候補ごとに戻した後、2つ目の候補の結果が、1つ目を計算しなかった場合とビット一致する。
   長さmの候補について追加入力はm-1回すべて`[1,1]`で、最後のtokenや未採点の後続tokenを入力しない。
   一括入力なら未来tokenに依存してしまう合成モデルでも、今回の逐次採点では前のtokenのスコアが不変となること。

**指標と判定**

8. `pair_effects`：既知の`LD`で`NE`の両方向の値と符号が合う。`delta < 1.0`と`delta < 0`の対が除外される。1を超える値・負の値が切り詰められない。
9. セルの判定：`P-DISRUPT`が`P-STRONG`より優先される。各閾値の境界（ちょうど0.50、ちょうど0.25、5/6ファミリー）で正しく判定される。除外後0件で`"undefined"`になる。
   候補質量は保たれて書き出し尤度だけが閾値未満の例でもP-DISRUPTとなり、各破壊閾値と同値なら破壊にしない。Gのnullを0扱いしない。
   donor符号一致率は元から同符号でも数え、どちらかが0なら不一致とする。
10. bootstrap：同じseedで同じ区間になる。系列単位で再標本化している（対単位ではない）。
11. `map_patching`：規則0〜4のそれぞれに当たる合成のセル判定で正しい規則になる。特に、`G`・`S`・`T`のどれか（または複数）の層28以上だけがP-STRONGなら規則3、`T`の層24がP-STRONGなら規則1、`T`の層28だけがP-STRONGで`G`の層16がP-STRONGなら規則2になる。`cross`の併記が判定を変えない。
12. `health`：`self`が1件でも不一致なら対応づけが`"held"`になる。
    陽性対照は全語彙のビット一致を検査し、4候補以外に差がある場合も不合格にする。
    donorとGの分布が一致し、口座全体のP-STRONGはない例でも合格し、全セル非P-STRONGなら規則4に到達する。
    TがP-PARTIALでS/Gが中間層P-STRONGの場合の説明を確認し、全対除外の場合はno_eligible_pairsで保留する。
    crossの記述が口座identityと順序を区別したことや文脈必須を主張しないこと、cross破壊時は解釈を保留することも確認する。

**局所文言ベースライン**

13. 窓の切り出し：口座の直前N文字を正しく取り、口座文字列を含まない。テキストの先頭近くで足りない場合に先頭から取る。
14. 窓にだけラベルの手がかりを埋め込んだ合成データで、対内正解率が高くなる。

**共通**

15. リーク防止：宣言の全体検査は通るが、取得・donor選択・fit・評価の処理関数に検証行を渡すと失敗し、検証bundleは開かれない。
    宣言読み込み192件と利用0件が区別して記録される。出力先が既にあれば失敗する。同じseedで同じ出力になる。
16. freeze：作業ツリーがdirty、レポートのcommitが不一致、referenceのSHA-256が不一致、既存ファイルがある、の各場合に失敗する。
17. bundle：完了済みはスキップされ、checksum不一致で停止する。
    donor正常計算の第1パスでの例外も不変な失敗bundleを保持して停止し、2パス合計の時間上限を検査する。

## 9. 品質チェックとコミット

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
python3 -m compileall -q src tests
ruff check .
ruff format --check .
pytest
```

- すべて通ってからコミットする（機能単位に分けてよい）。
- `PROJECT_STATE.md`には「パッチングの実装完了、未実行」とだけ1〜2行で追記する。
- 仕様との不一致や判断の必要な点が見つかったら、コミットせずに一覧にして研究実施者に報告する。

## 10. 実行手順（参考。研究実施者の指示があってから行う）

1. クリーンなcommitで`tokenizer-preflight`を実行する（モデル不要）。
2. 同じcommitで`gpu-preflight`を実行する。
3. `set -o noclobber`のうえで`pip freeze > artifacts/phase2-activation-patching-environment-<commit7>.lock`を実行し、`freeze`を実行する。
4. `capture`を起動する（**2026-11-20 23:59 JSTまで**。起動の日時をログに記録する）。
5. `collection-manifest`で取得のmanifestを作り、ログと一緒に別のcommitに保存する。
6. その別のcommitで`analyze`を一度だけ実行する。
7. `local_wording_baseline run`を一度だけ実行する（GPU不要なので、1〜6と独立に実行してよい。ただしクリーンなcommitで行う）。
8. 結果の要約とログを作る（研究実施者の指示による）。

## 11. 完了時に報告すること

- 作成・変更したファイルの一覧と、各テストが対応する仕様の節
- 品質チェックの出力（失敗があればそのまま）
- 許可した`ResidualPatch`の追加と`PROJECT_STATE.md`追記以外に既存ファイルの変更がなく、既存モジュールの挙動も変えていないことの確認（`git diff --stat`等）
- 実装上の判断（この指示書に書かれていなかった点）と、その理由。特に次の点：
  - フックの順序の保証方法（4節）
  - キャッシュの戻し方と`transformers`の版での動作（5.1節）
  - recipient先頭の専用直列化helperと既存serializerの違い（3.2節）、宣言の検証例外と利用0件の記録
  - 逐次採点の回数・全語彙分布のビット比較・書き出し破壊判定が仕様と一致すること
