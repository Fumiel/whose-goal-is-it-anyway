# Research Decision Records

このディレクトリには、研究計画または実験プロトコルに対する重要な判断を、Research Decision Record（RDR）として一判断一ファイルで保存する。

[`../research_proposal.md`](../research_proposal.md)は現在有効な研究目的、Research Questionおよび新規性を示し、[`../experimental_protocol.md`](../experimental_protocol.md)は現在有効な実験手順を示す。本ディレクトリは、それらがいつ、どの根拠で変更されたかを記録する履歴であり、現在の手順そのものを重複して定義する場所ではない。

## 記録規則

- ファイル名は`YYYY-MM-DD_short_description.md`とする。
- 各記録に安定した`decision_id`、日付、状態、研究段階およびtest setの確認状況を付ける。
- 変更前の設計、採用した変更、採用しなかった案、科学的根拠、実現可能性上の根拠を記録する。
- 影響を受けるResearch Question、仮説、データ、schema、解析および再現性を明記する。
- Pilotまたはtest setの確認後に変更した場合は、確認済みの情報と変更判断の関係を明記する。
- 過去の記録は書き換えて現在の判断に合わせず、後続のRDRから`supersedes`で参照する。
- 外部資料をGitへ保存しない場合は、確認した資料名、版、日付および取得可能な識別子を記録し、存在しないchecksumを推測しない。

## 状態

- `proposed`: 検討中であり、現行計画には未反映。
- `accepted`: 現行計画またはプロトコルへ反映済み。
- `superseded`: 後続の判断によって置き換えられた。
- `rejected`: 検討したが採用しなかった。

## Index

