# Banking pilot先行18件の実行と人手監査への引き継ぎ

- 実行prefix: `banking-pilot-001`
- 実行Git commit: `2a709f2eed2e693bd65700bbb35df08b681a430e`
- 標本: `configs/experiments/banking_pilot_v1.freeze.json`
- runtime freeze: `artifacts/pilot-runtime.freeze.json`
- rawと監査成果物の所在・SHA-256: [小型manifest](../../data/manifests/2026-10-02_banking_pilot_lead.json)
- 確認的test: 未作成・未実行・結果未閲覧

凍結順で先行18条件（clean 6、IPI 12）を実行した。各条件は一つのimmutable raw
bundleを作り、18件とも`run.json`のstatusは`completed`だった。stage bundleの
statusは`awaiting_human_audit`で、技術的停止はなかった。18件のartifact manifest、
required file、run schema、resolved config checksumを`load_records`で検証した。
この記録は収集完了と監査可能性を示し、成功・失敗率や研究上の結論を示さない。

自動ラベルとaggregateを含まない監査票を
`artifacts/pilot-lead-audit.json`に作成した。18件の`bundle_manifest_sha256`は
raw manifestと一致した。初回判断用のファイル案内は
`artifacts/pilot-lead-audit-guide.md`に置いた。現時点で記入済みの人手判定は0件。
監査者は実際のblind状況、初回判定、証拠、必要な裁定を監査票に保存する。
未記入票から拡張gateの合否は判断しない。残り72条件は未実行である。

別工程の固定prefix全系列残差取得は、事前指定4条件のうち最初の
`banking_pilot_v1_4fb7f8324a191b52`をimmutable派生bundleとして保存した。
次の`banking_pilot_v1_4bcd2e89355ab958`では12 GiBのGPU上限を超え、
`oom_or_resource_limit: detail GPU ceiling exceeded`でprocessがexit code 1となった。
この失敗は派生bundle作成前に起きたため、失敗条件のimmutable detail bundleはない。
失敗と既存bundleのchecksumを
`artifacts/processed/pilot_detail_v1/detail-stop-banking-pilot-001.json`へ記録した。
後続の指定2条件は未試行で、再試行・条件交換はしていない。raw先行18件は変更していない。
詳細取得の修正・再収集を行う場合は、既存の資源上限とRDRの手続に従って別途判断する。

実行用checkoutのHEADと作業treeをfreezeに一致させるため、この記録は別ブランチ
`pilot-lead-20261002-record`へコミットした。実行時のruntime freezeはこの記録commitではなく、
上記実行commitを参照する。raw run、残差tensor、model weightはGitへ含めない。
