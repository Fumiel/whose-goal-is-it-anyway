# 2026-09-24 shakedown raw run 監査

対象は WSL ホストの `artifacts/runs/` にある Qwen3-8B int8 と Qwen3-4B BF16 の全 8 bundle（technical failure 1 件を含む）。WSL 上の Codex が raw を読み取り専用で照合した結果を記録する。Mac 側には raw bundle を取得しておらず、この文書の数値を Mac 側で独立再計算したものではない。行動成績や activation 値は集計・転記していない。以下の byte 数は各ディレクトリ内の**全実ファイル**の合計で、`manifest.json` 自体も含む。

| Run ID (`artifacts/runs/` 以下) | manifest 記載 artifact 数 | 総 byte | `git_commit` | `git_dirty` | commit 存在 |
| --- | ---: | ---: | --- | --- | --- |
| `qwen3-8b-int8-shakedown-001-banking_read_only_user_task_1` | 8 | 626,063 | `829278cce1f763f4a62f345e3e946d8d07ea3535` | `false` | 確認 |
| `qwen3-8b-int8-shakedown-001-technical-failure` | 1 | 776 | `run.json` なし | `run.json` なし | 判定不可 |
| `qwen3-8b-int8-shakedown-002-banking_read_only_user_task_1` | 8 | 626,062 | `aed648e5b7ea046e759b4727f81869278ec22045` | `false` | 確認 |
| `qwen3-8b-int8-shakedown-002-banking_multistep_user_task_3` | 8 | 696,276 | `aed648e5b7ea046e759b4727f81869278ec22045` | `false` | 確認 |
| `qwen3-8b-int8-shakedown-002-banking_same_tool_args_user_task_0_injection_0` | 9 | 1,602,643 | `aed648e5b7ea046e759b4727f81869278ec22045` | `false` | 確認 |
| `qwen3-4b-bf16-shakedown-001-banking_read_only_user_task_1` | 8 | 515,452 | `aed648e5b7ea046e759b4727f81869278ec22045` | `false` | 確認 |
| `qwen3-4b-bf16-shakedown-001-banking_multistep_user_task_3` | 8 | 525,305 | `aed648e5b7ea046e759b4727f81869278ec22045` | `false` | 確認 |
| `qwen3-4b-bf16-shakedown-001-banking_same_tool_args_user_task_0_injection_0` | 9 | 1,054,050 | `aed648e5b7ea046e759b4727f81869278ec22045` | `false` | 確認 |

合計 59 artifact、8 manifest、5,646,627 byte。各 manifest の全相対パスについて実ファイルの SHA-256 と byte 数が一致し、欠落・重複記載・未記載ファイルはなかった。`run.json` 内の artifact 一覧と manifest、resolved configuration の checksum も一致した。失敗 bundle は `failure.json` のみを manifest に載せており、`QwenToolCallParseError`（1 assistant turn 内の複数 tool call は非対応）を記録する。失敗 bundle には `run.json`、Git 情報、activation がない。後続の `-002` run の `parent_run_id` は `null` であり、この失敗 bundle への参照は記録されていない。

上表の合計 byte 数と artifact 数は、この文書の行別数値からも再計算して一致する。Mac 側では記録された両 commit の存在と、`aed648e` における実行時 token 照合コードを確認した。WSL での監査コマンドと監査実行時刻はこの記録に含まれないため、raw に対する再実行可能な監査手順の保存は未完了である。

7 件の activation について、各 `metadata.json` の 36 層 `model.layers.0`～`35` と safetensors 内の tensor 名、全層の shape・dtype、データ範囲を照合し、すべて一致した。4B は clean 2 件が各層 `[1, 1, 2560]`、攻撃 fixture が `[1, 4, 2560]`。8B は clean 3 件が各層 `[1, 1, 4096]`、攻撃 fixture が `[1, 4, 4096]`。全層の dtype は metadata の `torch.bfloat16` と safetensors の `BF16` が対応する。int8 は 8B の重みの量子化設定であり、保存した残差 tensor の dtype を意味しない。

保存位置は clean の read-only が `[1919]`、multistep が `[1977]`、攻撃 fixture が `[1619, 1677, 1679, 1689]`（両モデル共通）。各位置は記録された token 列の範囲内にあり、`run.json`・`tokens.json` の位置と token ID、および activation metadata の token 列と一致した。safetensors の第 2 軸も位置数 1 または 4 と一致する。ただし safetensors 単体には元の token index が埋め込まれていないため、各行が物理的にその位置から取得されたことは保存記録間の整合性以上には立証できない。

## RDR-2026-09-22-01 §7 の終了条件

| 項目 | 判定 | 根拠・限界 |
| --- | --- | --- |
| 1. serialization → tool call → return → 次の assistant 生成 | 確認 | 8B `-002` 攻撃 fixture の actual loop に `user_to_assistant`、`first_tool_to_assistant`、`later_tool_to_assistant` の prefix と assistant/tool message が記録されている。 |
| 2. 同一 prefix から正規／攻撃候補を teacher-force scoring | 確認 | 両モデルの攻撃 fixture で両候補の有限 score が保存され、score の `prefix_id` は測定 prefix と一致する。 |
| 3. generation・capture・scoring の入力 token ID 列を比較 | 実行時照合を確認。raw からの独立再照合は不可 | capture 用列は `tokens.json`・metadata・`run.json` で一致する。当時の commit `aed648e` の実装は、capture 後に `activation.assert_matches(prefix)`、scoring 時に候補を付加した入力の prefix と元の token 列の一致確認、generation 後に再直列化した prefix と元の token 列の一致確認を行う。成功 run はこれらの検査を通過して保存された。ただし各経路の入力列を独立した artifact としては保存しておらず、raw だけで再照合できない。 |
| 4. 指定位置の hidden state と shape・位置 | 確認 | 7 件すべてで 36 層の safetensors と metadata が一致し、位置・token ID も記録間で一致する。 |
| 5. 時間・peak GPU memory・保存容量 | 確認 | 7 件の `resolved_config.json` に前二者があり、本監査で各 bundle の byte 数を測定した。 |
| 6. immutable bundle に revision・設定・token・checksum | 確認 | 7 件の通常 run にこれらがあり、checksum が実ファイルと一致する。writer は同名 bundle の上書きを拒否する。失敗 bundle は例外として Git・revision・token 情報を持たない。 |

終了後・正式候補評価前の別要件は未完了。`integration_gate.yaml` には未設定の必須値と `sample_manifest: null`、`tie_break_rule: null` が残る。shakedown 除外対象は `pre_gate_shakedown.yaml` に記録済みだが、凍結済み gate・選定用 sample manifest・新 RDR・その設定 checksum は確認できない。

この監査と当時の実装確認により、終了条件 1～6 は工学的には確認された。ただし項目 3 の raw 単独での再照合はできない。失敗 bundle の Git 情報欠落と後続 run からの参照欠落も provenance 上の制限として残し、既存の immutable raw bundle は変更しない。これらを解消済みと記述したり、shakedown の挙動を候補選定に使用したりしない。
