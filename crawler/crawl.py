# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright"]
# ///
"""X の検索から「ご報告」の画像つき投稿を拾い、raw/posts.json に足していく（重複は URL で除く）。

  uv run crawler/crawl.py                 # 2016年から今年まで、3か月ずつ
  uv run crawler/crawl.py --from 2026     # 今年だけ取り直す
  uv run crawler/crawl.py --query "私事ではございますが"
  uv run crawler/crawl.py --import ~/Downloads/notice_posts.json   # ふだんの Chrome で集めたものを足す（窓は開かない）

X は検索にログインが要る。手元の Chrome を専用のプロファイル（raw/profile、git に入れない）で開くので、
初回だけ開いた窓で自分でログインする（ログインを見つけたら自動で始まる）。ヘッドレスだと弾かれるので窓は出したまま。
filter:images を since/until と一緒に書くと結果が0件になるので、画像の有無はページの側で見る。
1回の検索は35〜50件ほどで打ち切られる（「話題」タブの上限）ので、3か月ずつに分けて探す。件数は時期どうしで比べられない。
"""
import argparse, datetime, json, re, time, urllib.parse, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright

RAW = Path(__file__).resolve().parent.parent / "raw"
POSTS = RAW / "posts.json"

# 表示中の投稿から {url: {url, date, user, text, imgs}} を拾う
GRAB = """() => {
  const c = {};
  for (const a of document.querySelectorAll('article[data-testid="tweet"]')) {
    const link = [...a.querySelectorAll('a[href*="/status/"]')].find(x => x.querySelector('time'));
    if (!link) continue;
    const imgs = [...a.querySelectorAll('img[src*="pbs.twimg.com/media"]')].map(i => i.src.replace(/name=\\w+/, 'name=large'));
    if (!imgs.length) continue;
    const url = link.href.split('/photo')[0];
    c[url] = { url, date: link.querySelector('time').getAttribute('datetime'),
      user: (a.querySelector('[data-testid="User-Name"]') || {}).innerText?.replace(/\\n/g, ' | ') || '',
      text: (a.querySelector('[data-testid="tweetText"]') || {}).innerText || '', imgs };
  }
  return c;
}"""


def img_file(u):
    """画像 URL → raw/img/ のファイル名（?format=jpg の形と .jpg の形の両方がある）"""
    m = re.search(r"media/([\w-]+)(?:\?format=|\.)(\w+)", u)
    return f"{m.group(1)}.{m.group(2)}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="y0", type=int, default=2016)
    ap.add_argument("--to", dest="y1", type=int, default=datetime.date.today().year)
    ap.add_argument("--query", default="ご報告")
    ap.add_argument("--min-faves", type=int, default=3000)
    ap.add_argument("--scrolls", type=int, default=12)
    ap.add_argument("--import", dest="imp", help="ふだんの Chrome で集めた JSON を足すだけにする")
    ap.add_argument("--months", type=int, default=3, choices=[1, 2, 3, 4, 6, 12])
    a = ap.parse_args()

    RAW.mkdir(exist_ok=True)
    posts = json.loads(POSTS.read_text()) if POSTS.exists() else {}
    if a.imp:
        got = json.loads(Path(a.imp).expanduser().read_text())
        print(f"{len(got)}件を読み込み（新しく {len(set(got) - set(posts))}件）")
        posts.update(got)
        POSTS.write_text(json.dumps(posts, ensure_ascii=False))
    else:
        browse(a, posts)
    download(posts)


def browse(a, posts):
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(RAW / "profile", channel="chrome", headless=False, viewport={"width": 1200, "height": 1000})
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto("https://x.com/home")
        page.wait_for_timeout(4000)
        logged_in = lambda: any(c["name"] == "auth_token" for c in ctx.cookies("https://x.com"))
        if not logged_in():
            print("開いた Chrome で X にログインしてください（ログインできるまで15分待ちます）", flush=True)
            for _ in range(15 * 60 // 3):
                if logged_in():
                    break
                page.wait_for_timeout(3000)
            else:
                raise SystemExit("ログインできなかったので止めます")
            page.goto("https://x.com/home")
        print("ログインを確認しました。集め始めます", flush=True)
        # 1回の検索は35〜50件で打ち切られるので、--months か月ずつに分けて探す
        starts = [datetime.date(y, m, 1) for y in range(a.y0, a.y1 + 1) for m in range(1, 13, a.months)]
        for s0 in [d for d in starts if d <= datetime.date.today()]:
            m1 = s0.month - 1 + a.months
            s1 = datetime.date(s0.year + m1 // 12, m1 % 12 + 1, 1)
            y = f"{s0:%Y-%m}"
            q = f"{a.query} min_faves:{a.min_faves} since:{s0} until:{s1}"
            page.goto("https://x.com/search?" + urllib.parse.urlencode({"q": q, "f": "top"}))
            page.wait_for_timeout(3500)
            got = {}
            for _ in range(a.scrolls):
                got.update(page.evaluate(GRAB))
                page.mouse.wheel(0, 2500)
                page.wait_for_timeout(1500)
            got.update(page.evaluate(GRAB))
            new = len(set(got) - set(posts))
            posts.update(got)
            POSTS.write_text(json.dumps(posts, ensure_ascii=False))   # 途中で止まっても残す
            print(f"{y}〜: {len(got)}件（新しく {new}件） 合計 {len(posts)}件")
        ctx.close()


def download(posts):
    # 画像を落とす（文字を読むため。ページには載せず、X の画像 URL をそのまま使う）
    (RAW / "img").mkdir(exist_ok=True)
    todo = [(u, RAW / "img" / img_file(u)) for v in posts.values() for u in v["imgs"]]
    todo = [(u, f) for u, f in todo if not f.exists()]
    for u, f in todo:
        try:
            f.write_bytes(urllib.request.urlopen(u, timeout=30).read())
        except Exception as e:
            print("画像を落とせなかった", u, e)
        time.sleep(0.2)
    print(f"画像 {len(todo)}枚を落とした")


if __name__ == "__main__":
    main()
