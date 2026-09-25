"""Deterministic seed data for the 4shared WebHarbor mirror."""

from __future__ import annotations

import sys
from datetime import datetime, timedelta


def _app_module():
    module = sys.modules.get("app")
    if module is not None:
        return module
    main = sys.modules.get("__main__")
    if main is not None and hasattr(main, "db") and hasattr(main, "FileItem"):
        return main
    import app as module
    return module


_app = _app_module()
BENCHMARK_PASSWORD = _app.BENCHMARK_PASSWORD
Comment = _app.Comment
DownloadLog = _app.DownloadLog
Favorite = _app.Favorite
FileItem = _app.FileItem
Folder = _app.Folder
PlanOrder = _app.PlanOrder
SavedFile = _app.SavedFile
SharedLink = _app.SharedLink
User = _app.User
db = _app.db
slugify = _app.slugify

SEED_TIME = datetime(2026, 8, 20, 10, 0, 0)

UPLOADERS = [
    "Open Culture Shelf", "Atlas Media Lab", "Commons Studio", "Learning Exchange",
    "Field Notes Collective", "Open Source Desk", "Archive Lantern", "Community Library",
]

CATALOG = {
    "Music": {
        "ext": "mp3", "mime": "audio/mpeg", "license": "Public domain recording",
        "items": [
            ("Moonlight Sonata First Movement", "A measured solo-piano performance recorded in a quiet recital hall.", "piano beethoven classical nocturne", "Duration 5:42 · 320 kbps · recorded on a Steinway Model B."),
            ("Clair de Lune Studio Performance", "An intimate interpretation of Debussy's atmospheric piano work.", "piano debussy impressionist classical", "Duration 4:51 · 256 kbps · remastered from a 2018 session."),
            ("Morning Meadow Field Recording", "Dawn birds, light wind, and a distant creek captured in early spring.", "nature birds ambience field recording", "Duration 12:08 · stereo · recorded at 48 kHz."),
            ("Nocturne in E Flat Practice Take", "A complete practice-room reading with natural room ambience.", "chopin piano nocturne practice", "Duration 4:33 · 192 kbps · take number 7."),
            ("Cello Suite Prelude Live", "A warm live performance of the familiar unaccompanied prelude.", "bach cello suite live classical", "Duration 3:09 · audience recording · restored in 2024."),
            ("Rain on Library Windows", "A seamless ambience track of gentle rain against tall windows.", "rain ambience sleep study nature", "Duration 18:40 · stereo · no music or voice."),
            ("Blue Hour Jazz Trio", "Original piano, upright bass, and brushed drums in a relaxed medium tempo.", "jazz trio original instrumental", "Duration 6:17 · 24-bit source · key of F minor."),
            ("Acoustic Guitar Warmup Etude", "A fingerstyle study designed for intermediate practice sessions.", "guitar acoustic etude practice", "Duration 2:58 · 120 BPM · standard tuning."),
            ("Ocean Pier Evening Ambience", "Waves, gulls, and wooden pier creaks recorded just after sunset.", "ocean waves ambience coast", "Duration 14:22 · binaural recording · light wind."),
            ("Brass Quintet Festival Fanfare", "An original ceremonial fanfare for two trumpets, horn, trombone, and tuba.", "brass quintet fanfare original", "Duration 2:14 · score revision 3 · concert pitch."),
            ("Violin Partita Courante", "A clear rehearsal recording focused on articulation and dance rhythm.", "violin bach partita baroque", "Duration 3:37 · mono room mic · no edits."),
            ("Quiet Cafe Background Loop", "Low conversation and table sounds for creative-work ambience.", "cafe ambience background focus", "Duration 9:30 · seamless loop · no identifiable speech."),
            ("Mountain Stream in Late Summer", "Close-miked flowing water from a shaded alpine stream.", "water stream nature field recording", "Duration 10:45 · 48 kHz WAV source · normalized to -16 LUFS."),
            ("String Quartet Rehearsal Sketch", "An original two-theme chamber sketch from an open rehearsal.", "strings quartet rehearsal original", "Duration 7:06 · rehearsal letter C begins at 3:12."),
            ("Vintage Metronome at 72 BPM", "A wooden mechanical metronome captured for music practice.", "metronome rhythm practice 72 bpm", "Duration 5:00 · 72 beats per minute · dry studio sound."),
            ("Evening Crickets Field Session", "A summer-night chorus recorded near a woodland edge.", "crickets night nature ambience", "Duration 11:11 · stereo pair · recorded in August."),
        ],
    },
    "Video": {
        "ext": "mp4", "mime": "video/mp4", "license": "Creative Commons Attribution",
        "items": [
            ("Introduction to Urban Sketching", "A practical lesson on line, shape, and quick watercolor washes.", "art drawing watercolor tutorial", "Runtime 18:24 · 1080p · includes three street-scene demonstrations."),
            ("Night Walk Across Tower Bridge", "A stabilized dusk-to-night walk with ambient city sound.", "london travel bridge city walk", "Runtime 12:36 · 4K master · filmed from south to north."),
            ("Denali Landscape Study", "A slow visual study of the mountain, tundra, and reflected light.", "denali alaska mountain nature landscape", "Runtime 8:15 · 2160p · filmed over two clear mornings."),
            ("Build a Simple Weather Station", "A classroom demonstration using open hardware sensors.", "science weather tutorial sensors education", "Runtime 22:41 · 1080p · bill of materials appears at 04:18."),
            ("Five-Minute Desk Mobility Routine", "A low-impact guided routine for shoulders, hips, and wrists.", "fitness mobility desk stretch", "Runtime 5:38 · captions included · no equipment required."),
            ("Open Data Mapping Basics", "A beginner overview of layers, coordinates, and map styling.", "maps gis open data tutorial", "Runtime 27:03 · 1080p · sample project uses GeoJSON."),
            ("Coastal Birds Field Guide", "Identification notes and footage for eight common shoreline birds.", "birds coast nature guide", "Runtime 14:19 · captions included · eight species chapters."),
            ("Bread Dough Fermentation Timelapse", "A controlled side-by-side rise at three room temperatures.", "bread baking science timelapse", "Runtime 6:52 · labels show 18°C, 22°C, and 27°C."),
            ("Community Garden Summer Tour", "A volunteer-led walk through pollinator beds and raised plots.", "garden plants community tour", "Runtime 16:08 · 1080p · filmed in July."),
            ("Beginner Astronomy Moon Phases", "A model-based explanation of the lunar cycle and viewing geometry.", "astronomy moon phases education", "Runtime 11:44 · includes a 29.5-day cycle diagram."),
            ("Restoring a Wooden Chair", "A careful repair demonstration from disassembly through finish.", "woodworking restoration chair tutorial", "Runtime 31:20 · chapter markers · hand tools only."),
            ("Museum Archive Handling Basics", "Gloves, supports, labeling, and safe movement of paper objects.", "museum archive preservation training", "Runtime 13:57 · accessibility captions · revised 2025."),
            ("City Cycling Route Planning", "How to evaluate gradients, protected lanes, and intersection risk.", "cycling city maps route planning", "Runtime 19:05 · sample route length 8.4 km."),
            ("Watercolor Clouds Three Techniques", "Wet-on-wet, lifting, and dry-brush cloud studies.", "painting watercolor clouds art", "Runtime 15:31 · 1080p · materials list in opening minute."),
            ("Library Digitization Workflow", "A demonstration of capture, naming, metadata, and quality control.", "library scanning metadata workflow", "Runtime 24:12 · TIFF master workflow · PDF access copies."),
            ("Seed Saving for Beginners", "A seasonal guide to collecting, drying, labeling, and storage.", "garden seeds sustainability guide", "Runtime 17:46 · covers tomatoes, beans, and lettuce."),
        ],
    },
    "Apps": {
        "ext": "zip", "mime": "application/zip", "license": "Open-source package",
        "items": [
            ("OpenMap Desktop Portable", "Portable offline map viewer package with sample public data.", "maps desktop offline open source", "Version 3.4.2 · Linux and Windows launchers · SHA-256 listed in README."),
            ("NoteStack Markdown Editor", "A lightweight local-first editor for Markdown notes.", "notes markdown editor productivity", "Version 2.8.0 · spellcheck included · export to HTML and PDF."),
            ("PhotoBatch Community Edition", "Resize, rotate, and rename image collections without cloud upload.", "photos images batch resize open source", "Version 1.9.5 · supports JPEG, PNG, and WebP."),
            ("AudioTag Library Tool", "Edit common audio metadata fields and organize albums.", "music audio tags organizer", "Version 4.1.1 · reads ID3 and Vorbis comments."),
            ("StudyTimer Focus Utility", "A simple configurable focus and break timer.", "timer study focus productivity", "Version 1.6.3 · three color themes · CSV session export."),
            ("ArchivePeek File Inspector", "Browse archive contents and checksums before extraction.", "archive zip checksum utility", "Version 2.2.4 · ZIP, TAR, and 7z read support."),
            ("ArchivePeek File Inspector Legacy Build", "An archived compatibility build of the file inspector for older systems.", "archive file inspector legacy compatibility", "Version 1.7.9 · ZIP-only inspection · no checksum comparison."),
            ("ArchivePeek File Inspector Checksums Add-on", "Optional checksum definitions for ArchivePeek deployments.", "archive file inspector checksum addon", "Version 2.1.0 · definitions package only · requires the main application."),
            ("ArchivePeek File Inspector Portable Notes", "Release notes and deployment examples for portable ArchivePeek installations.", "archive file inspector portable documentation", "Version 2.2 notes · documentation package · contains no executable."),
            ("ArchivePeek File Inspector Recovery Plug-in", "A recovery plug-in for damaged archive headers.", "archive file inspector recovery plugin", "Version 0.6.3 · experimental plug-in · TAR recovery only."),
            ("ArchivePeek File Inspector Test Fixtures", "Sample archives for validating file-inspection workflows.", "archive file inspector test fixtures", "Version 2026.4 · 42 synthetic fixtures · not an application installer."),
            ("ColorScope Palette Assistant", "Inspect colors and create accessible palette combinations.", "design color accessibility palette", "Version 5.0.0 · WCAG contrast preview · GPL-3.0."),
            ("PocketWeather Sample Client", "Demonstration client for an open weather-data endpoint.", "weather sample api client", "Version 0.9.8 · demo data works offline · MIT license."),
            ("BookShelf EPUB Catalog", "Catalog local EPUB metadata and reading status.", "books epub catalog library", "Version 3.0.1 · OPF metadata import · local database only."),
            ("SubtitleShift Timing Utility", "Adjust subtitle timing by a fixed offset or scale.", "video subtitles timing utility", "Version 1.4.6 · SRT and WebVTT support."),
            ("GeoJournal Field Notes", "Create location-aware field notes with offline maps.", "journal maps offline field notes", "Version 2.5.7 · GPX import · coordinates optional."),
            ("DiagramLite Flow Editor", "Small vector diagram editor with SVG export.", "diagram svg flowchart editor", "Version 0.8.9 · 24 bundled shapes · autosave enabled."),
            ("Checksum Desk", "Generate and compare common file checksums locally.", "checksum sha256 files security", "Version 1.2.0 · SHA-256, SHA-512, and BLAKE2."),
            ("CaptionCraft Transcriber", "Manual caption authoring workspace with keyboard controls.", "captions accessibility video editor", "Version 2.0.3 · WebVTT export · waveform preview."),
            ("GardenPlot Planner", "Lay out beds and track crop rotations by season.", "garden planner crops open source", "Version 4.3.0 · metric and imperial grids."),
            ("FontLedger Collection Viewer", "Preview locally installed font families and metadata.", "fonts typography viewer design", "Version 1.1.8 · specimen PDF export."),
        ],
    },
    "Images": {
        "ext": "jpg", "mime": "image/jpeg", "license": "Creative Commons image",
        "items": [
            ("London Skyline at Blue Hour", "A wide cityscape over the Thames as evening lights appear.", "london skyline city travel bridge", "Resolution 3840 × 2160 · captured at 20:14 · lens 24 mm."),
            ("New York Skyline at Sunset", "Manhattan towers against a clear pastel sunset.", "new york skyline city sunset", "Resolution 3840 × 2160 · ISO 200 · exposure 1/80 s."),
            ("Denali Reflection Panorama", "Snow-covered Denali reflected in still tundra water.", "denali mountain alaska panorama nature", "Resolution 2824 × 2176 · morning light · elevation viewpoint 640 m."),
            ("Library Reading Room Windows", "Tall windows and long study tables in a historic reading room.", "library architecture reading room", "Resolution 2400 × 1600 · natural light · no people."),
            ("Atlantic Coast Boardwalk", "Weathered boards leading through dunes toward the sea.", "ocean coast boardwalk landscape", "Resolution 3000 × 2000 · late afternoon · focal length 35 mm."),
            ("Community Garden Pollinators", "Bees visiting purple flowers in a neighborhood garden.", "garden flowers bees nature", "Resolution 2200 × 1467 · macro crop · photographed in July."),
            ("Grand Lake Sunrise", "Warm sunrise light over a mountain lake and surrounding ridges.", "mountain lake sunrise colorado", "Resolution 3200 × 2133 · tripod capture · 06:21 local time."),
            ("Ceramic Studio Workbench", "Tools, clay, and unfinished vessels on a working studio table.", "ceramics art studio craft", "Resolution 2600 × 1733 · window light · documentary series."),
            ("Red Bicycle by Brick Wall", "A city bicycle parked beside a warm red-brick facade.", "bicycle city street red", "Resolution 2400 × 1600 · 50 mm lens · overcast light."),
            ("Winter Pines After Snow", "Fresh snow resting on dense evergreen branches.", "winter snow trees forest", "Resolution 3000 × 2000 · temperature -6°C · polarizing filter."),
            ("Music Notebook and Fountain Pen", "A patterned music notebook and fountain pen arranged on a wooden desk.", "notebook fountain pen desk music", "Resolution 2400 × 1600 · overhead composition · daylight."),
            ("Harbor Boats in Morning Fog", "Small sailboats emerging through pale harbor fog.", "harbor boats fog water", "Resolution 2800 × 1867 · 85 mm lens · photographed at 07:03."),
            ("Wildflower Trail in Spring", "A narrow hillside trail lined with yellow and blue flowers.", "wildflowers trail spring hiking", "Resolution 3200 × 2133 · elevation 1,120 m · April capture."),
            ("Classic Camera Detail", "Close view of the controls on a restored mechanical camera.", "camera vintage photography detail", "Resolution 2500 × 1667 · focus-stacked from six frames."),
            ("Rainy City Street at Night", "Wet pavement and storefront lights on a quiet city street after dark.", "rain city street night lights", "Resolution 2400 × 1600 · available-light photograph · monochrome."),
            ("Map and Compass Flat Lay", "A paper trail map, field compass, and pencil arranged for a hike.", "map compass hiking navigation", "Resolution 3000 × 2000 · overhead studio light · north arrow visible."),
        ],
    },
    "Books": {
        "ext": "epub", "mime": "application/epub+zip", "license": "Public domain text",
        "items": [
            ("The Secret Garden Illustrated Edition", "A carefully proofread edition of the classic garden story.", "classic fiction garden children", "338 pages · EPUB 3 · 12 original illustrations."),
            ("A Study in Scarlet", "The first Sherlock Holmes novel in a clean reflowable edition.", "classic mystery sherlock holmes", "164 pages · chapter navigation · British spelling retained."),
            ("The Time Machine", "H. G. Wells's compact science-fiction novel with editorial notes.", "science fiction classic time travel", "128 pages · 12 chapters · notes begin after page 116."),
            ("Anne of Green Gables", "A reflowable edition with a Prince Edward Island map.", "classic fiction anne canada", "412 pages · 38 chapters · includes one regional map."),
            ("The Adventures of Tom Sawyer", "A proofread edition with a historical-context introduction.", "classic fiction mark twain adventure", "296 pages · 35 chapters · introduction by Open Shelf editors."),
            ("The Wonderful Wizard of Oz", "A color-illustrated EPUB edition of the original 1900 story.", "classic fantasy oz illustrated", "214 pages · 24 chapters · 20 color plates."),
            ("Walden", "Thoreau's reflections on simple living with linked endnotes.", "essays nature philosophy thoreau", "384 pages · linked endnotes · 18 chapter essays."),
            ("Pride and Prejudice", "A typographically polished edition with character index.", "classic romance austen fiction", "432 pages · 61 chapters · character index included."),
            ("Frankenstein 1818 Text", "The original 1818 edition with a concise textual history.", "gothic science fiction shelley", "280 pages · 1818 text · three-volume structure retained."),
            ("The Jungle Book", "Stories and poems in a navigable illustrated edition.", "classic stories kipling jungle", "246 pages · 14 illustrations · poems indexed separately."),
            ("Meditations Public Domain Translation", "A clear English translation arranged by book and section.", "philosophy stoicism marcus aurelius", "192 pages · 12 books · searchable section numbers."),
            ("The Federalist Papers", "All 85 essays with author and topic index.", "history politics essays constitution", "672 pages · 85 essays · searchable topic index."),
            ("The Anti-Federalist Papers Selection", "A selected set of arguments opposing ratification, with editorial context.", "history politics essays constitution federalist papers", "244 pages · 24 selected essays · chronological reading list."),
            ("Federalist Papers Study Questions", "Classroom prompts organized around major constitutional themes.", "history politics education federalist papers", "118 pages · 60 study questions · instructor notes appendix."),
            ("Federalist Papers Author Concordance", "A reference concordance comparing commonly attributed authorship.", "history politics reference federalist papers", "206 pages · author tables · no full essay text."),
            ("Federalist Papers Historical Reader", "Speeches, letters, and newspaper extracts from the ratification debate.", "history politics primary sources federalist papers", "356 pages · 41 source extracts · timeline included."),
            ("Federalist Papers Constitutional Index", "A subject index linking constitutional clauses to related debates.", "history politics constitution federalist papers", "174 pages · clause index · cross-references only."),
            ("Grimms Household Tales Selection", "Thirty selected tales in a reflowable reading edition.", "fairy tales folklore grimm", "318 pages · 30 tales · content notes included."),
            ("The Souls of Black Folk", "Du Bois's landmark essays with preserved musical epigraphs.", "history essays sociology du bois", "286 pages · 14 essays · musical bars encoded as images."),
            ("Leaves of Grass 1892 Edition", "The deathbed edition with section-level navigation.", "poetry whitman american", "476 pages · 17 sections · line breaks preserved."),
            ("Twenty Thousand Leagues Under the Seas", "An illustrated translation of Verne's undersea adventure.", "adventure science fiction ocean verne", "512 pages · 47 chapters · 32 illustrations."),
        ],
    },
    "Documents": {
        "ext": "pdf", "mime": "application/pdf", "license": "Open educational resource",
        "items": [
            ("Urban Tree Inventory Field Guide", "A practical guide to measuring, identifying, and recording street trees.", "trees city field guide environment", "64 pages · revision 2.1 · diameter worksheet on page 41."),
            ("Community Workshop Facilitation Notes", "Reusable agendas and exercises for small public workshops.", "community workshop facilitation guide", "38 pages · six agenda templates · accessibility checklist on page 32."),
            ("Beginner Map Reading Workbook", "Exercises covering scale, symbols, contour lines, and coordinates.", "maps navigation workbook education", "72 pages · 24 exercises · answer key begins on page 66."),
            ("Open Photography Metadata Handbook", "A reference to common EXIF, IPTC, and rights fields.", "photography metadata exif handbook", "54 pages · field matrix on page 17 · version 1.4."),
            ("Home Energy Audit Checklist", "Room-by-room observations for a non-invasive home energy review.", "energy home checklist sustainability", "22 pages · 87 checklist items · climate notes appendix."),
            ("Small Archive Digitization Plan", "A staged plan for naming, scanning, metadata, storage, and QA.", "archive scanning digitization workflow", "46 pages · 12-week sample schedule · risk register on page 39."),
            ("Rain Garden Planting Guide", "Site selection and plant lists for compact residential rain gardens.", "garden rain water plants guide", "58 pages · three planting zones · maintenance calendar on page 49."),
            ("Accessible Event Planning Workbook", "Prompts for venue, communication, sensory, and mobility access.", "accessibility events workbook planning", "44 pages · 63 prompts · vendor questions on page 29."),
            ("Volunteer Trail Survey Form", "Printable forms for recording trail surface and drainage conditions.", "hiking trail survey form", "18 pages · four field forms · condition codes on page 5."),
            ("Local History Interview Toolkit", "Consent, recording, description, and preservation guidance.", "history interview oral archive", "66 pages · sample release on page 55 · metadata sheet on page 59."),
            ("Public Data Cleaning Recipes", "Spreadsheet-first techniques for dates, categories, and missing values.", "data spreadsheet cleaning tutorial", "82 pages · 19 recipes · validation checklist on page 78."),
            ("Neighborhood Bird Count Protocol", "A repeatable ten-minute observation protocol for volunteers.", "birds citizen science protocol", "26 pages · ten-minute count · weather codes on page 12."),
            ("Creative Commons Licensing Primer", "A plain-language guide to the six standard CC licenses.", "copyright creative commons licensing", "34 pages · license comparison chart on page 16."),
            ("Remote Study Group Playbook", "Roles, meeting formats, and reflection prompts for peer study.", "study remote learning playbook", "40 pages · four meeting formats · facilitator cards appendix."),
            ("Museum Label Writing Guide", "Techniques for concise, accessible object labels and panels.", "museum writing accessibility guide", "52 pages · 75-word label exercise on page 21."),
            ("Community Garden Crop Calendar", "A temperate-climate planting and harvest planning calendar.", "garden crops calendar planning", "30 pages · zone 6 reference · succession table on page 24."),
        ],
    },
    "Archives": {
        "ext": "zip", "mime": "application/zip", "license": "Creative Commons collection",
        "items": [
            ("Urban Sketching Practice Sheets", "Printable perspective, texture, and value exercises.", "art drawing worksheets archive", "28 files · 44.6 MB unpacked · includes PDF and PNG formats."),
            ("Open Map Symbol Collection", "A compact set of SVG symbols for community mapping.", "maps icons svg open data", "146 files · SVG format · symbol index included."),
            ("Birdsong Identification Samples", "Short labeled clips for common woodland and garden birds.", "birds audio samples nature", "32 files · 96 MB unpacked · WAV and metadata CSV."),
            ("Public Domain Botanical Plates", "Scanned botanical plates cleaned for classroom use.", "plants botanical images education", "48 files · 212 MB unpacked · 300 dpi JPEG."),
            ("Accessible Presentation Templates", "High-contrast slide layouts with reading-order notes.", "accessibility slides templates", "14 files · PPTX and ODP · font list included."),
            ("Community Survey Starter Pack", "Editable questionnaires, consent language, and coding sheets.", "survey community research templates", "21 files · DOCX, ODT, and XLSX formats."),
            ("Field Recording Metadata Forms", "Sheets for location, equipment, rights, and technical notes.", "audio field recording metadata", "17 files · printable and spreadsheet versions."),
            ("Historic Map Georeference Samples", "Practice maps with control points and completed examples.", "maps history gis tutorial", "26 files · GeoTIFF and CSV · five completed examples."),
            ("Beginner Python Data Exercises", "Small CSV datasets and notebooks for introductory analysis.", "python data education notebooks", "39 files · 18 exercises · solutions in separate folder."),
            ("Neighborhood Photo Walk Prompts", "Prompt cards and release forms for a group photo walk.", "photography community prompts", "24 files · 18 prompt cards · bilingual release form."),
            ("Garden Planning Grid Pack", "Printable bed grids in metric and imperial dimensions.", "garden planning printable grids", "36 files · PDF and SVG · six page sizes."),
            ("Oral History Audio Test Files", "Synthetic calibration clips for a digitization workflow.", "audio archive calibration testing", "12 files · WAV format · tones and spoken test counts."),
            ("Open Icon Accessibility Set", "Simple interface icons with names and usage notes.", "icons accessibility interface svg", "180 files · SVG and PNG · 24 px and 48 px sizes."),
            ("Classroom Weather Data Pack", "One year of fictional station readings for data lessons.", "weather data classroom csv", "13 files · 365 daily rows · data dictionary included."),
            ("Local Newsletter Layout Kit", "Editable two- and four-page community newsletter layouts.", "newsletter design templates community", "18 files · Scribus and PDF · three color variants."),
            ("Trail Sign Vector Collection", "Editable wayfinding and safety sign illustrations.", "trail hiking signs vector", "64 files · SVG and PDF · monochrome and color variants."),
        ],
    },
}

