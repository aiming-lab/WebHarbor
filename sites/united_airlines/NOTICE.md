# Mirror notice — united_airlines (www.united.com)

This directory contains a functional mirror of https://www.united.com/
(en/us market) built for the WebHarbor offline benchmark environment. It is a
benchmark fixture, not an official United Airlines product.

## What is mirrored

- The home booking widget: origin/destination airport pickers from the real
  united.com airport lookup API, departure/return dates, adult/child counts
  and the United fare families (Basic Economy, United Economy®, Economy
  Plus®, United Premium Plus®, United Business® / United First®).
- Flight search over the frozen real-flight network captured from the
  upstream flight-status APIs (flight numbers, routes, departure/arrival
  times, aircraft), with fare columns per cabin, Premier member fares, sort
  and time-of-day/nonstop filters, and round-trip outbound+return selection.
- The booking chain: traveler details with name/date-of-birth/MileagePlus
  validation, contact details, card payment validation (Visa/Mastercard/
  Amex/Discover), award redemption for signed-in MileagePlus members, and
  the confirmation page with the six-character confirmation number.
- My Trips: lookup by confirmation number + last name, trip detail with
  seats (per-aircraft seat map with Economy Plus fees), checked bags at the
  online/airport price ladder with Premier free-bag allowances, flight
  changes (no change fee, fare difference) and cancellations (refund vs
  future flight credit by fare family).
- Online check-in: the 24-hour window, seat selection on the real per-
  aircraft seat map, boarding group assignment and the boarding pass.
- Flight status by flight number and by route over the frozen operations
  snapshot, with links to the aircraft and terminal details.
- Baggage: checked bag fee ladder ($35/$40 online, $40/$45 at the airport,
  extra/overweight/oversized), weight limits by cabin and Premier status,
  carry-on and personal item size limits, and the checked bag fee
  calculator by route/cabin/status.
- MileagePlus: join, sign in, account dashboard (award miles, PQF/PQP
  progress, PlusPoints, activity ledger), the Premier tier table (12 PQF +
  4,000 PQP for Silver up to 54 PQF + 18,000 PQP for 1K), earning rates
  (5x-11x per $1) and award travel at payment.
- Cabin experience pages (Basic Economy rules, Economy, Economy Plus,
  Premium Plus, First/Business, Polaris), the fleet pages with real seat
  maps and aircraft specs, and the airport guides for the hubs and every
  destination in the network.
- Change/cancel policy pages (no change fee, 24-hour flexible booking,
  refunds vs future flight credits, Basic Economy rules), the deals page
  and the help center with scored FAQ search.

## Where the data comes from

All airport, flight, aircraft and content data in this mirror was captured
from the real united.com (and its APIs) on 2026-09-28 via the Internet
Archive Wayback Machine — see provenance.json for the per-source map. Images are the real upstream united.com media assets
(see asset_inventory.json for per-file bytes, SHA-256 and source URLs).
