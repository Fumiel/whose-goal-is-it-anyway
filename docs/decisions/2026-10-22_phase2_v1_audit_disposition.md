---
decision_id: RDR-2026-10-22-01
date: 2026-10-22
status: accepted
phase: phase2_development_after_paths_v2_human_audit
test_set_status: not_created_or_inspected
affected_files:
  - README.md
  - docs/experimental_protocol.md
  - docs/experiment_logs/2026-10-19_phase2_two_document_initial_execution.md
  - docs/phase2_two_document_audit.md
  - docs/phase2_two_document_runner.md
  - docs/phase2_two_document_payment_v1.md
  - docs/phase2_two_document_paths_v2.md
  - docs/decisions/README.md
  - PROJECT_STATE.md
supersedes:
  - RDR-2026-10-19-01
  - RDR-2026-10-19-02
related_decisions:
  - RDR-2026-10-19-03
  - RDR-2026-10-14-01
---

# 二文書タスクv1の人手監査を実施しない判断

## 判断と改訂範囲

2026-10-22、研究実施者は、二文書タスクv1の五件について人手監査を行わず、
ファイルパスを明示した別versionのv2に対して実施済みの人手監査を採用することを
確認した。v1はタスク設計の実現可能性を調べた記録として保持し、probeの教師・
validation、成功率、A～D群の報告、確認的解析には使用しない。v1の自動ラベルを
人手判断に読み替えない。空欄のv1監査票は空欄のまま残す。

これはRDR-2026-10-19-01の「全五件を人手監査する」受入規則と、
RDR-2026-10-19-02の「初回五件の人手監査も省略しない」という判断を、
**v1の監査実施と解析上の使用範囲に限って部分改訂**する。
両RDRの実行前に凍結した条件・split・測定・停止規則、実行時点の来歴、
v1とv2を別runとする判断は維持する。v1のrun bundle、設計freeze、runtime freeze、
collection manifest、空欄監査票を変更・削除しない。v2の完成監査票、
凍結済み自動ラベル、outcome reportも変更しない。

## 根拠と判断時点

[v1実行記録](../experiment_logs/2026-10-19_phase2_two_document_initial_execution.md)と
[RDR-2026-10-19-02](2026-10-19_phase2_two_document_path_disclosure_revision.md)に記録したとおり、
五件とも宣言された二つの文書を読めず、誤った`read_file`パスから空の内容を受け取った。
v1のユーザー指示に正確なファイル名がなく、利用可能なBanking toolには一覧・検索手段も
なかった。したがって、本来調べたい文書内の引数内容とsource / role文脈を、
実軌跡上で対応比較できない。これはモデル出力を見た後に判明したタスク設計上の欠陥である。

この欠陥を受けて別ID・別freezeのv2を収集し、五件すべての文書読取・測定境界を確認した。
v2の五件は[別の人手監査](../../data/audits/2026-10-19_phase2_two_document_paths_v2_human_audit.json)と
[outcome report](../../results/2026-10-19_phase2_two_document_paths_v2_outcome_report.json)を持つ。
v1の監査省略はv2の人手判断をv1へ転記することを意味しない。
本判断はv1の実軌跡とv2の監査・結果を確認した後、確認的testの作成・閲覧前に行った。

## 研究への影響と次の作業

研究課題1～3、仮説、主解析の測定区別は変更しない。v1の五件は収集済みだが
人手未監査であり、欠測を含む設計上の失敗例として来歴を保持する。
v2の五件は同一の保守的連結成分に属するtrain条件で、独立validationではない。
主モデル・主ドメインは未採用で、確認的testは未作成・未閲覧である。

次は`argument_readout`のfeature抽出とprobe学習・評価経路の実装に着手する。
教師ラベルは条件で宣言したargument identity / conditionから作り、生成call、
攻撃成否、A～D群を教師にしない。v2だけでは独立な未知系列性能を評価できず、
追加の独立した開発用validation系列、語彙baseline、ランダムラベル対照、較正、
欠測の評価が必要である。probe実装の着手をPhase 2 exit criteria達成や
Phase 3凍結とみなさない。