THUMBNAILS = [
    "images/london.jpg",
    "images/new-york.jpg",
    "images/denali.jpg",
    "images/library-reading-room.jpg",
    "images/atlantic-boardwalk.jpg",
    "images/garden-pollinators.jpg",
    "images/alpine-lake-mist.jpg",
    "images/ceramic-workbench.jpg",
    "images/red-bicycle-brick-wall.jpg",
    "images/winter-pines-snow.jpg",
    "images/notebook-fountain-pen.jpg",
    "images/harbor-boats-fog.jpg",
    "images/wildflower-trail.jpg",
    "images/classic-camera.jpg",
    "images/rainy-window-lights.jpg",
    "images/map-compass.jpg",
]


def seed_database():
    """Seed the public catalog once; an existing catalog is a complete no-op."""
    if FileItem.query.filter_by(public=True).count() > 0:
        return
    file_id = 1
    for category, spec in CATALOG.items():
        for index, (title, description, tags, detail) in enumerate(spec["items"]):
            filename = f"{title}.{spec['ext']}"
            thumbnail = ""
            if category == "Images":
                thumbnail = THUMBNAILS[index]
            item = FileItem(
                id=file_id,
                filename=filename,
                slug=f"{slugify(filename)}-{file_id}",
                category=category,
                extension=spec["ext"],
                mime_type=spec["mime"],
                size_bytes=(index + 3) * (1_380_000 if category in {"Music", "Video"} else 438_000),
                description=description,
                tags=tags,
                license_name=spec["license"],
                uploader_name=UPLOADERS[(file_id + index) % len(UPLOADERS)],
                public=True,
                featured=index in {1, 6},
                thumbnail=thumbnail,
                preview_text=detail,
                uploaded_at=SEED_TIME - timedelta(days=(index * 5 + file_id % 9)),
                modified_at=SEED_TIME - timedelta(days=(index * 3 + file_id % 7)),
                download_count=670 + ((file_id * 733) % 48_000),
                rating=round(3.8 + ((file_id * 7) % 13) / 10, 1),
            )
            db.session.add(item)
            file_id += 1
    db.session.commit()


