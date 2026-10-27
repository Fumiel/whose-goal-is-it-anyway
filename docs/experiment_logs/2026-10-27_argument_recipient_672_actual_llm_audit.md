# 672条件 実走行112件のLLM監査（2026-10-27）

[実走行112件の記録](2026-10-27_argument_recipient_672_b2_b5_and_actual_sample.md)に対する、[監査準備](../phase2_argument_recipient_672_audit_preparation.md)の「実行前に固定した情報」どおりのLLM監査。小さな要約は[results](../../results/2026-10-27_phase2_argument_recipient_672_actual_llm_audit_v1.json)。出力は`artifacts/processed/argrec672-v1-act-003-llm-audit-v1/`（不変、commit対象外）。

## 実行

- 判定者：Codex CLI `0.164.0`の`gpt-6-sol`1つ、読み取り専用、packetに自動評価を含めない。監査prompt v1・JSON schema（checksumは`spec.json`）。
- ランナーcommit `3a6e0d0`（クリーン）。実行前に全112 bundleのchecksumを照合した。112件をrun ID順に1回ずつ判定し、技術失敗・再試行なし。所要は判定時間の合計で約12分（1件最大9.3秒）。
- Codexは設計にも関与したため、設計から独立した判定とは呼ばない。人手監査ではない。

## 結果

| 項目 | 値 |
|---|---|
| 判定済み | 112/112（未判定0、失敗0） |
| LLM `user_task_success` 真 | 67 |
| LLM `recipient_correct` 真 | 98 |
| LLM `required_reads_complete` 真 | 94 |
| LLM対自動strictの`user_task_success`一致 | 112/112（不一致0） |
| 人手確認候補（機械的理由） | 0 |

LLMと自動評価の分類は次のとおり。誤送金14件（受取人誤り）はLLMも`recipient_correct`偽とした。受取人が正しいのに失敗した31件のうち、読取済みの18件はLLMも読取完了と判定しており、金額・件名・日付など受取人以外が原因とみられる。読取なしの13件は、LLMも読取未完了と判定した。これらの個別原因は、生ログで確認していない。

## 解釈の限定

- 単一LLM判定者が自動評価と全件一致した事実は、自動評価の妥当性の補強にとどまる。判定者が1つで設計関与があり、自動評価と同じ観測（tool event・状態）から判定するため、独立な検証ではない。
- 機械的な人手確認候補が0でも、人手で確認したことにはならない。112件は人手未確認のまま。
- 受取人が正しいが失敗した31件の失敗原因別内訳は未集計。
