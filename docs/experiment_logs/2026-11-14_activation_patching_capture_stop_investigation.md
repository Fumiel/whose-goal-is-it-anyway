# パッチング本取得の技術停止調査（2026-11-14）

研究実施者の「途中で止まった原因を分析し、対策を考える」という依頼に対する調査記録。
既存run、freeze、ログ、環境lockは読み取り専用で調べた。モデル実行、介入効果の集計、
再開、プロセス停止、設定変更は行っていない。以下の復旧策は提案であり、採用済みの設計変更ではない。

## 結論と現状

直接の停止理由は、`c475`の介入処理後の資源検査で発生した
`RuntimeError: condition time ceiling exceeded`である。600秒を超えたため、
仕様どおり失敗bundleを保持し、終了コード1で全体を停止した。
今回の終了をSSH切断やCUDA OOMによる強制終了とする証拠はない。

速度低下の有力な背景はWSLのホストメモリ圧迫である。停止条件の処理中に
RAMの割当失敗とswap枯渇が記録され、調査時点でも大量ログを表示する端末プロセスが
RAMとswapを大量に使用していた。ただし、端末メモリの時系列計測と対策前後の比較はなく、
ログ表示が速度低下の全量を説明するとの因果的な断定はしない。

| 項目 | 読み取りで確認した状態 |
|---|---|
| 実行commit | `76e538a09d0727d053b6e882d2a04b518d1f2208` |
| runtime freeze | `artifacts/phase2-activation-patching-runtime-76e538a.freeze.json` |
| 対象 | 訓練側240条件 |
| 完了 | 48条件（20%） |
| 技術失敗 | `argrec672-v1-pt-001-c475`、`F6-2-rx_ref_y`、介入段階 |
| 未実行 | 191条件。復旧で必要な完了取得は失敗1件を含む192条件 |
| 保存検査 | 49 bundleのmanifestが宣言する435ファイルのサイズ・SHA-256が一致 |
| 失敗時GPUピーク | 9.412519 GiB、12 GiB上限未満 |
| 完了48条件の時間 | 最小499.372秒、平均507.785秒、最大525.841秒 |
| 同commitのGPU事前確認 | passed、先頭2条件457.875秒・455.198秒 |

`c475`は正準条件番号であり、475件取得した意味ではない。実際には49番目の介入対象だった。
完了条件の規則U0/UN/UI/D1/D1M/D2別の平均は505.959〜510.270秒で、
完了48件に限れば特定の課題規則だけが大幅に遅い状況ではなかった。

## 時刻とOS側の証拠

時刻はJST。bundleの時刻はmanifestのファイル更新時刻であり、計算タイマーそのものではない。

- 最初の完了bundle（c368）: 11月14日06:30:58。これ以前に本取得が始まっている。
- 最後の完了bundle（c300）: 13:04:17。
- 13:10:03、13:11:20、13:12:41、13:14:47:
  `/var/log/kern.log`に`kworker/0:1: page allocation failure: order:7`。
  VMBus/vsock関連の割当経路で失敗している。
- 13:10:04のkernel記録:
  `Free swap = 0kB`、`Total swap = 16777216kB`。
  Normal zoneの空きは35,272 kB、DMA32の空きは49,892 kB。
- 13:16:53:
  `python: page allocation failure: order:4`、PID 32600。
  `p9_client_read_once`・`v9fs_issue_read`等のファイル読出し経路で割当失敗。
  同じ記録でswap空き0 kB。PythonのCUDA OOM例外とは異なる。
- c475の失敗manifest保存: 13:17:04。最後の完了保存から767.202秒。
  この間隔をc475の正確な計算時間としては扱わない。
- 実行ログの最終更新: 13:17:47。末尾は上記例外と`PATCHING_EXIT_CODE=1`。

WSL設定は`/mnt/c/Users/dacha/.wslconfig`で`memory=12GB`、`swap=16GB`、`processors=8`だった。
調査時点でもswap空きは約8 MBしかなかった。現在のGPU使用量は1,131 MiB、利用率1%で、
パッチング用Pythonはプロセス照会で見つからなかった。
Windows側のイベント照会からは利用できる結果を得ていないため、Windows全体に関する障害不在は断定しない。

## 大量警告と端末メモリ

実行ログ`artifacts/phase2-activation-patching-capture-76e538a.log`は
**3,529,034,711 bytes、41,518,080行**だった。
内容の大半は同じ`MatMul8bitLt: inputs will be cast from torch.bfloat16 to float16 during quantization`の反復である。
ローカルのbitsandbytes 0.50.2の`autograd/_functions.py:129`は、これを
`logger.warning(...)`として出力している。Pythonの`warnings.warn`ではない。

調査時点に残っていたプロセスの親子関係は次のとおり。

```text
cmux-tui headless (PID 550)
  cmux-tui terminal-host (PID 32903)
    bash (PID 32904)
      tail -f artifacts/phase2-activation-patching-capture-76e538a.log (PID 32953)
```

`/proc/<pid>/exe`の実体はいずれも`/home/fumiel/.local/bin/cmux-tui (deleted)`だった。
観測したメモリ使用量は次のとおり。終了後の一時点の値であり、停止瞬間の値ではない。

| PID | RSS (kB) | VmSwap (kB) |
|---|---:|---:|
| 550 | 9,138,096 | 14,328,260 |
| 32903 | 36,652 | 2,269,292 |

