"""Materialize benchmark fixtures using the pinned, reviewed media mapping."""
from datetime import datetime, timedelta
import json
from pathlib import Path

SEED_MEDIA = json.loads(Path(__file__).with_name('seed_media.json').read_text())
DEMO_PASSWORD_HASH = '$2b$12$xmu6gQgfkGSUV4aAOEKL9OSEptDVIFuw7cptBw93.2cTSXzyEnzSW'


def seed_database(db, Channel, Video, Playlist, PlaylistVideo):
    if Channel.query.count() > 0:
        return

    channels_data = [
        ('quantum-lab', 'Hafu Go', 'Science', '#7c4dff', True),
        ('frame-by-frame', 'AI Uncovered', 'Technology', '#3ea6ff', True),
        ('night-shift-jazz', 'Magic Club', 'Music', '#ff4e45', False),
        ('pixel-quest', 'MrBeast Gaming', 'Gaming', '#00c853', True),
        ('pantry-notes', 'cookingWITHfred', 'Cooking', '#ff9800', False),
        ('window-seat', 'Walking OZ', 'Travel', '#00b8d4', True),
    ]
    channels = {}
    for slug, name, category, accent, verified in channels_data:
        channel_assets = SEED_MEDIA['channels'][slug]
        channel = Channel(
            slug=slug,
            name=name,
            category=category,
            description=f'{name} publishes polished {category.lower()} videos with strong visual storytelling and deep detail.',
            subscriber_count={
                'Science': 4820000,
                'Technology': 3610000,
                'Music': 1980000,
                'Gaming': 5280000,
                'Cooking': 1120000,
                'Travel': 2410000,
            }[category],
            avatar_path=channel_assets['avatar_path'],
            banner_path=channel_assets['banner_path'],
            verified=verified,
            accent_color=accent,
        )
        db.session.add(channel)
        channels[slug] = channel
    db.session.flush()

    published_base = datetime(2024, 3, 1, 12, 0, 0)
    video_specs = [
        ('quantum-lab', 'how-quantum-sensors-read-invisible-changes', 'Level 1 to 100 Science Gadgets', 'Science', ['quantum', 'sensor', 'lab'], '14:42', 882000, 42100, True, True, 2, 'jpg'),
        ('quantum-lab', 'why-lunar-dust-destroys-precision-hardware', 'Level 1 to 100 Science Experiments', 'Science', ['moon', 'engineering', 'dust'], '11:28', 531000, 19800, False, True, 6, 'jpg'),
        ('quantum-lab', 'building-a-tabletop-gravity-wave-demo', 'I Tested Every Science Gadget on Amazon', 'Science', ['physics', 'demo', 'gravity'], '19:03', 263000, 11100, False, True, 11, 'jpg'),
        ('frame-by-frame', 'inside-the-tiny-pc-that-replaced-my-laptop', 'I Tested the Rarest Tech in 2026!', 'Technology', ['mini pc', 'review', 'productivity'], '12:35', 1260000, 63300, True, True, 1, 'jpg'),
        ('frame-by-frame', 'can-this-studio-camera-beat-a-flagship-phone', 'R.I.P. Normal Flagship Phones but Why?', 'Technology', ['camera', 'studio', 'comparison'], '18:21', 917000, 54100, True, True, 4, 'jpg'),
        ('frame-by-frame', 'three-display-calibrators-tested-back-to-back', 'Top 17 New Technology Trends That Will Define 2026', 'Technology', ['display', 'color', 'creator'], '16:09', 302000, 17300, False, True, 10, 'jpg'),
        ('night-shift-jazz', 'loft-session-midnight-rhodes-and-tape-echo', 'Best Acoustic Covers of Popular Songs 2026 Deep Focus & Chill Study Music', 'Music', ['jazz', 'session', 'lofi'], '36:10', 471000, 23900, True, True, 3, 'jpg'),
        ('night-shift-jazz', 'rainy-city-vinyl-mix-for-late-work', 'Ibiza Summer Mix 2026 Best Of Tropical Deep House Music Chill Out Mix 2025 Chillout Lounge', 'Music', ['vinyl', 'mix', 'study'], '58:32', 712000, 38100, True, True, 8, 'jpg'),
        ('night-shift-jazz', 'sunrise-sax-theme-with-analog-delay', 'Music Mix 2026 EDM Remixes of Popular Songs EDM Mood Up', 'Music', ['sax', 'analog', 'mood'], '9:54', 121000, 7100, False, True, 15, 'jpg'),
        ('pixel-quest', 'speedrunning-the-archive-ruins-in-18-minutes', '1 Day vs 50,000 Day Build Challenge', 'Gaming', ['speedrun', 'rpg', 'challenge'], '18:45', 1560000, 80100, True, True, 2, 'jpg'),
        ('pixel-quest', 'which-stealth-build-survives-nightmare-mode', 'Omg! NEW VERSION BEST AGGRESSIVE RUSH GAMEPLAY PUBG Mobile - BGMI', 'Gaming', ['stealth', 'build', 'nightmare'], '22:12', 841000, 45200, False, True, 5, 'jpg'),
        ('pixel-quest', 'five-open-world-settings-that-still-feel-new', 'We Built a Gaming PC to BEAT the PS5 in 2026', 'Gaming', ['open world', 'analysis', 'design'], '13:31', 402000, 18900, False, False, 13, 'jpg'),
        ('pantry-notes', 'the-crispy-chili-oil-noodles-i-make-weekly', 'Pasta | Pasta recipe | How to make pasta', 'Cooking', ['noodles', 'recipe', 'chili oil'], '8:41', 298000, 14400, False, True, 7, 'jpg'),
        ('pantry-notes', 'freezer-dumplings-with-a-restaurant-finish', "Tajio's Ultimate Grand Line Curry Cook-off! #shorts #onepiece #curry #sanji", 'Cooking', ['dumplings', 'meal prep', 'crispy'], '10:52', 429000, 22100, True, True, 12, 'jpg'),
        ('pantry-notes', 'three-knife-skills-that-change-weeknight-cooking', 'Me vs Grandma Cooking Challenge | Kitchen Hacks and Tricks by Mega DO Challenge', 'Cooking', ['knife skills', 'prep', 'beginner'], '15:08', 188000, 9700, False, True, 21, 'jpg'),
        ('window-seat', 'a-weekend-rail-journey-across-northern-spain', 'MADRID, Spain Full City Walk - 9 Hours of Exploration | 4K Tour', 'Travel', ['train', 'spain', 'itinerary'], '17:18', 509000, 24700, True, True, 9, 'jpg'),
        ('window-seat', 'how-to-pack-one-bag-for-a-rainy-spring-city', 'London City Walk | Chelsea London Walking Tour | London Spring Walk | Central London View [4K HDR]', 'Travel', ['packing', 'city break', 'spring'], '12:11', 366000, 16800, False, True, 16, 'jpg'),
        ('window-seat', 'the-quiet-coffee-streets-of-kyoto-at-dawn', 'New York City walk - Explore Manhattan', 'Travel', ['kyoto', 'coffee', 'dawn'], '20:27', 287000, 13900, False, True, 25, 'jpg'),
        ('quantum-lab', 'can-you-hear-a-starquake-through-data', 'Is Science Dying?', 'Science', ['stars', 'waves', 'analysis'], '13:07', 341000, 15400, False, True, 14, 'jpg'),
        ('frame-by-frame', 'desk-studio-lighting-under-100-dollars', 'Dr. Eric Schmidt: The Future of Technology at 300', 'Technology', ['lighting', 'studio', 'budget'], '9:38', 276000, 13000, False, True, 18, 'jpg'),
        ('night-shift-jazz', 'blue-hour-piano-loop-for-deep-focus', 'Best Acoustic Songs 2025 Chill English Acoustic Love Songs Cover Acoustic Songs 2025 Playlist', 'Music', ['piano', 'focus', 'loop'], '42:16', 288000, 15000, False, True, 19, 'jpg'),
        ('pixel-quest', 'best-controller-settings-for-faster-aiming', 'The Switch 2 is Finally a Great Handheld', 'Gaming', ['controller', 'settings', 'aiming'], '11:44', 523000, 24800, False, True, 17, 'jpg'),
        ('pantry-notes', 'one-pan-garlic-rice-for-busy-weeknights', 'How to Cook Eggs with Tomatoes and Cheese for Breakfast. Tomatoes. Onion.Eggs.', 'Cooking', ['rice', 'one pan', 'quick meal'], '7:56', 215000, 11200, False, True, 22, 'jpg'),
        ('window-seat', '48-hours-in-lisbon-without-a-car', '25 Best Countries To Visit In 2026 | Travel Video', 'Travel', ['lisbon', 'walking', 'weekend'], '14:10', 319000, 14900, False, True, 23, 'jpg'),
    ]

    videos = {}
    for spec in video_specs:
        channel_slug, slug, title, category, tags, duration, views, likes, trending, comments_enabled, days_ago, _image_ext = spec
        asset_paths = SEED_MEDIA['videos'][slug]
        video = Video(
            slug=slug,
            title=title,
            channel_id=channels[channel_slug].id,
            description=f'{title} breaks down the creative and technical details behind the topic with clear chapters and a polished visual treatment.',
            category=category,
            tags_json=json.dumps(tags),
            duration=duration,
            duration_seconds=sum(int(part) * scale for part, scale in zip(duration.split(':'), [60, 1]) if len(duration.split(':')) == 2),
            thumbnail_path=asset_paths['thumbnail_path'],
            poster_path=asset_paths['poster_path'],
            views=views,
            likes=likes,
            comment_count=0,
            published_at=published_base - timedelta(days=days_ago),
            is_trending=trending,
            comments_enabled=comments_enabled,
        )
        db.session.add(video)
        videos[slug] = video
    db.session.flush()

    playlist_specs = [
        ('frame-by-frame', 'Studio Upgrade Path', ['inside-the-tiny-pc-that-replaced-my-laptop', 'can-this-studio-camera-beat-a-flagship-phone', 'three-display-calibrators-tested-back-to-back']),
        ('night-shift-jazz', 'After Hours Mix', ['loft-session-midnight-rhodes-and-tape-echo', 'rainy-city-vinyl-mix-for-late-work', 'sunrise-sax-theme-with-analog-delay']),
        ('window-seat', 'Slow Travel Essentials', ['a-weekend-rail-journey-across-northern-spain', 'how-to-pack-one-bag-for-a-rainy-spring-city', 'the-quiet-coffee-streets-of-kyoto-at-dawn']),
    ]

    for channel_slug, title, video_slugs in playlist_specs:
        playlist = Playlist(
            slug='-'.join(title.lower().split()),
            channel_id=channels[channel_slug].id,
            title=title,
            description=f'{title} collects a tight sequence of videos with a consistent mood and topic arc.',
        )
        db.session.add(playlist)
        db.session.flush()
        for position, video_slug in enumerate(video_slugs, start=1):
            db.session.add(PlaylistVideo(playlist_id=playlist.id, video_id=videos[video_slug].id, position=position))

    db.session.commit()


