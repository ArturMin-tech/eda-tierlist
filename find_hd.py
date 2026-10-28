"""Поиск HD-фото товаров: собирает кандидатов и склеивает их в один лист для сверки глазами.

  python find_hd.py search [id ...] [--out DIR]   # без id — все товары без image_hd
  python find_hd.py pick <id> <номер> [--out DIR] # сохранить кандидата в images_hd/

На листе слева вырезка со скриншота, дальше пронумерованные кандидаты с разрешением.
Сохранять только при 100% совпадении упаковки (дизайн, размер, регион).
"""
import argparse
import hashlib
import html
import io
import json
import re
import tempfile
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).parent
DEFAULT_OUT = Path(tempfile.gettempdir()) / "eda_hd_candidates"
MAX_CANDIDATES = 15
MIN_SIDE = 300
# Магазины, где уже находились точные канадские упаковки, — их кандидаты идут первыми.
PREFERRED = ("walmartimages", "cloudfront.net/product-image", "instacart", "saveonfoods",
             "cdn.shopify.com/s/files/1/0557/6858", "voila", "loblaws", "kraftheinz", "mccain")


def get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": "eda-tierlist/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def bing_images(query):
    url = "https://www.bing.com/images/async?" + urllib.parse.urlencode(
        {"q": query, "first": 0, "count": 35, "mmasync": 1})
    text = get(url).decode("utf-8", "ignore")
    return [html.unescape(u) for u in re.findall(r'murl&quot;:&quot;(.*?)&quot;', text)]


def giant_tiger(query):
    url = "https://www.gianttiger.com/search/suggest.json?" + urllib.parse.urlencode(
        {"q": query, "resources[type]": "product", "resources[limit]": 6})
    data = json.loads(get(url))
    return [p["image"] for p in data["resources"]["results"].get("products", []) if p.get("image")]


def collect_urls(name):
    urls = []
    for fn, q in [(bing_images, name), (bing_images, f"{name} Canada"), (giant_tiger, name)]:
        try:
            urls += fn(q)
        except Exception as e:
            print(f"  ! {fn.__name__}: {e}")
    seen, uniq = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u)
            uniq.append(u)
    uniq.sort(key=lambda u: not any(p in u for p in PREFERRED))
    return uniq


def download(url):
    try:
        data = get(url)
        img = Image.open(io.BytesIO(data))
        img.load()
        if min(img.size) < MIN_SIDE:
            return None
        return url, data, img
    except Exception:
        return None


def label(img, text, size):
    tile = Image.new("RGB", (size, size + 28), "white")
    im = img.convert("RGBA")
    im.thumbnail((size - 8, size - 8))
    tile.paste(im, ((size - im.width) // 2, (size - im.height) // 2), im)
    d = ImageDraw.Draw(tile)
    d.rectangle((0, size, size, size + 28), fill="black")
    d.text((6, size + 7), text, fill="white")
    return tile


def search(pid, products, out):
    p = products[pid]
    print(f"{pid}: {p['name']}")
    d = out / pid
    d.mkdir(parents=True, exist_ok=True)
    urls = collect_urls(p["name"])[:40]
    with ThreadPoolExecutor(8) as ex:
        results = [r for r in ex.map(download, urls) if r]
    cands, hashes = [], set()
    for url, data, img in results:
        h = hashlib.md5(img.convert("L").resize((16, 16)).tobytes()).hexdigest()
        if h in hashes:
            continue
        hashes.add(h)
        cands.append((url, data, img))
        if len(cands) == MAX_CANDIDATES:
            break
    meta = []
    for i, (url, data, img) in enumerate(cands, 1):
        ext = (img.format or "jpg").lower().replace("jpeg", "jpg")
        f = d / f"{i:02}.{ext}"
        f.write_bytes(data)
        meta.append({"n": i, "file": f.name, "url": url, "size": img.size})
    (d / "candidates.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    size, cols = 260, 4
    tiles = [label(Image.open(ROOT / p["image"]), "ORIGINAL (screenshot)", size)]
    tiles += [label(img, f"#{i}  {img.width}x{img.height}", size)
              for i, (_, _, img) in enumerate(cands, 1)]
    rows = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * (size + 6), rows * (size + 34)), (60, 60, 60))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * (size + 6) + 3, (i // cols) * (size + 34) + 3))
    sheet.save(d / "sheet.jpg", quality=85)
    print(f"  {len(cands)} candidates -> {d / 'sheet.jpg'}")


def pick(pid, n, out):
    meta = json.loads((out / pid / "candidates.json").read_text(encoding="utf-8"))
    c = next(m for m in meta if m["n"] == n)
    img = Image.open(out / pid / c["file"])
    for old in (ROOT / "images_hd").glob(f"{pid}.*"):
        old.unlink()
    if c["file"].endswith((".jpg", ".png")):
        dst = ROOT / "images_hd" / f"{pid}{Path(c['file']).suffix}"
        dst.write_bytes((out / pid / c["file"]).read_bytes())
    else:  # webp/gif и прочее — в png
        dst = ROOT / "images_hd" / f"{pid}.png"
        img.save(dst)
    print(f"{pid}: saved {dst.name} {img.size} from {c['url']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["search", "pick"])
    ap.add_argument("args", nargs="*")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    products = {p["id"]: p for p in json.loads((ROOT / "products.json").read_text(encoding="utf-8"))}
    if a.cmd == "search":
        ids = a.args or [pid for pid, p in products.items() if not p.get("image_hd")]
        for pid in ids:
            search(pid, products, a.out)
    else:
        pick(a.args[0], int(a.args[1]), a.out)


if __name__ == "__main__":
    main()
