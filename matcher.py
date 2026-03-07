import numpy as np

def align_songs_to_activity(activity, streams, spotify_tracks, audio_features=None):
    """
    Match each Spotify track to the slice of activity data it overlaps with.

    Returns a list of dicts, one per song, with averaged metrics for that window.
    """
    from datetime import datetime, timezone

    start_ts = datetime.fromisoformat(
        activity["start_time"].replace("Z", "+00:00")
    ).timestamp()

    time_arr     = streams["time"]       # seconds since activity start
    hr_arr       = streams["hr"]
    cadence_arr  = streams["cadence"]    # SPM = cadence * 2 for running
    altitude_arr = streams["altitude"]
    speed_arr    = streams["speed"]      # m/s

    matched = []

    for track in spotify_tracks:
        # Convert absolute timestamps to offsets from activity start
        offset_start = track["start_ts"] - start_ts
        offset_end   = track["end_ts"]   - start_ts

        # Clamp to activity window
        offset_start = max(0, offset_start)
        offset_end   = min(time_arr[-1] if time_arr else 0, offset_end)

        if offset_end <= offset_start:
            continue

        # Find all stream indices that fall within this song's window
        idxs = [i for i, t in enumerate(time_arr) if offset_start <= t <= offset_end]

        if not idxs:
            continue

        def safe_mean(arr):
            vals = [arr[i] for i in idxs if i < len(arr)]
            return round(float(np.mean(vals)), 1) if vals else None

        def safe_max(arr):
            vals = [arr[i] for i in idxs if i < len(arr)]
            return round(float(np.max(vals)), 1) if vals else None

        entry = {
            "track":              track["name"],
            "artist":             track["artist"],
            "spotify_id":         track["spotify_id"],
            "offset_start_s":     round(offset_start),   # seconds into the run
            "offset_end_s":       round(offset_end),
            "duration_in_run_s":  round(offset_end - offset_start),

            # Metrics averaged over the song window
            "avg_hr":             safe_mean(hr_arr),
            "max_hr":             safe_max(hr_arr),
            "avg_spm":            round(safe_mean(cadence_arr) * 2, 1) if safe_mean(cadence_arr) else None,
            "avg_speed_ms":       safe_mean(speed_arr),
            "avg_speed_min_per_km": round(1000 / (safe_mean(speed_arr) * 60), 2) if safe_mean(speed_arr) else None,
            "elevation_gain_m":   round(
                max(altitude_arr[i] for i in idxs if i < len(altitude_arr)) -
                min(altitude_arr[i] for i in idxs if i < len(altitude_arr)), 1
            ) if altitude_arr else None,

            # Raw series for plotting
            "hr_series":      [hr_arr[i] for i in idxs if i < len(hr_arr)],
            "spm_series":     [cadence_arr[i] * 2 for i in idxs if i < len(cadence_arr)],
        }

        # Attach Spotify audio features if available
        if audio_features and track["spotify_id"] in audio_features:
            feat = audio_features[track["spotify_id"]]
            entry.update(feat)
            if feat.get("bpm") and entry.get("avg_spm"):
                entry["cadence_to_bpm_ratio"] = round(entry["avg_spm"] / feat["bpm"], 3)

        matched.append(entry)

    return matched


def print_summary(matched):
    """Print a readable summary of the matched results."""
    print(f"\n{'='*60}")
    print(f"{'SONG':<30} {'HR':>5} {'SPM':>5} {'BPM':>5} {'MIN/KM':>7}")
    print(f"{'='*60}")
    for m in matched:
        offset_min = m['offset_start_s'] // 60
        offset_sec = m['offset_start_s'] % 60
        print(f"[{offset_min:02d}:{offset_sec:02d}] {m['track'][:28]:<28} "
              f"{str(m['avg_hr'] or '?'):>5} "
              f"{str(m['avg_spm'] or '?'):>5} "
              f"{str(round(m.get('bpm', 0)) or '?'):>5} "
              f"{str(m.get('avg_speed_min_per_km') or '?'):>7}")
    print(f"{'='*60}\n")