def seed_benchmark_users(db, User, Subscription, WatchLater, WatchHistory, UserLike, Comment, Video, Channel):
    if User.query.filter_by(email='alice.j@test.com').first():
        return

    users = [
        ('alice.j@test.com', 'Marques Brownlee', 'mkbhd', '#ff4e45'),
        ('bob.c@test.com', 'Mrwhosetheboss', 'mrwhosetheboss', '#00c853'),
        ('carol.d@test.com', 'Hafu Go', 'hafu-go', '#7c4dff'),
        ('david.k@test.com', 'WALKS and the CITY', 'walks-and-the-city', '#3ea6ff'),
    ]
    created = {}
    for email, name, handle, color in users:
        user = User(email=email, display_name=name, handle=handle, avatar_color=color)
        user.password_hash = DEMO_PASSWORD_HASH
        db.session.add(user)
        created[email] = user
    db.session.flush()

    channels = {channel.slug: channel for channel in Channel.query.all()}
    videos = {video.slug: video for video in Video.query.all()}

    subscriptions = {
        'alice.j@test.com': ['frame-by-frame', 'night-shift-jazz', 'window-seat'],
        'bob.c@test.com': ['pixel-quest', 'quantum-lab'],
        'carol.d@test.com': ['pantry-notes', 'window-seat', 'quantum-lab'],
        'david.k@test.com': ['frame-by-frame', 'pixel-quest'],
    }
    for email, channel_slugs in subscriptions.items():
        for channel_slug in channel_slugs:
            db.session.add(Subscription(user_id=created[email].id, channel_id=channels[channel_slug].id))

    watch_later = {
        'alice.j@test.com': ['can-this-studio-camera-beat-a-flagship-phone', 'rainy-city-vinyl-mix-for-late-work'],
        'bob.c@test.com': ['which-stealth-build-survives-nightmare-mode', 'a-weekend-rail-journey-across-northern-spain'],
        'carol.d@test.com': ['the-crispy-chili-oil-noodles-i-make-weekly', 'a-weekend-rail-journey-across-northern-spain'],
        'david.k@test.com': ['how-quantum-sensors-read-invisible-changes'],
    }
    for email, video_slugs in watch_later.items():
        for video_slug in video_slugs:
            db.session.add(WatchLater(user_id=created[email].id, video_id=videos[video_slug].id))

    history = {
        'alice.j@test.com': ['inside-the-tiny-pc-that-replaced-my-laptop', 'loft-session-midnight-rhodes-and-tape-echo'],
        'bob.c@test.com': ['speedrunning-the-archive-ruins-in-18-minutes', 'how-quantum-sensors-read-invisible-changes'],
        'carol.d@test.com': ['a-weekend-rail-journey-across-northern-spain'],
        'david.k@test.com': ['can-this-studio-camera-beat-a-flagship-phone', 'speedrunning-the-archive-ruins-in-18-minutes'],
    }
    for email, video_slugs in history.items():
        for offset, video_slug in enumerate(video_slugs):
            db.session.add(WatchHistory(user_id=created[email].id, video_id=videos[video_slug].id, watched_at=datetime(2024, 3, 1, 12, 0, 0) - timedelta(hours=offset + 1)))

    likes = {
        'alice.j@test.com': ['inside-the-tiny-pc-that-replaced-my-laptop'],
        'bob.c@test.com': ['speedrunning-the-archive-ruins-in-18-minutes'],
        'carol.d@test.com': ['a-weekend-rail-journey-across-northern-spain'],
        'david.k@test.com': ['can-this-studio-camera-beat-a-flagship-phone'],
    }
    for email, video_slugs in likes.items():
        for video_slug in video_slugs:
            db.session.add(UserLike(user_id=created[email].id, video_id=videos[video_slug].id))

    comment_specs = [
        ('can-this-studio-camera-beat-a-flagship-phone', 'alice.j@test.com', 'This flagship comparison was way more practical than most hype videos.', 264),
        ('can-this-studio-camera-beat-a-flagship-phone', 'bob.c@test.com', 'Battery and thermals section was the best part.', 118),
        ('how-quantum-sensors-read-invisible-changes', 'carol.d@test.com', 'Loved the gadget progression from basic to advanced.', 207),
        ('how-quantum-sensors-read-invisible-changes', 'david.k@test.com', 'The visual demos make the science part much easier to follow.', 96),
        ('a-weekend-rail-journey-across-northern-spain', 'alice.j@test.com', 'That city-walk style pacing is perfect for planning routes.', 88),
        ('rainy-city-vinyl-mix-for-late-work', 'carol.d@test.com', 'Great background mix for long editing sessions.', 73),
        ('speedrunning-the-archive-ruins-in-18-minutes', 'bob.c@test.com', 'The build order in the first three minutes is super efficient.', 54),
        ('the-crispy-chili-oil-noodles-i-make-weekly', 'david.k@test.com', 'Simple ingredients but very strong flavor balance.', 42),
    ]
    for video_slug, email, body, like_count in comment_specs:
        db.session.add(
            Comment(
                video_id=videos[video_slug].id,
                user_id=created[email].id,
                body=body,
                like_count=like_count,
            )
        )
        videos[video_slug].comment_count += 1

    db.session.commit()
