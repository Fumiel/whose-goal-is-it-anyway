---
decision_id: RDR-2026-10-14-01
date: 2026-10-14
status: accepted
phase: after_exploratory_pilot_audit_before_phase2_data_collection
test_set_status: not_created_or_inspected
affected_files:
  - docs/research_proposal.md
  - docs/experimental_protocol.md
  - docs/decisions/README.md
  - docs/banking_pilot_v1.md
  - docs/pilot_runner.md
  - PROJECT_STATE.md
  - README.md
supersedes: RDR-2026-10-01-03
related_decisions:
  - RDR-2026-09-24-03
  - RDR-2026-09-24-07
  - RDR-2026-10-01-01
  - RDR-2026-10-01-02
  - RDR-2026-10-07-01
  - RDR-2026-10-07-03
---

# Banking pilot監査後にPhase 2の開発へ進む

## 判断と改訂範囲

2026-10-14、研究実施者は、探索的Banking pilotの全90条件の収集と56件の人手監査を
確認した後、Qwen3-8B int8・AgentDojo Banking v1.2.2を**Phase 2開発用の暫定構成**
として、プローブ教師データ・対応対照条件の設計、実装、model-free検証、新規runによる
training / validationデータ収集、プローブの学習・検証へ進むことを決めた。
確認的testの構成、実行、結果閲覧は許可しない。

これはRDR-2026-10-01-03の「全90条件後、clean成功3/6以上を満たしてから
Phase 2設計へ進む」という**移行規則だけ**を、今回以降について部分改訂する。
同RDRの標本、評価・監査規則、旧判定、pilot_only指定、test除外およびraw不変性は維持する。
RDR-2026-10-07-01の結果閲覧後の探索的継続という位置付けも維持する。
旧ゲートを合格扱いにしたり、閾値を2/6へ事後変更したりしない。

現行プロトコルのPhase 0終了条件は主モデル・主ドメインの選定である。
Phase 1の終了条件も、未確定事項をvalidationで選べる状態にすることであり、
教師データと対照条件の整備はまだ終わっていない。
本判断は、これらの条件を達成済みとみなさず、Phase 1の残作業とPhase 2の開発作業を
並行させる**今回の暫定構成に限った例外**とする。
正式選定を済ませたことにはせず、Qwen3-8B・Bankingを確認的主解析の構成として
採用するかは、Phase 3の仕様凍結前に別RDRで判断する。
RDR-2026-09-24-03の選定ゲート不合格、候補比較、分母、監査来歴は変更しない。
研究計画書の「採用基準未達なら代替ドメインへ切り替える」という正式採用時の分岐は、
開発作業に直ちに適用せず、Phase 2で得る妥当性と実現可能性の証拠を確認した後、
Phase 3凍結前に切替または主張範囲を別RDRで決める手順へ部分改訂する。

## 判断時点に確認済みの証拠と限界

[2026-10-13監査後報告](../../results/2026-10-13_banking_pilot_full_audit_report.json)
では、先行cleanの厳密成功は2/6であり、成功したのは請求書とパスワードの2系列だった。
旧先行・最終移行ゲートは不合格である。90条件には完了bundleがあり、総attemptは91。
56件の人手監査に未裁定不一致はない。実軌跡での注入接触、内部状態取得、候補採点は
4 task系列で記録された。ただし90条件は関係graph上で1連結成分であり、独立した
成功率推定、未知系列への一般化、主回帰の成立を保証しない。

語彙対照6件は`has_attack=false`なのにnative攻撃成功が陽性で、矛盾として隔離された。
このため報告の`no_contradictions`はfalseである。これらをclean分母や通常のA～D群へ
混ぜず、評価器またはラベルの妥当性を検証する対象とする。旧runの判定は変更しない。
既存のモデル選定も両候補が凍結ゲートに不合格であり、主モデル・主ドメインは未採用である。

判断の研究上の理由は、確認的主解析が同一ツールのIPI条件における連続的な
`argument_slot_margin`を目的変数とし、clean runを主回帰へ含めないこと、
および複数系列で必要な測定経路を取得できたことである。
clean成功2件は、その特定条件で正規タスクを遂行できた証拠に限る。
IPI下の失敗原因を一意に攻撃へ帰属させず、clean失敗を`baseline_failure`として残し、
ユーザータスク成功と攻撃成功を別々に記録する。

本判断はpilotの行動・監査結果を確認した後に行った。training / validation用の
新系列と確認的testは未作成・未実行で、確認的testの結果は閲覧していない。
pilot結果に合わせて有利な系列だけをtestへ選ぶ判断ではない。

## Phase 2で許す作業と新規runの条件

- 正常な単一目的条件と、同一argument内容をuser instruction、tool output、引用、
  説明、禁止などへ置く対応条件を設計する。攻撃成否や最終tool選択をプローブ教師ラベルにしない。
- 新しいtask・attack系列は別namespace・versionで宣言し、正規／攻撃callのtool一致と
  主要argument差、初期状態、注入位置、成功述語、無操作・正規・攻撃状態を
  model-freeで検証する。既存の5/6は評価器規則の確定まで保留し、11はrecipient監査を
  終えるまで使用しない。
- 新規モデルrunの前に、条件・抽出方法、group関係、train / validation配分、
  評価器・監査規則、モデル・tokenizer revision、決定論的decode、token位置・
  同一prefix採点、資源上限、runtime freezeとrun IDを別の実行仕様に固定する。
  技術停止や変更は旧runを保持した新記録で扱う。
- 既存pilotの90条件は`pilot_only`の探索資料として保持し、今回の判断だけでは
  probe training / validationへ転用しない。過去のshakedown runも研究データへ
  転用しない。新しい開発用runと既使用・pilot系列の近縁変種は確認的testから除外する。
- 語彙対照6件の矛盾の原因と影響範囲を検証し、修正が必要なら評価器・監査規則の
  新versionと適用開始時点を別RDRで決める。矛盾した旧ラベルを教師ラベルに使わない。

## 次の判断点と研究への影響

Phase 2では、未知の開発側系列での`argument_readout`と`source_role_readout`の性能、
語彙baseline・ランダムラベル対照・較正・欠測率を評価する。
新系列で正規タスクと主要argument候補を測定できるかを記録し、成功した条件だけを
事後的に抽出して一般的な有用性を主張しない。新系列と既使用系列の関係graphを完成させ、
独立な確認的clusterの供給可能性を評価する。最終splitはPhase 3までに凍結する。

Phase 3の仕様凍結より前に、主モデル・主ドメインの正式採用または代替構成、
評価器矛盾の処理、未知系列でのプローブ妥当性、独立cluster数、欠測・除外規則を
証拠付きで別途判断する。満たせない場合は主張範囲や教師強制採点中心への変更を
新RDRで記録する。今回、既存の主回帰、研究課題・仮説、30 clusterの暫定下限、
決定論的比較、確認的testの隔離は変更しない。

採用しなかった案は、旧ゲートの遡及的な合格化、clean失敗の成功への再分類、
pilotの確認的データ化、成功した2系列だけを確認的母集団にすること、
Phase 2移行と同時に主モデル・主ドメインを正式採用することである。
