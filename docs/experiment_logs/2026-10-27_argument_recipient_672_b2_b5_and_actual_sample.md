# 672条件 B1再導出・B2〜B5累積fit・実走行112件（2026-10-27）

[B1記録](2026-10-27_argument_recipient_672_b1_capture_and_fit.md)の続き。[RDR-2026-10-27-01](../decisions/2026-10-27_argument_recipient_672_review_capture_and_staging.md)と[RDR-2026-10-27-02](../decisions/2026-10-27_argument_recipient_672_preprocessing_and_undefined_metric_rules.md)に従う開発段階の実行記録。検証G/Hは各段階で閲覧しているため、結果は適応的な開発結果であり、独立確認ではない。

**この記録の位置づけ**：実行は2026-10-27 02:09〜02:26に完了していたが、当時は記録がなかった。本ログは、`artifacts/`の読み取り専用検査（run.json・manifest.jsonの照合、checksum再計算、更新時刻、解析report）から後から作成した。実行中のランナーログは参照していない。小さな要約は[results](../../results/2026-10-27_phase2_argument_recipient_672_b2_b5_and_actual_v1.json)に保存した。

## 実行

実行commitは`02b931a`（クリーン）、runtime freezeのSHA-256は`8f14cd3f…`（`artifacts/phase2-argument-recipient-672-runtime-02b931a.freeze.json`と一致）、design freezeは`397236f3…`。

| prefix | 内容 | 件数 | commit |
|---|---|---|---|
| `argrec672-v1-001` | B1正準capture | 288 | `0ec9579` |
| `argrec672-v1-002` | B1再capture（`fa07335`用freeze） | 288 | `fa07335` |
| `argrec672-v1-003` | B1〜B5正準capture（train 480 + validation 192） | 672 | `02b931a` |
| `argrec672-v1-act-003` | 実走行（actual）標本 | 112 | `02b931a` |

全1,360バンドルが`completed`で、manifest記載のartifact（1,728 + 1,728 + 4,032 + 1,120件）は欠落なくsize・SHA-256が一致した。資源上限超過・技術失敗はなく、実走行のGPUピーク最大は11.66 GiB（上限12 GiB）。

- `003`のB1部分の解析（`an-003-B1`）のreportは`an-002-B1`と完全に一致した。選択ファイルの差はprovenanceとcapture manifestのchecksumのみ。これはB1記録末尾の「再導出の結果が一致するか」の確認にあたる。
- ステージ順序：各ステージのtrain取得の更新時刻は、直前ステージまでの解析出力の後だった（B2取得 02:13:40〜14:42 は B1解析 02:13:22 の後、B3取得 02:17:04〜 は B1→B2解析 02:15:41 の後、B4 02:19:32〜 は B1→B3 02:19:14 の後、B5 02:22:06〜 は B1→B4 02:21:49 の後）。RDR-01の「前段の検証fit後に次の96件を取得する」規則と矛盾しない。ただし根拠はファイル更新時刻のみ。
- 層8 / C=1.0は`argrec672-v1-an-003-b1-selection.json`（SHA-256 `0496a94d…`）で固定され、B2〜B5で変更していない。

## 結果（主指標：G/H 48条件の`role_swap_auc`、層8 / C=1.0）

| 段階 | train条件数 | probe | TF-IDF | I/J診断 | lexical-present | random-label対照（10回の範囲） |
|---|---|---|---|---|---|---|
| B1 | 96 | 0.521 | 0.530 | 0.510 | 0.513 | 0.444〜0.542 |
| B2 | 192 | 0.477 | 0.542 | 0.531 | 0.493 | 0.438〜0.530 |
| B3 | 288 | 0.526 | 0.542 | 0.569 | 0.543 | 0.425〜0.559 |
| B4 | 384 | 0.536 | 0.528 | 0.540 | 0.538 | 0.410〜0.595 |
| B5 | 480 | **0.613** | 0.531 | 0.547 | 0.603 | 0.436〜0.576 |

- 全段階で検証条件の欠測はなく、主指標は`complete`。開発到達基準0.80は**どの段階でも未達**。
- B5の0.613はTF-IDFと、そのB5のrandom-label対照の最大値0.576を上回る。ただしB4のrandom-label最大値は0.595でB4のprobe値0.536を上回っており、10回のrandom-label対照の最小〜最大は0.10〜0.19の幅を持つ。B1〜B5の変化は単調ではなく（B2で低下）、B5の上昇を学習曲線の傾向と判断するには根拠が足りない。
- B5の候補別AUROCはv1 0.632、v2 0.563、v3 0.583、v4 0.674。境界別層別（B5）は`user_to_assistant`、`first_tool_to_assistant`、`later_tool_to_assistant`で件数が小さく（later_tool_to_assistantは8条件）、層別値は解釈に使わない。
- B5のvalidation較正は5 binでECEが大きく、候補v1は0.207。確率はよく較正されていない。

## 実走行112件

標本は[選択案](../../data/splits/phase2_argument_recipient_672_review_actual_sample.json)どおり、56系列から1タスクずつ、`rx_ref_y`と`ry_ref_x`の両方を走らせたもの。Qwen3-8B int8、決定論的デコード（temperature 0、最大256トークン、最大8ステップ）。

- 厳密評価（strict）とnative評価は112件すべて一致。ユーザータスク成功67、失敗45。
- 失敗45件の内訳：参照口座（支払元口座）への誤受取人送金14、送金なし等31。誤送金したのに最終回答は送金成功と述べる例がある（a001）。
- 文書読取前に送金した（`reads_before_transfer=false`）のは18件。許可されたツール順序は112件すべて。
- 選択位置はすべて`Tend_assistant`で、`boundary_matches_canonical`は112件すべて真。

| 区分 | 条件数 | 成功 | 誤受取人送金 |
|---|---|---|---|
| 規則D1 | 22 | 20 | 2 |
| D1M | 18 | 18 | 0 |
| D2 | 8 | 8 | 0 |
| U0 | 26 | 11 | 1 |
| UN | 14 | 6 | 2 |
| UI | 24 | 4 | 9 |
| source: 文書内 | 48 | 46 | 2 |
| source: ユーザー指示 | 64 | 21 | 12 |

ユーザー指示形式（U系）の成功率が文書形式（D系）より低い。件数が小さく監査も未実施のため、傾向の記述にとどめる。

## 解釈の限定

- 累積fitは、B5でもG/Hの`role_swap_auc`が0.80に届かない。「受取人と参照口座の役割を`Tend_assistant`の残差から読み出せる」という主張は、この段階では支持されない。
- 実走行112件は自動ラベルのみで、人手・LLM監査は未実施。残り560条件の行動成功率を推定したものではない。
- 実走行では、正準取得の教師用位置と実走行の`Tend_assistant`の転移（canonical→actual）は、まだ評価していない。
- 検証G/Hは5段階すべてで閲覧済みであり、検証の閲覧範囲と停止閾値はRDR上なお未決。

## 未実施

- 112件へのLLM監査（`gpt-6-sol`）と、不一致・要確認ログの人手確認。
- 転移評価（正準で学習したprobeを実走行の`Tend_assistant`に適用）。
- B5までの結果を受けた設計判断（追加のtrain拡張、位置・特徴の再検討、停止）。これは別RDRで決める。
