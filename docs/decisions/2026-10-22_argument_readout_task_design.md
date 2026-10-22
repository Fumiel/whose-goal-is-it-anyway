---
decision_id: RDR-2026-10-22-02
date: 2026-10-22
status: accepted
phase: phase2_development_before_argument_probe_implementation_and_independent_validation
test_set_status: not_created_or_inspected
affected_files:
  - docs/phase2_argument_readout_task_design.md
  - docs/experimental_protocol.md
  - docs/decisions/README.md
  - PROJECT_STATE.md
  - README.md
supersedes: null
related_decisions:
  - RDR-2026-10-22-01
  - RDR-2026-10-19-01
  - RDR-2026-10-19-02
  - RDR-2026-10-14-01
  - RDR-2026-10-07-03
  - RDR-2026-10-01-02
---

# `argument_readout`用のタスク設計方針

## 判断と適用範囲

2026-10-22、研究者は会話で提示した`argument_readout`設計案を、次の新規Phase 2教師・validation条件の方針として採用した。最初のprobeはBankingの`send_money.recipient`専用とし、候補値が送金操作のrecipient内容として提示されるかを、実験条件から付ける多ラベル教師信号で読む。攻撃成功、生成call、A～D群から教師ラベルを作らない。候補の正規・代替の役割、情報源、引用・説明・禁止などの文脈、別slotへの配置を交差させる。主要な一般化評価は既知候補値を用いた未知の意味的task / attack系列とする。未知の引数値そのものを初見で復号することは必須目標にしない。

候補値ごとの正則化付き線形二値分類器と連続decision scoreを最初の実装候補とする。単一目的教師条件から両候補提示IPIへの適用を、独立した開発用validationで検証する。本判断は方針であり、候補値・候補数、具体的系列、split、probe選択、閾値、層・位置、確認的test、実行runtimeのfreezeではない。[設計指針](../phase2_argument_readout_task_design.md)に条件と未固定項目を記す。

## 理由、時点、既存判断との関係

[研究計画第6節](../research_proposal.md)は既知候補集合または対応条件を認め、未知argument valueのzero-shot復号を必須とせず、内容・情報源・操作的権限・行動選好を区別している。[実験プロトコル第14節](../experimental_protocol.md)は単一目的教師条件、train-only前処理、validationでのprobe選択を規定する。今回の判断はそれらを`send_money.recipient`で具体化する。異なるslotを一つに混ぜず、両候補が同時に存在するIPIでも双方の内容を測れる形にする。引用された先行研究の未検証の数値や評価を、この判断の実証根拠にはしない。

判断時点で二文書v2の五条件は実行・人手監査済みで、いずれもtrain側の同一連結成分にある。v1はRDR-2026-10-22-01により未監査の設計失敗記録としてprobe教師・validationから除外される。pilotの90条件は`pilot_only`である。独立validationはまだない。結果を確認したv2と近縁系列を確認的testに戻さない。

## 変更しない制約と次の判断点

RDR-2026-10-14-01の暫定モデル・ドメイン、旧clean gate不合格、新規run前の条件・評価器・split・runtime固定を維持する。RDR-2026-10-07-03の同一tool・異なる主要argumentという確認的範囲、既存の関係graphによる漏洩防止とtest隔離も維持する。候補値がsplit間で既知でも、共有する具体的attack goal/style等でedgeが生じれば同じ連結成分であり、独立validationとは扱わない。

新規収集前に、具体的な口座値、条件と対応cell、ID粒度、graph、ラベルの曖昧例、評価器・監査、取得位置、実行・停止規則を別の実行仕様で固定する。validationで層・位置、正則化、score変換・較正、主解析用スコアを選び、Phase 3でtest前に凍結する。probe得点の上昇だけから目的採用や因果性を主張しない。主モデル・主ドメイン正式採用と確認的testの許可は本判断に含まない。
