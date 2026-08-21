# Dataset splits

splitはrun単位ではなくgroup単位で固定します。同じtask・attack template、意味的対応pair、近いparaphrase、確率的反復が異なるsplitへ漏れないgroup IDを作り、割当表をここへ保存します。

本実験のtest splitを確認した後は既存割当を変更せず、新しいsplit versionを追加します。
