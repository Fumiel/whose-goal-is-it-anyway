# Pilot runner の実装と使用方法

2026-10-02、凍結済みBanking標本を扱うrunnerとテストを追加した。
条件・順序・停止閾値・標本freezeは変更していない。研究判断の正本は
[プロトコル第5.3節](experimental_protocol.md)と
[RDR-2026-10-01-03](decisions/2026-10-01_banking_pilot_sample_freeze.md)である。
利用者の指定により、capture値の決定とGPU実行は次の作業に残した。

## 実装と検証範囲

`src/goal_takeover/pilot/`にplan、native preflight、strict evaluation、位置対応、
Attention取得、GPU service、段階実行、監査・集計を置いた。
途中失敗を含むrun recordは専用`data/schemas/pilot_run.schema.json`（v1）で検証し、
既存の一般run v2 schemaを変更しない。
`QwenTransformersBackend.next_action_from_prefix`により、生成・残差取得・候補採点が
同じ直列化済みprefixを受け取る。tool返却のJSONエスケープも位置対応に含める。

実軌跡の全assistant境界を記録し、宣言vectorへの初回接触でIPI位置・window・候補採点を
取得する。初回接触が後続返却ならlater境界と実際の返却番号を保持する。非接触では
行動結果と欠測理由を残す。leadの12 IPIには別環境の固定prefix診断を付ける。
診断は追加条件や実軌跡の成功件数として数えない。

全候補sequence、各slot、重複tokenを除いたjoint、whole-callのmarginを保存する。
後続slotが先行candidate tokenに条件付くことも記録する。
native判定、厳密な新規操作・最終状態・副作用、宣言攻撃call発生を別ラベルとし、
途中で復元された不正操作も副作用として残す。人手監査前のstrict値は自動判定にすぎない。

