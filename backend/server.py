import os
import json
import uuid
import math
import xml.etree.ElementTree as ET
from datetime import datetime
from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app, supports_credentials=True, origins=["http://localhost:5173", "http://127.0.0.1:5173"])

FRONTEND_URL = "http://localhost:5173"
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# ── Token-based session store ───────────────────────────────────────
# Avoids cookie/cross-origin issues between frontend and backend ports.

_sessions = {}             # token -> {strava_access_token, spotify_access_token, ...}
_garmin_clients = {}       # token -> Garmin client
_uploaded_activities = {}  # token -> list of parsed activities
_pending_tokens = {}       # state -> token (for OAuth flows)


def _get_session(token=None):
    """Get session data for the given token (from Authorization header or param)."""
    if token is None:
        auth_header = request.headers.get("Authorization", "")
        token = auth_header.replace("Bearer ", "") if auth_header else ""
    return _sessions.get(token, {}), token


# ── Auth: Strava ────────────────────────────────────────────────────

@app.route("/api/auth/strava")
def strava_auth():
    # Get or create a token for this user
    token = request.args.get("token", str(uuid.uuid4()))
    if token not in _sessions:
        _sessions[token] = {}

    # Use state param to pass our token through the OAuth flow
    state = str(uuid.uuid4())
    _pending_tokens[state] = token

    client_id = os.getenv("STRAVA_CLIENT_ID")
    redirect_uri = "http://127.0.0.1:8000/api/auth/strava/callback"
    return redirect(
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={client_id}&redirect_uri={redirect_uri}"
        f"&response_type=code&scope=activity:read_all"
        f"&state={state}"
    )


@app.route("/api/auth/strava/callback")
def strava_callback():
    code = request.args.get("code")
    state = request.args.get("state", "")
    token = _pending_tokens.pop(state, None)

    if not code or not token:
        return redirect(f"{FRONTEND_URL}?error=strava_denied")

    import requests as req
    r = req.post("https://www.strava.com/oauth/token", data={
        "client_id":     os.getenv("STRAVA_CLIENT_ID"),
        "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
        "code":          code,
        "grant_type":    "authorization_code"
    })
    if r.status_code != 200:
        return redirect(f"{FRONTEND_URL}?error=strava_token_failed")

    tokens = r.json()
    _sessions[token]["strava_access_token"] = tokens["access_token"]
    _sessions[token]["strava_refresh_token"] = tokens["refresh_token"]
    return redirect(f"{FRONTEND_URL}?auth=strava_ok&token={token}")


# ── Auth: Spotify ───────────────────────────────────────────────────

@app.route("/api/auth/spotify")
def spotify_auth():
    token = request.args.get("token", str(uuid.uuid4()))
    if token not in _sessions:
        _sessions[token] = {}

    state = str(uuid.uuid4())
    _pending_tokens[state] = token

    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    redirect_uri = "http://127.0.0.1:8000/callback"
    return redirect(
        f"https://accounts.spotify.com/authorize"
        f"?client_id={client_id}&redirect_uri={redirect_uri}"
        f"&response_type=code&scope=user-read-recently-played"
        f"&state={state}"
    )


@app.route("/callback")
def spotify_callback():
    code = request.args.get("code")
    state = request.args.get("state", "")
    token = _pending_tokens.pop(state, None)

    if not code or not token:
        return redirect(f"{FRONTEND_URL}?error=spotify_denied")

    import requests as req
    r = req.post("https://accounts.spotify.com/api/token", data={
        "grant_type":    "authorization_code",
        "code":          code,
        "redirect_uri":  "http://127.0.0.1:8000/callback",
        "client_id":     os.getenv("SPOTIFY_CLIENT_ID"),
        "client_secret": os.getenv("SPOTIFY_CLIENT_SECRET"),
    })
    if r.status_code != 200:
        return redirect(f"{FRONTEND_URL}?error=spotify_token_failed")

    tokens = r.json()
    _sessions[token]["spotify_access_token"] = tokens["access_token"]
    _sessions[token]["spotify_refresh_token"] = tokens.get("refresh_token")
    return redirect(f"{FRONTEND_URL}?auth=spotify_ok&token={token}")


