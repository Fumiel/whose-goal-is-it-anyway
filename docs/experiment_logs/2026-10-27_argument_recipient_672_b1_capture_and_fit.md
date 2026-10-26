# 672条件 B1 の正準capture、B1内CV、最初の累積fit（2026-10-27）

[RDR-2026-10-27-01](../decisions/2026-10-27_argument_recipient_672_review_capture_and_staging.md)と、fit前に前処理・較正・未定義規則を固定した[RDR-2026-10-27-02](../decisions/2026-10-27_argument_recipient_672_preprocessing_and_undefined_metric_rules.md)に従う開発段階の実行記録。検証G/Hは各段階で繰り返し閲覧するため、結果は適応的な開発結果であり、独立確認ではない。

## 経過

1. commit `0ec9579`・対応するruntime freezeの下で、B1正準capture（prefix `argrec672-v1-001`、train 96 + validation 192）を実行した。288件`completed`、1,728ファイルのchecksum一致、技術失敗なし、所要約3分28秒。この時点でprobe score・CV・validation値は計算していない。
2. RDR-2026-10-27-02をcommit `fa07335`として保存した。runnerはruntime freezeのcommitと現在のHEADの一致を要求するため、旧freezeは使えなくなった。
3. `fa07335`用に、凍結済み実行宣言`data/templates/phase2_argument_recipient_672_v1.json`を入力としてnative（2,688対照）、tokenizer（672条件）、GPU（最長一資料条件`G4-2-rx_ref_y`、peak 11,492,392,960 byte ≒ 10.70 GiB）の事前検査を行い、別の環境ロックとruntime freezeを作成した。native・tokenizerの出力は旧freezeのchecksumと一致した。
4. **取り違えの記録**：最初の事前検査の入力に、実行宣言ではなく草案JSON（`..._draft.json`）を渡した。その3出力は`artifacts/*-fa07335-wrong-input-draft.json`として保持し、freezeには使っていない。正しい入力で再実行した出力をfreezeに使った。
5. 旧bundle（`-001`）は旧commit・旧freezeに結びついており、新freezeの解析は受け付けなかった（解析は0.2秒で停止し、何も保存していない）。B1を新しいrun ID `argrec672-v1-002`で再captureした。288件`completed`、checksum一致、所要約3分27秒。**残差は`-001`と288条件すべてでバイト単位に一致した。** `-001`は削除せず保持する。
6. B1解析（`argrec672-v1-an-002`）は約23秒で完了した。

## 結果（B1のみ、層8 / C=1.0）

[小さい要約](../../results/2026-10-27_phase2_argument_recipient_672_b1_fit_v1.json)に値を保存した。

| 項目 | 値 |
|---|---|
| B1内leave-one-series-out CVの`role_swap_auc`（選ばれた組） | 0.502（全18組で0.391〜0.502） |
| **主指標：G/H 48条件の`role_swap_auc`** | **0.521**（候補別0.465〜0.569） |
| I/J（train近縁）診断 | 0.510 |
| TF-IDF baseline（同一指標） | 0.530 |
| lexical-present副指標 | 0.513 |
| random-label対照（10回） | 0.444〜0.542 |
| 開発到達基準0.80 | 未達 |

検証条件の欠測はなく、主指標は`complete`だった（RDR-2026-10-27-02の未定義規則は発動していない）。

## 解釈の限定

- 96条件（8系列）で学習したprobeは、未知系列の二口座の役割を`Tend_assistant`から読み出せていない。値はrandom-label対照およびTF-IDFと区別できない。
- B1の1段階であり、B2以降で変化するかは未確認。途中結果を理由に規則を変更しない（RDR-2026-10-27-01）。
- 選ばれた層8 / C=1.0はB1内CVが0.50で、設定間の差は偶然水準のため、層・Cの選択に情報はほぼない。

## 後続の手順上の注意

この記録のcommitによりHEADが変わるため、B2に進む前に新commit用のruntime freeze、B1の再capture・再解析が必要になる。再導出の結果が本ログと一致するかは、次のログで確認する。
