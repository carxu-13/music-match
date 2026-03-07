import os
from garminconnect import Garmin
from dotenv import load_dotenv

load_dotenv()

def get_garmin_client():
    """Login and return authenticated client. Tokens cached to ~/.garminconnect."""
    client = Garmin(os.getenv("GARMIN_EMAIL"), os.getenv("GARMIN_PASSWORD"))
    try:
        client.login()
    except Exception as e:
        print(f"Garmin login failed: {e}")
        return None
    return client

def get_garmin_activity_hr(client, activity_id):
    """
    Fetch HR data for a specific Garmin activity.
    Note: Garmin activity IDs are different from Strava IDs.
    Use get_recent_garmin_activities() to find the right one.
    """
    details = client.get_activity(activity_id)
    return details

def get_recent_garmin_activities(client, n=10):
    activities = client.get_activities(0, n)
    return [
        {
            "id":         a["activityId"],
            "name":       a["activityName"],
            "start_time": a["startTimeGMT"],
            "duration_s": a["duration"],
        }
        for a in activities
    ]