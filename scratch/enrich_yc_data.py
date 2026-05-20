import json
import re

content_path = "/home/winterandchaiyun/.gemini/antigravity-cli/brain/3439a752-1b49-4e1f-ad7b-cc7e1516d545/.system_generated/steps/756/content.md"

with open(content_path, 'r') as f:
    content = f.read()

# Extract data-page attribute
match = re.search(r'data-page="({.*?})"', content)
if match:
    data_str = match.group(1).replace('&quot;', '"')
    data = json.loads(data_str)
    
    # Save the extracted data for reference
    with open('/home/winterandchaiyun/misc/WebHarbor/scratch/yc_live_data.json', 'w') as out:
        json.dump(data, out, indent=2)
    
    print("Successfully extracted live YC data.")
else:
    print("Could not find data-page JSON.")
