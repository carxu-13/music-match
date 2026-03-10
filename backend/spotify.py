import os
import re
import json
import time
import sqlite3
import spotipy
import requests
from concurrent.futures import ThreadPoolExecutor
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

TRACK_CACHE_FILE = "spotify_track_cache.json"
BPM_DB_FILE = "bpm_cache.db"

# ── BPM Database ──────────────────────────────────────────────────

def _init_bpm_db():
    """Create BPM cache SQLite database if it doesn't exist."""
    conn = sqlite3.connect(BPM_DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bpm_cache (
            spotify_id TEXT PRIMARY KEY,
            song_name  TEXT,
            artist     TEXT,
            bpm        REAL,
            source     TEXT,
            looked_up  REAL
        )
    """)
    conn.commit()
    return conn


def _get_cached_bpm(conn, spotify_id):
    """Return cached BPM or None. Returns -1 if we checked and found nothing."""
    row = conn.execute(
        "SELECT bpm FROM bpm_cache WHERE spotify_id = ?", (spotify_id,)
    ).fetchone()
    if row is None:
        return None  # never checked
    return row[0]    # float or None (checked but not found)


def _set_cached_bpm(conn, spotify_id, song_name, artist, bpm, source=""):
    conn.execute(
        """INSERT OR REPLACE INTO bpm_cache
           (spotify_id, song_name, artist, bpm, source, looked_up)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (spotify_id, song_name, artist, bpm, source, time.time())
    )
    conn.commit()


# ── Migrate old JSON cache to SQLite ──────────────────────────────

def _migrate_json_cache():
    """One-time migration from bpm_cache.json to SQLite."""
    json_file = "bpm_cache.json"
    if not os.path.exists(json_file):
        return
    try:
        with open(json_file) as f:
            old_cache = json.load(f)
        if not old_cache:
            return
        conn = _init_bpm_db()
        for spotify_id, bpm in old_cache.items():
            _set_cached_bpm(conn, spotify_id, "", "", bpm, "migrated")
        conn.close()
        os.rename(json_file, json_file + ".bak")
        print(f"  Migrated {len(old_cache)} BPM entries from JSON to SQLite")
    except Exception as e:
        print(f"  BPM cache migration failed: {e}")


# Run migration on import
_migrate_json_cache()


def get_spotify_client():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=     os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret= os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=  "http://127.0.0.1:8000/callback",
        scope=         "user-read-recently-played",
        cache_path=    ".spotify_cache"
    ))

def get_tracks_during_activity(sp, activity_start_iso, activity_duration_s):
    """
    Return all Spotify tracks played during a given activity window.
    Checks local cache first, then falls back to Spotify API.
    """
    start_dt = datetime.fromisoformat(activity_start_iso.replace("Z", "+00:00"))
    start_ts = start_dt.timestamp()
    end_ts   = start_ts + activity_duration_s

    # Always refresh cache with latest Spotify history
    cache_spotify_tracks(sp)

    # Search cache for tracks overlapping the activity window
    cached = _load_track_cache()
    tracks = []
    seen = set()
    for t in cached:
        if t["end_ts"] < start_ts or t["start_ts"] > end_ts:
            continue
        key = (t["spotify_id"], t["end_ts"])
        if key not in seen:
            seen.add(key)
            tracks.append(t)

    # Also try the Spotify API directly (in case cache is stale)
    try:
        before_ms = int(end_ts * 1000) + 60_000
        results = sp.current_user_recently_played(limit=50, before=before_ms)
        for item in results["items"]:
            played_at  = datetime.fromisoformat(item["played_at"].replace("Z", "+00:00"))
            track_end  = played_at.timestamp()
            duration_s = item["track"]["duration_ms"] / 1000
            track_start = track_end - duration_s

            if track_end < start_ts or track_start > end_ts:
                continue

            key = (item["track"]["id"], track_end)
            if key not in seen:
                seen.add(key)
                tracks.append({
                    "name":       item["track"]["name"],
                    "artist":     item["track"]["artists"][0]["name"],
                    "spotify_id": item["track"]["id"],
                    "start_ts":   track_start,
                    "end_ts":     track_end,
                    "duration_s": duration_s,
                })
    except Exception as e:
        print(f"  Note: Spotify API lookup failed ({e}), using cached data only")

    return sorted(tracks, key=lambda t: t["start_ts"])

