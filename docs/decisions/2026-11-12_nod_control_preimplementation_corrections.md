---
decision_id: RDR-2026-11-12-02
date: 2026-11-12
status: accepted
phase: phase2_argument_recipient_672_execution_design_review
test_set_status: not_created_or_inspected
supersedes: null
related_decisions:
  - RDR-2026-11-06-01
  - RDR-2026-11-12-01
affected_files:
  - docs/phase2_position_sweep_nod_control_spec.md
  - docs/phase2_position_sweep_nod_control_implementation_brief.md
---

# D除外対照の実装前レビュー修正

研究実施者は2026-11-12、Codexが提示した4点をすべて採用し、修正文書のコミット後に
実装と本実行へ進むよう指示した。手順3の結果と局所文言による説明は閲覧済みだが、
D除外対照の取得・比較・再解析は未実行。確認的testは未作成・未閲覧である。

1. 再解析省略はR-EXACTかつ比較Nの全240条件・5位置・36層のビット一致の場合のみ。
   R-NOISEでは10条件の観測幅以下でも再解析する。小さい差でもラベルを運び得るためであり、
   10条件の最大値を他の230条件のノイズ上限とは扱わない。Δの読み取りは引き続き併記のみ。
2. P/Nは別々の入力変更に伴う差として記述する。ノルムの非加法性と異なる分母のため
   寄与割合へ分解しない。Pは入力変更の影響であり、同一入力の再実行差Rとは区別する。
3. reference.gpu_preflight_reportを追加して参照を4ファイルにする。
   旧GPU事前確認レポートは旧runtime freeze内のchecksumとも照合する。
4. bfloat16をint16として再解釈し、ビット列を比較する。torch.equalの浮動小数点比較では
   +0と-0が同一になるため、厳密なビット一致という仕様に揃える。

再現性の10条件・先頭5対、モデル・層・seed・probe・閾値・42セル・train限定の原則は維持する。
本判断は今回の対照の本実行を許可するが、パッチング自体は含めない。
Dの影響の有無にかかわらず、A1/A2の局所文言の説明とH1の証拠にしない留保は維持する。
既存raw bundle、派生出力、freeze、収集manifestは変更しない。
