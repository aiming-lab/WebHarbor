from datetime import datetime, timedelta

BRAND_LOGO_PATH = '/static/images/weather/upstream/branding/weather-channel-logo.svg'
WEATHER_MEDIA_CARDS = [
    {
        'title': 'Wall Of Flames In South Florida Could See Rain In Forecast',
        'image': '/static/images/weather/upstream/media/00-wall-of-flames-in-south-florida-could-see-rain-in-forecast.jpg',
        'watch_url': 'https://weather.com/news/video/broward-florida-wildfire-containment-update',
    },
    {
        'title': 'Lucky Labrador Lives After Lake Rescue',
        'image': '/static/images/weather/upstream/media/01-lucky-labrador-lives-after-lake-rescue.jpg',
        'watch_url': 'https://weather.com/news/video/lake-mohawk-dog-rescue',
    },
    {
        'title': 'Greatest Weather-Named Albums For World Record Store Day',
        'image': '/static/images/weather/upstream/media/02-greatest-weather-named-albums-for-world-record-store-day.jpg',
        'watch_url': 'https://weather.com/news/video/best-weather-albums-record-store-day-drake-prince-rihanna-metallica',
    },
    {
        'title': "Over A Week Later, Georgia's Pineland Road Fire Still Burns",
        'image': '/static/images/weather/upstream/media/03-over-a-week-later-georgia-s-pineland-road-fire-still-burns.png',
        'watch_url': 'https://weather.com/news/video/pineland-road-wildfire-blazes-on',
    },
    {
        'title': 'Weather Whiz: May 10',
        'image': '/static/images/weather/upstream/media/04-weather-whiz-may-10.jpg',
        'watch_url': 'https://weather.com/news/news/2026-05-04-weather-whiz-may-10',
    },
    {
        'title': 'Weather Of The World: May 10',
        'image': '/static/images/weather/upstream/media/05-weather-of-the-world-may-10.jpg',
        'watch_url': 'https://weather.com/news/news/2026-05-04-weather-of-the-world-may-10',
    },
    {
        'title': 'Where Has It Spread? Dozens Of Passengers Left Hantavirus Cruise Ship After First Death',
        'image': '/static/images/weather/upstream/media/06-where-has-it-spread-dozens-of-passengers-left-hantavirus-cruise-ship-after-first-death.jpg',
        'watch_url': 'https://weather.com/news/news/2026-05-05-hantavirus-cruise-ship-human-to-human-transmission',
    },
    {
        'title': 'Riders Narrowly Avoid Falling Utility Pole In Violent Storm',
        'image': '/static/images/weather/upstream/media/07-riders-narrowly-avoid-falling-utility-pole-in-violent-storm.jpg',
        'watch_url': 'https://weather.com/news/video/power-pole-collapse-thailand-storm',
    },
    {
        'title': 'Weather Whiz: May 3',
        'image': '/static/images/weather/upstream/media/08-weather-whiz-may-3.jpg',
        'watch_url': 'https://weather.com/news/news/2026-04-27-weather-whiz-may-3',
    },
    {
        'title': 'Weather Of The World: May 3',
        'image': '/static/images/weather/upstream/media/09-weather-of-the-world-may-3.jpg',
        'watch_url': 'https://weather.com/news/news/2026-04-27-weather-of-the-world-may-3',
    },
]


def image_path(section: str, slug: str, ext: str = 'svg') -> str:
    return f'/static/images/{section}/{slug}.{ext}'


def seed_site_metadata(db, SiteAsset, WeatherMediaCard) -> bool:
    changed = False
    if SiteAsset.query.filter_by(asset_key='brand_logo').first() is None:
        db.session.add(SiteAsset(asset_key='brand_logo', asset_path=BRAND_LOGO_PATH))
        changed = True

    if WeatherMediaCard.query.count() == 0:
        for index, card in enumerate(WEATHER_MEDIA_CARDS):
            db.session.add(
                WeatherMediaCard(
                    position=index,
                    title=card['title'],
                    image_path=card['image'],
                    watch_url=card['watch_url'],
                )
            )
        changed = True
    return changed


