import os
import re
import json
import spotipy
import requests
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

TRACK_CACHE_FILE = "spotify_track_cache.json"

def get_spotify_client():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=     os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret= os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=  "http://127.0.0.1:8000/callback",
        scope=         "user-read-recently-played",
        cache_path=    ".spotify_cache"   # saves token so you don't re-auth every time
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


def _search_bpm_deezer(song_name, artist):
    """Look up BPM via the free Deezer API (no auth needed)."""
    try:
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
    except requests.RequestException:
        pass
    return None


def get_audio_features(sp, track_ids):
    """Fetch BPM for Spotify track IDs using the free Deezer API."""
    if not track_ids:
        return {}

    features = {}

    for track_id in track_ids:
        try:
            track_info = sp.track(track_id)
            raw_name = track_info["name"]
            raw_artist = track_info["artists"][0]["name"]
        except Exception:
            features[track_id] = {"bpm": None}
            continue

        clean_name = _clean_name(raw_name)
        clean_artist = _clean_name(raw_artist)

        # Try cleaned names first, then raw names as fallback
        bpm = _search_bpm_deezer(clean_name, clean_artist)
        if bpm is None and (clean_name != raw_name or clean_artist != raw_artist):
            bpm = _search_bpm_deezer(raw_name, raw_artist)

        if bpm:
            print(f"  BPM found: {raw_name} -> {int(bpm)} BPM")
        else:
            print(f"  BPM not found: {raw_name}")

        features[track_id] = {"bpm": bpm}

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
    """Fetch the latest Spotify history and merge into the local cache.
    Call this regularly (e.g. after each activity) to build up history
    beyond Spotify's 24-hour API limit."""
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