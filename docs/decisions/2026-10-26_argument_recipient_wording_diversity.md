---
decision_id: RDR-2026-10-26-03
date: 2026-10-26
status: accepted
phase: phase2_argument_recipient_learning_curve_task_design
test_set_status: not_created_or_inspected
affected_files:
  - docs/phase2_argument_recipient_expansion_task_design.md
  - docs/experimental_protocol.md
  - docs/decisions/README.md
  - PROJECT_STATE.md
supersedes: RDR-2026-10-26-02
related_decisions:
  - RDR-2026-10-26-01
  - RDR-2026-10-22-03
  - RDR-2026-10-22-02
---

# 拡張recipient内容タスクの言い回しの多様化

## 判断と部分改訂の範囲

2026-10-26、研究実施者は、RDR-2026-10-26-02で未決定としていた**指示の言い回しの設計方針**について、会話で提示された複数の文型を使う方針を採用した。候補文型は依頼文、説明文、短い欄形式、手順に埋め込む文、文中に埋め込む文、表形式である。[設計表](../phase2_argument_recipient_expansion_task_design.md)に概念例を記す。recipient文と別用途参照文の文型を固定ペアにせず交差させ、A/Bの役割、二文の順序、口座文をタスク説明の前後どちらへ置くかも変える。資料由来のrecipient規則では、ユーザー指示の資料読取・照合依頼も複数の表現にするが、読取前に資料由来の口座値をユーザー指示へ漏らさない。

`supersedes`はRDR-2026-10-26-02の「言い回しの種類は未決定」という箇所だけを部分改訂する。同RDRの5種類のrecipient決定規則、4条件の役割入替え、露出後位置の選択、旧96条件の不変性、IPI等の後続対照は維持する。ここで採用したのは**多様化と交差の方針**であり、6文型をそのまま実行用の固定文言とする判断ではない。文型数・正確な英語本文・各セルへの割当・近い言い換えのgraph edge・train/validation内の既知／未知文型配分は、各収集の実行仕様で固定する。

## 理由、時点と実装前に残る判断

初回96条件の未知REC/DONでは、recipient役割を読む残差probeの四候補平均AUROC 0.484に対し、指示文のTF-IDFは0.852だった。この差は定型句が性能差の原因と証明するものではないが、文型と役割が強く結び付いた設計を点検する理由になる。新しい文型を学習と検証へ広げるとともに、文型の新規性と意味系列の新規性を別に集計する。表現だけの置換を独立意味系列とは数えず、同一タスクと近い言い換えをsplit間へ漏らさない。

この判断は旧96条件のprobe結果を確認した後、確認的test未作成・未閲覧の時点で行った開発上の設計変更である。新しい系列を確認的testへ戻さず、既存runと旧probe結果を上書きしない。文型ごとの効果、native task受入、モデルのコピー、AUROC改善は未検証である。最初の新規fit/run前に、文型ID、交差・均衡規則、条件本文、関係graph、取得位置、評価器、監査、splitとruntimeを別仕様へ固定する。
