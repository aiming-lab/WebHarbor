import json
import sqlite3
import os

DB_PATH = '/home/winterandchaiyun/misc/WebHarbor/sites/y_combinator/instance/y_combinator.db'
JSON_PATH = '/home/winterandchaiyun/misc/WebHarbor/sites/y_combinator/scraped_data/extra_sections.json'

if not os.path.exists(DB_PATH):
    print("DB not found")
    exit(1)

with open(JSON_PATH, 'r') as f:
    data = json.load(f)

faqs = data.get('faq', [])
if not faqs:
    print("No FAQs found in JSON")
    exit(1)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Clear existing FAQs
cursor.execute("DELETE FROM faq")

for item in faqs:
    cursor.execute("INSERT INTO faq (question, answer) VALUES (?, ?)", (item['q'], item['a']))

conn.commit()
conn.close()
print(f"Updated {len(faqs)} FAQs in DB")
