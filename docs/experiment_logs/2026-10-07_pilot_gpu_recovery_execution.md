# 2026-10-07 Banking pilot GPU停止後の再開実行

[RDR-2026-10-07-02](../decisions/2026-10-07_pilot_gpu_recovery.md)の専用経路で、
旧51番の失敗bundleと旧拡張stageを保持したまま、51番を`c051-a2`として取得し、
52～90を凍結順に実行した。実行code commitは
`9fa8985ace6642e466f334524054cad61656675b`、別runtime freezeは
`artifacts/pilot-runtime-recovery.freeze.json`
（SHA-256 `480e5d582dc09b4fe47679c048003bc1272c84fd3ee27c56217c83dac690a536`）。
Authorizationは`configs/experiments/banking_pilot_technical_recovery_v1.json`。

新たな40条件はすべて`completed`。別の不変stage bundle
`artifacts/runs/banking-pilot-001-recovery-status`は`awaiting_human_audit`、
`stop=null`、40 run pathを記録する。stage manifestのSHA-256は
`f0f671628830a962b6cbff1d17ad0c3572a4d5632add11147150b9f07e238e85`。
全90条件のbundle manifestを`load_records`で検証し、最終状態は
`completed` 90、条件の新規試行を含む総attempt数91である。旧`c051-a1`は
引き続き`technical_failure`として保存し、`c051-a2`の親runとして参照する。
51番新runのper-condition GPU peakは11.06 GiB、全90条件の完了runの最大は
11.70 GiBであり、凍結した12 GiBを超えていない。

監査前の機械集計は`artifacts/pilot-full-unaudited-report-2026-10-07.json`、
blind用の空欄票は`artifacts/pilot-full-audit-template-2026-10-07.json`に別々に保存した。
各SHA-256は順に`815df1f0d47131e9c18467bd4b0e7d059529e9f36f3ce4dc9c9ead73b8442fed`、
`c039515fed67e8f6ba8bb607d458570e6b5e1193c9639dad48c15c90d874f16b`。
後者は56 runの審査欄を含む（先行18を含む）。この時点で拡張分の人手監査は未完了で、
機械集計を最終研究結果と扱わない。先行clean成功2/6と元のゲート不合格、
Phase 2・主モデル採用・確認的test未許可はそのままである。
