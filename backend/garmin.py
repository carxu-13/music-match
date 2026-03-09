import os
from datetime import datetime
from garminconnect import Garmin
from dotenv import load_dotenv

load_dotenv()

TOKENSTORE = os.path.join(os.path.expanduser("~"), ".garminconnect")


def get_garmin_client(email=None, password=None):
    """Login and return authenticated Garmin client.
    Uses saved tokens when possible to avoid repeated logins."""
    email = email or os.getenv("GARMIN_EMAIL")
    password = password or os.getenv("GARMIN_PASSWORD")

    client = Garmin(email, password)
    try:
        client.login(tokenstore=TOKENSTORE)
    except Exception:
        # Token expired or first login — authenticate with credentials
        try:
            client.login()
            # Save tokens for next time
            client.garth.dump(TOKENSTORE)
        except Exception as e:
            print(f"Garmin login failed: {e}")
            return None
    return client


def get_recent_garmin_activities(client, n=10):
    """Return a list of recent Garmin activities."""
    activities = client.get_activities(0, n)
    return [
        {
            "id":            a["activityId"],
            "name":          a.get("activityName", "Untitled"),
            "type":          a.get("activityType", {}).get("typeKey", "unknown"),
            "start_time":    a.get("startTimeGMT", ""),
            "duration_s":    int(a.get("duration", 0)),
            "distance_m":    a.get("distance", 0) or 0,
            "has_heartrate": a.get("hasPolyline", False),  # rough proxy
        }
        for a in activities
    ]


def get_garmin_hr_for_strava_activity(client, strava_start_iso, strava_duration_s):
    """Find the matching Garmin activity by start time and return per-second HR data.

    Args:
        client: Authenticated Garmin client
        strava_start_iso: UTC ISO string from Strava (e.g. "2026-03-06T14:02:25Z")
        strava_duration_s: Activity duration in seconds

    Returns:
        List of HR values (one per second), or empty list if not found.
    """
    strava_start = datetime.fromisoformat(strava_start_iso.replace("Z", "+00:00"))

    # Fetch recent Garmin activities and find one matching by start time
    activities = client.get_activities(0, 30)

    best_match = None
    best_diff = float("inf")

    for a in activities:
        gmt_str = a.get("startTimeGMT", "")
        if not gmt_str:
            continue
        try:
            garmin_start = datetime.fromisoformat(gmt_str.replace("Z", "+00:00"))
        except ValueError:
            # Sometimes Garmin returns format without timezone info
            try:
                garmin_start = datetime.fromisoformat(gmt_str + "+00:00")
            except ValueError:
                continue

        diff = abs((garmin_start - strava_start).total_seconds())
        if diff < best_diff:
            best_diff = diff
            best_match = a

    if best_match is None or best_diff > 300:  # 5-minute tolerance
        print(f"  No matching Garmin activity found (closest diff: {best_diff:.0f}s)")
        return []

    activity_id = best_match["activityId"]
    print(f"  Matched Garmin activity: {best_match.get('activityName', 'Untitled')} (id={activity_id})")

    return _extract_hr_stream(client, activity_id, strava_duration_s)


def _extract_hr_stream(client, activity_id, expected_duration_s):
    """Extract per-second HR data from Garmin activity details.

    Response format:
      metricDescriptors: [{metricsIndex: 0, key: "directSpeed"}, {metricsIndex: 2, key: "directHeartRate"}, ...]
      activityDetailMetrics: [{metrics: [1.66, 1.65, 82.0, ...]}, ...]
    The metrics array is flat — position matches metricsIndex.
    """
    max_chart = max(2000, int(expected_duration_s * 1.1))
    details = client.get_activity_details(activity_id, maxchart=max_chart)

    if not details:
        return []

    # Find which array index corresponds to heart rate
    descriptors = details.get("metricDescriptors", [])
    hr_index = None
    time_index = None

    for desc in descriptors:
        key = desc.get("key", "").lower()
        idx = desc.get("metricsIndex")
        if key == "directheartrate":
            hr_index = idx
        elif key == "directtimestamp":
            time_index = idx

    if hr_index is None:
        print("  No heart rate metric found in Garmin activity details")
        return []

    # Extract HR values — metrics is a flat array indexed by metricsIndex
    data_points = details.get("activityDetailMetrics", [])
    hr_values = []

    for point in data_points:
        vals = point.get("metrics", [])
        if hr_index < len(vals) and vals[hr_index] is not None:
            hr_values.append(int(vals[hr_index]))
        else:
            hr_values.append(0)

    non_zero = [v for v in hr_values if v > 0]
    if non_zero:
        print(f"  Garmin HR: {len(hr_values)} samples, avg={sum(non_zero)//len(non_zero)} bpm")
    else:
        print(f"  Garmin HR: {len(hr_values)} samples but all zero")

    return hr_values
