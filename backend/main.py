import json
from strava   import get_access_token, get_recent_activities, get_streams
from spotify  import get_spotify_client, get_tracks_during_activity, get_audio_features
from matcher  import align_songs_to_activity, print_summary

def main():
    # --- 1. Authenticate ---
    print("Authenticating...")
    strava_token = get_access_token()
    sp = get_spotify_client()   # opens browser first time for Spotify OAuth

    # --- 2. Pick an activity ---
    print("\nFetching your recent Strava activities...\n")
    activities = get_recent_activities(strava_token, n=10)

    for i, a in enumerate(activities):
        duration_min = a["duration_s"] // 60
        hr_flag = "HR" if a.get("has_heartrate") else "no HR"
        print(f"  [{i}] {a['name']} — {a['type']} — {a['start_time']} — {duration_min} min — {hr_flag}")

    idx = int(input("\nEnter the number of the activity to analyze: "))
    activity = activities[idx]
    print(f"\nAnalyzing: {activity['name']}")

    # --- 3. Fetch Strava streams ---
    print("Fetching Strava streams...")
    streams = get_streams(activity["id"], strava_token)

    if not streams["time"]:
        print("No stream data found for this activity.")
        return

    if not streams["hr"]:
        print("No HR data from Strava. Trying Garmin Connect...")
        try:
            from garmin import get_garmin_client, get_garmin_hr_for_strava_activity
            gc = get_garmin_client()
            if gc:
                hr_data = get_garmin_hr_for_strava_activity(
                    gc, activity["start_time"], activity["duration_s"]
                )
                if hr_data:
                    streams["hr"] = hr_data
                    print(f"  Got {len(hr_data)} HR samples from Garmin!")
                else:
                    print("  No HR data found in Garmin either.")
        except Exception as e:
            print(f"  Garmin HR fetch failed: {e}")

    # --- 4. Fetch Spotify tracks ---
    print("Fetching Spotify recently played...")
    tracks = get_tracks_during_activity(sp, activity["start_time"], activity["duration_s"])

    if not tracks:
        print("\nNo Spotify tracks found during this activity window.")
        print("Tip: Run this script soon after your activity to cache tracks.")
        print("     Cached tracks are stored in spotify_track_cache.json for future use.")
        return

    print(f"Found {len(tracks)} tracks during this activity.")

    # --- 5. Fetch BPM via web search ---
    print("Searching for BPM data...")
    track_ids = [t["spotify_id"] for t in tracks]
    audio_features = get_audio_features(sp, track_ids)

    # --- 6. Match songs to activity segments ---
    print("Matching songs to activity data...")
    matched = align_songs_to_activity(activity, streams, tracks, audio_features)

    # --- 7. Show results ---
    print_summary(matched)

    # --- 8. Save to JSON for further analysis ---
    output = {
        "activity": activity,
        "matched_tracks": matched
    }
    filename = f"results_{activity['id']}.json"
    with open(filename, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Full results saved to {filename}")

if __name__ == "__main__":
    main()