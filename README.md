# Whose Goal Is It Anyway?

Indirect Prompt Injectionを受けたツール利用型LLMエージェントについて、ユーザー目的と攻撃者目的の内部表現が、外部データの読み取りからツール選択までにどう変化するかを調べる卒業研究リポジトリです。

研究計画の詳細は [`docs/research_proposal.md`](docs/research_proposal.md) を参照してください。

## 現在の状態

現在はPilot実験前の基盤整備段階です。モデルと主対象ドメインはまだ確定しておらず、`configs/**/example.yaml`は選定候補を記入するための雛形です。合成fixtureに加え、AgentDojo 0.1.35 / Banking v1.2.2用adapterとQwen3 Transformers runnerを実装済みです。Qwen3-8B int8とQwen3-4B BF16のWindows GPU工学shakedownは各3 fixtureを完走し、WSL上のraw bundle監査も記録しました。これらは正式な候補評価や研究結果ではありません。測定値と確認範囲は[技術記録一覧](docs/experiment_logs/README.md)を、作業時点の状態は[`PROJECT_STATE.md`](PROJECT_STATE.md)を参照してください。

## ディレクトリ

- `configs/`: モデル、ドメイン、実験、Probeの宣言的設定
- `src/goal_takeover/`: エージェント、計測、評価、データ処理のコード
- `data/templates/`: ユーザータスク、攻撃、対照条件のテンプレート
- `data/schemas/`: 条件・実行記録のJSON Schema
- `data/conditions/`: 生成済みの小さな条件宣言
- `data/manifests/`: 外部保存artifactの所在とchecksum
- `data/splits/`: task・attack template単位のデータ分割
- `artifacts/`: Git管理外のraw run、processed data、analysis output
- `results/`: provenance付きの小さな確定表・図
- `tests/`: 小さな合成fixtureを用いた回帰テスト
- `docs/`: 計画書、実験プロトコル、実験記録（`experiment_logs/`）、教授向け報告書（`reports/`）

## セットアップ

PyTorchが対応するPython版を確認した上で、Python 3.11または3.12の利用を推奨します。

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev,research]'
cp .env.example .env
```

モデルの利用規約に同意が必要な場合だけ、`.env`へトークンを設定します。`.env`はGit管理されません。

## 最小チェック

外部依存を導入する前でも、標準ライブラリだけを使う単体テストと構文検査を実行できます。

```bash
make check-fast
```

開発依存を導入した後は次も実行します。

```bash
make check
```

設定とschemaは次のコマンドで検査できます。

```bash
make validate
```

AgentDojo研究依存を導入した環境では、固定した3 fixtureをモデルを読まずに検査できます。

```bash
make agentdojo-preflight
```

Windows 11 / WSL2 GPU環境の構築と実行方法は[`docs/windows_wsl_execution.md`](docs/windows_wsl_execution.md)を参照してください。実モデルshakedownは、8B int8候補なら次のように開始します。

```bash
goal-takeover gpu-preflight
goal-takeover agentdojo-shakedown configs/selection/pre_gate_shakedown.yaml \
  --model-config configs/models/qwen3_8b_int8.yaml \
  --run-prefix qwen3-8b-int8-shakedown-YYYYMMDD-NNN
```

`YYYYMMDD-NNN`は未使用の実行IDに置き換えてください。既存runは上書きしません。
この3 fixtureの行動成否はモデル選定、閾値設定、研究結果に使用しません。

正式なBankingモデル選定は7条件を両候補に適用します。実行前監査とblind人手監査は
[`docs/selection_audit.md`](docs/selection_audit.md)を参照してください。

```bash
goal-takeover selection-preflight configs/selection/integration_gate.yaml
goal-takeover agentdojo-selection configs/selection/integration_gate.yaml \
  --run-prefix banking-selection-YYYYMMDD-NNN
goal-takeover selection-report configs/selection/integration_gate.yaml \
  --run-prefix banking-selection-YYYYMMDD-NNN --audit <audit.json>
```

最初のモデル選定run `banking-selection-20260924-001` は14件を生成しましたが、
最終回答と生成時の生出力が保存されず、必須のblind監査に使用できません。
旧runを残したまま、凍結済みの修正版から**新しいrun prefixで両候補7件ずつ**再実行してください。

## 実験出力

各実行は`artifacts/runs/<run_id>/`に独立して保存し、少なくとも次を残します。

- 解決済み設定とGit commit
- モデル・tokenizerのrevision
- condition、pair、task、attack templateのID
- seedとdecoding条件
- ユーザータスク成功・攻撃成功・群A～D
- 各処理段階のtoken indexとtoken ID
- 正規／攻撃argument slotとwhole callの系列Log probability
- Activation等の保存先とchecksum

Activation、Attention、モデルWeight、大量の実行ログはGitへコミットしません。再現に必要なmanifest、設定、集計済みの表と図のみをGit管理します。合成end-to-end試験は`make dry-run`で実行できます。同じ`run_id`が既に存在する場合は上書きせず失敗します。

## 再現性上の注意

- 主解析は原則greedy decodingまたはtemperature 0で行います。
- 近い言い換え、同一条件の反復、意味的対応ペアをsplit間で分離しません。
- Action readout、Argument readout、Source-role readout、Authority score、Attention、Tool-call preferenceを別の指標として扱います。
- Probe scoreだけを根拠に目的の採用や因果的Takeoverを主張しません。

詳細な固定事項とPilot後の変更手順は [`docs/experimental_protocol.md`](docs/experimental_protocol.md) に記録します。
