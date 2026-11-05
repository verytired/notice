# notice

X に投稿された「ご報告」の画像を集めて、内容と言い回しで並べ替えるページ。

- 見る：https://verytired.github.io/notice/
- `index.html` … ページ本体。`data.json` を読む
- `generator/` … ここに出てくる言い回しでご報告の画像を作る
- `crawler/` … データの作り直し（手元の macOS で）
  1. `uv run crawler/crawl.py` … X の検索から拾う（初回は開いた Chrome で自分でログイン）
  2. `python3 crawler/make.py` … 画像の文字を読み、分類して `data.json` を書く。消された投稿は外す

画像は X の URL をそのまま読み込んでいて、このリポジトリには置かない（集めた画像は `raw/` に置き、git に入れない）。
