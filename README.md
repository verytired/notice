# notice

A data visualization of "ご報告" (personal announcement) images posted on X — marriages, pregnancies, retirements, apologies and more — sorted by what they announce and the phrases they use.

- Live: https://verytired.net/web/notice/
- `index.html` — the page; reads `data.json`
- `generator/` — make your own announcement image from the common phrases
- `crawler/` — rebuild the data (macOS)
  1. `uv run crawler/crawl.py` — collect posts from X search (log in yourself in the Chrome window on first run)
  2. `python3 crawler/make.py` — OCR the images, classify them and write `data.json`; deleted or private posts are dropped

Images are loaded directly from X and are not stored in this repository (collected images stay in `raw/`, which is git-ignored).
