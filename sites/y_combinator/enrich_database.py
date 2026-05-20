import json
import os
import sys
from app import app, db, Company, Founder

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SCRAPED_DIR = os.path.join(BASE_DIR, 'scraped_data')

def slugify(text):
    import re
    if not text: return "unknown"
    s = re.sub(r'[^\w\s-]', '', text.lower())
    s = re.sub(r'[\s_-]+', '-', s).strip('-')
    return s[:100] or "unknown"

def enrich():
    with app.app_context():
        # 1. Process Companies
        companies_path = os.path.join(SCRAPED_DIR, 'algolia_results.json')
        if os.path.exists(companies_path):
            print("Processing companies...")
            with open(companies_path, 'r') as f:
                data = json.load(f)
                # hits are in data[1]['results'][0]['hits']
                hits = data[1]['results'][0]['hits']
                for hit in hits:
                    name = hit.get('name')
                    if not name: continue
                    slug = hit.get('slug') or slugify(name)
                    
                    existing = Company.query.filter_by(slug=slug).first()
                    if not existing:
                        existing = Company.query.filter_by(name=name).first()
                        
                    if not existing:
                        comp = Company(
                            name=name,
                            slug=slug,
                            batch=hit.get('batch'),
                            industry=hit.get('industry'),
                            description=hit.get('one_liner'),
                            full_description=hit.get('long_description'),
                            website=hit.get('website'),
                            logo_url=hit.get('small_logo_thumb_url')
                        )
                        db.session.add(comp)
                    else:
                        # Update missing fields
                        if not existing.full_description:
                            existing.full_description = hit.get('long_description')
                        if not existing.description:
                            existing.description = hit.get('one_liner')
                        if not existing.logo_url:
                            existing.logo_url = hit.get('small_logo_thumb_url')
            db.session.commit()

        # 2. Process Founders
        founders_path = os.path.join(SCRAPED_DIR, 'founders_algolia.json')
        if os.path.exists(founders_path):
            print("Processing founders...")
            with open(founders_path, 'r') as f:
                data = json.load(f)
                # Hits might be in multiple results
                all_hits = []
                for res_group in data:
                    for res in res_group.get('results', []):
                        all_hits.extend(res.get('hits', []))
                
                for hit in all_hits:
                    first_name = hit.get('first_name')
                    last_name = hit.get('last_name')
                    if not first_name: continue
                    
                    name = f"{first_name} {last_name}" if last_name else first_name
                    slug = hit.get('url_slug') or slugify(name)
                    
                    existing = Founder.query.filter_by(slug=slug).first()
                    comp_slug = hit.get('company_slug')
                    company = None
                    if comp_slug:
                        company = Company.query.filter_by(slug=comp_slug).first()
                        
                    if not existing:
                        bio = hit.get('about')
                        if not bio and company:
                            bio = f"Founder at {company.name}"
                        
                        founder = Founder(
                            name=name,
                            slug=slug,
                            title=hit.get('current_title'),
                            bio=bio,
                            image_url=hit.get('avatar_thumb'),
                            company_id=company.id if company else None
                        )
                        db.session.add(founder)
                    else:
                        if not existing.bio and company:
                            existing.bio = f"Founder at {company.name}"
                        if not existing.image_url:
                            existing.image_url = hit.get('avatar_thumb')
                        if not existing.title:
                            existing.title = hit.get('current_title')
                        if not existing.company_id and company:
                            existing.company_id = company.id
            db.session.commit()

        # 3. Process People (YC Staff)
        people_path = os.path.join(SCRAPED_DIR, 'people_data.json')
        if os.path.exists(people_path):
            print("Processing YC staff...")
            with open(people_path, 'r') as f:
                data = json.load(f)
                sections = data.get('props', {}).get('sections', [])
                for section in sections:
                    for p in section.get('people', []):
                        name = p.get('name')
                        if not name: continue
                        slug = slugify(name)
                        
                        existing = Founder.query.filter_by(slug=slug).first()
                        bio = p.get('bio')
                        if not bio:
                            bio = f"{p.get('title')} at Y Combinator"
                            
                        if not existing:
                            staff = Founder(
                                name=name,
                                slug=slug,
                                title=p.get('title'),
                                bio=bio,
                                image_url=p.get('photo'),
                                company_id=None
                            )
                            db.session.add(staff)
                        else:
                            if not existing.bio:
                                existing.bio = bio
            db.session.commit()

        # 4. Integrate Top Founder Bios (from scraping)
        top_bios_path = os.path.join(BASE_DIR, 'top_founder_bios.json')
        if os.path.exists(top_bios_path):
            print("Integrating top founder bios...")
            with open(top_bios_path, 'r') as f:
                top_bios = json.load(f)
                for f_slug, info in top_bios.items():
                    founder = Founder.query.filter_by(slug=f_slug).first()
                    if founder:
                        if info.get('bio'):
                            founder.bio = info.get('bio')
                        if info.get('image_url'):
                            founder.image_url = info.get('image_url')
            db.session.commit()

    print("Enrichment complete!")

if __name__ == "__main__":
    enrich()
