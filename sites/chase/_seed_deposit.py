"""Chase deposit products catalog — checking, savings and CD accounts.

Captured from personal.chase.com and chase.com product pages
(2026-09-22 snapshot): monthly service fees, fee-waiver rules, features and
page copy follow the live site's product tiles and detail pages.
"""

CHECKING = [
    {
        "slug": "total-checking",
        "name": "Chase Total Checking®",
        "tagline": "Our most popular checking account.",
        "monthly_fee": 15.00,
        "fee_text": "$15 or $0 Monthly Service Fee",
        "fee_waiver": "You can avoid the Monthly Service Fee on Total Checking when you do at least ONE of the following each statement period: have a qualifying direct deposit of $500 or more; OR maintain a balance at the beginning of each day of $1,500 or more in this account; OR maintain an average beginning day balance of $5,000 or more in any combination of this account and qualifying linked Chase deposits/investments; OR pay a $5 Monthly Service Fee (no waiver).",
        "min_deposit": 0,
        "tab": "all",
        "features": [
            "Comes with Chase Overdraft Assist℠ — no overdraft fees if you're overdrawn by $50 or less at the end of the business day, or if your account is overdrawn by more than $50 and you bring it to $50 or less by the end of the next business day",
            "Write checks and send money with Zelle®",
            "Access to more than 14,000 ATMs and nearly 4,700 branches",
            "New Chase checking customers can earn a bonus when opening an account with qualifying activities",
        ],
        "image": "products/advisor-with-client-654.png",
    },
    {
        "slug": "secure-banking",
        "name": "Chase Secure Banking℠",
        "tagline": "Banking essentials with no overdraft fees.",
        "monthly_fee": 4.95,
        "fee_text": "$4.95 or $0 Monthly Service Fee",
        "fee_waiver": "No Monthly Service Fee for account owners who are 17–24 years old. 17-year-olds must open in branch.",
        "min_deposit": 0,
        "tab": "all",
        "features": [
            "Get your paycheck up to 2 days early with direct deposit",
            "Send and receive money with Zelle® at no extra charge",
            "No overdraft fees",
            "$0 Monthly Service Fee for account owners who are 17–24 years old",
        ],
        "image": "products/advisor-with-client-654.png",
    },
    {
        "slug": "premier-plus-checking",
        "name": "Chase Premier Plus Checking℠",
        "tagline": "Keep more of your money for your financial goals",
        "monthly_fee": 25.00,
        "fee_text": "$25 or $0 Monthly Service Fee",
        "fee_waiver": "Have a qualifying Chase First Mortgage or Chase Sapphire℠ Banking account; OR maintain an average beginning day balance of $15,000 or more in any combination of this account and qualifying linked Chase deposits/investments.",
        "min_deposit": 0,
        "tab": "all",
        "features": [
            "No Chase fees on ATMs across the globe, non-Chase ATM usage fees, or adjustment fees",
            "Perks for military members with $0 Monthly Service Fee and no minimum deposit required",
            "Earn interest on your balance",
            "Complimentary Chase debit card",
        ],
        "image": "products/advisor-with-client-654.png",
    },
    {
        "slug": "first-banking",
        "name": "Chase First Banking℠",
        "tagline": "Parent-owned and designed with kids ages 6–12 in mind and available for kids 6–17 years old.",
        "monthly_fee": 0.00,
        "fee_text": "$0 Monthly Service Fee",
        "fee_waiver": "",
        "min_deposit": 0,
        "tab": "students",
        "features": [
            "A debit card for kids with oversight by parents",
            "Gives kids tools, tips and safety features to help them learn money basics",
            "Requires an eligible Chase checking account to open",
        ],
        "image": "products/advisor-with-client-654.png",
    },
    {
        "slug": "high-school-checking",
        "name": "Chase High School Checking℠",
        "tagline": "Parent co-owned for teens ages 13 to 17.",
        "monthly_fee": 0.00,
        "fee_text": "$0 Monthly Service Fee",
        "fee_waiver": "",
        "min_deposit": 0,
        "tab": "students",
        "features": [
            "A checking account with tools for teens, in partnership with parents",
            "Access to Zelle® and direct deposit",
            "Must be opened in branch",
            "Requires an eligible Chase checking account to open",
        ],
        "image": "products/advisor-with-client-654.png",
    },
    {
        "slug": "college-checking",
        "name": "Chase College Checking℠",
        "tagline": "For students 17–24 enrolled in school.",
        "monthly_fee": 6.00,
        "fee_text": "$6 or $0 Monthly Service Fee",
        "fee_waiver": "No Monthly Service Fee while the account owner is a student 17–24 years old, up to the graduation date provided in the account opening process (a five-year maximum applies).",
        "min_deposit": 0,
        "tab": "students",
        "features": [
            "No Monthly Service Fee while enrolled in school for students 17–24",
            "Access to more than 14,000 ATMs and nearly 4,700 branches",
            "Chase Mobile® app banking",
        ],
        "image": "products/advisor-with-client-654.png",
    },
    {
        "slug": "private-client-checking",
        "name": "Chase Private Client Checking℠",
        "tagline": "Dedicated banker support and investing guidance from J.P. Morgan Wealth Management.",
        "monthly_fee": 35.00,
        "fee_text": "$35 or $0 Monthly Service Fee",
        "fee_waiver": "Have a qualifying linked Chase Private Client Savings℠ or Chase First Mortgage; OR maintain an average beginning day balance of $150,000 or more in any combination of qualifying Chase deposits/investments.",
        "min_deposit": 0,
        "tab": "premium",
        "features": [
            "Higher limits on everyday transactions",
            "No ATM fees worldwide",
            "24/7 priority service line",
            "Dedicated Chase Private Client Banker",
        ],
        "image": "products/chase-private-client-logo.jpg",
    },
    {
        "slug": "sapphire-banking",
        "name": "Chase Sapphire℠ Banking",
        "tagline": "Premium banking relationship with no everyday banking fees.",
        "monthly_fee": 0.00,
        "fee_text": "$0 Monthly Service Fee",
        "fee_waiver": "",
        "min_deposit": 0,
        "tab": "premium",
        "features": [
            "No everyday banking fees",
            "No Chase fees on ATMs across the globe",
            "Sapphire Banking rates on qualifying linked savings",
        ],
        "image": "products/chase-private-client-logo.jpg",
    },
]

