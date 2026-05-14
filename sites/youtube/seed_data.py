import json
import os
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHANNEL_ASSET_PATHS = {
    'quantum-lab': {
        'avatar_path': '/static/images/youtube/channels/quantum-lab-avatar.png',
        'banner_path': '/static/images/youtube/channels/quantum-lab-banner.jpg',
    },
    'frame-by-frame': {
        'avatar_path': '/static/images/youtube/channels/frame-by-frame-avatar.png',
        'banner_path': '/static/images/youtube/channels/frame-by-frame-banner.jpg',
    },
    'night-shift-jazz': {
        'avatar_path': '/static/images/youtube/channels/night-shift-jazz-avatar.png',
        'banner_path': '/static/images/youtube/channels/night-shift-jazz-banner.jpg',
    },
    'pixel-quest': {
        'avatar_path': '/static/images/youtube/channels/pixel-quest-avatar.png',
        'banner_path': '/static/images/youtube/channels/pixel-quest-banner.jpg',
    },
    'pantry-notes': {
        'avatar_path': '/static/images/youtube/channels/pantry-notes-avatar.png',
        'banner_path': '/static/images/youtube/channels/pantry-notes-banner.jpg',
    },
    'window-seat': {
        'avatar_path': '/static/images/youtube/channels/window-seat-avatar.png',
        'banner_path': '/static/images/youtube/channels/window-seat-banner.jpg',
    },
}


def image_path(section: str, slug: str, ext: str = 'svg') -> str:
    return f'/static/images/{section}/{slug}.{ext}'


def pick_video_asset(video_slug: str):
    return {
        'thumbnail_path': image_path('youtube/thumbnails', video_slug, 'jpg'),
        'poster_path': image_path('youtube/posters', video_slug, 'jpg'),
    }


def pick_channel_asset(channel_slug: str):
    return CHANNEL_ASSET_PATHS.get(
        channel_slug,
        {
            'avatar_path': image_path('youtube/channels', 'frame-by-frame-avatar', 'png'),
            'banner_path': image_path('youtube/channels', 'frame-by-frame-banner', 'jpg'),
        },
    )


