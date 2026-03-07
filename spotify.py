import os
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

def get_spotify_client():
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=     os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret= os.getenv("SPOTIFY_CLIENT_SECRET"),
        redirect_uri=  "http://localhost:8888/callback",
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

def get_audio_features(sp, track_ids):
    """
    Fetch BPM, energy, valence etc. for a list of spotify track IDs.
    Returns a dict keyed by track_id.
    """
    if not track_ids:
        return {}
    features = sp.audio_features(track_ids)
    return {
        f["id"]: {
            "bpm":     f["tempo"],
            "energy":  f["energy"],    # 0.0–1.0, intensity
            "valence": f["valence"],   # 0.0–1.0, musical positivity
            "danceability": f["danceability"]
        }
        for f in features if f is not None
    }