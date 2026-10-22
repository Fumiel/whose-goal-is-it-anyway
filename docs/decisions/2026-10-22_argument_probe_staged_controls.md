---
decision_id: RDR-2026-10-22-03
date: 2026-10-22
status: accepted
phase: phase2_development_before_96_condition_design_review
test_set_status: not_created_or_inspected
affected_files:
  - docs/phase2_argument_readout_task_design.md
  - docs/phase2_argument_readout_96_condition_draft.md
  - docs/experimental_protocol.md
  - docs/decisions/README.md
  - PROJECT_STATE.md
supersedes: RDR-2026-10-22-02
related_decisions:
  - RDR-2026-10-14-01
  - RDR-2026-10-01-02
  - RDR-2026-10-22-01
---

# 初回argument probe用96条件と後続の対応対照を分ける

## 判断と部分改訂の範囲

2026-10-22、研究者は、最初に`argument_readout`の学習経路を成立させるため、Bankingの`send_money.recipient`について6意味系列・各4タスク・各4条件、計96条件の小規模な基礎セットを設計する方針を示した。4系列をtraining、2系列をdevelopment validationの候補とする。各タスクでは、二つの候補口座の一方をrecipient、もう一方を別用途の参照口座へ置き換える。4候補口座を系列・split内で均衡させる。24タスクと96条件の具体案は研究者が確認してから実行仕様を固定する。

初回96条件は、正規ユーザー指示中のrecipient内容を主に扱う。tool出力中のIPI、引用・禁止、両口座がrecipient候補になる条件は、**後続の追加セット**として別に設計・検証する。これは[RDR-2026-10-22-02](2026-10-22_argument_readout_task_design.md)で定めた対応対照の**収集順序と初回セットの内訳だけ**の部分改訂である。同RDRの`send_money.recipient`への限定、条件由来の多ラベル内容ラベル、既知候補での未知系列validation、正規／攻撃の区別を内容ラベルへ混ぜない規則は維持する。追加セットを省略したり、96条件だけでIPIへの適用を妥当化したりする判断ではない。研究計画の主解析とプロトコルのPhase 2終了条件も維持する。

## 根拠と時点

96条件は、候補ごとの線形二値probe、train-only前処理、ラベル・featureの接続、系列単位のvalidationを小規模に検証するための段階的な設計である。同じ口座文字列をrecipientと別slotへ置く対応条件は、文字列出現だけを読むprobeの検出にも使える。ただしユーザー指示の四条件だけでは、異なる情報源、引用・禁止、両recipient候補の同時提示への分布移動は評価できない。これらを後続セットで確かめる前に、主解析用の攻撃者側`argument_readout`として採用しない。

判断時点で二文書v2の五runと人手監査は完了しているが、同一train側成分であり、独立validationはない。初回v1は未監査の設計失敗記録、pilotは`pilot_only`である。確認的testは未作成・未実行・未閲覧である。96条件の本文、候補口座実値、関係graph、split manifest、model-free検証、runtime freeze、モデルrunはまだ存在しない。過去のモデル結果を96条件の成功例選別に用いない。

## 実行前の条件と研究への影響

新規runの前に、候補値・全条件・ラベル裁定・既使用系列を含む関係graph・split・評価器と対照・取得位置・監査・停止規則・runtimeを固定する。系列名や候補口座の共有だけで独立groupと認定しない。trainingとvalidationが同一連結成分になれば、その割当で未知系列validationを実施しない。確認的test候補は開発・既使用系列から隔離する。

RDR-2026-10-14-01の暫定Qwen3-8B int8 / Bankingと旧clean gate不合格、主モデル・主ドメイン未採用は維持する。この段階化はResearch Question、仮説、確認的主回帰、主張範囲を変更しない。96条件でprobeが動いても、source-roleやauthorityの成立、IPIへの一般化、目標の採用や因果性を示したとは扱わない。
