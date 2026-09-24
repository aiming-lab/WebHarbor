# Archived catalog and variant review

The unchanged source archive is HF PR #45. Some source colors share a text name while their SKU color codes differ. For example BLUE code 62 and BLUE code 65 were collapsed into one JavaScript option, sometimes choosing a different price/stock record. The tracked extraction migration appends the source color code only where a product has this ambiguity. It preserves variant IDs and all existing carts/orders. Historical order text remains as purchased.

The original SUPIMA product URL was inspected in Chromium on 2026-09-23 (HTTP 200). Its visible flow includes color/size selection, stock, cart, wish list, materials and reviews. The current upstream redirects to newer product inventory; this mirror retains the original archived catalog and makes no claim of current stock. Demo accounts, orders and carts are benchmark fixtures. Required workflows use the mirrored archived data.
