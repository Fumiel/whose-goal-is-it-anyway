---
decision_id: RDR-2026-10-27-02
date: 2026-10-27
status: accepted
phase: phase2_argument_recipient_672_b1_collected_pre_fit
test_set_status: not_created_or_inspected
affected_files:
  - src/goal_takeover/phase2/argument_recipient_672_cv.py
  - src/goal_takeover/phase2/argument_recipient_672_fit.py
  - src/goal_takeover/phase2/argument_recipient_672_metric.py
  - docs/decisions/README.md
  - PROJECT_STATE.md
supersedes: null
related_decisions:
  - RDR-2026-10-27-01
  - RDR-2026-10-26-01
---

# 672条件probeの前処理・較正と主指標未定義時の規則

## 位置づけ

RDR-2026-10-27-01が「最初の新規fit前に固定する」と残した、前処理・較正の詳細と`role_swap_auc`の欠測・未定義時の規則を固定する。研究実施者の指示（2026-10-27）に基づき、現行実装（commit `0ec9579`）が実際に行う処理を文書化し、未定義時の扱いを明文化したもの。**実装は変更しない。**

## 固定時点の状態

- B1のcapture（run prefix `argrec672-v1-001`、288件、全件`completed`、checksum照合済み）は完了しているが、**probe fit、B1内CV、validation scoreはまだ一つも計算・閲覧していない。**
- したがって以下の規則は、probeのscoreを見る前に決めている。capture bundleの件数・状態・checksumだけを閲覧済みである。
- 本RDRはdesign freeze（9入力ファイル）の対象外の文書であり、凍結済みファイルは変更しない。

## 前処理

1. 特徴量は選択層の`Tend_assistant`残差（1条件1ベクトル）をそのまま使う。PCA、L2正規化、白色化、位置間の平均化、他位置との連結は行わない。
2. 標準化は`StandardScaler`（平均・標準偏差）を**そのfitに使うtrain行だけ**で推定し、held-out行・validation行には推定済みの値を適用する。B1内CVではfoldごとに残り7系列の84行、段階fitでは累積trainで推定する。validationの統計量は一切使わない。分散ゼロの次元はscikit-learnの既定（scale=1）に従う。
3. 分類器は候補口座ごとに独立した二値logistic回帰（L2、solver既定、class weightなし、`max_iter=1000`、`random_state`は実行設定のseed）とする。各候補のtrain行は、その口座を提示しない条件（ラベル0）も含めた全行とする。
4. 層とCはRDR-2026-10-27-01のB1内CVで1組を選び、B1～B5で固定する。validation値での再選択、層・C・前処理の変更はしない。

## 較正

5. 較正（Platt、isotonic、温度、閾値選択）は行わない。AUROCは順位のみに依存するため、主指標・副指標・CV選択はlogit（`decision_function`）で計算する。
6. `predict_proba`は信頼性図（5区間）とBrier scoreの**記述的診断**にのみ使い、合否判定や選択には使わない。

## 主指標が未定義になる場合

7. 主指標`role_swap_auc`は、G/Hの48条件から、各候補が実際に提示される24条件（正例12・負例12）の**全てに有限なscoreがある場合のみ**定義する。1件でもscoreの欠測・非有限・未提示があれば、候補別AUROCと4候補平均を`null`、statusを`undefined_incomplete_scores`とし、欠測した条件IDと候補を記録する。
8. 欠測を補完しない。部分的な平均、分母の変更、条件の差し替え、別の指標への読み替えはしない。AUROCの同点は0.5として数える。
9. 主指標が未定義の段階は、開発到達基準（AUROC ≥ 0.80）を**「達成」とも「未達」とも判定せず「未定義」と報告する**。欠測の原因を記録し、再収集は技術失敗時の規則に従い新しいrun IDで行う。
10. train captureの欠測、特徴量の形状不一致、非有限値は、未定義にせず**fitを停止**する（現行実装どおり）。B1内CVでも、いずれかの(層, C)で指標が不完全なら、その設定を除外せず停止する。
11. B1内CVの同点は、宣言順で早い層、次に小さいCを選ぶ。
12. 0.80基準は、G/Hの`role_swap_auc`（4候補等重み平均）に適用する。候補別値、I/J診断、lexical-present副指標、TF-IDF baseline、random-label対照は別欄に報告し、合否には使わない。TF-IDF baselineとの比較は記述として報告する。

## 注意すべき点

- 実行設定には`cluster_bootstrap_repeats: 200`が書かれているが、672用の解析コードには現時点で対応する処理がない。信頼区間は未実装であり、基準判定にも使わない。実装する場合は、別のRDRで仕様を固定し、結果閲覧前に行う。
- 検証系列の閲覧範囲、停止規則の数値、LLM判定と人手裁定の一致率の扱いは、本RDRでは固定しない。RDR-2026-10-27-01の未固定事項として残る。
- G/Hの48条件は全段階で繰り返し閲覧するため、これらの値は適応的な開発結果であり、未閲覧の独立確認ではない。
