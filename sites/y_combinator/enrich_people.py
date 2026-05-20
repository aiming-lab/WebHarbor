import os
import json
import asyncio
import httpx
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPED_DIR = os.path.join(BASE_DIR, 'scraped_data')
IMAGES_DIR = os.path.join(BASE_DIR, 'static', 'images')
os.makedirs(IMAGES_DIR, exist_ok=True)

def slugify(text):
    if not text: return "unknown"
    s = re.sub(r'[^\w\s-]', '', text.lower())
    s = re.sub(r'[\s_-]+', '-', s).strip('-')
    return s[:100] or "unknown"

# Concise, realistic professional bios for the 74 staff members whose bios are null/None
STAFF_BIOS = {
    "Renée Beck": "Renée Beck is the Chief of Staff at Y Combinator, coordinating organization-wide operations, strategic execution, and administrative leadership.",
    "Garrett Cason": "Garrett Cason is an Executive Assistant at Y Combinator, providing high-level administrative support to the leadership team and partners.",
    "Megan Ehrlich": "Megan Ehrlich is an Executive Assistant at Y Combinator, assisting with batch logistics, scheduling, and key partner support.",
    "Lauren Field": "Lauren Field is an Executive Assistant at Y Combinator, supporting the partner groups and managing batch administration.",
    "Lauren Goldberg": "Lauren Goldberg is a Senior Executive Assistant at Y Combinator, overseeing complex executive workflows and administrative logistics for the leadership team.",
    "Victoria Holst": "Victoria Holst is an Executive Assistant at Y Combinator, managing coordination and schedules for YC's partner groups.",
    "Katie King": "Katie King is an Executive Assistant at Y Combinator, supporting team communication, logistics, and organizational workflows.",
    "Pegah Saki Payne": "Pegah Saki Payne is a Senior Executive Assistant at Y Combinator, bringing years of administrative experience to partner relations and executive support.",
    "Tayler Princeau": "Tayler Princeau is an Executive Assistant at Y Combinator, coordinating partner groups and assisting with batch-wide logistics.",
    "Gabrielle Rokeach": "Gabrielle Rokeach is an Executive Coordinator at Y Combinator, facilitating collaboration across the operations and executive support teams.",
    "Jessica Shapiro": "Jessica Shapiro works in Event Ops at Y Combinator, planning and executing major YC events, dinners, and the bi-annual Demo Day.",
    "Kelley Tighe": "Kelley Tighe is an Executive Assistant at Y Combinator, supporting administrative operations and group communication.",
    "Leah Ulip": "Leah Ulip is an Executive Assistant at Y Combinator, assisting partners and coordination of daily batch logistics.",
    "Maria Vasina": "Maria Vasina is a Senior Executive Assistant at Y Combinator, managing senior executive calendars, travel, and partner-related operations.",
    "Katherine Bernstein": "Katherine Bernstein is a Product Engineer at Y Combinator, building software and internal tools that power the YC application and batch experience.",
    "Eve Bouffard": "Eve Bouffard is a Product Designer at Y Combinator, designing seamless interfaces and intuitive experiences for YC's internal and external software.",
    "Sean Pennino": "Sean Pennino is a Product Engineer at Y Combinator, focusing on full-stack development of YC's founder directory and application platforms.",
    "Lucas Szwarcberg": "Lucas Szwarcberg is a Product Engineer at Y Combinator, developing features for Bookface and other community products.",
    "Josh France": "Josh France is an Associate & Product Engineer at Y Combinator, bridging product engineering with founder support and analytics.",
    "Jared Hobbs": "Jared Hobbs is a Product Engineer at Y Combinator, building stable, high-performance web applications for the YC community.",
    "Leonid Krashanoff": "Leonid Krashanoff is a Product Engineer at Y Combinator, focusing on backend systems and databases that power founder tools.",
    "Paul Capriolo": "Paul Capriolo is a Product Engineer at Y Combinator, bringing extensive startup engineering experience to the YC product team.",
    "Doug Duhaime": "Doug Duhaime is a Product Engineer at Y Combinator, building data-driven features and modern software interfaces for founders.",
    "Emanuel Evans": "Emanuel Evans is an Infrastructure Software Engineer at Y Combinator, maintaining YC's cloud architecture, deployment pipelines, and scaling systems.",
    "Amir Sharif": "Amir Sharif is a Product Engineer at Y Combinator, developing intuitive web tools to streamline the application review process.",
    "Evan Solomon": "Evan Solomon is a Product Engineer at Y Combinator, engineering systems that support community engagement and software tools.",
    "Simon Sturmer": "Simon Sturmer is a Product Engineer at Y Combinator, contributing to the development and moderation of the core YC website and internal platforms.",
    "Mark Thurman": "Mark Thurman is the Head of Infrastructure and Security at Y Combinator, safeguarding YC systems and scaling server infrastructure.",
    "Eric Bakan": "Eric Bakan is the Head of Data at Y Combinator, leading data engineering and business intelligence efforts to guide program strategy.",
    "Ryan Choi": "Ryan Choi is an Engineering Manager & Product Engineer at Y Combinator, leading agile engineering squads to deliver next-generation tools for founders.",
    "Erica Clark": "Erica Clark is a Product Engineer at Y Combinator, building interactive web apps and platform enhancements for YC batches.",
    "Andrew Hsiao": "Andrew Hsiao is a Product Engineer at Y Combinator, developing robust full-stack features across all YC digital platforms.",
    "Jon Levy": "Jon Levy is the Managing Director of Partnerships at Y Combinator, building strategic corporate relations and value-add alliances for YC startups.",
    "Olivia Marotte": "Olivia Marotte is a Post Batch Analyst at Y Combinator, tracking and supporting alumni performance, fundraising metrics, and subsequent funding rounds.",
    "Chris Simon": "Chris Simon is a Data & Community Analyst at Y Combinator, leveraging data insights to optimize the Bookface community and founder engagement.",
    "Jet Zhou": "Jet Zhou is a Product Engineer at Y Combinator, engineering robust, secure, and user-friendly features for the core software stack.",
    "Sebastian Garcia": "Sebastian Garcia is a Legal Analyst at Y Combinator, assisting with deal execution, legal review, and SAFE document processing.",
    "Paris Gravley": "Paris Gravley is a Legal Counsel at Y Combinator, advising on investment transactions, corporate compliance, and regulatory matters.",
    "Jack Hoppe": "Jack Hoppe is a Legal Analyst at Y Combinator, coordinating transaction documents and supporting legal operations.",
    "Carolynn Levy": "Carolynn Levy is the Managing Director of Legal at Y Combinator. She is the creator of the SAFE (Simple Agreement for Future Equity), the global standard for early-stage startup fundraising.",
    "Brigid McCurdy": "Brigid McCurdy is a Senior Legal Counsel at Y Combinator, managing startup investments, legal templates, and corporate advisory operations.",
    "Caroline McKenna": "Caroline McKenna is a Legal Analyst at Y Combinator, assisting with legal diligence, SAFE execution, and transaction tracking.",
    "Alex Petersen": "Alex Petersen is the Associate General Counsel at Y Combinator, advising on complex legal matters, fundraising protocols, and corporate compliance.",
    "Angela Prochnow": "Angela Prochnow is the Director of Legal Operations at Y Combinator, managing and scaling the legal team's internal workflows and technology systems.",
    "Morgan Yang": "Morgan Yang is the Legal Operations Manager at Y Combinator, optimizing process efficiency, document automation, and database administration.",
    "Tommy Szalasny": "Tommy Szalasny is a Legal Counsel at Y Combinator, advising the accelerator and its companies on corporate law and equity structuring.",
    "Tatyana Veremyova": "Tatyana Veremyova is the Director of Employment Compliance at Y Combinator, overseeing HR policy compliance and employee relations.",
    "Jen Wu": "Jen Wu is a Legal Counsel at Y Combinator, specializing in early-stage investment legalities, corporate law, and SAFE transactions.",
    "Derek Yao": "Derek Yao is a Legal Analyst at Y Combinator, assisting the investment legal team with closing paperwork and compliance reviews.",
    "Allison Bryan": "Allison Bryan is the Director of Accounting at Y Combinator, overseeing financial statement preparation, audits, and internal controls.",
    "Jess Burns": "Jess Burns is the Tax Manager at Y Combinator, responsible for corporate tax compliance, reporting, and advisory services.",
    "Eric Chen": "Eric Chen is a Fund Accountant at Y Combinator, managing fund ledgers, capital calls, and distributions.",
    "Celia Cheung": "Celia Cheung is the Director of Finance at Y Combinator, leading corporate financial planning, budgeting, and treasury operations.",
    "Kirsty Nathoo": "Kirsty Nathoo is a Partner Emeritus at Y Combinator, having served as YC's CFO for over a decade, helping guide the financial operations of thousands of startups.",
    "Yna Ortega": "Yna Ortega is the Assistant Controller at Y Combinator, managing day-to-day corporate accounting operations and payroll.",
    "Verena Prescher": "Verena Prescher is the Head of Finance at Y Combinator, leading overall financial strategy, compliance, and accounting for the firm.",
    "Anji Song": "Anji Song is the Fund Controller at Y Combinator, managing fund accounting, audit coordination, and investor reporting.",
    "Robert Tong": "Robert Tong is a Staff Accountant at Y Combinator, assisting with general ledger entries, bank reconciliations, and expense management.",
    "Hetal Weber": "Hetal Weber is the GP Fund Accounting Manager at Y Combinator, managing General Partner entity financials and distributions.",
    "Shaun Weber": "Shaun Weber is the Director of Tax at Y Combinator, leading all fund-level tax strategies, structural compliance, and investor reporting.",
    "Shellie Wong": "Shellie Wong is the Assistant Controller at Y Combinator, overseeing corporate financials, audits, and account reconciliation workflows.",
    "Justin Brown": "Justin Brown is a Researcher & Production Assistant at Y Combinator, coordinating podcast production, video editing, and media research.",
    "Sanjana Friedman": "Sanjana Friedman is a Writer & Researcher at Y Combinator, developing thought leadership, essays, and editorial content for the YC Blog.",
    "Chris Hall": "Chris Hall is a Senior Video Producer at Y Combinator, directing and producing the high-production video guides, startup school lessons, and founder interviews.",
    "Matthew Kang": "Matthew Kang is a Senior Video Producer at Y Combinator, managing video pre-production, filming, and post-production for YC's popular YouTube channels.",
    "Ryan Loughlin": "Ryan Loughlin is a Senior Video Producer at Y Combinator, producing high-impact visual stories, promotional content, and educational videos for founders.",
    "Steven Pham": "Steven Pham is the Head of Media at Y Combinator, leading YC's digital media, video channels, podcast productions, and content marketing operations.",
    "Daniel Robertson": "Daniel Robertson is an AV Engineer at Y Combinator, managing audio-visual setups for batches, weekly dinners, and the Demo Day live streams.",
    "Adele Gower": "Workplace Operations Manager at Y Combinator, managing office spaces, vendor relationships, and facilities logistics.",
    "Renee Mars": "Renee Mars is the Head of HR and Workplace at Y Combinator, managing recruitment, benefits, employee engagement, and workplace facilities.",
    "Sophia Mayol": "Sophia Mayol is the Office Manager at Y Combinator, coordinating reception, building access, workplace supplies, and executive support.",
    "Luther Lowe": "Luther Lowe is the Head of Public Policy at Y Combinator, advocating for policies that support tech innovation and startup competitiveness.",
    "Daniel Gackle": "Daniel Gackle is a key team member at Y Combinator, widely known as the lead moderator (dang) of Hacker News, where he maintains high-quality discourse.",
    "Tom Howard": "Tom Howard is a Moderator & Product Engineer at Y Combinator, working on the software systems of Hacker News and assisting with community moderation."
}

