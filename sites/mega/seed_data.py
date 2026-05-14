"""Deterministic seed data for the MEGA mirror."""
import json
from datetime import datetime

from app import (
    CloudItem, Download, HelpArticle, PaymentMethod, Plan, ProductPage,
    SubscriptionOrder, SupportTicket, User, VaultItem, db, slugify
)

PASSWORD = "TestPass123!"
SEED_DATE = "2026-05-12"


def dumps(value):
    return json.dumps(value, sort_keys=True)


def seed_database():
    if Plan.query.count() > 0:
        return

    plans = [
        ("Free", "free", "individual", "storage", 0, 0, 0.02, 0.10, 1, 0, 0, 0, False,
         "Start with encrypted storage",
         "A no-cost account for basic encrypted storage, sharing, and testing MEGA apps.",
         ["20 GB starting storage", "Encrypted file sharing", "Mobile and desktop apps", "Basic transfer quota"], ["Transfer quota is limited"]),
        ("Pro Lite", "pro-lite", "individual", "storage", 5.49, 54.99, 0.40, 1.00, 1, 5, 1, 0, False,
         "Extra space for everyday files",
         "A compact plan for personal documents, phone photos, and a small password vault.",
         ["400 GB storage", "1 TB transfer", "MEGA Pass included", "VPN on 5 devices"], ["Best for one person"]),
        ("Pro I", "pro-i", "individual", "storage", 10.99, 109.99, 2.00, 2.00, 1, 10, 1, 0, True,
         "More room for photos and projects",
         "Balanced encrypted cloud storage with enough transfer for active personal workflows.",
         ["2 TB storage", "2 TB transfer", "10 VPN devices", "Password manager", "Priority email support"], []),
        ("Pro II", "pro-ii", "individual", "storage", 21.99, 219.99, 8.00, 8.00, 1, 10, 1, 0, False,
         "Large encrypted storage for creators",
         "A larger plan for video archives, client project files, and recurring backups.",
         ["8 TB storage", "8 TB transfer", "File versioning", "MEGA Pass", "MEGA VPN"], []),
        ("Pro III", "pro-iii", "individual", "storage", 32.99, 329.99, 16.00, 16.00, 1, 10, 1, 0, False,
         "Maximum personal capacity",
         "High-capacity encrypted storage for heavy archives and large media libraries.",
         ["16 TB storage", "16 TB transfer", "Large shared links", "Priority support", "Advanced recovery tools"], []),
        ("VPN Monthly", "vpn-monthly", "individual", "vpn", 3.99, 0, 0, 0, 1, 10, 0, 0, False,
         "Private browsing month to month",
         "Standalone VPN access with ad blocking, unsafe network detection, and a kill switch.",
         ["10 devices", "Unlimited VPN traffic", "Ad blocking", "Kill switch", "Automatic unsafe network protection"], []),
        ("VPN Annual", "vpn-annual", "individual", "vpn", 2.34, 28.08, 0, 0, 1, 10, 0, 0, True,
         "Lowest VPN monthly equivalent",
         "Annual VPN access for users who want the lowest monthly equivalent price.",
         ["10 devices", "Unlimited traffic", "Always-on protection", "City-level locations", "Ad blocking"], ["Charged annually"]),
        ("Pass Free", "pass-free", "individual", "pass", 0, 0, 0, 0, 1, 0, 1, 0, False,
         "Secure password storage",
         "MEGA Pass for a starter vault with encrypted login storage.",
         ["Encrypted vault", "Password generator", "Autofill", "Device sync"], ["Limited sharing"]),
        ("Pass Pro", "pass-pro", "individual", "pass", 2.99, 29.99, 0, 0, 1, 0, 1, 0, False,
         "Unlimited password protection",
         "Full MEGA Pass with unlimited vault entries, secure notes, and sharing.",
         ["Unlimited passwords", "Secure notes", "Password health", "One-time password support", "Vault export"], []),
        ("Business Starter", "business-starter", "business", "business", 15.00, 150.00, 3.00, 3.00, 3, 10, 3, 0, False,
         "Small team storage",
         "A team plan for startups that need encrypted storage, user management, and shared folders.",
         ["3 users included", "3 TB pooled storage", "Admin dashboard", "Shared folders", "Team chat"], []),
        ("Business Pro", "business-pro", "business", "business", 24.00, 240.00, 10.00, 10.00, 5, 10, 5, 0, True,
         "Team collaboration with room to grow",
         "Expanded team storage with stronger administration, compliance exports, and priority support.",
         ["5 users included", "10 TB pooled storage", "User management dashboard", "External collaborator controls", "Priority support"], []),
        ("Business Enterprise", "business-enterprise", "business", "business", 40.00, 400.00, 25.00, 25.00, 10, 10, 10, 0, False,
         "Large-team governance",
         "Encrypted collaboration for larger teams with advanced support and account governance.",
         ["10 users included", "25 TB pooled storage", "Advanced account recovery", "Audit-ready exports", "Dedicated onboarding"], []),
        ("S4 Fixed Storage", "s4-fixed-storage", "business", "objectstorage", 19.99, 199.99, 3.00, 15.00, 1, 0, 0, 3, False,
         "Predictable S3-compatible storage",
         "Object storage for backups and media libraries with zero surprise egress on typical workloads.",
         ["3 TB base object storage", "S3-compatible API", "5x included egress guide", "Lifecycle-friendly archive use"], []),
        ("Pro Flexi", "pro-flexi", "business", "objectstorage", 16.00, 160.00, 3.00, 3.00, 1, 10, 1, 3, False,
         "Pay as you grow",
         "Flexible base storage and transfer for variable cloud workloads and S4 experiments.",
         ["3 TB base storage and transfer", "Additional TB billing", "MEGA VPN", "MEGA Pass", "Priority support"], ["Usage can vary monthly"]),
        ("S4 Media Vault", "s4-media-vault", "business", "objectstorage", 29.00, 290.00, 6.00, 18.00, 1, 0, 0, 6, False,
         "Media archive object storage",
         "A media-focused object storage plan for teams keeping large video libraries online.",
         ["6 TB object storage", "Media lifecycle workflows", "Preview-friendly archive structure", "Predictable monthly billing"], []),
        ("S4 Analytics Reserve", "s4-analytics-reserve", "business", "objectstorage", 34.00, 340.00, 8.00, 12.00, 1, 0, 0, 8, False,
         "Data lake reserve capacity",
         "Object storage for analytics exports and model training sets with steady retention needs.",
         ["8 TB object storage", "Analytics export staging", "Retention labels", "Team access policies"], []),
        ("S4 Developer Sandbox", "s4-developer-sandbox", "business", "objectstorage", 9.00, 90.00, 1.00, 2.00, 1, 0, 0, 1, False,
         "Small object storage sandbox",
         "A lower-capacity object storage plan for development tests and automation rehearsals.",
         ["1 TB object storage", "Test automation workflows", "Temporary datasets", "Developer-friendly setup"], []),
        ("S4 Enterprise Archive", "s4-enterprise-archive", "business", "objectstorage", 58.00, 580.00, 20.00, 30.00, 1, 0, 0, 20, False,
         "Long-retention archive storage",
         "Large object storage capacity for compliance archives and disaster recovery copies.",
         ["20 TB object storage", "Archive policy planning", "Disaster recovery copies", "Priority onboarding"], []),
        ("Backup Reserve", "backup-reserve", "business", "objectstorage", 12.00, 120.00, 2.00, 4.00, 1, 0, 0, 2, False,
         "Backup-focused storage pool",
         "A near-miss storage option for backup teams that need object-style retention but less transfer.",
         ["2 TB retained backups", "Desktop backup staging", "Version history review", "Recovery planning"], []),
    ]
    for row in plans:
        db.session.add(Plan(
            name=row[0], slug=row[1], audience=row[2], category=row[3],
            monthly_price=row[4], yearly_price=row[5], storage_tb=row[6],
            transfer_tb=row[7], users_included=row[8], vpn_devices=row[9],
            pass_accounts=row[10], s4_base_tb=row[11], popular=row[12],
            tagline=row[13], description=row[14], features=dumps(row[15]),
            caveats=dumps(row[16]), image="logo-mega.png",
        ))

    pages = [
        ("Cloud storage", "storage", "Products", "Securely store, manage, and share encrypted files online.", "Feature-1.png",
         ["Encrypted storage by default", "Fast downloads and uploads", "Mobile and desktop access", "File and folder links"]),
        ("Business", "business", "Business", "Encrypted team storage, user management, and project collaboration.", "Business-img-1.png",
         ["Team dashboard", "Shared folders", "Video meetings", "Client-safe file exchange"]),
        ("Object storage", "objectstorage", "Products", "S3-compatible storage for backup, media, analytics, and automation.", "True-Nas-Community-edition.png",
         ["S3-compatible API", "Predictable pricing", "Backup and archiving", "Media and ML workloads"]),
        ("VPN", "vpn", "Products", "Private browsing with ad blocking, unsafe network detection, and a kill switch.", "MEGA-VPN_Locations.png",
         ["10 devices", "Unlimited VPN traffic", "Unsafe network detection", "Kill switch"]),
        ("Password manager", "pass", "Products", "Encrypted password vault, autofill, generator, and one-time-password support.", "pass-hero.png",
         ["Encrypted vault", "Password health", "OTP support", "Secure notes"]),
        ("Transfer.it", "transfer-it", "Products", "Fast, simple, and secure file transfers powered by MEGA.", "transfer-it-hero-1.png",
         ["Generous limits", "Frictionless performance", "Link-based transfers", "MEGA account controls"]),
        ("Desktop app", "desktop", "Apps", "Windows, macOS, and Linux app for sync, backup, and transfer control.", "DA-img-2.png",
         ["Selective sync", "Backup folders", "Transfer manager", "Windows, macOS, Linux"]),
        ("Mobile apps", "mobile", "Apps", "Android and iOS cloud storage, camera uploads, scan, print, and offline files.", "Mobile-img-2.png",
         ["Camera uploads", "Offline access", "Document scan", "Slideshow viewing"]),
        ("MEGA CMD", "cmd", "Apps", "Command-line access to MEGA services for automation and advanced workflows.", "20230215_Mega_icons_upd_00017.png",
         ["Interactive shell", "Scriptable commands", "QNAP and Synology packages", "Build documentation"]),
        ("Sync", "syncing", "Features", "Automated synchronisation across devices and shared folders.", "Sync-img-1-1.png",
         ["Shared-folder sync", "Selective sync", "Version handling", "Secure transport"]),
        ("Backup", "megabackup", "Features", "Back up and recover important files with visibility across devices.", "Backup-2.png",
         ["Device backups", "Recovery history", "Ransomware recovery", "Phone photo backups"]),
        ("Share", "share", "Features", "Secure sharing with links, contacts, upload folders, and chat collaboration.", "share-1.png",
         ["Folder sharing", "Upload requests", "Chat collaboration", "Link controls"]),
        ("Security and privacy", "security", "Company", "Zero-knowledge encryption, recovery keys, 2FA, and transparent security design.", "Sec-img-1.png",
         ["End-to-end encryption", "Recovery key", "2FA", "Ransomware recovery"]),
        ("Developers", "developers", "Resources", "MEGA SDK and developer documentation for integrating MEGA client access.", "20230215_Mega_icons_upd_00003.png",
         ["Core SDK", "C++ client engine", "API access model", "Open source references"]),
        ("Freelancers", "freelancers", "Solutions", "Encrypted storage and transfer workflows for independent professionals.", "MEGA-icon-cloud.png",
         ["Client delivery", "Password vault", "Project backups", "Shared folders"]),
        ("Small business", "small-business", "Solutions", "Storage, backups, chat, and external collaboration for small teams.", "Business-img-3.png",
         ["Admin dashboard", "Team folders", "Backup policies", "Client uploads"]),
        ("Media files", "media-files", "Solutions", "Large media previews, archives, delivery links, and encrypted collaboration.", "Media-and-video-storage.png",
         ["Video archive", "Preview links", "Transfer capacity", "Version recovery"]),
    ]
    for order, (title, slug, section, summary, image, highlights) in enumerate(pages, 1):
        body = (
            f"{title} on MEGA focuses on private, encrypted workflows. "
            f"The mirror keeps the same navigation and product framing while adding local forms and account data for benchmark tasks."
        )
        faq = [
            {"q": f"Who is {title} for?", "a": summary},
            {"q": "Does this work with a MEGA account?", "a": "Yes. Authenticated routes in this mirror persist to the local SQLite database."},
        ]
        db.session.add(ProductPage(
            title=title, slug=slug, section=section, summary=summary, body=body,
            hero_image=image, highlights=dumps(highlights), faq=dumps(faq), nav_order=order
        ))

    downloads = [
        ("Desktop", "Windows", "MEGAsyncSetup64.exe", "5.12.1", 83.4, "x64", True, "Windows-1.png", "Sync, backup, and transfer manager for Windows."),
        ("Desktop", "Windows", "MEGAcmdSetup64.exe", "1.7.2", 57.2, "x64", False, "Windows-2.png", "Command-line package for Windows automation."),
        ("Desktop", "Windows", "MEGAsyncSetup32.exe", "5.12.1", 79.2, "x86", False, "Windows-1.png", "Legacy Windows sync package for 32-bit systems."),
        ("Desktop", "Windows", "MEGAsyncARM64.exe", "5.12.1", 81.6, "ARM64", False, "Windows-2.png", "Windows ARM64 sync package."),
        ("CMD", "Windows", "MEGAcmdPortable.zip", "1.7.2", 49.8, "Portable x64", False, "20230215_Mega_icons_upd_00017.png", "Portable command-line archive for Windows automation."),
        ("Pass", "Windows", "MEGAPassDesktop.exe", "1.12.4", 58.6, "x64", False, "password-icon.png", "Desktop password manager companion for Windows."),
        ("Desktop", "macOS", "MEGAsync-macOS.dmg", "5.12.1", 96.1, "Apple silicon + Intel", True, "MacOS-1.png", "Desktop sync and backup for macOS."),
        ("Desktop", "Linux", "megasync-x86_64.deb", "5.12.1", 72.8, "Debian/Ubuntu", True, "DA-img-3.png", "Linux desktop client for sync and transfer control."),
        ("Mobile", "Android", "MEGA Android app", "14.8", 64.0, "ARM", True, "Android-1.png", "Camera uploads, offline files, and document scan."),
        ("Mobile", "iOS", "MEGA iOS app", "14.8", 71.5, "Universal", True, "iOS-1.png", "Camera uploads, slideshow, live text detection, and offline files."),
        ("VPN", "Windows", "MEGAvpnSetup64.exe", "2.3.0", 41.2, "x64", True, "Picture-3vpn.png", "MEGA VPN with kill switch and ad blocking."),
        ("VPN", "macOS", "MEGA VPN.dmg", "2.3.0", 46.5, "Apple silicon + Intel", True, "MEGA-VPN_Locations.png", "VPN client for macOS."),
        ("VPN", "Android", "MEGA VPN Android", "2.3.0", 38.2, "ARM", False, "Android-2.png", "Mobile VPN protection."),
        ("VPN", "iOS", "MEGA VPN iOS", "2.3.0", 39.0, "Universal", False, "iOS-2.png", "iOS VPN protection."),
        ("Pass", "Chrome", "MEGA Pass Chrome extension", "1.12.4", 9.2, "Browser", True, "icon-Chrome.png", "Autofill and password vault extension."),
        ("Pass", "Firefox", "MEGA Pass Firefox extension", "1.12.4", 9.4, "Browser", False, "firefox_logo_platform.png", "Firefox extension for MEGA Pass."),
        ("Pass", "Edge", "MEGA Pass Edge extension", "1.12.4", 9.3, "Browser", False, "icon-Microsoft-Edge.png", "Edge extension for MEGA Pass."),
        ("CMD", "QNAP", "MEGAcmd_QNAP.qpkg", "1.7.2", 65.3, "NAS", False, "20230215_Mega_icons_upd_00017.png", "QNAP package for command automation."),
        ("CMD", "Synology", "MEGAcmd_Synology.spk", "1.7.2", 62.9, "NAS", False, "Synology-logo.png", "Synology package for command automation."),
    ]
    for product, platform, package, version, size, architecture, recommended, icon, notes in downloads:
        db.session.add(Download(
            product=product, platform=platform, package_name=package, version=version,
            size_mb=size, release_date=SEED_DATE, architecture=architecture,
            checksum=f"sha256-{slugify(package)[:18]}-webharbor", notes=notes,
            recommended=recommended, icon=icon
        ))

    article_specs = [
        ("Account", "Save your recovery key", "Your recovery key is the safety net for a forgotten password. Download it, store it offline, and do not share it with support or teammates.", "recovery key account password backup"),
        ("Account", "Enable two-factor authentication", "Two-factor authentication adds a second verification step. Use an authenticator app and keep backup codes outside the vault.", "2fa authenticator security login"),
        ("Account", "Change account email address", "Verify the new email address before removing the old one. Team admins should confirm the user still appears in the dashboard.", "email profile account"),
        ("Cloud drive", "Create a shared folder", "Use folder sharing when collaborators need ongoing access. Choose read-only, read-and-write, or full access depending on the project.", "shared folder permissions collaboration"),
        ("Cloud drive", "Create a file link", "File links can be created from the detail menu. Add a decryption key only when the recipient is trusted.", "file link share key"),
        ("Cloud drive", "Find large files", "Sort by size or search by extension to identify large media archives before changing plans.", "large files storage quota search"),
        ("Cloud drive", "Recover deleted files", "Recovery depends on file versioning and retention. Check the backup source and modified date before restoring.", "restore deleted file ransomware"),
        ("Sync", "Set up selective sync", "Selective sync keeps chosen folders on each device while leaving the rest in the cloud.", "selective sync desktop folders"),
        ("Sync", "Resolve sync conflicts", "Conflicted copies show the device and timestamp. Keep the latest verified edit and archive the extra copy.", "sync conflict desktop"),
        ("Backup", "Add a desktop backup", "Choose folders from the desktop app, name the backup source, and confirm it appears in Cloud drive.", "backup desktop source"),
        ("Backup", "Recover from ransomware", "Disconnect the affected device, review version history, and restore a clean version from before the incident.", "ransomware recovery version history"),
        ("Mobile", "Turn on camera uploads", "Camera uploads can include photos and videos. Confirm the destination folder and mobile data preference.", "camera uploads mobile photos"),
        ("Mobile", "Make files available offline", "Mark files for offline access from the mobile app; they remain encrypted on the device.", "offline access mobile"),
        ("Pass", "Import passwords from a browser", "Export a CSV from the browser, import it into MEGA Pass, then delete the CSV after confirming entries.", "password import browser csv"),
        ("Pass", "Use one-time passwords", "MEGA Pass can store one-time-password seeds for accounts that support two-factor authentication.", "otp password manager two factor"),
        ("Pass", "Find weak passwords", "Password health highlights reused or weak entries. Update the oldest weak entries first.", "weak password health reused"),
        ("VPN", "Use automatic VPN on unsafe networks", "Automatic protection detects untrusted networks and starts the VPN without another click.", "unsafe network automatic vpn"),
        ("VPN", "Understand the kill switch", "The kill switch blocks internet traffic if the VPN tunnel drops, preventing accidental exposure.", "kill switch vpn privacy"),
        ("VPN", "Choose a VPN city", "Pick the nearest city for speed or a specific region for a location-sensitive workflow.", "vpn city location"),
        ("Object storage", "Estimate S4 costs", "S4 planning starts with stored terabytes and egress. Included egress is based on typical usage ratios.", "s4 object storage egress cost"),
        ("Object storage", "Connect S3 tools", "Use S3-compatible access keys with tools such as Rclone, Duplicacy, TrueNAS, and S3 Browser.", "s3 compatible rclone truenas duplicacy"),
        ("Object storage", "Plan backup and archiving", "Object storage works well for long-term archives, disaster recovery, and media libraries.", "backup archiving s4"),
        ("Business", "Invite a team member", "Admins invite users from the team dashboard and assign access to shared folders after acceptance.", "team invite admin dashboard"),
        ("Business", "Remove external collaborator access", "Review shared folders, remove the collaborator, and rotate links if they had download access.", "external collaborator remove access"),
        ("Business", "Review team storage usage", "The dashboard separates pooled storage, transfer, and backup sources so admins can plan upgrades.", "team storage usage dashboard"),
        ("Business", "Export a compliance summary", "Export account, device, and shared-folder summaries for internal audit workflows.", "compliance export audit"),
        ("Transfer.it", "Send a large transfer", "Transfer.it is for simple link-based delivery when a persistent shared folder is unnecessary.", "large transfer link"),
        ("Transfer.it", "Manage transfer expiry", "Set an expiry date for sensitive transfers and resend a new link if the recipient misses it.", "transfer expiry link"),
        ("Downloads", "Pick the right desktop package", "Windows users usually need MEGAsyncSetup64.exe; automation users may need MEGAcmdSetup64.exe.", "desktop windows cmd package"),
        ("Downloads", "Install CMD on NAS", "QNAP and Synology packages are available for NAS automation workflows.", "cmd qnap synology nas"),
        ("Security", "Understand zero-knowledge encryption", "MEGA cannot reset an account password without the user's recovery key because file keys are controlled by the user.", "zero knowledge encryption privacy"),
        ("Security", "Share safely with decryption keys", "Treat decryption keys like passwords and send them through a separate channel when needed.", "decryption key share"),
        ("Developers", "Use the MEGA SDK", "The SDK provides the client access engine and keeps encryption behavior consistent across integrations.", "sdk developers client engine"),
        ("Developers", "Automate with MEGA CMD", "MEGA CMD supports scripted uploads, downloads, sync checks, and account status commands.", "cmd automate commands"),
        ("Billing", "Switch from monthly to yearly", "Yearly billing uses the annual price and can reduce the monthly equivalent for eligible plans.", "billing yearly monthly savings"),
        ("Billing", "Update a payment method", "Add the new card, mark it default, then remove the old card after the next successful renewal.", "payment method card billing"),
    ]
    for category, title, body, terms in article_specs:
        db.session.add(HelpArticle(
            category=category, title=title, slug=slugify(title), body=body,
            applies_to=category, difficulty="standard", updated_at=SEED_DATE,
            related_terms=terms
        ))

    db.session.commit()


