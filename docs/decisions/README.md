# Research Decision Records

このディレクトリには、研究計画または実験プロトコルに対する重要な判断を、Research Decision Record（RDR）として一判断一ファイルで保存する。

[`../research_proposal.md`](../research_proposal.md)は現在有効な研究目的、Research Questionおよび新規性を示し、[`../experimental_protocol.md`](../experimental_protocol.md)は現在有効な実験手順を示す。本ディレクトリは、それらがいつ、どの根拠で変更されたかを記録する履歴であり、現在の手順そのものを重複して定義する場所ではない。

## 記録規則

- ファイル名は`YYYY-MM-DD_short_description.md`とする。
- 各記録に安定した`decision_id`、日付、状態、研究段階およびtest setの確認状況を付ける。
- 変更前の設計、採用した変更、採用しなかった案、科学的根拠、実現可能性上の根拠を記録する。
- 影響を受けるResearch Question、仮説、データ、schema、解析および再現性を明記する。
- Pilotまたはtest setの確認後に変更した場合は、確認済みの情報と変更判断の関係を明記する。
- 過去の記録は書き換えて現在の判断に合わせず、後続のRDRから`supersedes`で参照する。
- 外部資料をGitへ保存しない場合は、確認した資料名、版、日付および取得可能な識別子を記録し、存在しないchecksumを推測しない。

## 状態

- `proposed`: 検討中であり、現行計画には未反映。
- `accepted`: 現行計画またはプロトコルへ反映済み。
- `superseded`: 後続の判断によって置き換えられた。
- `rejected`: 検討したが採用しなかった。

## Index

| Date | Decision ID | Status | Summary |
|---|---|---|---|
| 2026-10-02 | [RDR-2026-10-02-01](2026-10-02_pilot_capture_resource_revision.md) | accepted | pilotの通常Attentionをlast-query集約へ変更し、固定prefix診断を採点専用にする。全sequence詳細保存を事前指定の別immutable派生取得へ移す部分改訂 |
| 2026-10-01 | [RDR-2026-10-01-03](2026-10-01_banking_pilot_sample_freeze.md) | accepted | 初回pilotの6task・4系列・90条件と停止規則を凍結。実行前gateは未完了 |
| 2026-10-01 | [RDR-2026-10-01-02](2026-10-01_existing_tasks_pilot_new_families_test.md) | accepted | 既存系列を予備実験へ、新系列を開発・確認用へ配分。shakedown系列の新規pilot実行を許す部分改訂 |
| 2026-10-01 | [RDR-2026-10-01-01](2026-10-01_banking_task_feasibility_review.md) | accepted | Banking候補の系列・既使用除外・評価器問題を記録し、予備実験前に独立groupの実現可能性を確認する |
| 2026-09-24 | [RDR-2026-09-24-07](2026-09-24_provisional_qwen3_8b_banking_pilot.md) | accepted | ゲート不合格を保持し、Qwen3-8B int8・Bankingを探索的予備実験の暫定構成とする |
| 2026-09-24 | [RDR-2026-09-24-06](2026-09-24_selection_self_audit.md) | accepted | 再実行結果の閲覧後、本人が非blindで14件を自己監査する逸脱と解釈上の限界を記録 |
| 2026-09-24 | [RDR-2026-09-24-05](2026-09-24_selection_audit_trace_rerun.md) | accepted | 初回runの最終回答・生出力欠落を補い、同じ7条件で両候補を再実行するcommitを凍結 |
| 2026-09-24 | [RDR-2026-09-24-04](2026-09-24_banking_selection_gate_freeze.md) | superseded | 初回7条件選定のGit commitと設定checksumの凍結 |
| 2026-09-24 | [RDR-2026-09-24-03](2026-09-24_native_model_selection_gate.md) | accepted | 既存Bankingタスクの7条件で縮小ゲートと選定標本を指定。正式凍結と実行は未了 |
| 2026-09-24 | [RDR-2026-09-24-02](2026-09-24_integration_gate_provisional_thresholds.md) | superseded | 旧暫定閾値。RDR-2026-09-24-03で縮小 |
| 2026-09-24 | [RDR-2026-09-24-01](2026-09-24_integration_gate_partial_decisions.md) | accepted | 統合試験ゲートの候補参照、tie-break、資源上限を部分決定。正式ゲートは未凍結 |
| 2026-09-22 | [RDR-2026-09-22-02](2026-09-22_agentdojo_shakedown_implementation.md) | accepted | AgentDojo、Qwen3候補、Windows / WSL2実行基盤と3 fixtureを固定 |
| 2026-09-22 | [RDR-2026-09-22-01](2026-09-22_pre_gate_engineering_shakedown.md) | accepted | 非選定engineering shakedownを限定許可。系列のpilot再利用禁止はRDR-2026-10-01-02で部分改訂 |
| 2026-09-16 | [RDR-2026-09-16-01](2026-09-16_agent_boundary_labels.md) | accepted | エージェント境界IDを情報の受け渡し元・先が分かる名称へ変更 |
| 2026-09-15 | [RDR-2026-09-15-01](2026-09-15_pre-pilot_scope_revision.md) | accepted | Pilot前の研究焦点、測定単位、実験規模および期限の改訂 |
