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
| 2026-09-22 | [RDR-2026-09-22-01](2026-09-22_pre_gate_engineering_shakedown.md) | accepted | Gate凍結前に、研究データから隔離した非選定engineering shakedownを限定的に許可 |
| 2026-09-16 | [RDR-2026-09-16-01](2026-09-16_agent_boundary_labels.md) | accepted | エージェント境界IDを情報の受け渡し元・先が分かる名称へ変更 |
| 2026-09-15 | [RDR-2026-09-15-01](2026-09-15_pre-pilot_scope_revision.md) | accepted | Pilot前の研究焦点、測定単位、実験規模および期限の改訂 |
