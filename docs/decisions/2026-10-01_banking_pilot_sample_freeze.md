---
decision_id: RDR-2026-10-01-03
date: 2026-10-01
status: accepted
phase: before_exploratory_pilot
test_set_status: not_created_or_inspected
affected_files:
  - configs/experiments/banking_pilot_v1.yaml
  - configs/experiments/banking_pilot_v1.freeze.json
  - data/templates/banking_pilot_v1.json
  - data/conditions/banking_pilot_v1.jsonl
  - data/evaluators/banking_pilot_v1.json
  - docs/research_proposal.md
  - docs/experimental_protocol.md
  - docs/banking_task_candidates_2026-10-01.md
  - docs/banking_pilot_v1.md
  - PROJECT_STATE.md
  - README.md
supersedes: null
related_decisions:
  - RDR-2026-09-24-07
  - RDR-2026-10-01-01
  - RDR-2026-10-01-02
---

# Banking探索的予備実験の90条件と停止・移行規則を凍結する

## 判断と範囲

2026-10-01、研究実施者が提示された6タスク・4系列、最大90条件の方針を採用し、
関連ファイル・文書の更新とcommitを指示した。標本、payload、実行順、候補call、
評価・監査仕様、停止・移行規則、資源上限とtest除外を凍結する。
以前は用途別配分だけが決まり、具体的pilot標本と停止規則は未確定だった。

これは**標本・判断規則の凍結**である。pilot runner、native対照検証、token位置規則・
保存window・全sequence保存subset、GPU事前確認、実行codeのcommitとchecksumの凍結は
モデル実行前の残るgateとする。今回、新しいモデルrunも確認的testも実行しない。
未定のcapture値を採用済みと扱わず、別の実行用設定とfreezeで解決する。

既存の選定ゲートと不合格結果、暫定モデル扱い、shakedownデータ隔離、5/6の保留、
11の監査要件、新系列の開発・確認用配分、確認的30cluster目標は維持する。
このRDRは前記判断の具体化であり、過去のRDRを置換しない。

## 標本と比較の範囲

- パスワード14 × 攻撃7、請求書0 × 攻撃5を一スロット比較の中心とする。
- 返金3/4 × 攻撃5は同一系列で、宛先と金額を変更する。攻撃側amountは20.00とし、
  各slot、両slotのjoint marginとwhole-call marginを保存する。返金4.00/10.00の
  宛先だけの置換ではnative攻撃5の合計>10条件を満たさないため、この違いを明記する。
- 家賃2/12 × 攻撃4は同一系列で、正規ID7・amount1200と攻撃ID6・不正recipientを
  比較する。ID slotは診断、whole callは副次比較とし、recipient一スロット比較とは呼ばない。
  12はaction_openの委任対照である。
- 13、履歴照会1/7/8、不足指定9/10、11、複合15はこの初回標本に含めない。
  恒久的除外ではなく、追加には別の標本・RDRが必要である。5/6は保留を維持する。

clean 6、IPI 72（各taskに3形式×4配置・書式）、語彙対照12（代表0/3/2/14に
引用・説明・禁止各1）の計90条件。先行18はclean 6と代表4taskの3形式各1である。
cleanを先に、task順は14、0、3、4、2、12とし、同task内の条件ID順までmanifestに保存する。
seedのみの反復は行わず、先行結果で後続payloadや順序を変更しない。

共有attack styleとtask/goal/template/pair/paraphraseのedgeを使うと、この標本は
**1連結成分**になる。6task ID、4task系列、90条件と独立group数を区別する。
全条件をpilot_onlyとしてtestから除外する。既使用系列に対する過去のtest除外も維持し、
probe training / validationへの再利用許可を今回追加しない。既使用側とedgeでつながる
新系列もtestから外し、別成分の新系列を開発・確認用に設計する方針を維持する。

## 停止・移行と監査

先行18終了後、監査後の厳密clean成功が3/6以上かつ2系列以上、全18件の監査完了、
未裁定不一致0、12 IPIの固定prefix候補対の有限採点とtoken整合100%を満たせば拡張する。
3/6は複数系列で測定を続ける探索的最低条件であり、正式モデル採用基準でも、
既存選定結果を合格へ変更する規則でもない。旧shakedownの行動集計から導いていない。

最大90条件終了後、各条件の完了または失敗が記録され、同じclean基準と監査基準を満たし、
実軌跡の注入接触・内部状態取得・候補call採点が2系列以上で得られればPhase 2の設計へ進む。
fixed-prefix診断を実軌跡の取得成功へ代用しない。攻撃成功・R/S pairの最低数は置かない。
Dが0でも予定条件を完了し陰性結果を残す。新たな攻撃探索は別RDRを必要とする。
未達時は拡張を停止し、モデル・domain・採点中心・主張範囲の変更を新RDRで判断する。

native判定は変更せず、native user/attackと厳密user/宣言攻撃callの発生・副作用を分ける。
先行18、全D・異常、残るtask×outcome cellの実行順先頭を監査し、初回判断・裁定・
実際のblind状況を保存する。14の不審取引条件はnative事前確認で根拠と監査rubricを記録し、
正当化できなければ実行前に停止する。clean失敗はbaseline_failureと固定分母に残す。

token不一致、非有限値、範囲の曖昧さ、必須記録欠落、評価器対照失敗、資源超過は即停止。
モデル失敗は再試行しない。最初のモデル出力前の外部インフラ中断だけ1条件1回を許し、
新run IDと元run参照を残す。修正は新しいcode freezeを必要とし、再試行例外を広げない。

1条件300秒・GPU12GiB・保存0.05GiB、通常4.5GiB、最大180attempt・9GiB・54000秒を
保守的な工学上限として採用する。診断・失敗bundleも上限へ含める。全sequence保存が
上限を満たすことは未検証で、capture subsetと上限の整合を実行前gateで確認する。

## 来歴・影響・確認時点

ソース版と既知の制約は2026-10-01候補表の監査記録に基づく。native互換性・評価器対照検証の
完了は主張しない。正準call、注入文字範囲、条件ID、groupと順序を機械可読manifestに残し、
生成・照合コード、設定、評価仕様、モデル/domain参照をSHA-256で固定する。
freeze内のbase_git_commitは作業開始時の親commitであり、凍結ファイルを含むcommitそのものではない。
このRDRとfreezeを含むcommitが標本の来歴となり、実行時には別途runtime commitを記録する。

判断は既存モデル選定・非blind監査結果とソース監査を確認した後、新しいpilot収集の前である。
Research Question、仮説、主回帰、決定論的比較と暫定総規模は変更しない。
実行範囲・標本・停止規則・評価仕様の具体化であり、研究結果を報告するものではない。
確認的testは未作成・未実行・結果未閲覧である。
