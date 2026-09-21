# carmax.com — recon notes (Phase 1.3)

Captured via WebFetch + WebSearch on 2026-05-14. No browser/image harvesting from
the sandbox; that step happens locally via `scrape_carmax.py`.

## URL patterns

| Pattern | Purpose |
|---|---|
| `/` | Homepage |
| `/cars` | Master inventory listing (supports `?location=`, `?make=`, etc.) |
| `/cars/<make>` | Make landing |
| `/cars/<make>/<model>` | Model listings |
| `/cars/<make>/<model>/<year>` | Year-filtered model listings |
| `/cars/<make>/<model>/<trim>/<year>` | Trim+year filter |
| `/cars/<model>?year=YYYY-YYYY&mileage=N` | Filter via query params |
| `/research` | Research landing |
| `/research/<make>/<model>/<year>` | Vehicle research page (specs, trims, FAQ, reviews) |
| `/research/car-comparison/<make>-<model>-<year>` | Comparison tool |
| `/reviews/<make>/<model>/<year>` | Customer reviews |
| `/value` | Used-car value entry |
| `/value/<make>/<model>/<year>` | Year-specific value lookup |
| `/sell-my-car` | Sell-my-car / instant offer flow |
| `/stores` | National store locator |
| `/stores/<state_2letter>` | State stores list |
| `/pre-qual/app` | Pre-qualification application |
| `/car-financing` | Financing landing |
| `/articles` | Articles index |
| `/articles/<slug>` | Article detail |
| `/faq` | FAQ root |
| `/car-buying-process/maxcare-service-plans` | MaxCare extended warranty |

## Functional modules (mirror scope: ALL of these)

1. **Inventory search** — filters: ZIP/location, make, model, year range, trim, body style, mileage max, price range, color, transmission, drive type, fuel type, features
2. **Vehicle detail** — photos, price, mileage, specs, features list, store assignment, transfer fee, reserve/test-drive/financing CTAs
3. **Research pages** — model overview with specs, trims, pros/cons, ratings, reliability score, FAQ
4. **Customer reviews** — 1-5 star ratings, written review text
5. **Vehicle comparison** — side-by-side
6. **Saved vehicles** — heart icon, per-user list
7. **Store locator** — 42 states, ~250 stores
8. **Pre-qualification** — soft credit check → personalized monthly payment terms
9. **Sell my car** — appraisal form, instant offer valid 7 days
10. **Reserve a vehicle** — hold up to 7 days
11. **Test drive scheduling** — in-store or at-home
12. **Order/Checkout** — buy reserved vehicle online
13. **MaxCare** — extended warranty info
14. **Articles** — content marketing posts
15. **My account** — saved cars, offers, orders, reservations, test drives, pre-qual status

## Vehicle data shape

Identity: year, make, model, trim, body_style, stock_number, vin, slug

Specs: engine_text, horsepower, torque, transmission, drive_type, fuel_type,
fuel_economy_{city,highway,combined}, seating_capacity, cargo_volume_cuft,
wheelbase, length, width, height

Commercial: price, list_price (MSRP), mileage, days_on_lot, exterior_color,
interior_color, store_id, transfer_fee, is_certified (always True), is_featured,
is_no_haggle (always True), customer_rating, customer_rating_count, repairpal_rating

Features (json list, sample tokens from real carmax research pages):
- Apple CarPlay, Android Auto, Bluetooth, Navigation System, BOSE Sound System,
  AM/FM Stereo, Satellite Radio Ready, Auxiliary Audio Input
- Backup/Rear View Camera, Blind Spot Monitor, Lane Departure Warning,
  Automated Cruise Control, Parking Sensors
- Heated Seats, Leather Seats, Power Seats, Power Windows, Power Locks,
  Power Mirrors, Heated Mirrors, Remote Start, Smart Key
