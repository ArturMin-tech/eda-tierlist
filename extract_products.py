"""Вырезает фото товаров со скриншотов заказа Instacart и собирает products.json."""
import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).parent
SHOTS = ROOT / "screenshots"
OUT = ROOT / "images"

# Координаты размечены по превью шириной 923px; реальные скриншоты 1080px.
REF_WIDTH = 923

# (скриншот, y первой строки названия, slug, название, цена, старая цена)
ITEMS = [
    ("order_02.jpg", 429, "nerds-gummy-clusters", "NERDS Candy Gummy Clusters", 3.83, None),
    ("order_02.jpg", 696, "hi-chew-strawberry", "Hi-Chew Strawberry Chewy Candy", 2.28, None),
    ("order_02.jpg", 1013, "pocky-green-tea", "Glico Pocky Green Tea", 1.79, None),
    ("order_02.jpg", 1280, "ramune-strawberry", "Hata Kosen Ramune Strawberry Soda", 3.12, None),
    ("order_01.jpg", 701, "haesong-seaweed", "Haesong Original Flavor Seaweed Snack", 3.12, None),
    ("order_01.jpg", 1017, "kibon-seaweed", "Kibon Roasted Seaweed Snack", 1.86, None),
    ("order_01.jpg", 1285, "nongshim-shrimp-chips", "Nongshim Shrimp Flavored Chips", 1.49, None),
    ("order_01.jpg", 1553, "cheery-chews-unicorn", "Cheery Chews Gummy Rush Unicorn Gummy", 1.05, None),
    ("order_03.jpg", 504, "our-finest-pad-thai", "Our Finest Chicken Pad Thai With Rice Noodles", 4.65, None),
    ("order_03.jpg", 820, "great-value-sp-ramen", "Great Value Sp Ramen Noodles", 4.17, None),
    ("order_03.jpg", 1088, "ristorante-three-cheese", "Dr. Oetker Ristorante Piccolissima Three Cheese Mini Pizzas", 4.18, 5.98),
    ("order_03.jpg", 1452, "chapmans-checkerboard", "Chapman's Original Chocolate & Vanilla Checkerboard Ice Cream", 4.47, 4.97),
    ("order_04.jpg", 446, "el-monterey-red-hot-beef", "El Monterey Red Hot Beef Burrito", 1.75, None),
    ("order_04.jpg", 714, "el-monterey-beef-bean", "El Monterey Beef & Bean Burrito", 1.75, None),
    ("order_04.jpg", 982, "el-monterey-egg-sausage", "El Monterey Egg Potato Cheese & Sausage Wraps", 3.18, None),
    ("order_04.jpg", 1297, "crave-carne-asada", "CRAVE Steak Carne Asada Burrito Bowl", 4.17, 4.97),
    ("order_04.jpg", 1613, "crave-chili-sesame", "CRAVE Chili Sesame Noodles with Pork Noodle Bowl", 4.17, 4.97),
    ("order_05.jpg", 444, "ristorante-pepperoni", "Dr. Oetker Ristorante Piccolissima Pepperoni Mini Pizzas", 4.18, 5.98),
    ("order_05.jpg", 857, "ristorante-spinaci", "Dr. Oetker Pizza Spinaci", 4.18, None),
    ("order_05.jpg", 1124, "green-giant-cheddar-pasta", "Green Giant Valley Selections Cheddar Pasta", 3.43, 3.97),
    ("order_05.jpg", 1440, "tinas-beef-bean", "Tina's Burritos Beef & Bean Burritos", 1.56, None),
    ("order_05.jpg", 1708, "tinas-bean-cheese", "Tina's Burritos Bean & Cheese Burrito", 1.56, None),
    ("order_06.jpg", 440, "swanson-sweet-sour-chicken", "Swanson's Sweet & Sour Chicken", 4.97, None),
    ("order_06.jpg", 708, "crave-pulled-chicken", "Crave Pulled Chicken Burrito Bowl Frozen Meal", 4.17, 4.97),
    ("order_06.jpg", 1024, "crave-chicken-poblano", "CRAVE Chicken Poblano Queso Burrito Bowl", 4.17, 4.97),
    ("order_06.jpg", 1340, "mccain-pockets-pepperoni", "McCain Pizza Pockets, Pepperoni", 2.98, 5.27),
    ("order_06.jpg", 1655, "mccain-pockets-three-cheese", "McCain Pizza Pockets, Three Cheese", 3.19, 5.27),
    ("order_07.jpg", 613, "crave-buffalo-mac", "Crave Buffalo Chicken Mac & Cheese", 4.17, 4.97),
    ("order_07.jpg", 929, "our-finest-butter-chicken", "Our Finest Buttered Chicken", 4.65, None),
    ("order_07.jpg", 1197, "crave-pesto-ravioli", "Crave Pesto Ravioli with Spicy Italian Sausage", 4.17, 4.97),
    ("order_07.jpg", 1512, "crave-korean-bbq-bolognese", "CRAVE Korean BBQ Inspired Beef Bolognese Frozen Meal", 4.25, 4.97),
]


def thumbnail_box(img, title_y):
    """Ищет картинку товара слева от названия: bbox непустых пикселей в окне."""
    k = img.width / REF_WIDTH
    x0, x1 = int(62 * k), int(200 * k)
    y0, y1 = int((title_y - 45) * k), int((title_y + 110) * k)
    win = img.crop((x0, y0, x1, y1)).convert("RGB")
    w, h = win.size
    px = win.load()
    mask = [[max(255 - c for c in px[x, y]) > 25 for x in range(w)] for y in range(h)]
    # Горизонтальные линии рамки карточки тянутся через всё окно — их отбрасываем.
    rows = [y for y in range(h) if 0 < sum(mask[y]) < 0.9 * w]
    cols = [x for x in range(w) if any(mask[y][x] for y in rows)]
    if not rows or not cols:
        raise ValueError(f"thumbnail not found at y={title_y}")
    pad = 4
    return (max(x0 + cols[0] - pad, 0), max(y0 + rows[0] - pad, 0),
            x0 + cols[-1] + pad + 1, y0 + rows[-1] + pad + 1)


def main():
    OUT.mkdir(exist_ok=True)
    products = []
    for shot, title_y, slug, name, price, old_price in ITEMS:
        img = Image.open(SHOTS / shot)
        box = thumbnail_box(img, title_y)
        img.crop(box).save(OUT / f"{slug}.png")
        # HD-версия, найденная в интернете вручную (точное совпадение упаковки).
        hd = next((ROOT / "images_hd").glob(f"{slug}.*"), None)
        products.append({
            "id": slug,
            "name": name,
            "price": price,
            "old_price": old_price,
            "image": f"images/{slug}.png",
            "image_hd": f"images_hd/{hd.name}" if hd else None,
            "source": shot,
            "store": "Instacart",
        })
        print(f"{slug:32} {box}")
    (ROOT / "products.json").write_text(
        json.dumps(products, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(products)} products -> products.json")


if __name__ == "__main__":
    main()
