# Artifact manifests

モデルWeightやActivation等の大容量artifactそのものではなく、次をJSONLまたはCSVで記録します。

- artifact IDと種類
- 対応するrun ID
- リポジトリ外の保存場所またはstorage key
- byte数とSHA-256 checksum
- 作成日時
- model revisionと生成コードのGit commit

秘密情報を含む完全なクラウドURLやcredentialは記録しません。
