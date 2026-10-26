# 672条件probe経路の実装準備

[研究実施者判断](decisions/2026-10-27_argument_recipient_672_review_capture_and_staging.md)に基づくレビュー段階の実装であり、新規fitや研究結果ではない。

- `argument_recipient_672_capture`はUのユーザー指示、D1/D1Mの一資料読取、D2の二資料読取を正準履歴として構成し、露出後のassistant生成直前の末尾tokenを選ぶ。
- `argument_recipient_672_bundle`はcaptureを不変のraw bundleへ保存する。`argument_recipient_672_features`はchecksum、revision、条件ID、位置、口座露出、残差の形状と有限性を照合して特徴量を読む。資料由来条件の語彙検査には読取後の直列化prefixを使う。
- `argument_recipient_672_cv`はB1の96件について8系列のleave-one-series-outを行い、6層×3個のCから系列外二口座`role_swap_auc`最大の組を選ぶ。標準化とlogistic probeは各foldの残り7系列だけでfitする。同点時は宣言順の早い層、小さいCとする。
- `argument_recipient_672_fit`は選んだ層・CでB1、B1+B2、…を累積fitし、G・Hの48件`role_swap_auc`、I・Jの関連系列診断、lexical-present副指標、TF-IDF baseline、random-label対照、source・規則・境界・ファミリー別結果、較正を別欄に返す。欠測検証条件は明示し、主指標に必要なscoreが一つでも欠ければ未定義にする。train capture欠測はfit停止とする。派生fitは新規ディレクトリへparameterとchecksum付きで保存する。

全672件の正準captureと112件の実走行を回す研究用CLIは、設計/runtime freeze照合と技術失敗保存を含めて実装した。[採用済みCodex監査prompt](../configs/audits/phase2_argument_recipient_672_codex_prompt_v1.md)と[JSON schema](../data/schemas/phase2_argument_recipient_672_codex_audit.schema.json)もある。GPU 12 GiB・1条件300秒・保存0.05 GiBを上限とし、技術失敗は不変bundle保存後に停止して同じIDでは再試行しない。[実行宣言とdesign freeze](../data/manifests/phase2_argument_recipient_672_v1.freeze.json)は作成済み。runtime freezeと同一commit GPU検査、Codex CLIのモデル利用可否は未了であり、新規研究runは開始しない。
