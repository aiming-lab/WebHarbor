import json
import os
import pathlib

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
COMPANIES_ALL = os.path.join(BASE_DIR, 'scraped_data', 'companies.json')
COMPANIES_DETAILED = os.path.join(BASE_DIR, 'scraped_data', 'companies_final.json')
EXTRA_SECTIONS = os.path.join(BASE_DIR, 'scraped_data', 'extra_sections.json')
DEEP_SECTIONS = os.path.join(BASE_DIR, 'scraped_data', 'deep_sections.json')
ULTRA_SECTIONS = os.path.join(BASE_DIR, 'scraped_data', 'ultra_sections.json')

def seed_database(db, Company, Founder):
    if Company.query.count() > 0:
        return
    
    if not os.path.exists(COMPANIES_ALL):
        print(f"Warning: {COMPANIES_ALL} not found. Skipping company seeding.")
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
        slug = name.lower().replace(' ', '-').replace('/', '-').replace('.', '')
        
        base_slug = slug
        count = 1
        while Company.query.filter_by(slug=slug).first():
            slug = f"{base_slug}-{count}"
            count += 1

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
            founder = Founder(
                name=fdata['name'],
                title=fdata.get('title'),
                bio=fdata.get('bio'),
                image_url=fdata.get('img'),
                local_img=fdata.get('local_img'),
                company_id=company.id
            )
            db.session.add(founder)

    db.session.commit()
    print(f"Seeded {len(all_data)} companies.")

def seed_benchmark_users(db, User, bcrypt):
    if User.query.filter_by(email='alice.j@test.com').first():
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
        db.session.add(LibraryItem(title=item['title'], url=item['href']))

    for item in data.get('blog', []):
        db.session.add(BlogPost(title=item['title'], date=item.get('date'), snippet=item.get('snippet')))

    db.session.commit()
    print("Seeded extra sections (FAQ, Library, Blog).")

def seed_deep_sections(db, Founder, Launch, LegalDocument):
    if Launch.query.count() > 0:
        return
    
    if not os.path.exists(DEEP_SECTIONS):
        return

    with open(DEEP_SECTIONS, 'r') as f:
        data = json.load(f)

    for item in data.get('founders', []):
        existing = Founder.query.filter_by(name=item['name']).first()
        if not existing:
            db.session.add(Founder(
                name=item['name'],
                title=item.get('title'),
                bio=f"Founder of {item.get('company')}"
            ))

    for item in data.get('launches', []):
        db.session.add(Launch(title=item['title'], tagline=item.get('tagline'), url=item.get('href')))

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
        "software": "Software Careers"
    }

    for slug, content in data.items():
        db.session.add(StaticPage(
            slug=slug,
            title=titles.get(slug, slug.capitalize()),
            content=content
        ))

    db.session.commit()
    print(f"Seeded {len(data)} ultra-deep sections.")
