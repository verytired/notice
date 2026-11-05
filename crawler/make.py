#!/usr/bin/env python3
"""raw/（posts.json と画像）から、ページが読む data.json を作る。crawl.py のあとに。

  python3 crawler/make.py

1. まだ読んでいない画像の文字を ocr.swift（macOS の Vision）で読み、raw/ocr.json に足す
2. 本文と画像の文字のキーワードでジャンルを当てる（上から順に、最初に当たったもの）
3. 文面の画像（4行以上で、ご報告らしい言葉を含む）がある投稿だけを data.json に書く。
   画像は X の URL をそのまま使う（本人が消せばページからも消える）
4. X の oEmbed が 404 / 403 を返す投稿（消された・鍵がかかった）は書かない。--no-check で飛ばせる
"""
import collections, datetime, json, re, subprocess, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW, OUT = HERE.parent / "raw", HERE.parent / "data.json"

# 細かい分類（訃報 > 出産 > … の順に当てる）。「ご迷惑をおかけ」「申し訳」は退所や休止の文面にも入るので謝罪には使わない
RULES = [
    ("訃報", r"逝去|永眠|訃報|他界|息を引き取|天国へ|死去"),
    ("出産", r"出産|誕生しま|生まれ|産まれ|第[一二三1-3]子|新しい家族を迎え"),
    ("妊娠", r"妊娠|新しい命|授か|安定期"),
    ("離婚", r"離婚|夫婦関係を解消|お別れしました|破局"),
    ("結婚", r"結婚|結縮|人着|入籍|婚姻|交際を|お付き合い|婚約"),   # 結縮・人着は文字認識の読み違い
    ("病気", r"療養|入院|手術|診断|病気|治療に|体調不良|疾患|難病|骨折|適応障害|感染|陽性|怪我"),
    ("区切り", r"引退|芸能界を離れ|芸能活動を終|脱退|卒業|解散|活動終了|グループを離れ|休止|休養|お休み|活動を一時|無期限停止|退所|独立|契約(が|を)?終了|契約解除|移籍|事務所を離れ|退職|辞め"),
    ("謝罪", r"お詫び|謝罪|深く反省|不適切|不祥事|騒動"),
]
GENRES = {"結婚": "結婚", "妊娠": "妊娠・出産", "出産": "妊娠・出産", "病気": "病気・けが", "区切り": "脱退・退所・引退",
          "謝罪": "謝罪", "訃報": "訃報", "離婚": "離婚・破局"}
NAMES = ["結婚", "妊娠・出産", "病気・けが", "脱退・退所・引退", "謝罪", "訃報", "離婚・破局", "その他"]
# 解散・退所などは件数が少ないので「脱退・退所・引退」にまとめ、中の言葉ごとの件数を別に数える
WORDS = ["解散", "退所", "脱退", "卒業", "独立", "移籍", "引退", "休止", "退職"]
PHRASES = ["感謝", "この度", "ご報告させて", "今後とも", "私事で", "いつも応援して", "関係者の皆様", "心より", "恐縮", "精進",
           "温かく見守", "入籍", "何卒", "お詫び申し上げ", "ご心配", "一般の方", "新しい命", "突然のご報告"]
LETTER = r"報告|皆様|皆さま|皆さん|応援|私事|お知らせ|ご迷惑|この度"


def img_file(u):
    m = re.search(r"media/([\w-]+)(?:\?format=|\.)(\w+)", u)
    return m.group(1), m.group(2)


def gone(u):
    """消された・非公開の投稿なら True。通信の失敗では消さない"""
    try:
        urllib.request.urlopen("https://publish.twitter.com/oembed?omit_script=1&url=" + urllib.parse.quote(u), timeout=15)
    except urllib.error.HTTPError as e:
        return e.code in (403, 404)
    except OSError:
        pass
    return False


def genre(t):
    k = next((n for n, r in RULES if re.search(r, t)), None)
    return NAMES.index(GENRES.get(k, "その他"))


def main():
    posts = json.loads((RAW / "posts.json").read_text())
    ocr_path = RAW / "ocr.json"
    ocr = json.loads(ocr_path.read_text()) if ocr_path.exists() else {}
    todo = [str(f) for f in sorted((RAW / "img").iterdir()) if "area" not in ocr.get(f.name, {})]   # area がない古い結果も読み直す
    for i in range(0, len(todo), 100):   # 100枚ずつ読んで足す
        ocr.update(json.loads(subprocess.run(["swift", HERE / "ocr.swift", *todo[i:i + 100]], capture_output=True, check=True).stdout))
        ocr_path.write_text(json.dumps(ocr, ensure_ascii=False))
    print(f"文字を読んだ画像 {len(todo)}枚（全部で {len(ocr)}枚）")

    items = []
    for p in posts.values():
        files = [(i, *img_file(u)) for i, u in enumerate(p["imgs"])]
        texts = [ocr.get(f"{mid}.{ext}", {}) for _, mid, ext in files]
        best = max(range(len(files)), key=lambda j: texts[j].get("lines", 0))
        o = texts[best]
        if o.get("lines", 0) < 4 or not re.search(LETTER, o.get("text", "")):
            continue   # 商品写真・ネタ画像などは外す
        whole = p["text"] + "\n" + "\n".join(t.get("text", "") for t in texts)
        name, handle = (p["user"].split(" | ") + ["", ""])[:2]
        items.append(dict(
            u=p["url"], d=p["date"][:10], n=name, h=handle.lstrip("@"), t=p["text"].strip(),
            img=[f"https://pbs.twimg.com/media/{mid}?format={ext}" for _, mid, ext in files], b=best,
            w=o.get("w"), hh=o.get("h"), g=genre(whole),
            p=[j for j, s in enumerate(PHRASES) if s in whole],
            k=[j for j, s in enumerate(WORDS) if s in whole],
        ))
    if "--no-check" not in sys.argv:
        dead = []
        for it in items:
            if gone(it["u"]):
                dead.append(it["u"])
            time.sleep(0.3)
        items = [it for it in items if it["u"] not in dead]
        print(f"消された・非公開の投稿 {len(dead)}件を外した", *dead, sep="\n  ")
    items.sort(key=lambda it: it["d"])
    pc = collections.Counter(j for it in items for j in it["p"])
    kc = collections.Counter(j for it in items for j in it["k"])
    json.dump(dict(
        updated=datetime.date.today().isoformat(), total=len(posts), names=NAMES,
        phrases=PHRASES, phrase_counts=[pc[j] for j in range(len(PHRASES))],
        words=WORDS, word_counts=[kc[j] for j in range(len(WORDS))], items=items,
    ), open(OUT, "w"), ensure_ascii=False, separators=(",", ":"))

    gc = collections.Counter(NAMES[it["g"]] for it in items)
    assert sum(gc.values()) == len(items) and all(0 <= it["g"] < len(NAMES) for it in items)
    print(f"集めた投稿 {len(posts)}件 → 文面の画像 {len(items)}件", gc.most_common())


if __name__ == "__main__":
    main()