# ── Auth: Garmin (email/password) ───────────────────────────────────

@app.route("/api/auth/garmin", methods=["POST"])
def garmin_auth():
    data = request.json
    email = data.get("email") or os.getenv("GARMIN_EMAIL")
    password = data.get("password") or os.getenv("GARMIN_PASSWORD")

    from garminconnect import Garmin
    client = Garmin(email, password)
    try:
        client.login()
    except Exception as e:
        return jsonify({"error": str(e)}), 401

    sess, token = _get_session()
    if not token or token not in _sessions:
        token = str(uuid.uuid4())
        _sessions[token] = {}
    _sessions[token]["garmin_authenticated"] = True
    _garmin_clients[token] = client
    return jsonify({"status": "ok", "token": token})


# ── Auth status ─────────────────────────────────────────────────────

@app.route("/api/auth/status")
def auth_status():
    sess, token = _get_session()
    return jsonify({
        "strava":  "strava_access_token" in sess,
        "spotify": "spotify_access_token" in sess,
        "garmin":  sess.get("garmin_authenticated", False),
    })


# ── Activities ──────────────────────────────────────────────────────

@app.route("/api/activities")
def list_activities():
    sess, token = _get_session()
    activities = []

    if "strava_access_token" in sess:
        from strava import get_recent_activities
        try:
            strava_acts = get_recent_activities(sess["strava_access_token"], n=15)
            for a in strava_acts:
                a["source"] = "strava"
            activities.extend(strava_acts)
        except Exception:
            pass

    if token in _uploaded_activities:
        activities.extend(_uploaded_activities[token])

    return jsonify(activities)


@app.route("/api/analyze/<activity_id>")
def analyze_activity(activity_id):
    sess, token = _get_session()
    activity_id = int(activity_id)

    uploaded = _uploaded_activities.get(token, [])
    uploaded_match = next((a for a in uploaded if a["id"] == activity_id), None)

    if uploaded_match:
        streams = uploaded_match.get("_streams", {})
        activity = {k: v for k, v in uploaded_match.items() if k != "_streams"}
    else:
        if "strava_access_token" not in sess:
            return jsonify({"error": "Not authenticated with Strava"}), 401
        from strava import get_recent_activities, get_streams
        strava_token = sess["strava_access_token"]
        activities = get_recent_activities(strava_token, n=20)
        activity = next((a for a in activities if a["id"] == activity_id), None)
        if not activity:
            return jsonify({"error": "Activity not found"}), 404
        streams = get_streams(activity_id, strava_token)

    # Try Garmin for HR if Strava has none
    if not streams.get("hr"):
        garmin_client = _garmin_clients.get(token)
        if garmin_client:
            from garmin import get_garmin_hr_for_strava_activity
            try:
                hr_data = get_garmin_hr_for_strava_activity(
                    garmin_client, activity["start_time"], activity["duration_s"]
                )
                if hr_data:
                    streams["hr"] = hr_data
            except Exception:
                pass

    # Get Spotify tracks
    tracks = []
    if "spotify_access_token" in sess:
        import spotipy
        sp = spotipy.Spotify(auth=sess["spotify_access_token"])
        from spotify import get_tracks_during_activity, get_audio_features
        try:
            tracks = get_tracks_during_activity(sp, activity["start_time"], activity["duration_s"])
        except Exception:
            pass

    if not tracks:
        return jsonify({
            "activity": activity,
            "matched_tracks": [],
            "message": "No Spotify tracks found for this activity window."
        })

    # Get BPM
    import spotipy
    from spotify import get_audio_features
    sp = spotipy.Spotify(auth=sess["spotify_access_token"])
    track_ids = [t["spotify_id"] for t in tracks]
    audio_features = get_audio_features(sp, track_ids)

    # Match
    from matcher import align_songs_to_activity
    matched = align_songs_to_activity(activity, streams, tracks, audio_features)

    return jsonify({
        "activity": activity,
        "matched_tracks": matched,
    })