def seed_database(db, Location, CurrentConditions, DailyForecast, HourlyForecast, SevereAlert, SiteAsset, WeatherMediaCard):
    metadata_changed = seed_site_metadata(db, SiteAsset, WeatherMediaCard)
    if Location.query.count() > 0:
        if metadata_changed:
            db.session.commit()
        return

    locations_data = [
        ('new-york-ny', 'New York', 'NY', 'United States', 41, 39, 67, 14, 'NNW', 2, 'Cloudy', 'jpg'),
        ('miami-fl', 'Miami', 'FL', 'United States', 82, 86, 72, 21, 'ESE', 8, 'Humid Sunshine', 'svg'),
        ('chicago-il', 'Chicago', 'IL', 'United States', 34, 29, 61, 18, 'W', 1, 'Lake Breeze', 'svg'),
        ('seattle-wa', 'Seattle', 'WA', 'United States', 47, 45, 75, 9, 'SW', 1, 'Light Rain', 'svg'),
        ('phoenix-az', 'Phoenix', 'AZ', 'United States', 76, 79, 28, 6, 'N', 7, 'Dry Sun', 'svg'),
        ('london-uk', 'London', 'England', 'United Kingdom', 49, 47, 80, 12, 'SW', 1, 'Drizzle', 'svg'),
        ('tokyo-jp', 'Tokyo', 'Tokyo', 'Japan', 58, 56, 52, 11, 'NE', 4, 'Bright Clouds', 'svg'),
        ('reykjavik-is', 'Reykjavik', 'Capital Region', 'Iceland', 28, 22, 78, 24, 'N', 0, 'Snow Showers', 'svg'),
        ('denver-co', 'Denver', 'CO', 'United States', 52, 48, 42, 13, 'W', 5, 'Sunny High Plains', 'jpg'),
        ('san-francisco-ca', 'San Francisco', 'CA', 'United States', 61, 59, 68, 16, 'NW', 4, 'Marine Layer', 'jpg'),
        ('singapore-sg', 'Singapore', 'Singapore', 'Singapore', 88, 95, 84, 7, 'S', 9, 'Tropical Showers', 'jpg'),
    ]
    hero_fallback = {
        'denver-co': '/static/images/weather/hero/feature-story.jpg',
        'san-francisco-ca': '/static/images/weather/hero/editor-pick.jpg',
        'singapore-sg': '/static/images/weather/hero/seasonal-tip.png',
    }
    radar_fallback = {
        'denver-co': '/static/images/weather/radar/new-york-ny.svg',
        'san-francisco-ca': '/static/images/weather/radar/new-york-ny.svg',
        'singapore-sg': '/static/images/weather/radar/new-york-ny.svg',
    }
    locations = {}
    for slug, city, region, country, temp, feels_like, humidity, wind, wind_dir, uv, label, hero_ext in locations_data:
        location = Location(
            slug=slug,
            city=city,
            region=region,
            country=country,
            search_label=f'{city}, {region}, {country}',
            hero_image=hero_fallback.get(slug, image_path('weather/hero', slug, hero_ext)),
            radar_image=radar_fallback.get(slug, image_path('weather/radar', slug)),
            summary=f'{city} has a rich local forecast view with current conditions, a 10-day outlook, and detailed alert tracking.',
        )
        db.session.add(location)
        locations[slug] = (location, temp, feels_like, humidity, wind, wind_dir, uv, label)
    db.session.flush()

    for slug, payload in locations.items():
        location, temp, feels_like, humidity, wind, wind_dir, uv, label = payload
        db.session.add(CurrentConditions(
            location_id=location.id,
            temperature_f=temp,
            feels_like_f=feels_like,
            humidity=humidity,
            wind_mph=wind,
            wind_direction=wind_dir,
            uv_index=uv,
            visibility_mi=10 if slug != 'reykjavik-is' else 4,
            air_quality='Good' if slug not in {'miami-fl', 'phoenix-az'} else 'Moderate',
            condition_label=label,
            updated_at=datetime(2024, 2, 15, 8, 0, 0),
        ))

    base_date = datetime(2024, 2, 15).date()
    day_profiles = {
        'new-york-ny': [(43, 35, 20, 'Cloudy'), (46, 33, 15, 'Windy'), (49, 36, 10, 'Partly Sunny'), (52, 39, 20, 'Clear'), (55, 41, 40, 'Rain Late'), (51, 38, 50, 'Showers'), (47, 34, 20, 'Bright Clouds'), (44, 31, 10, 'Clear'), (42, 29, 15, 'Cold Morning'), (45, 32, 25, 'Mixed Clouds')],
        'miami-fl': [(84, 74, 20, 'Humid Sunshine'), (85, 75, 30, 'Partly Cloudy'), (87, 76, 55, 'Thunderstorm Late'), (88, 77, 70, 'Tropical Storms'), (86, 75, 60, 'Scattered Rain'), (83, 74, 35, 'Warm Breeze'), (82, 73, 25, 'Sunny'), (81, 72, 20, 'Sunny'), (80, 71, 15, 'Clear'), (82, 72, 30, 'Showers')],
        'chicago-il': [(36, 28, 25, 'Lake Breeze'), (38, 29, 15, 'Cloudy'), (41, 31, 10, 'Partly Sunny'), (39, 27, 35, 'Snow Flurries'), (35, 24, 20, 'Cold Wind'), (37, 26, 15, 'Clear'), (40, 30, 20, 'Cloudy'), (42, 32, 30, 'Light Rain'), (45, 34, 40, 'Showers'), (43, 31, 20, 'Bright Clouds')],
        'seattle-wa': [(48, 43, 65, 'Light Rain'), (49, 42, 75, 'Steady Rain'), (47, 41, 70, 'Showers'), (50, 40, 50, 'Cloudy'), (53, 42, 35, 'Sun Breaks'), (54, 43, 30, 'Partly Sunny'), (52, 42, 45, 'Rain Late'), (49, 40, 60, 'Showers'), (48, 39, 55, 'Rain'), (50, 41, 40, 'Cloudy')],
        'phoenix-az': [(77, 55, 0, 'Dry Sun'), (79, 57, 0, 'Sunny'), (82, 58, 0, 'Sunny'), (80, 56, 0, 'Clear'), (78, 54, 0, 'Warm Sun'), (76, 52, 0, 'Sunny'), (74, 50, 0, 'Clear'), (73, 49, 0, 'Sunny'), (75, 51, 0, 'Warm Sun'), (77, 53, 0, 'Bright Sky')],
        'london-uk': [(50, 43, 70, 'Drizzle'), (51, 42, 55, 'Cloudy'), (53, 44, 35, 'Partly Sunny'), (54, 45, 40, 'Rain Late'), (52, 43, 50, 'Showers'), (49, 41, 45, 'Grey Skies'), (48, 40, 35, 'Cloudy'), (50, 41, 30, 'Brighter'), (52, 43, 35, 'Clear Spells'), (51, 42, 45, 'Drizzle')],
        'tokyo-jp': [(59, 48, 20, 'Bright Clouds'), (61, 49, 15, 'Sunny'), (63, 51, 20, 'Partly Sunny'), (62, 50, 30, 'Cloudy'), (60, 49, 35, 'Rain Late'), (58, 47, 25, 'Sunny'), (57, 46, 20, 'Clear'), (59, 47, 15, 'Mild Sun'), (61, 49, 25, 'Clouds'), (60, 48, 30, 'Showers')],
        'reykjavik-is': [(30, 21, 75, 'Snow Showers'), (32, 23, 70, 'Cloudy'), (33, 25, 60, 'Windy Snow'), (35, 27, 55, 'Bright Cold'), (34, 26, 65, 'Mixed Precip'), (31, 23, 70, 'Snow'), (29, 21, 80, 'Snow Showers'), (30, 22, 75, 'Cloudy'), (31, 24, 65, 'Cold Wind'), (33, 25, 60, 'Clear Breaks')],
        'denver-co': [(55, 36, 10, 'Sunny High Plains'), (58, 37, 5, 'Sunny'), (60, 39, 0, 'Dry and Clear'), (57, 35, 10, 'Breezy'), (54, 33, 15, 'Passing Clouds'), (52, 31, 20, 'Light Snow Late'), (50, 30, 20, 'Cold Morning'), (53, 34, 10, 'Bright Sun'), (56, 36, 5, 'Dry Sun'), (57, 37, 10, 'Partly Sunny')],
        'san-francisco-ca': [(62, 51, 20, 'Marine Layer'), (63, 52, 15, 'Morning Fog'), (65, 53, 10, 'Sun Breaks'), (64, 52, 15, 'Partly Cloudy'), (63, 51, 20, 'Coastal Breeze'), (62, 50, 25, 'Drizzle Late'), (61, 49, 25, 'Grey Morning'), (62, 50, 15, 'Bright Afternoon'), (63, 51, 10, 'Sun and Clouds'), (64, 52, 20, 'Mild Clouds')],
        'singapore-sg': [(89, 79, 70, 'Tropical Showers'), (90, 80, 75, 'Thunderstorms'), (91, 80, 65, 'Humid Clouds'), (90, 79, 60, 'Scattered Storms'), (89, 79, 70, 'Rain and Sun'), (88, 78, 80, 'Heavy Showers'), (89, 79, 70, 'Thunderstorms'), (90, 80, 65, 'Humid Sunshine'), (89, 79, 60, 'Cloudbursts Late'), (88, 78, 70, 'Tropical Rain')],
    }

    for slug, payload in locations.items():
        location = payload[0]
        for offset, (high, low, precip, label) in enumerate(day_profiles[slug]):
            db.session.add(DailyForecast(
                location_id=location.id,
                forecast_date=base_date + timedelta(days=offset),
                high_f=high,
                low_f=low,
                precip_pct=precip,
                humidity=payload[3],
                wind_mph=payload[4],
                uv_index=payload[6],
                sunrise='6:48 AM',
                sunset='5:39 PM',
                condition_label=label,
            ))

    for slug, payload in locations.items():
        location, temp, _, _, wind, _, _, label = payload
        for hour_offset in range(24):
            db.session.add(HourlyForecast(
                location_id=location.id,
                forecast_time=datetime(2024, 2, 15, 0, 0, 0) + timedelta(hours=hour_offset),
                temperature_f=max(18, temp - 6 + (hour_offset % 8)),
                precip_pct=min(90, (hour_offset * 7) % 65 + (10 if slug in {'miami-fl', 'seattle-wa'} else 0)),
                wind_mph=wind + (hour_offset % 4),
                condition_label=label if hour_offset < 12 else 'Partly Cloudy',
            ))

    alerts = [
        ('miami-fl', 'Coastal Flood Advisory', 'Moderate', 'Minor coastal flooding expected during the late afternoon tide cycle.', 18),
        ('seattle-wa', 'Rainfall Advisory', 'Minor', 'Persistent rain may slow evening traffic and reduce visibility.', 14),
        ('reykjavik-is', 'Wind Chill Warning', 'Severe', 'Arctic gusts will drive hazardous wind chill through the overnight hours.', 20),
        ('denver-co', 'Red Flag Warning', 'Moderate', 'Dry gusty conditions may cause rapid wildfire spread this afternoon.', 10),
        ('singapore-sg', 'Heat Advisory', 'Minor', 'High humidity and heat index values may cause heat stress during midday.', 8),
    ]
    for slug, alert_type, severity, details, hours in alerts:
        db.session.add(SevereAlert(
            location_id=locations[slug][0].id,
            alert_type=alert_type,
            severity=severity,
            headline=f'{alert_type} for {locations[slug][0].city}',
            details=details,
            expires_at=datetime(2024, 2, 15, 8, 0, 0) + timedelta(hours=hours),
        ))

    db.session.commit()


def seed_benchmark_users(db, User, SavedLocation, Location):
    if User.query.filter_by(email='alice.j@test.com').first():
        return

    users = [
        ('alice.j@test.com', 'Alice Jordan', 'imperial', 'new-york-ny', ['new-york-ny', 'london-uk', 'san-francisco-ca']),
        ('bob.c@test.com', 'Bob Chen', 'imperial', 'phoenix-az', ['phoenix-az', 'tokyo-jp', 'denver-co']),
        ('carol.d@test.com', 'Carol Diaz', 'metric', 'miami-fl', ['miami-fl', 'seattle-wa', 'singapore-sg']),
        ('david.k@test.com', 'David Kim', 'imperial', 'chicago-il', ['chicago-il', 'reykjavik-is', 'san-francisco-ca']),
    ]
    lookup = {location.slug: location for location in Location.query.all()}
    for email, name, units, home_slug, saved_slugs in users:
        user = User(email=email, full_name=name, preferred_units=units, home_location_id=lookup[home_slug].id)
        user.set_password('TestPass123!')
        db.session.add(user)
        db.session.flush()
        for slug in saved_slugs:
            db.session.add(SavedLocation(user_id=user.id, location_id=lookup[slug].id))

    db.session.commit()
