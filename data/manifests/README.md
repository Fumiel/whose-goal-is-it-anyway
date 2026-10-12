# Artifact manifests

モデルWeightやActivation等の大容量artifactそのものではなく、次をJSONLまたはCSVで記録します。

- artifact IDと種類
- 対応するrun ID
- リポジトリ外の保存場所またはstorage key
- byte数とSHA-256 checksum
- 作成日時
- model revisionと生成コードのGit commit

秘密情報を含む完全なクラウドURLやcredentialは記録しません。

## Windows / WSL側の保護対象目録

[`windows_wsl_protected_artifacts_2026-10-13.json`](windows_wsl_protected_artifacts_2026-10-13.json)は、
WSL側で確認したGit管理外の保護対象を、bundle単位または単独ファイル単位で列挙した日付付きsnapshotです。
`path`はリポジトリ相対パス、`evidence_path`はSHA-256を計算したファイルです。
bundleでは`manifest.json`のみをハッシュしており、bundle内の全ファイルを再検証した記録ではありません。
Mac側でファイル本体が見えなくても、この目録の記載を欠損の証拠と扱わないでください。
目録にある存在状態は`observed_at_utc`時点のWSL側の確認結果であり、現在の所在を保証しません。

新しい保護対象が確定したら、WSL側で実在と参照ファイルのchecksumを読み取り専用で確認し、
元のsnapshotを残して新しい日付付き目録を作成します。`PROJECT_STATE.md`のリンクを最新の
snapshotへ更新し、GitでMac側へ同期します。秘密情報、raw内容、モデルweightは目録に含めません。
