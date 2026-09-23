"""Chase lending rate snapshots — mortgage and auto loan example rates.

Captured from www.chase.com rate pages on 2026-09-22 (mortgage rates as of
4:48 AM ET for ZIP 60629 Chicago, IL; auto rates last updated 11/13/2025).
Numbers are frozen snapshots, not live rates.
"""

MORTGAGE_SNAPSHOT = {
    "as_of": "4:48 AM ET, September 22, 2026",
    "zip": "60629",
    "city": "Chicago, IL",
    "rows": [
        {
            "loan_type": "30 year fixed",
            "rate": 6.750,
            "apr": 6.946,
            "monthly_payment": 2270.00,
            "points": 1.977,
            "points_cost": 6920.00,
            "loan_amount": 350000,
            "ltv": "80%",
        },
        {
            "loan_type": "15 year fixed",
            "rate": 5.875,
            "apr": 6.177,
            "monthly_payment": 2930.00,
            "points": 1.911,
            "points_cost": 6689.00,
            "loan_amount": 350000,
            "ltv": "80%",
        },
        {
            "loan_type": "30 year FHA fixed",
            "rate": 6.250,
            "apr": 7.122,
            "monthly_payment": 1566.00,
            "points": 2.041,
            "points_cost": 5103.00,
            "loan_amount": 235000,
            "ltv": "96%",
        },
        {
            "loan_type": "30 year Jumbo fixed",
            "rate": 6.375,
            "apr": 6.561,
            "monthly_payment": 8110.00,
            "points": 1.922,
            "points_cost": 24946.00,
            "loan_amount": 1300000,
            "ltv": "70%",
        },
        {
            "loan_type": "7/6 month Jumbo ARM",
            "rate": 6.000,
            "apr": 6.406,
            "monthly_payment": 7794.00,
            "points": 2.087,
            "points_cost": 27131.00,
            "loan_amount": 1300000,
            "ltv": "70%",
        },
    ],
    "assumptions": (
        "Each rate shown includes the number of discount points listed alongside "
        "that rate and is based on the following assumptions: 30-year fixed and "
        "15-year fixed are based on a loan amount of $350,000 with a loan to value "
        "of 80%; 30-year fixed FHA is based on a loan amount of $235,000 with a "
        "loan to value of 96%; 7/6 ARM non-Agency products are based on a loan "
        "amount of $1,300,000 with a loan to value of 70%. All rates assume a "
        "single-family residence purchase mortgage with a rate lock period of 30 days."
    ),
}

AUTO_SNAPSHOT = {
    "last_updated": "11/13/2025",
    "table_updated": "09/17/2025",
    "rows": [
        {
            "product": "New car purchase",
            "apr": 6.04,
            "term_months": 60,
            "amount": 45000,
            "example_payment": 867.91,
            "example_note": "Purchase of a new car would have a 6.04% APR for 60 months, monthly payment of $867.91 for $45,000 financing, down payment of $0.",
        },
        {
            "product": "Used car purchase",
            "apr": 6.09,
            "term_months": 60,
            "amount": 30000,
            "example_payment": 582.34,
            "example_note": "Purchase of a used 2022 year car would have a 6.09% APR for 60 months, monthly payment of $582.34 for $30,000 financing, down payment of $0.",
        },
        {
            "product": "Refinancing",
            "apr": 6.59,
            "term_months": 48,
            "amount": 30000,
            "example_payment": 712.69,
            "example_note": "Refinance auto loan for a 2022 year car would have a 6.59% APR for 48 months, monthly payment of $712.69 for $30,000 financing, down payment of $0.",
        },
    ],
    "assumptions": (
        "Advertised APRs are for customers with excellent credit who apply online. "
        "Rates may vary based on credit history, vehicle, financing amount and term. "
        "These rates do not include taxes and other fees that may be charged at the "
        "dealership."
    ),
}
