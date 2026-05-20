import json
import os
import pathlib
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COMPANIES_ALL = os.path.join(BASE_DIR, 'scraped_data', 'companies.json')
COMPANIES_DETAILED = os.path.join(BASE_DIR, 'scraped_data', 'companies_final.json')
EXTRA_SECTIONS = os.path.join(BASE_DIR, 'scraped_data', 'extra_sections_enriched.json')
DEEP_SECTIONS = os.path.join(BASE_DIR, 'scraped_data', 'deep_sections_enriched.json')
ULTRA_SECTIONS = os.path.join(BASE_DIR, 'scraped_data', 'ultra_sections.json')

def slugify(text):
    if not text: return "unknown"
    s = re.sub(r'[^\w\s-]', '', text.lower())
    s = re.sub(r'[\s_-]+', '-', s).strip('-')
    return s[:100] or "unknown"

def get_unique_slug(model, text):
    base_slug = slugify(text)
    slug = base_slug
    count = 1
    while model.query.filter_by(slug=slug).first():
        slug = f"{base_slug}-{count}"
        count += 1
    return slug

def seed_database(db, Company, Founder):
    if Company.query.count() > 0:
        return
    
    if not os.path.exists(COMPANIES_ALL):
        return

    with open(COMPANIES_ALL, 'r') as f:
        all_data = json.load(f)

    detailed_map = {}
    if os.path.exists(COMPANIES_DETAILED):
        with open(COMPANIES_DETAILED, 'r') as f:
            detailed_data = json.load(f)
            for d in detailed_data:
                detailed_map[d['name']] = d

    for cdata in all_data:
        name = cdata['name']
        if not name: continue
        
        detailed = detailed_map.get(name, {})
        slug = get_unique_slug(Company, name)
        
        company = Company(
            name=name,
            batch=cdata.get('batch') or detailed.get('batch'),
            description=cdata.get('desc') or detailed.get('desc'),
            full_description=detailed.get('full_desc'),
            website=detailed.get('website') or cdata.get('href'),
            logo_url=cdata.get('logo') or detailed.get('logo'),
            local_logo=detailed.get('local_logo'),
            slug=slug
        )
        db.session.add(company)
        db.session.flush()

        for fdata in detailed.get('founders', []):
            f_slug = get_unique_slug(Founder, fdata['name'])
            founder = Founder(
                name=fdata['name'],
                title=fdata.get('title'),
                bio=fdata.get('bio'),
                image_url=fdata.get('img'),
                local_img=fdata.get('local_img'),
                slug=f_slug,
                company_id=company.id
            )
            db.session.add(founder)

    db.session.commit()
    print(f"Seeded {len(all_data)} companies.")

def seed_benchmark_users(db, User, bcrypt):
    if User.query.count() > 0:
        return
    
    users = [
        ('alice.j@test.com', 'password123'),
        ('bob.m@test.com', 'password123'),
        ('charlie.s@test.com', 'password123'),
        ('dana.w@test.com', 'password123')
    ]
    
    for email, password in users:
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(email=email, password=hashed_password)
        db.session.add(user)
    
    db.session.commit()
    print("Seeded benchmark users.")

def seed_extra_sections(db, FAQ, LibraryItem, BlogPost):
    if FAQ.query.count() > 0:
        return
    
    if not os.path.exists(EXTRA_SECTIONS):
        return

    with open(EXTRA_SECTIONS, 'r') as f:
        data = json.load(f)

    for item in data.get('faq', []):
        db.session.add(FAQ(question=item['q'], answer=item['a']))

    for item in data.get('library', []):
        slug = get_unique_slug(LibraryItem, item['title'])
        db.session.add(LibraryItem(title=item['title'], slug=slug, content=item.get('content', ''), url=item['href']))

    posts = data.get('blog_detailed', data.get('blog', []))
    for item in posts:
        slug = get_unique_slug(BlogPost, item['title'])
        db.session.add(BlogPost(
            title=item['title'], 
            slug=slug, 
            date=item.get('date'), 
            snippet=item.get('snippet', ''),
            content=item.get('content', '')
        ))

    db.session.commit()
    print("Seeded extra sections (FAQ, Library, Blog).")

def seed_deep_sections(db, Founder, Launch, LegalDocument):
    if Launch.query.count() > 0:
        return
    
    if not os.path.exists(DEEP_SECTIONS):
        return

    with open(DEEP_SECTIONS, 'r') as f:
        data = json.load(f)

    for item in data.get('founders', []) + data.get('people', []):
        f_slug = get_unique_slug(Founder, item['name'])
        existing = Founder.query.filter_by(name=item['name']).first() # Use name for matching
        if not existing:
            db.session.add(Founder(
                name=item['name'],
                title=item.get('title'),
                slug=f_slug,
                bio=item.get('bio', f"Founder of {item.get('company')}")
            ))
        else:
            # Update bio if the new one is better
            new_bio = item.get('bio')
            if new_bio and (not existing.bio or "Founder of" in existing.bio):
                existing.bio = new_bio
            if item.get('title'):
                existing.title = item.get('title')

    for item in data.get('launches', []):
        l_slug = get_unique_slug(Launch, item['title'])
        db.session.add(Launch(
            title=item['title'], 
            slug=l_slug, 
            tagline=item.get('tagline'), 
            content=item.get('content', ''),
            url=item.get('href')
        ))

    for item in data.get('documents', []):
        db.session.add(LegalDocument(title=item['title'], url=item.get('href')))

    db.session.commit()
    print("Seeded deep sections (Founders Directory, Launches, Documents).")

def seed_ultra_sections(db, StaticPage):
    if StaticPage.query.count() > 0:
        return
    
    if not os.path.exists(ULTRA_SECTIONS):
        return

    with open(ULTRA_SECTIONS, 'r') as f:
        data = json.load(f)

    titles = {
        "interviews": "YC Interview Guide",
        "partners": "YC Partners",
        "jobs": "Startup Jobs",
        "verify": "Verify Founders",
        "subscribe": "Newsletter",
        "cofounder": "Find a Co-Founder",
        "demoday": "Demo Day",
        "press": "Press",
        "contact": "Contact",
        "legal": "Legal",
        "software": "Software Careers",
        "rfs": "Requests for Startups",
        "investors": "For Investors",
        "people": "People at YC"
    }

    for slug, content in data.items():
        db.session.add(StaticPage(
            slug=slug,
            title=titles.get(slug, slug.capitalize()),
            content=content
        ))

    db.session.commit()
    print(f"Seeded {len(data)} ultra-deep sections.")
