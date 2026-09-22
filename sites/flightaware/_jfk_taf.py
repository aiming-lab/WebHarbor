"""JFK Terminal Area Forecast snapshot (audit fix for reviewer finding #4).

Rows exactly as published on the flightaware.com JFK weather page on the
mirror snapshot day (2026-09-22, capture in
wh-flightaware-review-evidence/upstream/weather_kjfk_full.png): the TAF
issued for KJFK that morning, one row per forecast hour, newest first.

Columns: Date, Time (EDT), Flight Rules, Wind Dir., Speed, Type, Height
AGL (ft), Visibility, Remarks. Type/Height cells may carry two stacked
values ("<br>"-joined) exactly like the upstream table.
"""

_SCT_SCT = ("Scattered<br>Scattered", "10,000<br>25,000")
_BKN = ("Broken", "7,000")
_FEW_OVC = ("Few<br>Overcast", "3,000<br>6,000")

JFK_TAF_ROWS = [
    ("23-Sep", "01:00PM", "VFR", "40°", "15 kt", _SCT_SCT[0], _SCT_SCT[1], ">= 6 miles",
     "Winds gusting to 22 knots."),
    ("23-Sep", "12:00PM", "VFR", "40°", "15 kt", _SCT_SCT[0], _SCT_SCT[1], ">= 6 miles",
     "Winds gusting to 22 knots."),
    ("23-Sep", "11:00AM", "VFR", "40°", "15 kt", _SCT_SCT[0], _SCT_SCT[1], ">= 6 miles",
     "Winds gusting to 22 knots."),
    ("23-Sep", "10:00AM", "VFR", "40°", "15 kt", _SCT_SCT[0], _SCT_SCT[1], ">= 6 miles",
     "Winds gusting to 22 knots."),
    ("23-Sep", "09:00AM", "VFR", "40°", "15 kt", _SCT_SCT[0], _SCT_SCT[1], ">= 6 miles",
     "Winds gusting to 22 knots."),
    ("23-Sep", "08:00AM", "VFR", "40°", "15 kt", _SCT_SCT[0], _SCT_SCT[1], ">= 6 miles",
     "Winds gusting to 22 knots."),
    ("23-Sep", "07:00AM", "VFR", "40°", "15 kt", _SCT_SCT[0], _SCT_SCT[1], ">= 6 miles",
     "Winds gusting to 22 knots."),
    ("23-Sep", "06:00AM", "VFR", "40°", "15 kt", _SCT_SCT[0], _SCT_SCT[1], ">= 6 miles",
     "Winds gusting to 22 knots."),
    ("23-Sep", "05:00AM", "VFR", "40°", "15 kt", _SCT_SCT[0], _SCT_SCT[1], ">= 6 miles",
     "Winds gusting to 22 knots."),
    ("23-Sep", "04:00AM", "VFR", "40°", "15 kt", _SCT_SCT[0], _SCT_SCT[1], ">= 6 miles",
     "Winds gusting to 22 knots."),
    ("23-Sep", "03:00AM", "VFR", "40°", "15 kt", _SCT_SCT[0], _SCT_SCT[1], ">= 6 miles",
     "Winds gusting to 22 knots."),
    ("23-Sep", "02:00AM", "VFR", "40°", "15 kt", _SCT_SCT[0], _SCT_SCT[1], ">= 6 miles",
     "Winds gusting to 22 knots."),
    ("23-Sep", "01:00AM", "VFR", "40°", "15 kt", _SCT_SCT[0], _SCT_SCT[1], ">= 6 miles",
     "Winds gusting to 22 knots."),
    ("23-Sep", "12:00AM", "VFR", "40°", "15 kt", _SCT_SCT[0], _SCT_SCT[1], ">= 6 miles",
     "Winds gusting to 22 knots."),
    ("22-Sep", "11:00PM", "VFR", "50°", "14 kt", _BKN[0], _BKN[1], ">= 6 miles",
     "Winds gusting to 24 knots."),
    ("22-Sep", "10:00PM", "VFR", "50°", "14 kt", _BKN[0], _BKN[1], ">= 6 miles",
     "Winds gusting to 24 knots."),
    ("22-Sep", "09:00PM", "VFR", "50°", "14 kt", _BKN[0], _BKN[1], ">= 6 miles",
     "Winds gusting to 24 knots."),
    ("22-Sep", "08:00PM", "VFR", "50°", "14 kt", _BKN[0], _BKN[1], ">= 6 miles",
     "Winds gusting to 24 knots."),
    ("22-Sep", "07:00PM", "VFR", "50°", "14 kt", _BKN[0], _BKN[1], ">= 6 miles",
     "Winds gusting to 24 knots."),
    ("22-Sep", "06:00PM", "VFR", "50°", "14 kt", _BKN[0], _BKN[1], ">= 6 miles",
     "Winds gusting to 24 knots."),
    ("22-Sep", "05:00PM", "VFR", "50°", "14 kt", _BKN[0], _BKN[1], ">= 6 miles",
     "Winds gusting to 24 knots."),
    ("22-Sep", "04:00PM", "VFR", "50°", "14 kt", _BKN[0], _BKN[1], ">= 6 miles",
     "Winds gusting to 24 knots."),
    ("22-Sep", "03:00PM", "VFR", "50°", "14 kt", _BKN[0], _BKN[1], ">= 6 miles",
     "Winds gusting to 24 knots."),
    ("22-Sep", "02:00PM", "VFR", "50°", "14 kt", _BKN[0], _BKN[1], ">= 6 miles",
     "Winds gusting to 24 knots."),
    ("22-Sep", "01:00PM", "VFR", "50°", "14 kt", _BKN[0], _BKN[1], ">= 6 miles",
     "Winds gusting to 24 knots."),
    ("22-Sep", "12:00PM", "VFR", "50°", "14 kt", _BKN[0], _BKN[1], ">= 6 miles",
     "Winds gusting to 24 knots."),
    ("22-Sep", "11:00AM", "VFR", "40°", "17 kt", _FEW_OVC[0], _FEW_OVC[1], ">= 6 miles",
     "Winds gusting to 20 knots. Vicinity showers."),
]
