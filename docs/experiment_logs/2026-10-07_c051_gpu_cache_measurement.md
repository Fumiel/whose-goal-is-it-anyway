# 2026-10-07 condition 51のGPUキャッシュ工学計測

`banking-pilot-001-c051-a1/prefixes.json`に保存された4 prefix
（1,551、2,105、2,156、2,313 token）を使用した。モデルは凍結したQwen3-8B
int8、BF16、`sdpa`、36層。旧失敗bundleや結果を変更せず、生成を再実行していない。

| 工学測定 | 最大割当 | 最大予約 | 判定 |
|---|---:|---:|---|
| 2,313 tokenの残差、取得間のキャッシュ解放なし | 9.48 GiB | 12.25 GiB | 12 GiB超過 |
| 4 prefixの残差、各取得前に未使用キャッシュ解放 | 9.48 GiB | 11.06 GiB | 全件12 GiB以内 |
| 4 prefixのlast-query attention、各取得前に同様の解放 | 9.48 GiB以下 | 11.06 GiB以下 | 全36層取得、全件12 GiB以内 |

PyTorchの`max_memory_allocated`と`max_memory_reserved`を測定。旧研究runの
失敗時peakは保存されなかったため、この数値を旧runの測定値として代用しない。
位置数は順に1、4、2、2。全prefix IDは保存値と一致した。
これは保存済み軌跡に対する資源診断で、行動や内部状態の研究結果ではない。
