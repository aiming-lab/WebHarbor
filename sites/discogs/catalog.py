"""Convert full Discogs release responses without filling missing facts."""
from datetime import datetime, timezone


def artist_credit(artists):
    parts = []
    for artist in artists:
        parts.append(artist.get("anv") or artist["name"])
        if artist.get("join"):
            parts.append(artist["join"])
    return " ".join(parts).strip()


def normalize_release(source):
    rid = source.get("id")
    if type(rid) is not int or rid <= 0:
        raise ValueError("A positive Discogs release ID is required")
    if source.get("resource_url") != f"https://api.discogs.com/releases/{rid}":
        raise ValueError(f"Release {rid}: source identity does not match")
    required = ("title", "artists", "labels", "formats", "genres", "tracklist")
    if any(key not in source for key in required) or not source["artists"]:
        raise ValueError(f"Release {rid}: expected a full release response, not search results")
    for artist in source["artists"]:
        if (artist.get("id") is not None and type(artist["id"]) is not int) or not artist.get("name"):
            raise ValueError(f"Release {rid}: artist identity is missing")
    for label in source["labels"]:
        if (label.get("id") is not None and type(label["id"]) is not int) or not label.get("name"):
            raise ValueError(f"Release {rid}: label identity is missing")
    formats = []
    names = []
    for item in source["formats"]:
        name = item["name"]
        qty = item.get("qty")
        description = [f"{qty} × {name}" if qty and str(qty) != "1" else name]
        description.extend(item.get("descriptions") or [])
        if item.get("text"):
            description.append(item["text"])
        formats.append(", ".join(description))
        names.extend([name, *(item.get("descriptions") or [])])
    tracks = []

    def add_tracks(items, depth=0):
        for item in items:
            tracks.append({
                "position": item.get("position") or "",
                "title": item["title"], "duration": item.get("duration") or "",
                "artist_credit": artist_credit(item.get("artists") or []),
                "kind": item.get("type_") or "", "depth": depth,
            })
            add_tracks(item.get("sub_tracks") or [], depth + 1)

    add_tracks(source["tracklist"])
    added_at = None
    if source.get("date_added"):
        added_at = datetime.fromisoformat(source["date_added"].replace("Z", "+00:00"))
        if added_at.tzinfo:
            added_at = added_at.astimezone(timezone.utc).replace(tzinfo=None)
    return {
        "id": rid, "title": source["title"], "artists": source["artists"],
        "artist_credit": artist_credit(source["artists"]), "labels": source["labels"],
        "master_id": source.get("master_id") or None,
        "year": source.get("year") or None, "country": source.get("country") or "",
        "released": source.get("released") or "", "notes": source.get("notes") or "",
        "data_quality": source.get("data_quality") or "",
        "barcodes": [item["value"] for item in source.get("identifiers", [])
                     if item.get("type") == "Barcode"],
        "genres": source["genres"], "styles": source.get("styles") or [],
        "format_names": list(dict.fromkeys(names)),
        "format_description": "; ".join(formats),
        "primary_format": source["formats"][0]["name"] if source["formats"] else "",
        "tracks": tracks, "added_at": added_at,
        "source_community": source.get("community") or {},
        "image_urls": [url for image in source.get("images") or []
                       for url in (image.get("uri"), image.get("uri150")) if url],
    }
