# 局所文言ベースラインの正式記録（2026-11-16）

[パッチング仕様](../phase2_activation_patching_spec.md)の11節（[RDR-2026-11-14-01](../decisions/2026-11-14_h1_scope_and_patching_focus.md)の決定3）に従う。
研究実施者の指示により、Claude Codeが一度だけ実行した。

**位置づけ：**
- [位置スイープの記録](2026-11-12_position_sweep.md)にある「結果閲覧後のレビューによる留保」の1（非公式確認）を、不変の派生出力として正式に記録するものである。
- 結果を見た後の、訓練側だけの解析である。手順3・D除外対照の判定は変更しない。
- GPUとモデルは使っていない。

## 実行

- commit：`ca51df750fbac8bd37ff5d3369cf15c7d9a7fef7`（`main`、clean）。
- 実行時刻：2026-11-16 13:29:14〜13:29:23 JST、終了コード0。
- BLASのスレッド数を指定する3変数は、コード内で1に設定される。
- 検証側の扱い：
  - 整合性検査のため、宣言全体（検証192行を含む）を読み込んだ。
  - 検証行の利用は0件、検証run bundleの読み込みも0件である。
- 設定（結果を見る前に仕様で固定）：
  - 位置は`A1`・`A2`。各口座の直前N文字（N = 32・64・128）を使う。
  - 文字2〜5-gramのTF-IDFとロジスティック回帰（L2、C=1.0、`max_iter`=1000、seed 20261027）。
  - TF-IDFの語彙と標準化は、foldの学習側だけでfitする。

```bash
set -o noclobber
PYTHONPATH=src HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 .venv/bin/python -m goal_takeover.phase2.local_wording_baseline run configs/analysis/phase2_activation_patching_v1.json > artifacts/phase2-local-wording-baseline-ca51df7.log 2>&1 < /dev/null
```

| 出力 | bytes | SHA-256 |
|---|---:|---|
| `artifacts/processed/argrec672-v1-dg-010-local-wording-baseline/report.json` | 514226 | `7ac92034d3c36cc112e6bc4d7c1d1d5fdd93d915a4d131ce47fbdbce947adee1` |
| `artifacts/processed/argrec672-v1-dg-010-local-wording-baseline/manifest.json` | 217 | `5347e7204d531e6248e55ac8e4e49cd469b0282c044dff093b5b36f07bd8b812` |
| `artifacts/phase2-local-wording-baseline-ca51df7.log`（出力パス1行のみ） | — | `592ef3cb7f76075015bea46899f11b3df87d1c31766c70c3ed0ab3fef48bfa1d` |

レポートの`research_result`は`formal_record_of_post_result_informal_check`、`changes_prior_classifications`は`false`である。

## 結果

120対の対内正解率。ファミリー除外（6 fold）が主な評価で、系列除外（40 fold）は比較用である。

| 位置 | N | ファミリー除外 | fold別（最小〜最大） | 系列除外 | 非公式確認（2026-11-12） |
|---|---:|---:|---|---:|---:|
| `A1` | 32 | 1.000 | 1.000〜1.000 | 1.000 | 1.000 |
| `A1` | 64 | 1.000 | 1.000〜1.000 | 1.000 | 1.000 |
| `A1` | 128 | 1.000 | 1.000〜1.000 | 1.000 | 1.000 |
| `A2` | 32 | 0.992 | 0.952〜1.000 | 0.992 | 0.992 |
| `A2` | 64 | 0.983 | 0.952〜1.000 | 0.983 | 0.983 |
| `A2` | 128 | 0.858 | 0.786〜0.944 | 0.867 | 0.858 |

- ファミリー除外の値は、6通りとも非公式確認と一致した。仕様11節により、今後は本記録の値を引用する。
- **窓の長さ：** 口座が提示テキストの先頭近くにある条件では、窓が指定のN文字より短くなる（テキストの先頭で切る実装どおりの動作）。
  - 該当件数（240条件中）：`A1`はN=32で6件、N=64で80件、N=128で168件。`A2`はN=128で61件。`A2`のN=32・64では0件。
  - これは結果を見た後に確認した事実で、どの窓長でも結論は同じである。

## 解釈

- 口座の直前32文字だけで、`A1`はすべての対で、`A2`は120対中119対で、送金先が先の口座か後の口座かを当てられた。
- 位置スイープで`A1`・`A2`から向きを読めた（R1）ことは、役割を示す文言が口座の直前にあり、その情報が口座の位置に乗っていることで説明できる。
- したがって、位置スイープの「`H1_consistent`」（規則3）を、H1の証拠として引用しないという留保を維持する。
  判定そのものは変更しない。
- 本記録は、パッチング（`T`・`S`・`G`の介入、[解析記録](2026-11-16_activation_patching_analysis.md)）の判定に影響しない。
  パッチングは`A1`・`A2`を対象にしておらず、H1については何も述べない（RDR-2026-11-14-01）。