- Sunroof, Alloy Wheels, Rear Spoiler, Turbo Charged Engine, Manual Transmission
- ABS Brakes, Traction Control, Side Airbags, Overhead Airbags, Air Conditioning,
  Rear Defroster

## Brand visual identity

- **Primary**: deep navy blue (carmax-blue ≈ `#1660a8` / `#0d3a72`)
- **Accent**: bright yellow (carmax-yellow ≈ `#FFD900` / `#FFC600`)
- **Background**: white + light gray (`#f7f7f7`)
- **Text**: near-black (`#202020`) on white; white on dark blue
- **Logo**: black "CarMax" wordmark, often paired with a yellow box icon
- **Vehicle cards**: white card on light gray, image top, price + mileage prominent,
  CarMax Certified badge, transfer fee badge, "shipping available" pill
- **CTAs**: yellow buttons with dark text (primary), navy outline buttons (secondary)

## Real image URL patterns (for the scrape script)

```
https://content-images.carmax.com/stockimages/<year>/<make>/<model>/<stock>-<view>-evoxwebmedium.png
  views: 089 (angled-front), 174 (dashboard), 118 (front), 037 (side), 119 (back), 122 (cargo)

https://content-images.carmax.com/qeontfmijmzv/<hash1>/<hash2>/<filename>.jpg
  Contentful CDN for article hero images & lifestyle photos

/stores/images/CarMax-Icon-Yellow-BOX-HEX.png  — logo icon
```

## Sales pitch / copy elements

- "CarMax Certified" (125+ point inspection, no flood/frame damage, no salvage)
- "10-day Money Back Guarantee"
- "30-day limited warranty" (60-day in CT/MN/RI, 90-day in MA/NJ/NY)
- "MaxCare extended service plan"
- "Free vehicle history report"
- "Upfront, no-haggle prices — same price for everyone"
- "Pre-qualified in 5 minutes, no impact to credit"
- "Real offer in under 2 minutes, valid 7 days"
- "Largest used car inventory in the nation, ~50,000 vehicles"
- "We'll buy your car even if you don't buy ours®"
- Shipping fee disclosure: "non-refundable transfer fee may apply"

## Store distribution (informs Store seed)

Sample from /stores page: AL 6, AZ 5, AR 1, CA 34, CO 6, CT 3, DE 1, FL 24,
GA 13, ID 1, IL 11, IN 4, IA 1, KS 2, KY 3, LA 5, ME 1, MD 9, MA 4, MI 1,
MN 2, MS 3, MO 4, NE 1, NV 4, NH 1, NJ 6, NM 2, NY 5, NC 13, OH 6, OK 3,
OR 3, PA 5, RI 1, SC 4, TN 10, TX 29, UT 1, VA 12, WA 7, WI 4. Total ≈250.

For seed we'll sample ~12 stores across diverse states (CA, TX, FL, GA, NY,
IL, VA, AZ, CO, NC, WA, MA).

## Trim/feature taxonomy (real, from research pages)

Honda Civic 2022 trims observed: LX, Sport, Sport Touring, EX, EX-L, Touring, SI
Body styles in catalog: Sedan, Hatchback, Coupe, SUV, Truck, Minivan, Convertible, Wagon
Engine sizes observed: 1.5L Turbo, 2.0L NA, 2.4L, 3.5L V6, 5.0L V8, 5.3L V8, 2.5L hybrid

## Sources

- https://www.carmax.com/
- https://www.carmax.com/cars
- https://www.carmax.com/cars/honda/civic/2022
- https://www.carmax.com/research/honda/civic/2022
- https://www.carmax.com/stores
- https://www.carmax.com/articles/carmax-questions-answered
- https://www.carmax.com/articles/pre-approval-vs-pre-qualified
- https://www.carmax.com/sell-my-car (referenced)
- https://www.carmax.com/value (referenced)
- https://www.carmax.com/pre-qual/app (referenced)

WebVoyager upstream_url for tasks: `https://www.carmax.com/`
