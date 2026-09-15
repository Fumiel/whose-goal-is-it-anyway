---
decision_id: RDR-2026-09-16-01
date: 2026-09-16
status: accepted
phase: pre-pilot
test_set_status: not_created_or_inspected
affected_files:
  - docs/research_proposal.md
  - docs/experimental_protocol.md
  - docs/reports/進捗報告_大場_20260916.md
supersedes: null
related_decisions:
  - RDR-2026-09-15-01
---

# エージェント境界IDの名称変更

## 1. 判断

エージェント境界の安定IDを、単なる連番から、情報の受け渡し元と次の生成主体を示す名称へ変更する。

| 旧ID | 新ID | 定義 |
|---|---|---|
| `B0` | `user_to_assistant` | ユーザー指示を直列化し、最初のアシスタント生成を始める直前 |
| `B1` | `first_tool_to_assistant` | 最初のツール返却を直列化し、次のアシスタント生成を始める直前 |
| `B2_plus` | `later_tool_to_assistant` | 2回目以降のツール返却後に、次のアシスタント生成を始める直前 |

## 2. 理由

旧IDは順序だけを表し、名称から観測境界の意味を判別できなかった。新IDは、ユーザーまたはツールからアシスタントへ情報が引き渡される境界を直接表す。攻撃の有無や成否を名称に含めないため、攻撃なし条件、攻撃失敗条件、攻撃成功条件で共通して使用できる。

## 3. 影響範囲

この変更は名称だけであり、観測時点の定義、Research Question、仮説、主解析またはデータ分割を変更しない。現時点で確認的test setと生成済みrunはないため、旧IDとの互換性処理は設けない。今後の設定、schema、run metadataおよび解析出力では新IDを使用する。

過去のRDRに記録された`B0`、`B1`および`B2_plus`は、当時の記録を保つため書き換えない。これらを参照する際は、本記録の対応表に従って読み替える。