def seed_benchmark_users():
    if User.query.filter_by(email="alice.j@test.com").first():
        return

    plan_by_slug = {p.slug: p for p in Plan.query.all()}
    users = [
        ("alice_j", "alice.j@test.com", "Alice Johnson", "Riverlight Studio", "Creative Director", "pro-ii", 5240, 1810, True, True),
        ("bob_c", "bob.c@test.com", "Bob Chen", "Northstar Analytics", "Data Engineer", "pro-flexi", 2320, 980, True, False),
        ("carol_d", "carol.d@test.com", "Carol Davis", "Cedar Legal Group", "Operations Manager", "business-pro", 7710, 2450, False, True),
        ("david_k", "david.k@test.com", "David Kim", "David Kim Photo", "Freelancer", "pro-i", 1180, 540, True, True),
    ]
    user_objs = {}
    for username, email, display, company, role, plan_slug, storage, transfer, two_factor, recovery in users:
        user = User(
            username=username, email=email, display_name=display, company=company, role=role,
            phone="317-555-0142", address_line1="415 Market Street", address_line2="Suite 8",
            city="Indianapolis", state="IN", postal_code="46204", country="United States",
            language="English", timezone="America/Indiana/Indianapolis",
            plan_id=plan_by_slug[plan_slug].id, storage_used_gb=storage, transfer_used_gb=transfer,
            two_factor_enabled=two_factor, recovery_key_saved=recovery
        )
        user.set_password(PASSWORD)
        db.session.add(user)
        user_objs[email] = user
    db.session.flush()

    for user in user_objs.values():
        db.session.add_all([
            PaymentMethod(user_id=user.id, label="Personal Visa", card_type="Visa", last4="4242", exp_month=12, exp_year=2028, billing_country="United States", is_default=True),
            PaymentMethod(user_id=user.id, label="Backup Mastercard", card_type="Mastercard", last4="1881", exp_month=9, exp_year=2029, billing_country="United States", is_default=False),
        ])

    alice = user_objs["alice.j@test.com"]
    bob = user_objs["bob.c@test.com"]
    carol = user_objs["carol.d@test.com"]
    david = user_objs["david.k@test.com"]

    def add_files(user, specs):
        for name, folder, item_type, size, modified, sync_status, shared, favorite, backup, summary in specs:
            db.session.add(CloudItem(
                user_id=user.id, name=name, slug=slugify(f"{user.username}-{folder}-{name}"),
                item_type=item_type, folder=folder, extension=(name.rsplit(".", 1)[-1].lower() if "." in name else ""),
                size_mb=size, modified_at=modified, sync_status=sync_status, shared_with=shared,
                share_link=(f"https://mega.nz/file/{slugify(name)[:10].upper()}#seeded" if shared else ""),
                favorite=favorite, backup_source=backup, content_summary=summary
            ))

    common_distractors = [
        ("Travel itinerary.pdf", "/Documents", "file", 3.4, "2026-04-22", "Synced", "", False, "", "Personal itinerary and bookings."),
        ("Old export passwords.csv", "/Security", "file", 0.7, "2025-10-02", "Synced", "", False, "", "Legacy password export retained for audit only."),
        ("Camera Uploads 2026.zip", "/Backups/Phone", "file", 884.0, "2026-05-01", "Synced", "david.k@test.com", False, "iPhone 15 Pro", "Photo and video backup archive."),
        ("Shared client intake.docx", "/Client Vault", "file", 2.1, "2026-04-18", "Synced", "carol.d@test.com", True, "", "Client intake form and checklist."),
        ("Tax receipts archive.zip", "/Finance", "file", 76.4, "2026-03-18", "Synced", "", False, "", "Annual tax receipt package."),
        ("Conference slides.pptx", "/Documents", "file", 44.9, "2026-04-02", "Synced", "", False, "", "Presentation slides for conference talk."),
        ("Device backup summary.pdf", "/Backups", "file", 2.8, "2026-05-05", "Synced", "", False, "Desktop app", "Backup status exported from desktop app."),
        ("Shared media preview.mp4", "/Media Archive", "file", 520.0, "2026-04-25", "Synced", "alice.j@test.com", False, "", "Preview video shared with collaborators."),
        ("Project notes.txt", "/Projects", "file", 0.2, "2026-05-03", "Synced", "", False, "", "General project notes."),
        ("Recovery checklist.pdf", "/Security", "file", 1.5, "2026-04-10", "Synced", "", True, "", "Account recovery and incident-response checklist."),
    ]
    add_files(alice, [
        ("Brand refresh brief.pdf", "/Projects/Atlas", "file", 18.6, "2026-05-08", "Synced", "bob.c@test.com", True, "", "Creative brief for Atlas rebrand."),
        ("Atlas launch footage.mov", "/Media Archive", "file", 4380.0, "2026-05-06", "Synced", "bob.c@test.com, carol.d@test.com", False, "MacBook Pro", "Long-form 4K launch footage for Atlas."),
        ("Atlas social cuts.zip", "/Media Archive", "file", 1260.0, "2026-05-07", "Syncing", "bob.c@test.com", False, "MacBook Pro", "Compressed short clips for social launch."),
        ("Q2 invoice batch.xlsx", "/Finance", "file", 9.8, "2026-04-30", "Synced", "carol.d@test.com", True, "", "Quarterly invoices and payment status."),
        ("MEGA recovery key.pdf", "/Security", "file", 0.4, "2026-01-15", "Synced", "", True, "", "Account recovery key saved offline."),
        ("Client testimonials raw.wav", "/Media Archive", "file", 740.5, "2026-05-03", "Synced", "", False, "Studio NAS", "Audio interviews for testimonial edit."),
        ("Atlas b-roll selects.mov", "/Media Archive", "file", 980.0, "2026-05-05", "Synced", "", False, "MacBook Pro", "B-roll clips for Atlas launch."),
        ("Atlas color grade preview.mp4", "/Media Archive", "file", 610.0, "2026-05-04", "Synced", "bob.c@test.com", False, "MacBook Pro", "Compressed color grade preview."),
        ("Podcast sponsor reel.mov", "/Media Archive", "file", 1320.0, "2026-04-27", "Synced", "", False, "Studio NAS", "Sponsor reel export."),
        ("Product stills archive.zip", "/Media Archive", "file", 980.0, "2026-04-19", "Synced", "carol.d@test.com", False, "", "Product photography archive."),
        ("Iceland selects 01.zip", "/Photos/Iceland", "file", 1860.0, "2026-02-18", "Synced", "david.k@test.com", True, "iPhone 15 Pro", "Edited Iceland travel photos."),
        ("Iceland selects 02.zip", "/Photos/Iceland", "file", 1744.0, "2026-02-20", "Synced", "", False, "iPhone 15 Pro", "Alternate photo set."),
        ("Studio insurance policy.pdf", "/Documents", "file", 5.5, "2026-03-11", "Synced", "", False, "", "Business insurance policy."),
        ("Ransomware drill notes.md", "/Security", "file", 1.2, "2026-04-12", "Synced", "bob.c@test.com", False, "", "Recovery rehearsal and restore timings."),
        ("Atlas", "/", "folder", 0, "2026-05-08", "Synced", "bob.c@test.com", True, "", "Project folder."),
        ("Media Archive", "/", "folder", 0, "2026-05-06", "Synced", "bob.c@test.com, carol.d@test.com", False, "", "Video and audio media."),
    ] + common_distractors)
    add_files(bob, [
        ("warehouse telemetry.parquet", "/S4 Imports", "file", 920.0, "2026-05-10", "Synced", "carol.d@test.com", False, "Pro Flexi S4", "Telemetry training data export."),
        ("S3 migration checklist.xlsx", "/S4 Imports", "file", 5.1, "2026-05-09", "Synced", "carol.d@test.com", True, "", "S3-compatible migration checklist."),
        ("rclone-config-redacted.txt", "/Automation", "file", 0.3, "2026-04-14", "Synced", "", False, "", "Rclone configuration with credentials removed."),
        ("quarterly model weights.bin", "/ML Models", "file", 3280.0, "2026-04-28", "Synced", "", False, "Linux workstation", "Model weights for quarterly forecast."),
        ("daily ingestion script.sh", "/Automation", "file", 0.1, "2026-05-11", "Synced", "", True, "", "MEGA CMD script for scheduled uploads."),
        ("backup manifest.json", "/Backups/NAS", "file", 2.2, "2026-05-11", "Synced", "", False, "Synology DS923+", "Backup manifest from NAS."),
    ] + common_distractors)
    add_files(carol, [
        ("2026 vendor contracts.zip", "/Legal", "file", 420.0, "2026-05-04", "Synced", "alice.j@test.com", True, "", "Signed vendor contract archive."),
        ("External collaborator review.xlsx", "/Team Admin", "file", 7.7, "2026-05-02", "Synced", "alice.j@test.com, bob.c@test.com", False, "", "External collaborator access review."),
        ("Compliance export May.csv", "/Team Admin", "file", 3.9, "2026-05-12", "Synced", "", True, "", "Team audit export."),
        ("Board meeting recording.mp4", "/Meetings", "file", 2160.0, "2026-04-26", "Synced", "", False, "Conference Room Mac", "Private meeting recording."),
        ("Client data retention policy.pdf", "/Legal", "file", 6.0, "2026-03-21", "Synced", "", False, "", "Retention policy for client files."),
        ("Team recovery key escrow.pdf", "/Security", "file", 1.1, "2026-01-08", "Synced", "", True, "", "Escrow record for admin recovery keys."),
    ] + common_distractors)
    add_files(david, [
        ("wedding edit final.mov", "/Client Delivery/Wedding", "file", 5120.0, "2026-05-09", "Synced", "alice.j@test.com", True, "Mac Studio", "Final wedding video export."),
        ("wedding edit trailer.mov", "/Client Delivery/Wedding", "file", 1180.0, "2026-05-08", "Synced", "", False, "Mac Studio", "Short trailer export."),
        ("print portfolio.zip", "/Portfolio", "file", 680.0, "2026-03-02", "Synced", "alice.j@test.com", True, "", "Portfolio print files."),
        ("client upload request list.xlsx", "/Client Delivery", "file", 1.8, "2026-05-01", "Synced", "", False, "", "Clients and upload request status."),
        ("Lightroom backup catalog.lrcat", "/Backups/Mac Studio", "file", 2420.0, "2026-04-29", "Synced", "", False, "Mac Studio", "Lightroom catalog backup."),
        ("MEGA Pass emergency kit.pdf", "/Security", "file", 0.6, "2026-02-12", "Synced", "", True, "", "Emergency vault recovery instructions."),
    ] + common_distractors)

    def add_vault(user, specs):
        for title, username, site_url, category, strength, changed, two_factor, notes in specs:
            db.session.add(VaultItem(
                user_id=user.id, title=title, slug=slugify(f"{user.username}-{title}"),
                username=username, site_url=site_url, category=category, strength=strength,
                last_changed=changed, two_factor=two_factor, notes=notes
            ))

    add_vault(alice, [
        ("Studio bank portal", "alice.j", "https://bank.example.com", "Finance", "Strong", "2026-04-03", True, "Used for invoice payments."),
        ("Old vendor FTP", "studio-old", "ftp://vendor.example.com", "Legacy", "Weak", "2024-11-12", False, "Replace before sending another media package."),
        ("Adobe admin", "alice@riverlight.example", "https://account.adobe.com", "Creative", "Strong", "2026-03-30", True, "Team license admin."),
        ("Client CMS", "alice_editor", "https://atlas.example.com", "Client", "Reused", "2025-07-09", False, "Shared during Atlas launch."),
    ])
    add_vault(bob, [
        ("AWS read-only", "bob.analytics", "https://console.aws.amazon.com", "Cloud", "Strong", "2026-02-18", True, "Read-only cost review."),
        ("Rclone test bucket", "bob-s4-test", "https://s4.mega.example", "Cloud", "Strong", "2026-05-03", True, "S4 test credentials."),
        ("Legacy Jenkins", "bob", "https://jenkins.example.com", "DevOps", "Weak", "2024-09-30", False, "Needs rotation."),
    ])
    add_vault(carol, [
        ("Payroll portal", "carol.ops", "https://payroll.example.com", "Finance", "Strong", "2026-01-18", True, "HR-only."),
        ("Vendor contract room", "carol_d", "https://contracts.example.com", "Legal", "Reused", "2025-05-05", False, "Rotate after vendor review."),
        ("Admin dashboard", "carol.admin", "https://mega.local/team", "Business", "Strong", "2026-04-20", True, "Team admin workflow."),
    ])
    add_vault(david, [
        ("Gallery delivery", "david", "https://gallery.example.com", "Client", "Strong", "2026-05-04", True, "Wedding galleries."),
        ("Old print lab", "dkim", "https://prints.example.com", "Vendor", "Weak", "2024-12-21", False, "No recent orders."),
        ("Portfolio hosting", "david.photo", "https://portfolio.example.com", "Creative", "Strong", "2026-03-09", True, "Public portfolio."),
    ])

    for user, plan_slug, cycle, seats, number, date in [
        (alice, "pro-ii", "yearly", 1, "MEGA-20260422-AJ", "2026-04-22"),
        (bob, "pro-flexi", "monthly", 1, "MEGA-20260415-BC", "2026-04-15"),
        (carol, "business-pro", "yearly", 5, "MEGA-20260328-CD", "2026-03-28"),
        (david, "pro-i", "monthly", 1, "MEGA-20260501-DK", "2026-05-01"),
    ]:
        plan = plan_by_slug[plan_slug]
        subtotal = plan.yearly_price * seats if cycle == "yearly" else plan.monthly_price * seats
        tax = round(subtotal * 0.07, 2)
        db.session.add(SubscriptionOrder(
            user_id=user.id, plan_id=plan.id, order_number=number, billing_cycle=cycle, seats=seats,
            subtotal=round(subtotal, 2), tax=tax, total=round(subtotal + tax, 2),
            status="active", created_at=date
        ))

    db.session.add_all([
        SupportTicket(user_id=alice.id, ticket_number="MEGA-T0429-AJ", subject="Question about sharing Atlas folder", category="Cloud drive", priority="Normal", status="Waiting on customer", message="Can an external collaborator upload without a MEGA account?", created_at="2026-04-29"),
        SupportTicket(user_id=bob.id, ticket_number="MEGA-T0508-BC", subject="S4 lifecycle policy example", category="Object storage", priority="Normal", status="Open", message="Need guidance for archive tiering with Rclone.", created_at="2026-05-08"),
        SupportTicket(user_id=carol.id, ticket_number="MEGA-T0502-CD", subject="External collaborator access audit", category="Business", priority="High", status="Open", message="Please confirm best practice for removing a contractor.", created_at="2026-05-02"),
        SupportTicket(user_id=david.id, ticket_number="MEGA-T0424-DK", subject="Client upload request expiry", category="Share", priority="Normal", status="Resolved", message="How long should a wedding upload request stay active?", created_at="2026-04-24"),
    ])

    db.session.commit()