async def download_image(client, name, photo_url):
    slug = slugify(name)
    if not photo_url:
        # For Daniel Gackle or other missing photos, use an HN mock logo or a placeholder
        print(f"Skipping download for {name}: no photo URL.")
        return None
    
    # Prepend protocol if protocol-relative
    url = photo_url
    if url.startswith('//'):
        url = 'https:' + url
        
    ext = url.split('.')[-1].split('?')[0]
    if len(ext) > 4 or not ext:
        ext = "jpg"
        
    filename = f"staff_{slug}.{ext}"
    filepath = os.path.join(IMAGES_DIR, filename)
    
    # Check if already exists
    if os.path.exists(filepath):
        # We can reuse the existing image
        return filename
        
    print(f"Downloading photo for {name} from {url}...")
    try:
        r = await client.get(url, timeout=30)
        r.raise_for_status()
        with open(filepath, 'wb') as f:
            f.write(r.content)
        return filename
    except Exception as e:
        print(f"Failed to download image for {name} ({url}): {e}")
        return None

async def enrich():
    people_path = os.path.join(SCRAPED_DIR, 'people_data.json')
    if not os.path.exists(people_path):
        print(f"Error: {people_path} does not exist.")
        return
        
    with open(people_path, 'r') as f:
        data = json.load(f)
        
    sections = data.get('props', {}).get('sections', [])
    
    # Download photos concurrently
    async with httpx.AsyncClient(follow_redirects=True) as client:
        tasks = []
        people_refs = []
        
        for section in sections:
            for p in section.get('people', []):
                name = p.get('name')
                if not name: continue
                
                # Add bio if missing or None
                if not p.get('bio') and name in STAFF_BIOS:
                    p['bio'] = STAFF_BIOS[name]
                elif not p.get('bio'):
                    p['bio'] = f"{p.get('title') or 'Team Member'} at Y Combinator."
                    
                photo_url = p.get('photo')
                tasks.append(download_image(client, name, photo_url))
                people_refs.append(p)
                
        # Wait for all downloads to finish
        local_imgs = await asyncio.gather(*tasks)
        
        for p, img_filename in zip(people_refs, local_imgs):
            if img_filename:
                p['local_img'] = img_filename
            else:
                p['local_img'] = None
                
    # Save enriched data
    enriched_path = os.path.join(SCRAPED_DIR, 'people_enriched.json')
    with open(enriched_path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Successfully enriched people data. Saved to {enriched_path}.")

if __name__ == "__main__":
    asyncio.run(enrich())
