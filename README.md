# Whose Goal Is It Anyway?

Indirect Prompt Injectionを受けたツール利用型LLMエージェントについて、ユーザー目的と攻撃者目的の内部表現が、外部データの読み取りからツール選択までにどう変化するかを調べる卒業研究リポジトリです。

研究計画の詳細は [`docs/research_proposal.md`](docs/research_proposal.md) を参照してください。

## 現在の状態

現在はPilot実験前の基盤整備段階です。モデルと主対象ドメインはまだ確定しておらず、`configs/**/example.yaml`は選定候補を記入するための雛形です。エンドツーエンドのモデル実行とAgentDojo接続は未実装です。

## ディレクトリ

- `configs/`: モデル、ドメイン、実験、Probeの宣言的設定
- `src/goal_takeover/`: エージェント、計測、評価、データ処理のコード
- `data/templates/`: ユーザータスク、攻撃、対照条件のテンプレート
- `data/schemas/`: 条件・実行記録のJSON Schema
- `data/manifests/`: 外部保存データの所在とchecksum
- `data/splits/`: task・attack template単位のデータ分割
- `data/raw/`, `data/processed/`: Git管理外の生成データ
- `outputs/`: Git管理外の実行出力
- `tests/`: 小さな合成fixtureを用いた回帰テスト
- `docs/`: 計画書と実験プロトコル

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
PYTHONPATH=src python3 -m unittest discover -s tests
python3 -m compileall -q src tests
```

開発依存を導入した後は次も実行します。

```bash
ruff check .
ruff format --check .
pytest
```

設定ファイルは次のコマンドで読み込みと最低限の必須キーを検査できます。

```bash
python -m goal_takeover.cli validate-config configs/experiments/pilot.yaml
```

## 実験出力

各実行は`outputs/runs/<run_id>/`に独立して保存し、少なくとも次を残す予定です。

- 解決済み設定とGit commit
- モデル・tokenizerのrevision
- condition、pair、task、attack templateのID
- seedとdecoding条件
- ユーザータスク成功・攻撃成功・群A～D
- 各処理段階のtoken indexとtoken ID
- 攻撃ツール・正規ツールの系列Log probability
- Activation等の保存先とchecksum

Activation、Attention、モデルWeight、大量の実行ログはGitへコミットしません。再現に必要なmanifest、設定、集計済みの表と図のみをGit管理します。

## 再現性上の注意

- 主解析は原則greedy decodingまたはtemperature 0で行います。
- 近い言い換え、同一条件の反復、意味的対応ペアをsplit間で分離しません。
- Goal readout、Role readout、Attention、行動Logitを別の指標として扱います。
- Probe scoreだけを根拠に目的の採用や因果的Takeoverを主張しません。

詳細な固定事項とPilot後の変更手順は [`docs/experimental_protocol.md`](docs/experimental_protocol.md) に記録します。
