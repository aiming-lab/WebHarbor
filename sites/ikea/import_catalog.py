"""Build the deterministic IKEA catalog from the source dataset snapshot.

The importer performs no visual selection or image transformation. It trusts
the dataset's first image as the product hero image and copies those bytes
unchanged from images-us.tar or the corresponding IKEA CDN URL.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import tarfile
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Callable
from pathlib import Path


SITE_DIR = Path(__file__).resolve().parent
CATALOG_PATH = SITE_DIR / "catalog_source.json"
TASKS_PATH = SITE_DIR / "tasks.jsonl"
IMAGES_DIR = SITE_DIR / "static" / "images" / "products"

DATASET_ID = "jeffreyszhou/ikea-us-products-2025"
DATASET_URL = f"https://huggingface.co/datasets/{DATASET_ID}"
IKEA_IMAGES_BASE = "https://www.ikea.com/us/en/images/products/"

CATEGORY_SLOTS = {
    "living-room-seating": ("living-room", ["IK-10001", "IK-10002"]),
    "bedroom-storage": ("bedroom", ["IK-10003", "IK-10004"]),
    "kitchen-dining": ("kitchen", ["IK-10005", "IK-10006"]),
    "home-office": ("office", ["IK-10007", "IK-10008"]),
    "lighting": ("lighting", ["IK-10009", "IK-10010"]),
    "bathroom": ("bathroom", ["IK-10011", "IK-10012"]),
    "kids-room": ("kids", ["IK-10013", "IK-10014"]),
    "outdoor-living": ("outdoor", ["IK-10015", "IK-10016"]),
    "entryway": ("entryway", ["IK-10017", "IK-10018"]),
    "textiles-rugs": ("textiles", ["IK-10019", "IK-10020"]),
    "storage-organization": ("storage", ["IK-10021", "IK-10022"]),
    "decor-mirrors": ("decor", ["IK-10023", "IK-10024"]),
}


def tree_value(row: dict, index: int) -> str:
    tree = row.get("category_tree") or []
    return tree[index].casefold() if len(tree) > index else ""


def searchable(row: dict) -> str:
    return " ".join(
        [
            row.get("title", ""),
            row.get("description", ""),
            " ".join(row.get("category_tree") or []),
        ]
    ).casefold()


def category_path(row: dict) -> str:
    return " > ".join(row.get("category_tree") or []).casefold()


def has_category(row: dict, labels: tuple[str, ...]) -> bool:
    path = category_path(row)
    return any(label in path for label in labels)


def excludes_title(row: dict, labels: tuple[str, ...]) -> bool:
    title = row.get("title", "").casefold()
    return not any(label in title for label in labels)


def product_series(row: dict) -> str:
    return clean_title(row["title"]).split(maxsplit=1)[0]


CATEGORY_RULES: dict[str, Callable[[dict], bool]] = {
    "living-room-seating": lambda row: has_category(
        row,
        (
            "modular sofas",
            "three-seat sofas",
            "loveseats",
            "sleeper sofa",
            "armchairs",
            "chaise lounges",
            "ottomans",
            "coffee tables",
            "end tables & side tables",
            "nesting tables",
        ),
    )
    and excludes_title(row, ("cover", "cushion", "headrest", "armrest", "leg for", "mattress")),
    "bedroom-storage": lambda row: has_category(
        row,
        (
            "bed frames with storage",
            "bed frames",
            "upholstered beds",
            "daybeds",
            "dressers",
            "wardrobes",
            "nightstands",
            "bedroom furniture sets",
            "underbed storage",
        ),
    )
    and excludes_title(row, ("cover", "slatted bed base", "leg", "glass top", "headboard")),
    "kitchen-dining": lambda row: has_category(
        row,
        (
            "dining tables",
            "extendable tables",
            "dining chairs",
            "dining benches",
            "bar stools",
            "bar tables",
            "kitchen islands",
            "kitchen carts",
            "sideboards",
        ),
    )
    and excludes_title(row, ("cover", "chair pad", "outdoor")),
    "home-office": lambda row: has_category(
        row,
        (
            "desks for home",
            "desks for office",
            "standing desks",
            "office chairs",
            "desk chairs for home",
            "drawer units for home",
            "filing cabinets",
            "office storage cabinets",
            "bookshelves & bookcases",
            "laptop stands",
        ),
    )
    and excludes_title(row, ("tabletop", "underframe", "pair of armrests", "cover", "door")),
    "lighting": lambda row: tree_value(row, 1) == "lighting"
    and excludes_title(row, ("lamp shade", "light bulb", "cord set", "lamp base", "driver")),
    "bathroom": lambda row: has_category(
        row,
        (
            "bathroom vanities",
            "bathroom carts",
            "bathroom shelves",
            "bathroom shelving units",
            "bathroom wall cabinets",
            "bathroom mirrors",
            "medicine cabinets with mirror",
            "bathroom stools & benches",
            "shower accessories",
            "laundry baskets",
            "towel stand",
        ),
    )
    and excludes_title(row, ("door", "hook", "rail", "faucet", "handle")),
    "kids-room": lambda row: has_category(
        row,
        (
            "kids furniture",
            "kids storage",
            "kids beds",
            "kids study furniture",
            "junior dining chairs",
            "kids table",
            "kids night lights",
            "nursery furniture",
            "cribs",
        ),
    )
    and excludes_title(
        row,
        (
            "cover",
            "sheet",
            "mattress",
            "tray",
            "suspension rail",
            "label holder",
            "tumbler",
            "cushion",
            "table top",
            "bed pocket",
            "box with lid",
        ),
    ),
    "outdoor-living": lambda row: has_category(
        row,
        (
            "outdoor patio furniture",
            "outdoor dining furniture",
            "outdoor seating",
            "outdoor storage",
            "outdoor tables",
            "outdoor lighting",
            "outdoor planters",
            "outdoor rugs",
        ),
    )
    and excludes_title(row, ("cover", "cushion", "chair pad", "inner back")),
    "entryway": lambda row: any(
        label in category_path(row)
        for label in (
            "shoe cabinets",
            "shoe racks",
            "clothes racks & stands",
            "hallway benches",
            "coat racks",
            "entryway tables",
        )
    ),
    "textiles-rugs": lambda row: has_category(
        row,
        ("rugs", "curtains & drapes", "blankets & throws", "bedspreads", "throw pillow covers", "door mats"),
    )
    and excludes_title(row, ("curtain rod", "tieback", "rail", "anti-slip pad")),
    "storage-organization": lambda row: tree_value(row, 1)
    in {"storage & organization", "storage containers, organizers & baskets"}
    and not any(
        label in category_path(row)
        for label in ("dressers", "wardrobe", "shoe cabinets", "shoe racks", "hallway benches")
    )
    and excludes_title(
        row,
        ("hinge", "frame", "rail", "knob", "handle", "leg", "post", "hanger", "door", "drawer front"),
    ),
    "decor-mirrors": lambda row: tree_value(row, 1)
    in {"home decor & accessories", "plants & planters"},
}


ROLE_SPECS: dict[str, tuple[str, str, Callable[[dict], bool]]] = {
    "IK-10001": (
        "wishlist_sofa",
        "living-room-seating",
        lambda row: "modular sofas" in category_path(row)
        and "sofa" in row["title"].casefold()
        and not any(
            word in row["title"].casefold()
            for word in ("cover", "section", "module", "armrest", "headrest", "frame")
        ),
    ),
    "IK-10002": (
        "deal_coffee_table",
        "living-room-seating",
        lambda row: "coffee table" in row["title"].casefold(),
    ),
    "IK-10005": (
        "compare_dining_table",
        "kitchen-dining",
        lambda row: "extendable tables" in category_path(row)
        and "extendable table" in row["title"].casefold(),
    ),
    "IK-10006": (
        "compare_dining_chair",
        "kitchen-dining",
        lambda row: "dining chairs" in category_path(row)
        and "chair" in row["title"].casefold()
        and not any(
            word in row["title"].casefold()
            for word in ("junior", "outdoor", "cover", "pad", "cushion")
        ),
    ),
    "IK-10007": (
        "cart_sit_stand_desk",
        "home-office",
        lambda row: "desk sit/stand" in row["title"].casefold(),
    ),
    "IK-10010": (
        "compare_pendant_lamp",
        "lighting",
        lambda row: "pendant lighting" in category_path(row)
        and "pendant lamp" in row["title"].casefold()
        and "shade" not in row["title"].casefold(),
    ),
    "IK-10020": (
        "dimensions_blackout_curtain",
        "textiles-rugs",
        lambda row: "curtain" in row["title"].casefold()
        and any(term in searchable(row) for term in ("black-out", "blackout", "block-out"))
        and bool(re.search(r"\d", row["title"])),
    ),
    "IK-10023": (
        "protection_floor_mirror",
        "decor-mirrors",
        lambda row: "floor mirror" in row["title"].casefold()
        and "cabinet" not in row["title"].casefold(),
    ),
}


TASK_TEMPLATES = {
    "IKEA--0": lambda roles: (
        f"Search for the {roles['wishlist_sofa']} and save it to the wishlist from its product page."
    ),
    "IKEA--1": lambda roles: (
        "Browse the living room seating category and find the "
        f"{roles['deal_coffee_table']}. Report its current price and whether it is marked as a local deal."
    ),
    "IKEA--2": lambda roles: (
        f"Use the search page to find the {roles['compare_dining_table']}, then compare it with the "
        f"{roles['compare_dining_chair']} using the compare flow."
    ),
    "IKEA--3": lambda roles: (
        "Filter products to the home office room and find the "
        f"{roles['cart_sit_stand_desk']}. Add one desk to the cart."
    ),
    "IKEA--4": lambda roles: (
        f"Open the product page for the {roles['protection_floor_mirror']} and identify which protection plan lasts longer."
    ),
    "IKEA--11": lambda roles: (
        "Search for black-out curtains and find the "
        f"{roles['dimensions_blackout_curtain']}. Report its dimensions from the product detail page."
    ),
    "IKEA--15": lambda roles: (
        f"Add the {roles['compare_pendant_lamp']} to the compare list, then open compare and report one spec row that is displayed there."
    ),
}


def valid_source_row(row: dict) -> bool:
    try:
        return bool(
            row["product_id"]
            and row["title"]
            and row["description"]
            and row["category_tree"]
            and row["image_urls"][0]
            and float(row["price"])
        )
    except (KeyError, IndexError, TypeError, ValueError):
        return False


def clean_title(title: str) -> str:
    suffix = " - IKEA US"
    return title[: -len(suffix)] if title.endswith(suffix) else title


def title_fields(title: str) -> tuple[str, str]:
    clean = clean_title(title)
    parts = [part.strip() for part in clean.split(",")]
    details = parts[1:]
    dimensions = details[-1] if details and re.search(r"\d", details[-1]) else ""
    color_parts = details[:-1] if dimensions else details
    return " / ".join(color_parts), dimensions


def source_record(row: dict, sku: str, category_slug: str, room_slug: str, role: str = "") -> dict:
    name = clean_title(row["title"])
    color, dimensions = title_fields(row["title"])
    image_path = row["image_urls"][0]
    image_name = Path(image_path).name
    return {
        "local_sku": sku,
        "task_role": role,
        "category_slug": category_slug,
        "room_slug": room_slug,
        "source_product_id": row["product_id"],
        "source_url": row["source_url"],
        "source_category_tree": row["category_tree"],
        "source_image_path": image_path,
        "source_image_url": IKEA_IMAGES_BASE + urllib.parse.quote(image_name),
        "image_path": f"images/products/{image_name}",
        "name": name,
        "series": name.split(maxsplit=1)[0],
        "description": row["description"],
        "price": float(row["price"]),
        "materials": row.get("materials") or [],
        "care_instructions": row.get("care_instructions") or [],
        "good_to_know": row.get("good_to_know") or [],
        "color": color,
        "dimensions": dimensions,
    }


def load_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle]
    if not rows or any(not isinstance(row, dict) for row in rows):
        raise ValueError("Source metadata must be non-empty JSONL objects")
    return rows


def select_catalog(rows: list[dict]) -> list[dict]:
    candidates = sorted((row for row in rows if valid_source_row(row)), key=lambda row: row["product_id"])
    selected: dict[str, dict] = {}
    used_source_ids: set[str] = set()
    used_names: set[str] = set()
    used_series_by_category: dict[str, set[str]] = {category: set() for category in CATEGORY_SLOTS}

    for sku, (role, category_slug, predicate) in ROLE_SPECS.items():
        match = next(
            (
                row
                for row in candidates
                if row["product_id"] not in used_source_ids
                and clean_title(row["title"]) not in used_names
                and CATEGORY_RULES[category_slug](row)
                and predicate(row)
            ),
            None,
        )
        if match is None:
            raise ValueError(f"No source row satisfies task role {role}")
        room_slug = CATEGORY_SLOTS[category_slug][0]
        selected[sku] = source_record(match, sku, category_slug, room_slug, role)
        used_source_ids.add(match["product_id"])
        used_names.add(clean_title(match["title"]))
        used_series_by_category[category_slug].add(product_series(match))

    filler_number = 11001
    for category_slug, (room_slug, special_skus) in CATEGORY_SLOTS.items():
        skus = list(special_skus)
        skus.extend(f"IK-{number:05d}" for number in range(filler_number, filler_number + 11))
        filler_number += 11
        for sku in skus:
            if sku in selected:
                continue
            match = next(
                (
                    row
                    for row in candidates
                    if row["product_id"] not in used_source_ids
                    and clean_title(row["title"]) not in used_names
                    and product_series(row) not in used_series_by_category[category_slug]
                    and CATEGORY_RULES[category_slug](row)
                ),
                None,
            )
            if match is None:
                raise ValueError(f"Not enough source rows for {category_slug}")
            selected[sku] = source_record(match, sku, category_slug, room_slug)
            used_source_ids.add(match["product_id"])
            used_names.add(clean_title(match["title"]))
            used_series_by_category[category_slug].add(product_series(match))

    products = sorted(selected.values(), key=lambda item: item["local_sku"])
    if len(products) != 156:
        raise ValueError(f"Expected 156 products, selected {len(products)}")
    image_paths = [product["source_image_path"] for product in products]
    if len(image_paths) != len(set(image_paths)):
        raise ValueError("Selected products must not share a hero image")
    return products


def extract_images(images_tar: Path, products: list[dict], destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    wanted = {product["source_image_path"].lstrip("./"): product for product in products}
    extracted: set[str] = set()
    with tarfile.open(images_tar, "r:") as archive:
        members = {member.name.lstrip("./"): member for member in archive if member.isfile()}
        missing = sorted(set(wanted) - set(members))
        if missing:
            raise ValueError(f"Image archive is missing {len(missing)} selected files; first: {missing[0]}")
        for source_path, product in wanted.items():
            source = archive.extractfile(members[source_path])
            if source is None:
                raise ValueError(f"Could not read {source_path}")
            output = destination / Path(product["image_path"]).name
            with output.open("wb") as handle:
                shutil.copyfileobj(source, handle)
            extracted.add(source_path)
    if extracted != set(wanted):
        raise ValueError("Not all selected images were extracted")


def download_images(products: list[dict], destination: Path, workers: int = 8) -> None:
    destination.mkdir(parents=True, exist_ok=True)

    def download(product: dict) -> None:
        output = destination / Path(product["image_path"]).name
        temporary = output.with_suffix(output.suffix + ".part")
        request = urllib.request.Request(
            product["source_image_url"],
            headers={"User-Agent": "Mozilla/5.0 WebHarbor IKEA catalog importer"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            content_type = response.headers.get_content_type()
            if not content_type.startswith("image/"):
                raise ValueError(f"Unexpected content type {content_type} for {product['source_image_url']}")
            with temporary.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        temporary.replace(output)

    with ThreadPoolExecutor(max_workers=workers) as executor:
        list(executor.map(download, products))


def write_catalog(products: list[dict], path: Path) -> None:
    payload = {
        "dataset": DATASET_ID,
        "dataset_url": DATASET_URL,
        "selection_version": 1,
        "selection_policy": "metadata-only; first dataset hero image; source image bytes unchanged",
        "products": products,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_tasks(products: list[dict], path: Path) -> None:
    role_names = {product["task_role"]: product["name"] for product in products if product["task_role"]}
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    for row in rows:
        template = TASK_TEMPLATES.get(row["id"])
        if template:
            row["ques"] = template(role_names)
        row["web"] = "http://localhost:40016/"
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata", type=Path, required=True, help="Path to products-us.jsonl")
    parser.add_argument("--images-tar", type=Path, help="Path to images-us.tar")
    parser.add_argument(
        "--download-images",
        action="store_true",
        help="Download only selected hero images from their metadata-derived IKEA CDN URLs",
    )
    parser.add_argument("--catalog-output", type=Path, default=CATALOG_PATH)
    parser.add_argument("--images-output", type=Path, default=IMAGES_DIR)
    parser.add_argument("--tasks", type=Path, default=TASKS_PATH)
    parser.add_argument("--metadata-only", action="store_true", help="Write catalog/tasks without extracting images")
    args = parser.parse_args()

    products = select_catalog(load_rows(args.metadata))
    write_catalog(products, args.catalog_output)
    update_tasks(products, args.tasks)
    if not args.metadata_only:
        if args.images_tar is not None and args.download_images:
            parser.error("choose either --images-tar or --download-images")
        if args.images_tar is not None:
            extract_images(args.images_tar, products, args.images_output)
        elif args.download_images:
            download_images(products, args.images_output)
        else:
            parser.error("--images-tar or --download-images is required unless --metadata-only is used")
    print(f"Selected {len(products)} products from {DATASET_ID}")


if __name__ == "__main__":
    main()