| Date | Decision ID | Status | Summary |
|---|---|---|---|
| 2026-10-26 | [RDR-2026-10-26-07](2026-10-26_argument_recipient_672_d1m_d2_revision_and_rdr_reconciliation.md) | accepted | D1M・D2資料を、項目ID・支払先名の照合が必要な構造（全項目に固有口座）へ修正し、同日RDR-01～06の食い違いについて現行有効な読み方と適用順を整理 |
| 2026-10-26 | [RDR-2026-10-26-06](2026-10-26_argument_recipient_672_three_task_structure.md) | accepted | 672条件（40＋16系列×3タスク×4条件、金額明記、U0/UN/UI・D1/D1M/D2）と文型規模（各文脈・役割で学習16＋検証専用8）を採用し、全168タスクの本文草案を生成。主指標・取得・graph・split・runtimeは未凍結 |
| 2026-10-26 | [RDR-2026-10-26-05](2026-10-26_argument_recipient_672_family_split_and_llm_audit.md) | accepted | recipient probe拡張を題材ファミリー単位の学習／検証分離（検証にI決済・銀行サービス由来を配置）とし、旧REC/DONの学習算入と、別系統LLMクロスチェック中心の層別監査を採用。672条件配分・主指標・日程は未採用 |
| 2026-10-26 | [RDR-2026-10-26-04](2026-10-26_argument_recipient_700_draft_and_mixed_curve.md) | accepted | 提示済み学習5・検証候補5系列を候補として採用し、資料由来条件も同じ混合学習曲線へ含める。Codex作成700条件レビュー草案はClaude確認前・未凍結 |
| 2026-10-26 | [RDR-2026-10-26-03](2026-10-26_argument_recipient_wording_diversity.md) | accepted | 拡張recipient内容タスクで複数の文型、recipient・参照文型の交差、口座役割・提示順・位置の入替えを採用。具体文言と配分は未凍結 |
| 2026-10-26 | [RDR-2026-10-26-02](2026-10-26_argument_recipient_rules_role_swap.md) | accepted | 拡張recipient内容タスクの5種類の決定規則と、同一タスク内の4条件によるrecipient・参照口座の役割入替えを設計方針として採用。具体条件は未凍結 |
| 2026-10-26 | [RDR-2026-10-26-01](2026-10-26_argument_recipient_learning_curve_expansion.md) | accepted | 96条件の未知系列性能を受け、recipient内容probeの開発用500学習・200検証条件、100条件刻みの学習曲線、未知系列AUROC 0.80到達基準を計画。具体条件・停止規則は未凍結 |
| 2026-10-24 | [RDR-2026-10-24-01](2026-10-24_argument_recipient_96_collection_freeze.md) | accepted | 研究者が96条件草案の内容と開発内配分候補を承認。独立graph、64 train / 32 validationと新規run前gateを具体化 |
| 2026-10-22 | [RDR-2026-10-22-03](2026-10-22_argument_probe_staged_controls.md) | accepted | 初回96条件をユーザー指示中のrecipient内容probe用に設計し、IPI・引用／禁止・両recipient候補の対応対照を後続セットへ分ける部分改訂 |
| 2026-10-22 | [RDR-2026-10-22-02](2026-10-22_argument_readout_task_design.md) | accepted | 初回argument probeを`send_money.recipient`へ絞り、多ラベルの内容ラベル、役割・文脈の交差、既知候補での未知系列validationを方針化 |
| 2026-10-22 | [RDR-2026-10-22-01](2026-10-22_phase2_v1_audit_disposition.md) | accepted | v1の監査省略を記録し、未監査v1を設計上の失敗記録として保持。v2監査を維持し、次にargument_readout probe実装へ進む |
| 2026-10-19 | [RDR-2026-10-19-03](2026-10-19_phase2_two_document_human_audit_interpretation.md) | accepted | v2実行後の人手監査で日付を除外、件名を意味的に許容し、口座番号の完全一致で初回判断を別欄裁定する。凍結済み自動評価は維持 |
| 2026-10-19 | [RDR-2026-10-19-02](2026-10-19_phase2_two_document_path_disclosure_revision.md) | accepted | 初回五条件のファイル発見失敗を受け、旧runを保持した新v2条件で両文書パスをユーザー指示へ明示する。当初のv1監査継続判断はRDR-2026-10-22-01で部分改訂 |
| 2026-10-19 | [RDR-2026-10-19-01](2026-10-19_phase2_two_document_initial_specification.md) | accepted | 二文書タスク五条件の開発用train割当、当初の全件監査、測定と停止規則を設計freeze。v1監査規則のみRDR-2026-10-22-01で部分改訂 |
| 2026-10-18 | [RDR-2026-10-18-01](2026-10-18_lexical_control_contradictions_probe_priority.md) | accepted | 語彙対照6件の行動・状態証拠と解釈の限界を記録し、追加の6件専用実験よりPhase 2のprobe実装を優先する |
| 2026-10-14 | [RDR-2026-10-14-01](2026-10-14_phase2_development_after_banking_pilot.md) | accepted | pilot監査後、旧ゲート不合格を維持しつつ暫定構成でPhase 2開発と新規training / validation収集を認める限定的移行 |
| 2026-10-07 | [RDR-2026-10-07-03](2026-10-07_argument_hijacking_scope_clarification.md) | accepted | pilot収集後・test未作成時点で、確認的主張と包含条件を同一ツールの引数乗っ取りへ限定する部分改訂 |
| 2026-10-07 | [RDR-2026-10-07-02](2026-10-07_pilot_gpu_recovery.md) | accepted | 51番の12 GiB資源停止に対しキャッシュ解放を検証し、旧失敗を保持した新runで51～90の探索的収集を再開する |
| 2026-10-07 | [RDR-2026-10-07-01](2026-10-07_banking_pilot_post_gate_exploratory_continuation.md) | accepted | 先行clean 2/6・ゲート不合格を維持し、残り72条件を結果閲覧後の探索的継続として収集する部分改訂 |
| 2026-10-02 | [RDR-2026-10-02-01](2026-10-02_pilot_capture_resource_revision.md) | accepted | pilotの通常Attentionをlast-query集約へ変更し、固定prefix診断を採点専用にする。全sequence詳細保存を事前指定の別immutable派生取得へ移す部分改訂 |
| 2026-10-01 | [RDR-2026-10-01-03](2026-10-01_banking_pilot_sample_freeze.md) | accepted | 初回pilotの6task・4系列・90条件と停止規則を凍結。実行前gateは未完了 |
| 2026-10-01 | [RDR-2026-10-01-02](2026-10-01_existing_tasks_pilot_new_families_test.md) | accepted | 既存系列を予備実験へ、新系列を開発・確認用へ配分。shakedown系列の新規pilot実行を許す部分改訂 |
| 2026-10-01 | [RDR-2026-10-01-01](2026-10-01_banking_task_feasibility_review.md) | accepted | Banking候補の系列・既使用除外・評価器問題を記録し、予備実験前に独立groupの実現可能性を確認する |
| 2026-09-24 | [RDR-2026-09-24-07](2026-09-24_provisional_qwen3_8b_banking_pilot.md) | accepted | ゲート不合格を保持し、Qwen3-8B int8・Bankingを探索的予備実験の暫定構成とする |
| 2026-09-24 | [RDR-2026-09-24-06](2026-09-24_selection_self_audit.md) | accepted | 再実行結果の閲覧後、本人が非blindで14件を自己監査する逸脱と解釈上の限界を記録 |
| 2026-09-24 | [RDR-2026-09-24-05](2026-09-24_selection_audit_trace_rerun.md) | accepted | 初回runの最終回答・生出力欠落を補い、同じ7条件で両候補を再実行するcommitを凍結 |
| 2026-09-24 | [RDR-2026-09-24-04](2026-09-24_banking_selection_gate_freeze.md) | superseded | 初回7条件選定のGit commitと設定checksumの凍結 |
| 2026-09-24 | [RDR-2026-09-24-03](2026-09-24_native_model_selection_gate.md) | accepted | 既存Bankingタスクの7条件で縮小ゲートと選定標本を指定。正式凍結と実行は未了 |
| 2026-09-24 | [RDR-2026-09-24-02](2026-09-24_integration_gate_provisional_thresholds.md) | superseded | 旧暫定閾値。RDR-2026-09-24-03で縮小 |
| 2026-09-24 | [RDR-2026-09-24-01](2026-09-24_integration_gate_partial_decisions.md) | accepted | 統合試験ゲートの候補参照、tie-break、資源上限を部分決定。正式ゲートは未凍結 |
| 2026-09-22 | [RDR-2026-09-22-02](2026-09-22_agentdojo_shakedown_implementation.md) | accepted | AgentDojo、Qwen3候補、Windows / WSL2実行基盤と3 fixtureを固定 |
| 2026-09-22 | [RDR-2026-09-22-01](2026-09-22_pre_gate_engineering_shakedown.md) | accepted | 非選定engineering shakedownを限定許可。系列のpilot再利用禁止はRDR-2026-10-01-02で部分改訂 |
| 2026-09-16 | [RDR-2026-09-16-01](2026-09-16_agent_boundary_labels.md) | accepted | エージェント境界IDを情報の受け渡し元・先が分かる名称へ変更 |
| 2026-09-15 | [RDR-2026-09-15-01](2026-09-15_pre-pilot_scope_revision.md) | accepted | Pilot前の研究焦点、測定単位、実験規模および期限の改訂 |