def seed_database(db, Channel, Video, Playlist, PlaylistVideo):
    if Channel.query.count() > 0:
        return

    channels_data = [
        ('quantum-lab', 'Quantum Lab', 'Science', '#7c4dff', True),
        ('frame-by-frame', 'Frame by Frame', 'Technology', '#3ea6ff', True),
        ('night-shift-jazz', 'Night Shift Jazz', 'Music', '#ff4e45', False),
        ('pixel-quest', 'Pixel Quest', 'Gaming', '#00c853', True),
        ('pantry-notes', 'Pantry Notes', 'Cooking', '#ff9800', False),
        ('window-seat', 'Window Seat', 'Travel', '#00b8d4', True),
    ]
    channels = {}
    for slug, name, category, accent, verified in channels_data:
        channel_assets = pick_channel_asset(slug)
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
        ('quantum-lab', 'How Quantum Sensors Read Invisible Changes', 'Science', ['quantum', 'sensor', 'lab'], '14:42', 882000, 42100, True, True, 2, 'jpg'),
        ('quantum-lab', 'Why Lunar Dust Destroys Precision Hardware', 'Science', ['moon', 'engineering', 'dust'], '11:28', 531000, 19800, False, True, 6, 'jpg'),
        ('quantum-lab', 'Building a Tabletop Gravity Wave Demo', 'Science', ['physics', 'demo', 'gravity'], '19:03', 263000, 11100, False, True, 11, 'jpg'),
        ('frame-by-frame', 'Inside the Tiny PC That Replaced My Laptop', 'Technology', ['mini pc', 'review', 'productivity'], '12:35', 1260000, 63300, True, True, 1, 'jpg'),
        ('frame-by-frame', 'Can This Studio Camera Beat a Flagship Phone', 'Technology', ['camera', 'studio', 'comparison'], '18:21', 917000, 54100, True, True, 4, 'jpg'),
        ('frame-by-frame', 'Three Display Calibrators Tested Back to Back', 'Technology', ['display', 'color', 'creator'], '16:09', 302000, 17300, False, True, 10, 'jpg'),
        ('night-shift-jazz', 'Loft Session: Midnight Rhodes and Tape Echo', 'Music', ['jazz', 'session', 'lofi'], '36:10', 471000, 23900, True, True, 3, 'jpg'),
        ('night-shift-jazz', 'Rainy City Vinyl Mix for Late Work', 'Music', ['vinyl', 'mix', 'study'], '58:32', 712000, 38100, True, True, 8, 'jpg'),
        ('night-shift-jazz', 'Sunrise Sax Theme With Analog Delay', 'Music', ['sax', 'analog', 'mood'], '9:54', 121000, 7100, False, True, 15, 'jpg'),
        ('pixel-quest', 'Speedrunning the Archive Ruins in 18 Minutes', 'Gaming', ['speedrun', 'rpg', 'challenge'], '18:45', 1560000, 80100, True, True, 2, 'jpg'),
        ('pixel-quest', 'Which Stealth Build Survives Nightmare Mode', 'Gaming', ['stealth', 'build', 'nightmare'], '22:12', 841000, 45200, False, True, 5, 'jpg'),
        ('pixel-quest', 'Five Open World Settings That Still Feel New', 'Gaming', ['open world', 'analysis', 'design'], '13:31', 402000, 18900, False, False, 13, 'jpg'),
        ('pantry-notes', 'The Crispy Chili Oil Noodles I Make Weekly', 'Cooking', ['noodles', 'recipe', 'chili oil'], '8:41', 298000, 14400, False, True, 7, 'jpg'),
        ('pantry-notes', 'Freezer Dumplings With a Restaurant Finish', 'Cooking', ['dumplings', 'meal prep', 'crispy'], '10:52', 429000, 22100, True, True, 12, 'jpg'),
        ('pantry-notes', 'Three Knife Skills That Change Weeknight Cooking', 'Cooking', ['knife skills', 'prep', 'beginner'], '15:08', 188000, 9700, False, True, 21, 'jpg'),
        ('window-seat', 'A Weekend Rail Journey Across Northern Spain', 'Travel', ['train', 'spain', 'itinerary'], '17:18', 509000, 24700, True, True, 9, 'jpg'),
        ('window-seat', 'How to Pack One Bag for a Rainy Spring City', 'Travel', ['packing', 'city break', 'spring'], '12:11', 366000, 16800, False, True, 16, 'jpg'),
        ('window-seat', 'The Quiet Coffee Streets of Kyoto at Dawn', 'Travel', ['kyoto', 'coffee', 'dawn'], '20:27', 287000, 13900, False, True, 25, 'jpg'),
        ('quantum-lab', 'Can You Hear a Starquake Through Data', 'Science', ['stars', 'waves', 'analysis'], '13:07', 341000, 15400, False, True, 14, 'jpg'),
        ('frame-by-frame', 'Desk Studio Lighting Under 100 Dollars', 'Technology', ['lighting', 'studio', 'budget'], '9:38', 276000, 13000, False, True, 18, 'jpg'),
        ('night-shift-jazz', 'Blue Hour Piano Loop for Deep Focus', 'Music', ['piano', 'focus', 'loop'], '42:16', 288000, 15000, False, True, 19, 'jpg'),
        ('pixel-quest', 'Best Controller Settings for Faster Aiming', 'Gaming', ['controller', 'settings', 'aiming'], '11:44', 523000, 24800, False, True, 17, 'jpg'),
        ('pantry-notes', 'One Pan Garlic Rice for Busy Weeknights', 'Cooking', ['rice', 'one pan', 'quick meal'], '7:56', 215000, 11200, False, True, 22, 'jpg'),
        ('window-seat', '48 Hours in Lisbon Without a Car', 'Travel', ['lisbon', 'walking', 'weekend'], '14:10', 319000, 14900, False, True, 23, 'jpg'),
    ]

    videos = {}
    for spec in video_specs:
        channel_slug, title, category, tags, duration, views, likes, trending, comments_enabled, days_ago, _image_ext = spec
        slug = title.lower().replace("'", '').replace('?', '').replace(':', '')
        slug = '-'.join(part for part in slug.replace(',', '').split())
        asset_paths = pick_video_asset(slug)
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


def seed_benchmark_users(db, User, Subscription, WatchLater, WatchHistory, UserLike, Video, Channel):
    if User.query.filter_by(email='alice.j@test.com').first():
        return

    users = [
        ('alice.j@test.com', 'Alice Jordan', 'alice-jordan', '#ff4e45'),
        ('bob.c@test.com', 'Bob Chen', 'bob-chen', '#00c853'),
        ('carol.d@test.com', 'Carol Diaz', 'carol-diaz', '#7c4dff'),
        ('david.k@test.com', 'David Kim', 'david-kim', '#3ea6ff'),
    ]
    created = {}
    for email, name, handle, color in users:
        user = User(email=email, display_name=name, handle=handle, avatar_color=color)
        user.set_password('TestPass123!')
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

    db.session.commit()
