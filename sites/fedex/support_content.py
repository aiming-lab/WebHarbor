"""Local help content for the offline FedEx mirror.

Every article describes how this deterministic demo actually behaves: the zone and
price rules in `shipping_rules.py`, the seeded service levels, locations, slots,
claim and invoice vocabularies, and the offline boundary. Nothing here states real
carrier policy, price or commitment, and no article requires a live FedEx service.

`shipment-exception-status` and `weather-delay-guidance` are the two guides that
benchmark tasks read directly, so their wording is part of the graded contract and
must not be reworded without updating the tasks and verifiers.
"""

# Shared disclaimer appended to every article body so the offline boundary stays
# visible on each help destination.
DISCLAIMER = (
    " This page is part of a deterministic local FedEx-style demo. It uses synthetic "
    "shipping records, seeded route milestones, and fixed support guidance so benchmark "
    "agents can practice tracking, billing, and pickup workflows without contacting any "
    "live carrier service."
)

SUPPORT_CONTENT = {
    "shipment-exception-status": {
        "summary": "Understand an exception scan and find the information needed to investigate it.",
        "body": (
            "Open the package's tracking detail and check its Timeline. Record the event time "
            "and event location of the latest exception, then read the explanation beneath it. "
            "A Shipment exception can describe a weather interruption. An Operational delay "
            "means address details are under review before a new delivery attempt. "
            "Use the Current ETA on the same page to see whether a delivery date is available."
        ),
        "topics": ["Tracking", "Delivery exceptions", "Address review"],
    },
    "weather-delay-guidance": {
        "summary": "Find the latest information for a shipment affected by a weather delay.",
        "body": (
            "Track the affected package and open its detail page. In the Timeline, locate the "
            "latest Shipment exception and read its event time, location and explanation. "
            "Compare that event with the Current ETA. A scan timestamp records an event; it "
            "is not a promised delivery time. If the ETA is pending weather clearance, there "
            "is no confirmed delivery date. Check the tracking detail again for an updated estimate."
        ),
        "topics": ["Tracking", "Weather disruptions", "Delivery estimates"],
    },
    "track-multiple-numbers": {
        "summary": "Track several demo packages in one request and read the results in order.",
        "body": (
            "Enter tracking numbers on the Track page separated by commas or line breaks. The "
            "demo accepts up to 30 numbers per request and normalizes them to upper case, so a "
            "number typed in lower case resolves to the same record. The results page lists "
            "the packages it found in the order you entered them and states how many of the "
            "requested numbers matched. Open any result card to reach its tracking detail page, "
            "which carries the full Timeline, the Current ETA and the signature requirement. "
            "Numbers that are not part of the seeded data return no record; they are not "
            "forwarded anywhere because this mirror is offline."
        ),
        "topics": ["Tracking", "Multiple packages", "Demo workflow"],
    },
    "address-correction-hold": {
        "summary": "Why a package pauses with an Operational delay status in the demo timeline.",
        "body": (
            "An Operational delay means the address details are being reviewed before another "
            "delivery attempt. On the tracking detail page the status summary reads 'Address "
            "details are being reviewed before another attempt' and the Current ETA reads "
            "'Customer action may be required' rather than naming a delivery date. Fifteen of "
            "the seeded packages carry this status. The demo does not collect corrected address "
            "information: there is no address-edit form for a package in transit, and no "
            "redelivery can be scheduled. Record the latest exception event time and location "
            "from the Timeline when you report on such a package."
        ),
        "topics": ["Tracking", "Address review", "Delivery exceptions"],
    },
    "proof-of-delivery": {
        "summary": "Read the signature requirement and the final handoff event for a package.",
        "body": (
            "Each tracking record carries a signature-required flag, and the tracking detail "
            "page states it plainly next to the delivery summary. A delivered package shows a "
            "final Timeline entry whose status label is Delivered, together with that entry's "
            "event time and the city and state where the handoff was scanned. Read both from the "
            "package's own detail page, because the flag and the final scan location differ "
            "between records. The demo stores no signature image, recipient name capture, or "
            "proof-of-delivery document, and requesting one leads to an offline notice. When a "
            "task asks whether a signature is required, answer from the detail page of that "
            "specific tracking number, because the flag differs between records."
        ),
        "topics": ["Tracking", "Signature", "Delivery"],
    },
    "demo-pickup-scheduling": {
        "summary": "How pickup scheduling works against seeded slots in this local mirror.",
        "body": (
            "Sign in, open Schedule & manage pickups, choose a location, then choose one of its "
            "seeded slots and enter a package count between 1 and 20. Each location offers the same "
            "three windows on three consecutive demo dates, listed earliest first, and each option "
            "shows its date, its time window and the capacity that remains. Read the window you need "
            "from that location's own picklist, because the same three windows repeat at every "
            "location and only your account page records which one you booked. Scheduling one pickup "
            "reduces that slot's remaining capacity by one; a slot with no capacity left cannot be "
            "booked. The demo then stores a confirmation code of the form PU-nnnn with the slot date, "
            "time window, package count and the status Scheduled, and lists it on your account "
            "page. Seeded pickups show either Scheduled or Ready for driver. No courier is "
            "dispatched and nothing is sent to a live carrier service."
        ),
        "topics": ["Pickup", "Slots", "Demo workflow"],
    },
    "rate-estimate-zones": {
        "summary": "The exact zone and price rule this demo uses for rate estimates.",
        "body": (
            "The demo derives a zone from the origin and destination states. Two addresses in "
            "the same state are zone 1. Two addresses in the same region are zone 2, where the "
            "regions are West (CA, WA, OR, AZ, CO), East (NY, MA, PA, FL, GA, NC, VA) and "
            "Central (TX, IL, OH, MI). Any other pair is zone 4. Each displayed quote is the "
            "service's base rate, plus its per-pound rate multiplied by the weight, plus its zone "
            "surcharge multiplied by the zone, plus a package handling fee, rounded to cents. The "
            "handling fees are $0 for an Envelope, $8 for a Box, $10 for a Tube, $48 for a Freight "
            "pallet and $6 for any other package type such as a Pak. Weight must be between 0.1 "
            "and 1000 lb. Submitting the form returns a link that carries the request, so the same "
            "quote can be reopened without retyping it."
        ),
        "topics": ["Shipping rates", "Zones", "Quotes"],
    },
    "ground-vs-overnight": {
        "summary": "Compare the five seeded service levels by commitment and rate structure.",
        "body": (
            "The demo exposes five service levels. FedEx Priority Overnight commits to the next "
            "business day by 10:30 AM and is the fastest and most expensive per pound. FedEx "
            "Standard Overnight commits to the next business day by 8:00 PM. FedEx 2Day commits to "
            "2 business days by 4:30 PM. FedEx Ground Home Delivery is quoted as 1 to 5 business "
            "days and is normally the cheapest option for small parcels. FedEx Freight Economy is "
            "quoted as 3 to 6 business days and carries the highest base rate, so it is usually the "
            "most expensive line in a quote list, especially for a Freight pallet. Quotes are listed "
            "in this fixed order, and each card shows the commitment text, the zone and the price. "
            "Because price depends on weight, package type and zone, compare the displayed cards "
            "rather than assuming the fastest service is the most expensive."
        ),
        "topics": ["Shipping rates", "Service levels", "Quotes"],
    },
    "weekend-delivery-commitments": {
        "summary": "Which seeded services publish weekend handling in this demo.",
        "body": (
            "Two of the five seeded service levels carry weekend delivery copy: FedEx Priority "
            "Overnight and FedEx Ground Home Delivery. FedEx Standard Overnight, FedEx 2Day and "
            "FedEx Freight Economy do not. The flag is shown on the service cards and in the "
            "quote list; it does not change the computed price. Delivery estimates in this demo "
            "count business days only, so Saturday and Sunday are skipped: from the fixed demo ship "
            "date a next-business-day service lands on the following weekday, a two-business-day "
            "service can land after the weekend, and the longest quoted commitment is six business "
            "days. Read the resulting Current ETA from the shipment's own tracking detail page "
            "rather than computing it from the service card."
        ),
        "topics": ["Shipping rates", "Weekend delivery", "Delivery estimates"],
    },
    "freight-pallet-guidance": {
        "summary": "Freight pallet quoting, fees and the locations that mention freight.",
        "body": (
            "Selecting the Freight pallet package type adds a $48 handling fee to every quoted "
            "service, on top of the base rate, per-pound and zone components. Freight Economy is "
            "the service level intended for palletized shipments and normally produces the highest "
            "price in the list. Freight is not available everywhere in this demo: some locations "
            "publish a freight cutoff or a freight dock opening time in their own pickup note, and "
            "at least one office records that it offers no freight service at all. Read that note on "
            "the location's own detail page, because the wording differs per location. The demo "
            "stores no pallet dimensions, no liftgate request and no freight bill of lading; those "
            "destinations show an offline notice."
        ),
        "topics": ["Freight", "Pallet", "Locations"],
    },
    "packaging-supplies-guide": {
        "summary": "Package types accepted by the demo and the fee each one adds.",
        "body": (
            "The ship and rate-estimate forms offer five package types: Envelope, Box, Tube, Pak "
            "and Freight pallet. Their handling fees in the demo price rule are $0, $8, $10, $6 and "
            "$48 respectively, so the package type changes every displayed quote. Seeded shipments "
            "use all five types. Ordering supplies themselves is not available offline: the print "
            "and packaging destinations in the navigation open an offline notice instead of a "
            "catalog. Locations that advertise 'Packing help', 'Pack and ship' or 'Packaging "
            "supplies' list those services on their detail pages."
        ),
        "topics": ["Packaging", "Package types", "Shipping rates"],
    },
    "hold-at-location": {
        "summary": "What the hold-at-location service means on a seeded location record.",
        "body": (
            "Several seeded locations list 'Hold at location' among their services, including the "
            "Seattle Downtown Ship Center, the San Francisco Market Hub, the Denver Union Station "
            "Ship Center, the Houston Midtown Ship Center, the Miami Brickell Print & Ship office "
            "and the Boston Back Bay Ship Center. In this demo the label is informational: it "
            "appears in the services list on the location card and detail page. There is no form to "
            "redirect a package to a hold location, and no hold can be created against a tracking "
            "number. Use the location detail page to read that location's hours, phone number, "
            "services, amenities and its own pickup note."
        ),
        "topics": ["Locations", "Hold at location", "Services"],
    },
    "dropoff-location-amenities": {
        "summary": "How to search locations and how to read a location detail page.",
        "body": (
            "The locations page lists all fifteen seeded locations ordered by state then city, and "
            "its search box filters by name, city, state or location type; searching 'Ship Center' "
            "returns the staffed counters, while 'Office Print' returns the print and ship offices. "
            "Each card shows the location type, the posted hours, the address, the phone number, the "
            "services offered and the lobby amenities. The detail page repeats those fields and adds "
            "that location's own pickup note, which is unique to it and states its freight, "
            "small-parcel, express or documentation cutoff, followed by its three pickup windows. "
            "Keep the location-level note and the per-slot cutoff notes apart: every slot carries its "
            "own booking note, and only the location-level note appears in the summary beside the "
            "address and phone number."
        ),
        "topics": ["Locations", "Search", "Amenities"],
    },
    "international-paperwork-demo": {
        "summary": "International documentation handling inside this offline mirror.",
        "body": (
            "Exactly one seeded office publishes an international documentation cutoff, in its own "
            "pickup note, shown on both its location card and its detail page. Open that location to "
            "read the wording and the cutoff time; no other location states one, and the locations "
            "directory is the only place it is published. That is "
            "the only international paperwork fact in the demo. No customs form, commercial "
            "invoice, harmonized code or duty estimate can be created here, and the international "
            "shipping destinations in the navigation open an offline notice. All seeded lanes are "
            "domestic United States state pairs."
        ),
        "topics": ["Shipping", "International", "Locations"],
    },
    "invoice-due-dates": {
        "summary": "How seeded and newly created invoices are dated and statused.",
        "body": (
            "Every shipment in the demo has exactly one invoice, and the invoices page lists them "
            "with the invoice number, the related shipment, the billed date, the due date, the "
            "amount and the status. Seeded invoices are billed on their shipment's creation date "
            "and fall due later the same month, with statuses Open, Paid or "
            "Processing. An invoice created by the shipping flow is billed on the fixed demo ship "
            "date, falls due fourteen days later, carries the same amount as the shipment's total "
            "cost, and starts as Open. Invoice numbers share their numeric suffix with the "
            "shipment code, so a shipment numbered SH-26nnnn pairs with the invoice INV-26nnnn. "
            "Paying or disputing an invoice is "
            "not available offline."
        ),
        "topics": ["Billing", "Invoices", "Account history"],
    },
    "account-invoices-export": {
        "summary": "Where billing contact details and invoice history live for a demo account.",
        "body": (
            "Each account stores an invoicing email alongside its profile fields, visible on the "
            "profile edit page; the four seeded accounts use addresses of the form "
            "billing+alice@test.com. Invoice history is listed per account under Invoices and on "
            "the account overview, newest billed date first. The profile form validates what it "
            "stores: names are required and limited to 80 characters, the state must be one of the "
            "listed labels, a ZIP code must be 5 digits with an optional 4-digit extension, a phone "
            "number may contain digits, spaces and the characters + ( ) - . only, the billing email "
            "must be a valid address, and the preferred location must be one of the seeded "
            "locations. Exporting or downloading billing data is not available offline and opens an "
            "offline notice."
        ),
        "topics": ["Billing", "Account", "Profile"],
    },
    "claims-status-timeline": {
        "summary": "The claim statuses and what each one means in the demo claims list.",
        "body": (
            "The claims page lists each claim with its claim number, the tracking number it refers "
            "to, the claim type, the amount, the opened date and the status. Two statuses appear in "
            "the seeded data. 'Info requested' means the claim is waiting for more information "
            "before it can be assessed, and every seeded claim with that status is a Damage review "
            "claim. 'Closed' means the claim is finished, and every seeded Closed claim is a Missing "
            "package claim. The claim vocabulary also includes an 'Under review' status and a 'Delay "
            "reimbursement' type. Claims are read-only in this mirror: no claim can be opened, "
            "updated or withdrawn, and the file-a-claim destinations open an offline notice."
        ),
        "topics": ["Claims", "Status", "Account history"],
    },
    "missing-package-claim": {
        "summary": "How missing package claims appear in the seeded claims data.",
        "body": (
            "A Missing package claim in this demo is a read-only record. Each one shows a claim "
            "number of the form CLM-nnnn, the tracking number it refers to, the claim type Missing "
            "package, the claimed amount, the date it was opened and the status Closed. Eight of the "
            "twelve seeded claims are of this type, spread across the four demo accounts, and they "
            "are visible only after signing in to the account that owns them. Filing a new claim is "
            "not available: the claim form destinations open an offline notice, and no claim row can "
            "be created, edited or deleted through the site."
        ),
        "topics": ["Claims", "Missing package", "Account history"],
    },
}


def article(slug: str, title: str, category: str, fallback_summary: str) -> dict[str, object]:
    """Return the stored content for one article, with the shared disclaimer.

    Every advertised topic must have real local guidance, so a slug without an
    entry is an error rather than a silently generic page.
    """
    try:
        content = SUPPORT_CONTENT[slug]
    except KeyError as exc:
        raise ValueError(f"support article has no local content: {slug}") from exc
    del title, category, fallback_summary
    return {
        "summary": content["summary"],
        "body": content["body"] + DISCLAIMER,
        "topics": list(content["topics"]),
    }