# ── File upload (Strava GPX) ───────────────────────────────────────

@app.route("/api/upload/activity", methods=["POST"])
def upload_activity():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    f = request.files["file"]
    filename = f.filename.lower()

    if filename.endswith(".gpx"):
        activity, streams = _parse_gpx(f)
    else:
        return jsonify({"error": "Unsupported format. Upload .gpx files."}), 400

    sess, token = _get_session()
    if not token or token not in _sessions:
        token = str(uuid.uuid4())
        _sessions[token] = {}

    if token not in _uploaded_activities:
        _uploaded_activities[token] = []

    activity["_streams"] = streams
    activity["source"] = "upload"
    _uploaded_activities[token].append(activity)

    return jsonify({
        "status": "ok",
        "token": token,
        "activity": {k: v for k, v in activity.items() if k != "_streams"},
    })


def _parse_gpx(file_obj):
    """Parse a GPX file and extract activity + streams data."""
    tree = ET.parse(file_obj)
    root = tree.getroot()

    ns = {"gpx": "http://www.topografix.com/GPX/1/1"}

    points = root.findall(".//gpx:trkpt", ns)
    if not points:
        points = root.findall(".//{http://www.topografix.com/GPX/1/1}trkpt")

    times, hrs, cadences, altitudes, speeds = [], [], [], [], []
    first_time = None
    prev_time = None
    prev_lat = prev_lon = None

    for pt in points:
        time_el = pt.find("gpx:time", ns) or pt.find("{http://www.topografix.com/GPX/1/1}time")
        if time_el is None:
            continue
        t = datetime.fromisoformat(time_el.text.replace("Z", "+00:00"))
        if first_time is None:
            first_time = t
        times.append((t - first_time).total_seconds())

        ele_el = pt.find("gpx:ele", ns) or pt.find("{http://www.topografix.com/GPX/1/1}ele")
        altitudes.append(float(ele_el.text) if ele_el is not None else 0)

        lat = float(pt.get("lat", 0))
        lon = float(pt.get("lon", 0))
        if prev_time and prev_lat is not None:
            dt = (t - prev_time).total_seconds()
            if dt > 0:
                dlat = math.radians(lat - prev_lat)
                dlon = math.radians(lon - prev_lon)
                a = (math.sin(dlat/2)**2 +
                     math.cos(math.radians(prev_lat)) * math.cos(math.radians(lat)) *
                     math.sin(dlon/2)**2)
                dist = 6371000 * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                speeds.append(dist / dt)
            else:
                speeds.append(speeds[-1] if speeds else 0)
        else:
            speeds.append(0)
        prev_time, prev_lat, prev_lon = t, lat, lon

        hr_val = cad_val = None
        for ext in pt.iter():
            tag = ext.tag.split("}")[-1] if "}" in ext.tag else ext.tag
            if tag == "hr" and ext.text:
                hr_val = int(float(ext.text))
            elif tag == "cad" and ext.text:
                cad_val = int(float(ext.text))
        hrs.append(hr_val or 0)
        cadences.append(cad_val or 0)

    start_time = first_time.isoformat() if first_time else ""
    duration = times[-1] if times else 0

    activity = {
        "id":            hash(start_time) & 0x7FFFFFFF,
        "name":          "Uploaded Activity",
        "type":          "Run",
        "start_time":    start_time,
        "duration_s":    int(duration),
        "distance_m":    0,
        "has_heartrate": any(h > 0 for h in hrs),
    }

    streams = {
        "time": times, "hr": hrs, "cadence": cadences,
        "altitude": altitudes, "speed": speeds,
    }

    return activity, streams


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True)
