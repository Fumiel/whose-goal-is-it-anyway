---
decision_id: RDR-2026-11-12-01
date: 2026-11-12
status: accepted
phase: phase2_argument_recipient_672_execution_design_review
test_set_status: not_created_or_inspected
supersedes: null
related_decisions:
  - RDR-2026-11-06-01
affected_files:
  - docs/phase2_position_sweep_spec.md
  - docs/phase2_position_sweep_implementation_brief.md
---

# 位置スイープ実装前レビューの4点を採用

研究実施者は2026-11-12、Codexのレビューで提示した推奨修正をすべて採用し、
文書修正を一度コミットしてから実装するよう指示した。
手順1・2の結果は閲覧済みだが、手順3の取得・解析は未実行である。確認的testは未作成・未閲覧。

## 修正と根拠

1. Gの評価スコアを「送金先 − 参照」から「提示順の先 − 後」へ変更する。
   主ラベルrecipient_firstと向きを揃えるためである。旧定義では両条件で正しい送金先を
   同じmarginで選好する合成例がpaired_accuracy=0.5となる。新定義では1.0になる。
2. probe精度がロジット精度以下の場合に比較フラグを立てる。旧指定の不等号は逆だった。
   記述は「同位置ロジットの精度以下」とし、説明関係や理論的上限を主張しない。
3. TだけR1、他はR3の合成テストは規則2（信号が途中で消える）を期待する。
   H2のケースはTとSまたはGがR1となる別例で検証する。仕様8節の規則自体は変更しない。
4. Tの残差の数値差と、42セル補正・位置ベースライン追加によるp値や判定の差を分ける。
   後者は残差が一致しても起こり得るため、すべてを数値誤差とは扱わない。

## 範囲

変更は手順3の別仕様と指示書に限定する。H1〜H3は引き続き観測的な対応づけであり、
研究計画の問い・確認的回帰、既存run・集計・freeze、位置・層・42セル・閾値・対象240条件は変更しない。
RDR-2026-11-06-01の他の制約も維持する。本判断はGPU事前確認・取得・解析本実行を許可しない。
