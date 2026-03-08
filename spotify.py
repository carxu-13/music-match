import os
import re
import spotipy
import requests
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

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
    activity_start_iso: UTC ISO string like "2024-03-01T10:00:00Z"
    activity_duration_s: total activity duration in seconds
    """
    start_dt = datetime.fromisoformat(activity_start_iso.replace("Z", "+00:00"))
    start_ts = start_dt.timestamp()
    end_ts   = start_ts + activity_duration_s

    # Spotify's `before` param is a Unix timestamp in milliseconds
    before_ms = int(end_ts * 1000) + 60_000  # add 1 min buffer for last track

    results = sp.current_user_recently_played(limit=50, before=before_ms)

    tracks = []
    for item in results["items"]:
        played_at  = datetime.fromisoformat(item["played_at"].replace("Z", "+00:00"))
        track_end  = played_at.timestamp()
        duration_s = item["track"]["duration_ms"] / 1000
        track_start = track_end - duration_s

        # Only keep tracks that overlap with the activity window
        if track_end < start_ts or track_start > end_ts:
            continue

        tracks.append({
            "name":       item["track"]["name"],
            "artist":     item["track"]["artists"][0]["name"],
            "spotify_id": item["track"]["id"],
            "start_ts":   track_start,    # absolute Unix timestamp
            "end_ts":     track_end,
            "duration_s": duration_s,
        })

    # Sort chronologically
    return sorted(tracks, key=lambda t: t["start_ts"])

def _clean_track_name(name):
    """Strip feat./ft., parenthetical content, and special chars for better search."""
    name = re.sub(r"\s*\(.*?\)", "", name)       # remove (feat. X), (Remix), etc.
    name = re.sub(r"\s*\[.*?\]", "", name)       # remove [Deluxe], etc.
    name = re.sub(r"\s*[-–—].*feat\..*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*feat\..*", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*ft\..*", "", name, flags=re.IGNORECASE)
    return name.strip()


def _search_getsongbpm(api_key, song_name, artist=None):
    """Search GetSongBPM and return the tempo if found, else None."""
    if artist:
        lookup = f"song:{song_name} artist:{artist}"
        search_type = "both"
    else:
        lookup = song_name
        search_type = "song"

    r = requests.get(
        "https://api.getsongbpm.com/search/",
        params={"api_key": api_key, "type": search_type, "lookup": lookup}
    )

    if r.status_code != 200:
        return None

    search_results = r.json().get("search")
    if not search_results:
        return None

    tempo = search_results[0].get("tempo")
    return float(tempo) if tempo else None


def get_audio_features(sp, track_ids, getbpm_api_key=None):
    """
    Fetch BPM and other features for a list of Spotify track IDs.
    Uses GetSongBPM API as a replacement for Spotify's deprecated audio-features endpoint.
    """
    if not track_ids or not getbpm_api_key:
        return {}

    features = {}

    for track_id in track_ids:
        track_info = sp.track(track_id)
        raw_name = track_info["name"]
        raw_artist = track_info["artists"][0]["name"]

        clean_name = _clean_track_name(raw_name)
        clean_artist = _clean_track_name(raw_artist)

        # Try: cleaned song + artist
        bpm = _search_getsongbpm(getbpm_api_key, clean_name, clean_artist)

        # Fallback: song name only
        if bpm is None:
            bpm = _search_getsongbpm(getbpm_api_key, clean_name)

        # Fallback: raw song name only
        if bpm is None and clean_name != raw_name:
            bpm = _search_getsongbpm(getbpm_api_key, raw_name)

        if bpm:
            print(f"  BPM found: {raw_name} -> {int(bpm)} BPM")
        else:
            print(f"  BPM not found: {raw_name}")

        features[track_id] = {
            "bpm":         bpm,
            "energy":      None,
            "valence":     None,
            "danceability": None
        }

    return features