---
decision_id: RDR-2026-11-14-02
date: 2026-11-14
status: accepted
phase: phase2_argument_recipient_672_execution_design_review
test_set_status: not_created_or_inspected
supersedes: null
related_decisions:
  - RDR-2026-11-14-01
  - RDR-2026-11-06-01
affected_files:
  - docs/phase2_activation_patching_spec.md
  - docs/phase2_activation_patching_implementation_brief.md
---

# パッチング仕様の対応づけ規則3の一般化（実装前の修正）

研究実施者は2026-11-14、Claude Codeが実装指示書の作成中に指摘した抜けについて、次の修正を採用した。
パッチングの実装・取得・解析は未実行で、パッチングの結果は存在しない。確認的testは未作成・未閲覧である。

- **抜け：** 確定済みの[パッチング仕様](../phase2_activation_patching_spec.md)6.3節の規則3は、「`G`の`L*`が層28以上」だけを扱っていた。
  `S`の層28以上だけでP-STRONGとなる場合や、`T`の層28〜32だけでP-STRONGとなり、`S`・`G`の中間層でも移せない場合は、規則0〜4のどれにも当たらなかった。
- **修正：** 規則3を「1・2に当たらず、どれかの位置の`L*`が層28以上 → 仮説への対応づけはしない」に一般化する。
- **理由：** 深い層の残差の書き換えは、どの位置でも出力をほぼ直接置き換える。そのため、選択が決まる時点の情報にならない。`G`だけを例外とする理由はない。
- **変更しないもの：** 規則0〜2・4、P-STRONGなどの閾値、層、位置、移し替え元、セル数。

実装指示書は、仕様に合わせて規則3を修正した。規則0〜4に当たらない組合せが見つかった場合は例外として報告させる。
暫定の`"unclassified"`の扱いは削除した。