SAVINGS = [
    {
        "slug": "chase-savings",
        "name": "Chase Savings℠",
        "tagline": "Our most popular savings account to help you reach your goals.",
        "monthly_fee": 5.00,
        "fee_text": "$5 or $0 Monthly Service Fee",
        "fee_waiver": "You can avoid the fee with a $300+ balance at the beginning of each day; OR $25+ in total Autosave or other repeating automatic transfers from your personal Chase checking account; OR by linking to a qualifying checking account; OR an account owner under the age of 25.",
        "min_deposit": 0,
        "apy_text": "Rates vary by location; see the Account Disclosures and Rates for your area.",
        "features": [
            "Savings made simple — set money aside automatically",
            "Earn interest on your balance",
            "Track savings on the go with the Chase Mobile® app",
            "$0 Monthly Service Fee for account owners under 25",
        ],
        "image": "products/premier-savings-tile.jpg",
    },
    {
        "slug": "premier-savings",
        "name": "Chase Premier Savings℠",
        "tagline": "Earn Premier relationship rates when you link to a Chase Premier Plus Checking℠ or Chase Sapphire℠ Banking account.",
        "monthly_fee": 25.00,
        "fee_text": "$25 or $0 Monthly Service Fee",
        "fee_waiver": "Have a linked Chase Premier Plus Checking℠ or Chase Sapphire℠ Banking account; OR maintain a balance at the beginning of each day of $15,000 or more in this account.",
        "min_deposit": 0,
        "apy_text": "Earn Premier relationship rates when linked to a Chase Premier Plus Checking℠ or Chase Sapphire℠ Banking account.",
        "features": [
            "Premier relationship rates",
            "Autosave available",
            "Interest compounded and credited monthly",
        ],
        "image": "products/premier-savings-tile.jpg",
    },
    {
        "slug": "private-client-savings",
        "name": "Chase Private Client Savings℠",
        "tagline": "Already a Chase Private Client Checking℠ customer? Link a Private Client Savings account to get the most of your relationship and earn relationship rates.",
        "monthly_fee": 0.00,
        "fee_text": "$0 Monthly Service Fee",
        "fee_waiver": "",
        "min_deposit": 0,
        "apy_text": "Relationship rates when linked to Chase Private Client Checking℠.",
        "features": [
            "Relationship rates for Private Client customers",
            "Priority service line",
            "Dedicated Chase Private Client Banker",
        ],
        "image": "products/private-client-tile.jpg",
    },
]

# CD terms and rates captured from the chase.com CD pages (2026-09-22 snapshot).
CD_TERMS = [
    ("6 months", 3.25, 1000),
    ("12 months", 3.50, 1000),
    ("18 months", 3.35, 1000),
    ("24 months", 3.30, 1000),
    ("30 months", 3.20, 1000),
    ("36 months", 3.15, 1000),
    ("48 months", 3.00, 1000),
    ("60 months", 2.95, 1000),
]

CD_FAQ = [
    {
        "q": "What is a Certificate of Deposit (CD)?",
        "a": "A Chase Certificate of Deposit (CD) is a type of savings account that earns a fixed interest rate over a set period of time. Your rate is locked in when you open the account and won't change during the term, regardless of changes in the market.",
    },
    {
        "q": "What is the minimum deposit to open a Chase CD?",
        "a": "You can open a Chase CD with $1,000 or more. Existing Chase checking or savings customers can open a CD online; new customers can visit a branch.",
    },
    {
        "q": "What happens when my CD reaches maturity?",
        "a": "At maturity, your CD automatically renews into the same term at the then-current rate unless you make changes during the 10-day grace period after maturity. You can withdraw funds, renew, or move the money into a different CD during that window.",
    },
    {
        "q": "Are there fees to open or maintain a Chase CD?",
        "a": "There is no monthly service fee for Chase CDs. An early withdrawal penalty applies if you withdraw funds before the maturity date.",
    },
]
