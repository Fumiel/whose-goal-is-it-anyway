---
decision_id: RDR-2026-10-07-03
date: 2026-10-07
status: accepted
phase: after_exploratory_pilot_collection_before_expansion_human_audit
test_set_status: not_created_or_inspected
affected_files:
  - docs/research_proposal.md
  - docs/experimental_protocol.md
supersedes: null
related_decisions:
  - RDR-2026-09-15-01
  - RDR-2026-10-07-01
  - RDR-2026-10-07-02
---

# 確認的主張を同一ツールの引数乗っ取りへ限定する

## 判断と変更前後

研究者の意図は、ツールが返す外部データによって、正規のツール呼出しの主要引数を攻撃者指定値へ変えさせるIPIを研究することである。従来の計画は同一ツール・異なる引数を「中心」としていたが、題目・研究目的はIPI一般に読め、異なるツールへの切替条件も主解析から明示的には除いていなかった。

確認的主解析の対象を**同一ツール・異なる主要引数**の条件に限定する。`argument_readout`、`source_role_readout`、操作的な`authority_score`と後続する引数marginの関係を主張の中心とし、`action_readout`と異なるツールへの切替攻撃は副次的・探索的に扱う。結果の外挿範囲は採用した一モデル・一ドメイン内の独立タスク／攻撃系列までとし、IPI一般の内部機構とは主張しない。Bankingは第一候補のままで、正式採用ゲートを通過したとはみなさない。

RDR-2026-09-15-01の主回帰、二つの時間軸、測定の区別、対照、splitおよび一モデル・一ドメインの制約は維持する。本判断は同RDRの主解析対象の表現と包含条件を部分的に狭めるもので、過去の記録を書き換えない。

## 判断時点と根拠

2026年10月7日時点で、Bankingの探索的pilotは90条件の収集を終え、拡張分の人手監査待ちである。先行18条件の厳密clean成功は2/6で、凍結したゲートは不合格だった。収集後の機械集計を確認的な証拠として用いない。確認的testは未作成・未実行・未閲覧である。

根拠は、研究者が引数乗っ取りへの特化を明示したこと、既存の主目的変数が`argument_slot_margin`であること、および題目・目的に残る広い表現と実験条件との不一致である。pilotで観測した攻撃成功の有無、効果量または有利なタスクの選択を根拠にしていない。ただし、pilot収集後の判断であるため事前の無結果変更とは扱わず、日付と閲覧済みの先行ゲート結果を明示する。

## 影響と制約

- Research Question 1と新規性の文言を引数内容と情報源・役割の分離へ絞る。Research Question 2・3の測定式と観測的解釈は維持する。
- 確認的runは正規・攻撃callのtool identity一致と主要argument差分を事前検査する。既存pilotやraw bundleの分類、成功判定、データ、freezeを変更しない。
- 異なるtoolへの切替条件があれば、副次的・探索的な結果として主回帰とは分ける。確認的testの構成と除外規則はtest作成・閲覧前に固定する。
- Bankingのcleanゲート不合格、主モデル・主ドメイン未選定、独立cluster数の実現可能性は未解決である。今回の文言修正はこれらのgateを通過させない。

採用しなかった案は、現在の探索的Banking pilotを確認的データへ格上げすること、Bankingを正式な主ドメインと断定すること、IPI全般または異なるツールへの切替へ結果を一般化することである。
