---
decision_id: RDR-2026-10-27-04
date: 2026-10-27
status: accepted
phase: phase2_argument_recipient_672_b5_transfer_evaluated
test_set_status: not_created_or_inspected
affected_files:
  - docs/experiment_logs/2026-10-27_argument_recipient_672_b5_transfer.md
  - docs/decisions/README.md
  - PROJECT_STATE.md
supersedes: null
related_decisions:
  - RDR-2026-10-27-01
  - RDR-2026-10-27-03
---

# D2正準履歴と実走行の読取呼び出しの形の差の扱い

## 判断（研究実施者、2026-10-27）

転移評価で、実走行112件のうち6件のprefixが正準とtoken単位で一致しなかった。6件はすべてD2（二資料）タスクの`later_tool_to_assistant`境界で、正準履歴は2つの`read_file`を別々の発話で逐次に呼ぶのに対し、実走行のモデルは両方を1回の発話にまとめて呼んでいた（実走行は8トークン短い。原因の確認は[転移評価ログ](../experiment_logs/2026-10-27_argument_recipient_672_b5_transfer.md)）。D2標本8条件のうち6件がまとめ呼び、2件が逐次呼びだった。

研究実施者は次を選んだ。

- **正準履歴・凍結済み設計・取得済みの正準bundleは変更しない。** 並列読みの履歴を加える取り直しはしない。
- D2の実走行について、正準が`later_tool_to_assistant`境界の実走行を代表しないことを、報告で明記する。prefixが一致する条件と一致しない条件を層別して報告し、不一致条件を除外しない。
- B5の主指標（G/H `role_swap_auc`）、B1～B5の学習曲線、層・Cの選択は正準だけで計算されており、この判断の影響を受けない。

## 将来の拘束

- D2後段境界の実走行にプローブを当てた値を、正準での性能の裏付けとして使わない。
- 並列読みの履歴を扱う必要が生じた場合は、別のcapture（新しいrun IDとRDR）として追加する。
