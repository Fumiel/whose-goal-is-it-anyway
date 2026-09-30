---
decision_id: RDR-2026-10-01-01
date: 2026-10-01
status: accepted
phase: after_provisional_pilot_transition_before_exploratory_pilot
test_set_status: not_created_or_inspected
affected_files:
  - docs/banking_task_candidates_2026-10-01.md
  - docs/experimental_protocol.md
  - PROJECT_STATE.md
  - README.md
supersedes: null
related_decisions:
  - RDR-2026-09-24-03
  - RDR-2026-09-24-07
---

# Banking予備実験前の系列数・評価器の実現可能性確認

## 判断

2026-10-01の依頼による候補表作成と関連文書更新を受け、AgentDojo Bankingの
タスク系列・攻撃系列・既使用除外と評価器の問題を、予備実験標本の固定前に確認する。
変更前のプロトコルも独立clusterと妥当な成功判定を要求していたが、nativeタスクごとの
適否と残せる未知系列は未整理だった。今回、その確認を第5.1節と開始前checklistへ具体化する。

`user_task_5`と`user_task_6`を成功率・主解析の標本として扱うことは、native環境での
対照検証と評価器・監査規則の固定まで保留する。`user_task_11`も使用前にrecipientの
監査規則を定める。native評価を補助監査と混同せず、評価器の差替えは別version・別RDRで扱う。

系列数の保守案は候補であり、最終groupやsplitはまだ採用・凍結していない。
複合タスク15の主解析除外、追加タスク作成、ドメイン変更、研究主張の縮小も、今回は決定しない。
既存タスクの全直積や表層variantを増やして独立cluster不足を解消したと扱う案は採用しない。

## 根拠と検証範囲

[タスク候補表](../banking_task_candidates_2026-10-01.md)は公式`agentdojo==0.1.35`の
固定commit `a75aba7631d3ca5fb7ab938965c97ead2f9ff84b`を対象とし、
benchmark `v1.2.2`までの定義更新、初期環境、注入vectorを照合した。
取得元・checksum・検査方法は同表に記録する。

- 16タスクには家賃2/12、返金3/4など近縁条件がある。保守案は15なしで8task系列であり、
  attack edgeや既使用除外後の最高位group数ではない。
- 初期環境を属性オブジェクトへ写し、固定ソースのutilityを空回答・無操作状態で実行すると、
  5/6がtrueとなった。5は既存Spotify送金、6は既存Spotify定期支払いを拾う。
  依存パッケージを使ったnative suiteの対照検証は未実施であり、検査は限定的である。
- 11のutilityは送金amountだけを判定する。同額の不正宛先への送金でもnative user-task
  successとattack successが同時にtrueとなり得る。
- 既使用系列を保守的に除くと未使用IDは5/6/11に限られる。これらを予備実験へ投入すれば
  その系列もtestから除かれるため、未知系列と暫定30cluster目標の実現可能性は未確定である。

## 研究への影響と時点

Research Question、仮説、主回帰、暫定実行規模・30cluster目標、漏洩防止規則は維持する。
影響は今後の標本選択、成功判定の監査、splitの実現可能性確認に限る。
schema・解析コード・凍結済み選定設定・過去のraw dataと判定は変更していない。
Qwen3-8B int8・Bankingは引き続き暫定構成で、主モデル・ドメインの最終採用ではない。

この判断は2026-09-24のモデル選定・非blind自己監査の後だが、新しい探索的予備実験の
実行前である。根拠はソース監査であり、新しいモデル挙動を確認して条件を選び直したものではない。
確認的test manifestは作成・実行・結果閲覧していない。

次の判断時には、候補graphの連結成分数、既使用・pilot除外後に残る未知系列、native評価器の
対照検証と補助監査規則を示す。独立系列が確保できなければ、範囲変更を新しいRDRで記録する。
