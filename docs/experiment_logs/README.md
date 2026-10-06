# Experiment logs

このディレクトリには、実験・工学的shakedownの実施記録を日付付きで保存する。
実行目的、設定とrun ID、観測した技術的事実、失敗と修正、検証できた範囲を記す。
正式な実験手順は`../experimental_protocol.md`、設計変更の判断は
`../decisions/`に記録する。

`../reports/`は教授への進捗報告など、提出・共有用の文書に使用する。
raw run、モデルweight、生activationなどの大きなデータはここにコピーせず、
`artifacts/runs/`または外部保存先に保持する。

## Index

- [2026-10-07 Banking pilot GPU停止後の再開実行（90条件収集完了、拡張監査待ち）](2026-10-07_pilot_gpu_recovery_execution.md)
- [2026-10-07 51番prefixのGPUキャッシュ計測](2026-10-07_c051_gpu_cache_measurement.md)
- [2026-10-07 post-gate探索的継続の技術的停止](2026-10-07_post_gate_continuation_technical_stop.md)
- [2026-10-02 pilot capture修正後の実行前計測](2026-10-02_capture_repair_preflight.md)
- [2026-10-02 pilot初回実行前計測](2026-10-02_pilot_preflight_measurements.md)
- [2026-10-02 task 14実行前の人手審査資料](2026-10-02_task14_preexecution_review_packet.md)
- [2026-10-02 Banking pilot先行18件の実行と人手監査への引き継ぎ](2026-10-02_banking_pilot_lead_execution.md)
- [2026-09-24 Banking選定再実行の自己監査用引き継ぎ](2026-09-24_banking_selection_self_audit_handoff.md)
- [2026-09-24 Banking選定試験の初回run監査](2026-09-24_banking_selection_first_run_audit.md)
- [2026-09-24 shakedown raw run 監査](2026-09-24_shakedown_raw_audit.md)
- [2026-09-24 AgentDojo / Qwen3-4B BF16 engineering shakedown](2026-09-24_agentdojo_qwen3_4b_shakedown.md)
- [2026-09-24 AgentDojo / Qwen3-8B int8 engineering shakedown](2026-09-24_agentdojo_qwen3_8b_shakedown.md)
