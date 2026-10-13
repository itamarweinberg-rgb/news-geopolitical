"""Pick a freely licensed Wikimedia Commons photo for each story that has an `img` query.

Results go to images.json keyed by "<date>|<topic>", with an 800px copy saved under img/.
Existing entries are kept, so each story is resolved once.
"""
import html, json, os, re, urllib.parse, urllib.request

API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "news-geopolitical-briefing/1.0 (github.com/itamarweinberg-rgb/news-geopolitical)"}
BAD_TITLE = re.compile(r"damaged|collision|restaurant|map|flag|logo|coat of arms|emblem|diagram|chart|locator|svg|seal of", re.I)
OK_LICENSE = re.compile(r"^(cc0|cc by(-sa)? [\d.]+|public domain|pd)", re.I)


def get(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        return r.read()


def strip(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


def candidates(query):
    params = {
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
        "gsrsearch": f"filetype:bitmap {query}", "gsrlimit": 20,
        "prop": "imageinfo", "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 800,
    }
    data = json.loads(get(API + "?" + urllib.parse.urlencode(params)))
    pages = sorted(data.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 99))
    for p in pages:
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = strip(meta.get("LicenseShortName", {}).get("value"))
        if ii.get("mime") != "image/jpeg" or BAD_TITLE.search(p["title"]):
            continue
        if ii.get("width", 0) < 1000 or not 0.45 <= ii["height"] / ii["width"] <= 1.0:
            continue
        if not OK_LICENSE.match(lic) or re.search(r"\bNC\b|\bND\b", lic):
            continue
        yield {
            "thumb": ii["thumburl"], "page": ii["descriptionurl"], "license": lic,
            "credit": strip(meta.get("Artist", {}).get("value"))[:80] or "Wikimedia Commons",
            "title": p["title"].removeprefix("File:"),
        }


def main():
    briefings = json.load(open("briefings.json", encoding="utf-8"))["briefings"]
    images = json.load(open("images.json", encoding="utf-8")) if os.path.exists("images.json") else {}
    os.makedirs("img", exist_ok=True)
    for b in briefings:
        for s in b["stories"]:
            key = f"{b['date']}|{s['topic']}"
            if not s.get("img") or key in images:
                continue
            # `img` may hold several queries separated by ";", tried in order.
            pick = next((c for q in s["img"].split(";") for c in candidates(q.strip())), None)
            print(key, "->", pick and pick["title"])
            if not pick:
                continue
            path = f"img/{b['date']}-{s['topic']}.jpg"
            with open(path, "wb") as f:
                f.write(get(pick.pop("thumb")))
            images[key] = {"src": path, **pick}
    with open("images.json", "w", encoding="utf-8") as f:
        json.dump(images, f, ensure_ascii=False, indent=1)


main()
