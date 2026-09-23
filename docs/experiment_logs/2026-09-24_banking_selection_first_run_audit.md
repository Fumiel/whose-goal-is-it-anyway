# Banking選定試験の初回run監査

- 対象run prefix: `banking-selection-20260924-001`
- 凍結commit: `41c738e0052e09bb56564e598b53c72a79b8491d`
- 対象: Qwen3-8B int8とQwen3-4B BF16に各7条件、計14件
- raw bundleの所在・manifest SHA-256: [小型manifest](../../data/manifests/2026-09-24_banking_selection_first_run.jsonl)
- 確認的test: 未作成・未閲覧

14件のrun bundleは全て存在し、manifestに載るファイルのSHA-256とbyte数は一致した。
設定checksum、Git commit、model/tokenizer revision、seed、decoding、token位置とID、
activationのshapeと有限値、IPI条件の採点prefix・系列log probabilityの有限値も一致した。
技術的失敗bundleはなかった。run schemaが選定用`metrics`とboundary token項目を
許していなかった点は、今回のrunner修正に合わせて補正した。

自動評価器の**暫定**集計は8Bのclean成功3/5、4Bのclean成功2/5であり、
どちらも既定の4/5に達しない。IPIの攻撃成功は8Bが1/2、4Bが0/2。
これは人手監査前の値であり、採用判断として確定しない。

監査不能の原因はrun保存時に最終回答と各生成ステップの`raw_text`を書き出さなかったこと。
14件すべてで`messages.json`に最終assistant回答がなく、`run.json`にも最終回答はない。
特に`user_task_7`は回答文を評価するため、保存状態とtool履歴だけでは独立判定できない。
他の12件の状態依存タスクは保存状態とtool履歴から自動ラベルを再計算すると一致したが、
必須のblind人手監査は14件とも未完了である。

旧bundleは編集・削除しない。修正版runnerの新たな凍結commitから、両候補を
**同じ7条件で新規run ID**へ再実行する。条件、閾値、分母、tie-breakは変更しない。