AttentionはQwen3 self-attentionの`(output, weights)`をhookで確認し、各層で集約した後に
weightsを解放する。通常保存で全層の行列を保持しない。完全行列は事前指定subsetのみ
CPUへ保存する。実際のbackendがweightsを返さない場合は明示的に停止する。
固定revisionの[Qwen chat template](https://huggingface.co/Qwen/Qwen3-8B/blob/b968826d9c46dd6066d109eabc6255188de91218/tokenizer_config.json)と
[Transformers 4.51.3の公式実装](https://github.com/huggingface/transformers/blob/v4.51.3/src/transformers/models/qwen3/modeling_qwen3.py)
を照合した。インストール先でのtokenizer・Attention・GPU互換性の完了は主張しない。

unit/integration testは小さい合成adapterを使用し、実験結果ではない。
90条件のmodel-free制御経路、先行18→監査→拡張72、陰性結果、監査不一致と裁定、
prefix/shape/非有限値、JSON文字範囲、失敗保存、再試行来歴、上書き・改変検出を検証する。
native AgentDojo対照検証、固定tokenizerによる位置検証、CUDA・容量の実測は未実施。
2026-10-02の検証用venvでは`unittest`/`pytest`の83件が成功し、AgentDojo未導入の
既存native test 3件はskipした。`compileall`、Ruff、repository宣言と標本freeze照合も成功した。

## 実行前gate

標本設定の`capture`に残るnullは埋めない。別runtime freezeを用意するまで
`agentdojo-pilot`はweights読み込み前に停止する。

runtime freezeはYAML/JSON mappingで、次を必要とする。

| Key | 要件 |
|---|---|
| `schema_version`, `status` | `1`, `frozen` |
| `sample_freeze_sha256` | 既存の標本freezeファイルのSHA-256 |
| `git_commit` | 実行codeのHEAD commit。作業treeがcleanであること |
| `files_sha256` | repository相対path→SHA-256。全`src/goal_takeover/**/*.py`、全`configs/**/*.yaml`、全`data/schemas/*.json`を含む。runtime自身は除く |
| `chat_template_sha256`, `tool_schema_sha256` | 固定tokenizerとnative suiteから検証したdigest |
| `capture` | 標本の固定項目を維持し、未定window左右幅と全sequence/全Attentionのcondition IDリストを明示。空リストは可、nullは不可 |
| `capture.position_rule_version` | 実装候補`protocol_offsets_v1`。固定tokenizerでの検証後に凍結する |
| `capture.attention` | 対応する実装候補は`query_position: Tend_assistant`、`aggregation: sum_and_mean`、`key_ranges: [user_goal, intervention, tool_metadata]` |
| `password_suspicion_review` | `approved: true`、`reviewer_id`、`evidence`、`rubric`。task 14の不審取引根拠を人が判断した記録 |
| `capture_resource_preflight_passed` | 指定captureと全sequence subsetがGPU・保存上限を満たすことを実測した後に`true` |

この表は対応可能な実装仕様であり、未決定capture値の採用や事前検証の代替ではない。
別のquery・集約・位置規則を採る場合は実装とtestを追加し、新runtime freezeにする。
runtimeを`artifacts/`等のGit対象外へ置けば、実行commit確定後にfreezeを作成でき、
freeze自身に自分のcommit hashを書き込む循環を避けられる。sample freezeは保持する。

## コマンド

以下はresearch依存関係と実行前gateの完了後に使う。`pilot-preflight`は全90条件を
native環境で検証し、モデルを読み込まない。無操作・正規・攻撃・誤対象・副作用の対照を
検証し、nativeとstrictの差を出力する。task 14の判断は別runtime reviewに残す。

```bash
goal-takeover pilot-preflight configs/experiments/banking_pilot_v1.yaml \
  > artifacts/pilot-native-preflight.json

goal-takeover agentdojo-pilot configs/experiments/banking_pilot_v1.yaml \
  --runtime-freeze artifacts/pilot-runtime.freeze.json \
  --run-prefix banking-pilot-001 --stage lead

goal-takeover pilot-audit-template configs/experiments/banking_pilot_v1.yaml \
  --run-prefix banking-pilot-001 > artifacts/pilot-lead-audit.json

goal-takeover pilot-report configs/experiments/banking_pilot_v1.yaml \
  --run-prefix banking-pilot-001 --audit artifacts/pilot-lead-audit.json

goal-takeover agentdojo-pilot configs/experiments/banking_pilot_v1.yaml \
  --runtime-freeze artifacts/pilot-runtime.freeze.json \
  --run-prefix banking-pilot-001 --stage expansion \
  --audit artifacts/pilot-lead-audit.json
```

拡張後は`pilot-audit-template`で90件時点の監査対象を再抽出する。
新しい監査票には先行18件も含まれる。先行監査票は保存したまま、初回判断・裁定・
blind状況を新しい監査票へそのまま引き継ぎ、追加対象だけを新たに記入する。
完成した監査票を`pilot-report`へ渡す。
監査票には自動ラベルやaggregateを入れず、初回判断と裁定を別欄に保存する。
`first_judgment`はnative user/attack、strict user、宣言攻撃call発生、副作用有無のboolを
要求する。`automatic_strict_user_task_success`というkeyを用いるが、記入値は人の判定である。
`reviewer_id`、`reviewed_at`、`evidence`、実際の`blind_to_automatic_labels`と
`model_aggregates_seen`も必須。不一致には`adjudication.labels`と裁定者・時刻・理由・証拠を残す。
bundle manifest checksumに監査を結び付け、rawファイルを編集しない。

## 出力・失敗・再試行

条件run IDは`<prefix>-c<execution_order>-a<attempt>`。各stageには
`<prefix>-lead-status`または`<prefix>-expansion-status`のimmutable状態bundleを残す。
条件bundleはresolved config、condition、messages、raw generationと生成token IDs、全prefix、
tool eventの前後状態、初期・最終状態、各測定の残差・Attention・採点とmanifestを含む。
診断とactualのscopeを明示し、全境界のtoken index/ID・offset・規則を保存する。

parse不成立、未知tool、tool error、最大step到達はモデルの実験上の失敗として保持し、
同条件を再生成しない。prefix不一致・曖昧な範囲・非有限値・OOM・資源超過などでは
直ちにbatchを止め、部分traceと残る未実行条件を残す。
300秒deadlineはPOSIX/WSLで適用し、GPU peakとbundle容量も各処理で確認する。
障害の保存自体が外部disk障害で不可能な場合には例外が返り、保存完了とは報告しない。

再試行を認めるのは`ExternalInfrastructureInterruption`で明示された外部中断かつ
最初のモデル出力前だけで、最大1回、新run ID・親参照・同じruntime freezeを要求する。
一般的なRuntimeError、OOM、parse error、timeoutをこの例外へ読み替えない。
既存stageの自動再開や別prefixによる同条件の都合のよい再生成は提供しない。
停止後の変更・再収集はプロトコルに従ってRDRと新freezeで判断する。

最終reportはclean分母6、native outcomeとbaseline_failure、技術的失敗、監査欠測、
実軌跡で接触・取得・採点できたtask系列を保持する。
Phase 2設計への移行は主モデル採用や確認的testの実行許可を意味しない。