def _clean_name(name):
    """Strip feat./ft., parenthetical content, and special chars for better search."""
    name = re.sub(r"\s*\(.*?\)", "", name)
    name = re.sub(r"\s*\[.*?\]", "", name)
    name = re.sub(r"\s*[-–—].*feat\..*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*feat\..*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*ft\..*", "", name, flags=re.IGNORECASE)
    return name.strip()


# ── BPM Lookup Sources ────────────────────────────────────────────

def _search_bpm_deezer(song_name, artist):
    """Look up BPM via the free Deezer API (no auth needed)."""
    try:
        # Try artist + title search first
        query = f"{song_name} {artist}"
        r = requests.get(
            "https://api.deezer.com/search",
            params={"q": query, "limit": 5},
            timeout=10,
        )
        if r.status_code != 200:
            return None

        results = r.json().get("data", [])
        for result in results:
            track_id = result.get("id")
            if not track_id:
                continue
            detail = requests.get(f"https://api.deezer.com/track/{track_id}", timeout=10)
            if detail.status_code != 200:
                continue
            bpm = detail.json().get("bpm", 0)
            if bpm and 40 <= bpm <= 250:
                return float(bpm)

        # Fallback: search with just the song title
        r2 = requests.get(
            "https://api.deezer.com/search",
            params={"q": song_name, "limit": 5},
            timeout=10,
        )
        if r2.status_code == 200:
            for result in r2.json().get("data", []):
                track_id = result.get("id")
                if not track_id:
                    continue
                detail = requests.get(f"https://api.deezer.com/track/{track_id}", timeout=10)
                if detail.status_code != 200:
                    continue
                bpm = detail.json().get("bpm", 0)
                if bpm and 40 <= bpm <= 250:
                    return float(bpm)
    except requests.RequestException:
        pass
    return None


def _search_bpm_musicbrainz(song_name, artist):
    """Look up BPM via MusicBrainz API (free, no auth, has rate limit of 1req/s)."""
    try:
        query = f'recording:"{song_name}" AND artist:"{artist}"'
        r = requests.get(
            "https://musicbrainz.org/ws/2/recording",
            params={"query": query, "limit": 5, "fmt": "json"},
            headers={"User-Agent": "MusicMatch/1.0 (learning project)"},
            timeout=10,
        )
        if r.status_code != 200:
            return None

        recordings = r.json().get("recordings", [])
        for rec in recordings:
            rec_id = rec.get("id")
            if not rec_id:
                continue
            time.sleep(1.1)  # rate limit
            detail = requests.get(
                f"https://musicbrainz.org/ws/2/recording/{rec_id}",
                params={"inc": "tags", "fmt": "json"},
                headers={"User-Agent": "MusicMatch/1.0 (learning project)"},
                timeout=10,
            )
            if detail.status_code != 200:
                continue
            tags = detail.json().get("tags", [])
            for tag in tags:
                name = tag.get("name", "")
                m = re.match(r"(?:bpm[:\s]*)?(\d{2,3})(?:\s*bpm)?$", name, re.IGNORECASE)
                if m:
                    bpm = int(m.group(1))
                    if 40 <= bpm <= 250:
                        return float(bpm)
    except requests.RequestException:
        pass
    return None


def _lookup_single_bpm(song_name, artist):
    """Try all BPM sources for a single track. Returns (bpm, source) or (None, None)."""
    clean_name = _clean_name(song_name)
    clean_artist = _clean_name(artist)

    # 1. Deezer (fast, no rate limit)
    bpm = _search_bpm_deezer(clean_name, clean_artist)
    if bpm:
        return bpm, "deezer"

    # Try with raw names if cleaning changed anything
    if clean_name != song_name or clean_artist != artist:
        bpm = _search_bpm_deezer(song_name, artist)
        if bpm:
            return bpm, "deezer"

    # 2. MusicBrainz (slow due to rate limit, but wider coverage)
    bpm = _search_bpm_musicbrainz(clean_name, clean_artist)
    if bpm:
        return bpm, "musicbrainz"

    return None, None


