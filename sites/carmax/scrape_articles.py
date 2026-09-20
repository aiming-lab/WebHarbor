#!/usr/bin/env python3
"""Download CarMax article hero images.

Each seeded article references /static/images/articles/<slug>.jpg. This
script fetches the real CarMax content-images.carmax.com hero image for
each article and saves it locally.

Run from the repo root:
    pip install httpx
    python sites/carmax/scrape_articles.py
"""
import os
import pathlib
import sys

# Force UTF-8 stdout so any unicode print does not crash on Windows GBK console.
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

try:
    import httpx
except ImportError:
    sys.exit("missing httpx. install with: pip install httpx")

ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "static" / "images" / "articles"
OUT.mkdir(parents=True, exist_ok=True)

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
      'AppleWebKit/537.36 (KHTML, like Gecko) '
      'Chrome/124.0.0.0 Safari/537.36')

# slug (matches seed_data.py) -> hero image URL on carmax content CDN
ARTICLE_HEROES = {
    'how-carmax-works':
        'https://content-images.carmax.com/qeontfmijmzv/3pDBIajbVpFy688qLx6XdN/'
        '357c3453f4691ba733764186573ae7b0/01-240117_CarMax_Store_052_2x.jpg',
    'how-to-sell-your-car-to-carmax':
        'https://content-images.carmax.com/qeontfmijmzv/7DIdfvK5g5050BjRMti3bj/'
        '71bbced50424d75704b715267d971ad4/'
        '02-How_to_Sell_Your_Car_GettyImages-1291494870_HiRes_2.jpg',
    'pre-approval-vs-pre-qualified':
        'https://content-images.carmax.com/qeontfmijmzv/44LpZ9Yk7L3HFoR8sjM0Df/'
        '0dbf783f7232012f6781173f87bfa743/'
        'NEW_Hero_Fullwidth_1440x780_GETTYimages.jpg',
    'best-compact-sedan-honda-civic-vs-toyota-corolla-vs-nissan-sentra':
        'https://content-images.carmax.com/qeontfmijmzv/7pHQrxB3gpMjo5bdDP01aC/'
        '802b0a22a85e782ee45fe10a510d628a/'
        'Best_Compact_Sedan_Civic-Corolla-Sentra_Hero_Fullwidth_1440x625.jpg',
    'best-hatchback-cars-ranking':
        'https://content-images.carmax.com/qeontfmijmzv/60SzfaTFIamvIj9EmTKeO9/'
        '149aaf80562785d7bf8763c7275b56a4/'
        '474204_BestHatchbackCars_Hero_Fullwidth_1440x500_2.png',
    'how-to-buy-a-used-car':
        'https://content-images.carmax.com/qeontfmijmzv/4lXC25xUvsSh54qogDVRWq/'
        '16c2c97f6ffd238f3de05032a14a7f9f/'
        '11-24-25-How_to_Buy_a_Used_Car-GettyImages-2152358874_HiRes.jpg',
    'maxcare-explained':
        'https://content-images.carmax.com/qeontfmijmzv/X7vHNvN8eaeOUTblYEq4b/'
        '5fec55afd57715736eb2a7516787e628/'
        'maxcare-explained_Hero_Fullwidth_1440x625.jpg',
    'first-time-car-buyer':
        'https://content-images.carmax.com/qeontfmijmzv/31NdNXfNgoLwSy9uEd6cYP/'
        '94b8c26ca9c4b19ac3f3ccf7ba53d6af/'
        '601201_Edmunds_5-Steps-to-Financing-Your-First-Car_Hero_Fullwidth_1440x625.jpg',
    'best-high-mpg-cars':
        'https://content-images.carmax.com/qeontfmijmzv/2H3DQYX05wSeyyS2OFRMKL/'
        '9e06e606f995eca5aad0246e6556e289/'
        '617103_Best-High-MPG-Cars_Hero_Fullwidth_1440x625.jpg',
    'attainable-dream-cars-under-50000':
        'https://content-images.carmax.com/qeontfmijmzv/605BZbR1bg8CoqsBYwB3L/'
        'a687fe4756f7dae4df831449f2620f1d/'
        'Dream_Cars_on_a_Budge_Hero_Fullwidth_1440x625.jpg',
}


def main():
    print(f"[articles] downloading {len(ARTICLE_HEROES)} article hero images")
    ok = skipped = failed = 0
    with httpx.Client(headers={'User-Agent': UA},
                      follow_redirects=True, timeout=30) as cx:
        for slug, url in ARTICLE_HEROES.items():
            dest = OUT / f"{slug}.jpg"
            if dest.exists() and dest.stat().st_size > 2000:
                print(f"  -- skipping {slug} (already present)")
                skipped += 1
                continue
            try:
                r = cx.get(url)
                if r.status_code == 200 and len(r.content) > 2000:
                    dest.write_bytes(r.content)
                    print(f"  [OK] {slug}  ({len(r.content) // 1024} KB)")
                    ok += 1
                else:
                    print(f"  [!!] {slug}: HTTP {r.status_code}")
                    failed += 1
            except Exception as e:
                print(f"  [!!] {slug}: {e}")
                failed += 1
    print(f"\n[articles] done: downloaded={ok}, skipped={skipped}, failed={failed}")
    print(f"[articles] images saved under {OUT}")


if __name__ == '__main__':
    main()
