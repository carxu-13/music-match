import requests
import os
from dotenv import load_dotenv

load_dotenv()

def get_access_token():
    """Exchange refresh token for a fresh access token."""
    r = requests.post("https://www.strava.com/oauth/token", data={
        "client_id":     os.getenv("STRAVA_CLIENT_ID"),
        "client_secret": os.getenv("STRAVA_CLIENT_SECRET"),
        "refresh_token": os.getenv("STRAVA_REFRESH_TOKEN"),
        "grant_type":    "refresh_token"
    })
    r.raise_for_status()
    return r.json()["access_token"]

# Activity types where cadence (steps/min) data is available
CADENCE_ACTIVITY_TYPES = {
    "Run", "TrailRun", "VirtualRun",
    "Walk", "Hike",
    "Elliptical", "StairStepper",
    "Snowshoe", "RockClimbing",
}


def get_recent_activities(access_token, n=10):
    """Return a list of your n most recent activities that support cadence data."""
    r = requests.get(
        "https://www.strava.com/api/v3/athlete/activities",
        headers={"Authorization": f"Bearer {access_token}"},
        params={"per_page": n * 3}  # fetch extra to account for filtered-out types
    )
    r.raise_for_status()

    activities = []
    for a in r.json():
        if a["type"] not in CADENCE_ACTIVITY_TYPES:
            continue
        activities.append({
            "id":            a["id"],
            "name":          a["name"],
            "type":          a["type"],
            "start_time":    a["start_date"],          # UTC ISO string
            "duration_s":    a["elapsed_time"],         # total seconds
            "distance_m":    a["distance"],
            "has_heartrate": a.get("has_heartrate", False),
        })
        if len(activities) >= n:
            break

    return activities

def get_streams(activity_id, access_token):
    """
    Return per-second data streams for an activity.
    Each stream is a list where index i = value at time[i] seconds after start.
    """
    r = requests.get(
        f"https://www.strava.com/api/v3/activities/{activity_id}/streams",
        headers={"Authorization": f"Bearer {access_token}"},
        params={
            "keys": "time,heartrate,cadence,altitude,velocity_smooth",
            "key_by_type": True
        }
    )
    r.raise_for_status()
    data = r.json()

    # Extract each stream's data array, default to empty list if not present
    return {
        "time":     data.get("time",             {}).get("data", []),
        "hr":       data.get("heartrate",        {}).get("data", []),
        "cadence":  data.get("cadence",          {}).get("data", []),
        "altitude": data.get("altitude",         {}).get("data", []),
        "speed":    data.get("velocity_smooth",  {}).get("data", []),
    }