BENCHMARK_USERS = [
    ("alice.j@test.com", "Alice Johnson", "Seattle, Washington", "Photographer and community archive volunteer."),
    ("bob.c@test.com", "Bob Chen", "Austin, Texas", "Maps, field recordings, and open-data projects."),
    ("carol.d@test.com", "Carol Davis", "Chicago, Illinois", "Teacher building accessible classroom resources."),
    ("david.k@test.com", "David Kim", "Atlanta, Georgia", "Designer and neighborhood garden coordinator."),
]

PRIVATE_FILES = [
    ("Quarterly retreat budget.xlsx", "Documents", 184_320, "Working budget with venue and travel estimates."),
    ("Seattle photo selects.zip", "Archives", 8_340_000, "Shortlisted city images for the fall exhibit."),
    ("Field recording notes.docx", "Documents", 94_208, "Location and microphone notes from the coast session."),
    ("Reading list autumn.txt", "Documents", 12_288, "Personal reading list and library holds."),
    ("Community map draft.pdf", "Documents", 2_430_000, "Draft map for the public workshop."),
    ("Old outline.txt", "Documents", 7_168, "Superseded outline retained in Trash."),
]


def seed_benchmark_users():
    """Seed four benchmark accounts and their state once; reruns are no-ops."""
    if User.query.filter_by(email="alice.j@test.com").first():
        return
    public_files = FileItem.query.filter_by(public=True).order_by(FileItem.id).all()
    private_id = (public_files[-1].id if public_files else 0) + 1
    for user_index, (email, name, location, bio) in enumerate(BENCHMARK_USERS):
        user = User(
            id=user_index + 1,
            email=email,
            display_name=name,
            location=location,
            bio=bio,
            plan="Premium" if user_index == 3 else "Free",
            storage_limit_mb=102400 if user_index == 3 else 15360,
            joined_at=SEED_TIME - timedelta(days=800 - user_index * 73),
        )
        user.set_password(BENCHMARK_PASSWORD)
        db.session.add(user)
        db.session.flush()
        folders = []
        for folder_index, folder_name in enumerate(("Work", "Photos", "Shared Projects", "Music")):
            folder = Folder(
                user_id=user.id,
                name=folder_name,
                created_at=SEED_TIME - timedelta(days=150 - folder_index * 9 - user_index),
            )
            db.session.add(folder)
            db.session.flush()
            folders.append(folder)
        owned = []
        for item_index, (base_name, category, size, description) in enumerate(PRIVATE_FILES):
            prefix = ("Alice", "Bob", "Carol", "David")[user_index]
            filename = f"{prefix} {base_name}"
            extension = filename.rsplit(".", 1)[1].lower()
            item = FileItem(
                id=private_id,
                owner_id=user.id,
                folder_id=folders[item_index % len(folders)].id if item_index < 5 else None,
                filename=filename,
                slug=f"{slugify(filename)}-{private_id}",
                category=category,
                extension=extension,
                mime_type="application/octet-stream",
                size_bytes=size + user_index * 4096,
                description=description,
                tags="private personal benchmark",
                license_name="Private",
                uploader_name=name,
                public=False,
                deleted=item_index == 5,
                preview_text=f"Private file owned by {name}. {description}",
                uploaded_at=SEED_TIME - timedelta(days=40 - item_index * 3 + user_index),
                modified_at=SEED_TIME - timedelta(days=10 - item_index + user_index),
                download_count=0,
                rating=0,
            )
            db.session.add(item)
            owned.append(item)
            private_id += 1
        for offset in range(4):
            public = public_files[(user_index * 19 + offset * 9) % len(public_files)]
            db.session.add(Favorite(user_id=user.id, file_id=public.id, created_at=SEED_TIME - timedelta(days=12 + offset)))
        for offset in range(3):
            public = public_files[(user_index * 23 + offset * 11 + 5) % len(public_files)]
            db.session.add(SavedFile(user_id=user.id, file_id=public.id, created_at=SEED_TIME - timedelta(days=20 + offset)))
        for offset in range(2):
            public = public_files[(user_index * 13 + offset * 17 + 2) % len(public_files)]
            db.session.add(DownloadLog(user_id=user.id, file_id=public.id, downloaded_at=SEED_TIME - timedelta(days=offset + 2)))
        db.session.add(SharedLink(
            user_id=user.id,
            file_id=owned[0].id,
            token=f"demo-{user_index + 1}-retreat-budget",
            permission="download" if user_index % 2 else "view",
            label="Planning group",
            created_at=SEED_TIME - timedelta(days=5 + user_index),
        ))
        if user_index == 3:
            db.session.add(PlanOrder(
                user_id=user.id,
                plan_name="Premium",
                billing_period="annual",
                amount=77.88,
                card_last4="4242",
                status="Active",
                created_at=SEED_TIME - timedelta(days=44),
            ))
    for index in range(12):
        db.session.add(Comment(
            user_id=(index % 4) + 1,
            file_id=public_files[(index * 7 + 3) % len(public_files)].id,
            body=(
                "The detail notes and file metadata were especially useful for our workshop."
                if index % 2 == 0 else
                "Preview opened correctly, and the format information matched the download."
            ),
            created_at=SEED_TIME - timedelta(days=30 - index),
        ))
    db.session.commit()


if __name__ == "__main__":
    with _app.app.app_context():
        db.create_all()
        seed_database()
        seed_benchmark_users()
        print(f"seeded {FileItem.query.count()} files and {User.query.count()} users")