合計は約24.6 GiB。大量の警告を端末へ流し続ける経路と、端末側の大きい匿名メモリ使用は確認できた。
端末内部でどのデータ構造が増えたか、以前からの他セッションがどれだけ寄与したかは未計測である。
したがって「大量表示→端末メモリ増加→swap圧迫→速度低下→600秒超過」を有力な説明とし、
cmuxの特定の実装バグやパッチングコードのメモリリークを確定したとはしない。

## 実装側の問題と再開の制約

- `activation_patching.py`の資源検査は90介入と正常再確認が終わってから行われる。
  600秒はOSがプロセスを打ち切るタイムアウトではなく、事後検査の上限である。
- 失敗bundleは`condition.json`、`resolved_config.json`、`run.json`とmanifestだけを保持する。
  正確な経過秒、forward内訳、介入結果は保存されていない。
  原因の確定と部分計算の再利用には限界がある。
- 完了48条件では逐次1token順伝播が総条件時間の約94.9%を占め、1回平均約155.7 msだった。
  GPU事前確認の約455〜458秒より本取得は約11%遅い。forward時間には同期やログ処理も含むため、
  この差をGPUカーネルだけの差とは解釈しない。
- `completed_bundle()`は既存の失敗IDを見つけると
  `retained failure: retry requires a new run ID prefix`で停止する。
  同じコマンドを再実行してもc475を越えて続行できない。
- prefixを一律変更すると完了48件も再取得する。既存のcollection-manifest・解析も
  単一prefixの全条件を要求するため、48件を引き継ぐには取得だけでなく入力解決経路の追加も必要。

## 推奨する対策と順序（未実施）

1. **先にログ表示とホストメモリを安定させる。** 生ログ全体の`tail -f`を端末に流さず、
   進捗・終了・例外だけを低頻度で表示する。実行出力はWSL内のファイルへ直接保存する。
   対象の型変換メッセージだけをloggingのfilterで最初の1回に制限し、他の警告・例外は残す。
   `PYTHONWARNINGS`だけではこのlogger出力を制御できない。計算dtypeや採点経路は変更しない。
   端末のメモリ解放には対象表示セッションの終了・必要なら端末再起動を検討するが、
   他の作業を確認してから行う。調査ではプロセスを終了していない。
2. **600秒を維持して再計測する。** RAM空き、swap使用・swap入出力、メモリpressure、
   プロセスRSS/VmSwap、GPUメモリ・利用率を記録する。
   短い事前確認だけでなく複数条件の連続工学計測で時間とメモリの推移を見る。
   600秒をさらに引き上げる前に、環境圧迫を除いた状態で再現するか確認する。
   実施する工学計測の対象・範囲は事前に記録し、研究結果や条件選択には使わない。
3. **失敗時の診断記録を増やす。** 経過秒と処理内訳、最後に完了したセル、利用可能RAM・swap等を
   新規失敗bundleへ保存する。正常計算・各donor群の開始終了を時刻付きで記録する。
   計測やログの変更が数値を変えないことを、self・陽性対照・キャッシュ復元の厳密一致で再確認する。
4. **専用の復旧経路を作る。** 旧48完了bundleと失敗c475は保持する。
   条件IDごとに旧完了48件と新規192件のrun ID・commit・freeze・manifest checksumを対応づける
   recovery manifestを定め、c475は新しい試行IDとする。donorの正常計算は新実行内で全240条件分再取得し、
   既存48件との正常残差・分布・記録の一致を検証する。取得・manifest・解析の読込経路で混在来歴を明示する。
   計算の省略や効果による選別はせず、対象・donor・層・位置・閾値を固定したままにする。
5. **復旧方針を記録してから実行する。** 変更commit、事前確認、環境lockと新runtime freezeを用意する。
   旧結果を新条件で事後的に合格扱いせず、旧失敗も除去しない。
   時間上限変更や既存runを引き継ぐ手順の変更を採用する場合は、影響と今回閲覧した証拠をRDRに記録する。

現状の完了平均を192条件へ外挿すると約27.1時間で、donor再計算・事前確認・検証等は別途必要。
ログ制御後の速度は未測定のため、改善幅は約束しない。
介入の科学的結果をまだ集計していないので、この停止からH2/H3の支持・不支持は判断できない。

## 保存記録の識別

| 記録 | SHA-256 |
|---|---|
| captureログ | `130d2f57643a38bf40fd8d595e520bab4fbf790e709a9e6fd9222f5292361f53` |
| GPU事前確認76e538a | `9c67f2b6bfd981c5f004ea16c1823e9e8e402b44a7c4cba89e41c3b180e6908b` |
| runtime freeze 76e538a | `eacf581fd2ebcde0342f698f24b44981634b3f62ca78a98028aa481b8f480a7d` |
| c475 manifest | `9f3069029c68b2ff712830409ae8ecc5a5443ba3d52a253268aae574de51b02a` |
| c475 run.json | `5b5862d6343d1e801d39df20b5210e5d4ef778c675013156de2a009d8ab11bb3` |

根拠となる現行手順は[仕様](../phase2_activation_patching_spec.md)、
[runner](../phase2_activation_patching_runner.md)、
[RDR-2026-11-14-04](../decisions/2026-11-14_patching_time_limit_revision.md)。
本記録は過去の「本取得未開始」という記述以降に確認した実行事実を記録するもので、
過去のRDRや事前確認記録を遡って変更しない。