def get_audio_features(sp, track_ids):
    """Fetch BPM for Spotify track IDs. Uses SQLite cache, Deezer + MusicBrainz APIs."""
    if not track_ids:
        return {}

    conn = _init_bpm_db()
    features = {}
    uncached_ids = []

    # Phase 1: Check cache for all tracks
    for track_id in track_ids:
        cached = _get_cached_bpm(conn, track_id)
        if cached is not None:
            # We have a result (could be a real BPM or None for "checked, not found")
            features[track_id] = {"bpm": cached if cached else None}
        else:
            uncached_ids.append(track_id)

    if not uncached_ids:
        conn.close()
        print(f"  BPM: all {len(track_ids)} tracks served from cache")
        return features

    print(f"  BPM: {len(track_ids) - len(uncached_ids)} cached, {len(uncached_ids)} to look up")

    # Phase 2: Get track info from Spotify for uncached tracks
    track_info_map = {}
    for track_id in uncached_ids:
        try:
            info = sp.track(track_id)
            track_info_map[track_id] = (info["name"], info["artists"][0]["name"])
        except Exception:
            features[track_id] = {"bpm": None}
            _set_cached_bpm(conn, track_id, "", "", None, "spotify_error")

    # Phase 3: Look up BPMs concurrently via Deezer (no rate limit)
    def lookup_deezer(track_id):
        name, artist = track_info_map[track_id]
        bpm = _search_bpm_deezer(_clean_name(name), _clean_name(artist))
        if bpm is None and (_clean_name(name) != name or _clean_name(artist) != artist):
            bpm = _search_bpm_deezer(name, artist)
        return track_id, name, artist, bpm

    ids_to_lookup = [tid for tid in uncached_ids if tid in track_info_map]
    still_missing = []

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lookup_deezer, ids_to_lookup))

    for track_id, name, artist, bpm in results:
        if bpm:
            features[track_id] = {"bpm": bpm}
            _set_cached_bpm(conn, track_id, name, artist, bpm, "deezer")
            print(f"  BPM found (Deezer): {name} -> {int(bpm)}")
        else:
            still_missing.append(track_id)

    # Phase 4: Try MusicBrainz for remaining (sequential due to rate limit)
    for track_id in still_missing:
        name, artist = track_info_map[track_id]
        bpm = _search_bpm_musicbrainz(_clean_name(name), _clean_name(artist))
        if bpm:
            features[track_id] = {"bpm": bpm}
            _set_cached_bpm(conn, track_id, name, artist, bpm, "musicbrainz")
            print(f"  BPM found (MusicBrainz): {name} -> {int(bpm)}")
        else:
            features[track_id] = {"bpm": None}
            _set_cached_bpm(conn, track_id, name, artist, None, "not_found")
            print(f"  BPM not found: {name}")

    conn.close()
    return features


# ── Spotify track cache ─────────────────────────────────────────────

def _load_track_cache():
    if os.path.exists(TRACK_CACHE_FILE):
        with open(TRACK_CACHE_FILE) as f:
            return json.load(f)
    return []


def _save_track_cache(tracks):
    # Deduplicate by (spotify_id, end_ts)
    seen = set()
    unique = []
    for t in tracks:
        key = (t["spotify_id"], t["end_ts"])
        if key not in seen:
            seen.add(key)
            unique.append(t)
    with open(TRACK_CACHE_FILE, "w") as f:
        json.dump(unique, f, indent=2)


def cache_spotify_tracks(sp):
    """Fetch the latest Spotify history and merge into the local cache."""
    results = sp.current_user_recently_played(limit=50)
    new_tracks = []
    for item in results["items"]:
        played_at = datetime.fromisoformat(item["played_at"].replace("Z", "+00:00"))
        track_end = played_at.timestamp()
        duration_s = item["track"]["duration_ms"] / 1000
        new_tracks.append({
            "name":       item["track"]["name"],
            "artist":     item["track"]["artists"][0]["name"],
            "spotify_id": item["track"]["id"],
            "start_ts":   track_end - duration_s,
            "end_ts":     track_end,
            "duration_s": duration_s,
        })

    existing = _load_track_cache()
    merged = existing + new_tracks
    _save_track_cache(merged)
    print(f"  Spotify cache: {len(merged)} total tracks stored")
    return merged
