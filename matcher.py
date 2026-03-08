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

    time_arr     = streams["time"]
    hr_arr       = streams["hr"]
    cadence_arr  = streams["cadence"]   # SPM = cadence * 2 for running
    altitude_arr = streams["altitude"]
    speed_arr    = streams["speed"]     # m/s

    matched = []

    for track in spotify_tracks:
        offset_start = track["start_ts"] - start_ts
        offset_end   = track["end_ts"]   - start_ts

        offset_start = max(0, offset_start)
        offset_end   = min(time_arr[-1] if time_arr else 0, offset_end)

        if offset_end <= offset_start:
            continue

        idxs = [i for i, t in enumerate(time_arr) if offset_start <= t <= offset_end]

        if not idxs:
            continue

        def safe_mean(arr):
            vals = [arr[i] for i in idxs if i < len(arr)]
            return round(float(np.mean(vals)), 1) if vals else None

        def safe_max(arr):
            vals = [arr[i] for i in idxs if i < len(arr)]
            return round(float(np.max(vals)), 1) if vals else None

        avg_speed_ms = safe_mean(speed_arr)
        # Convert m/s to min/mile (imperial)
        avg_speed_min_per_mile = round(1609.34 / (avg_speed_ms * 60), 2) if avg_speed_ms else None

        entry = {
            "track":                  track["name"],
            "artist":                 track["artist"],
            "spotify_id":             track["spotify_id"],
            "offset_start_s":         round(offset_start),
            "offset_end_s":           round(offset_end),
            "duration_in_run_s":      round(offset_end - offset_start),

            "avg_hr":                 safe_mean(hr_arr),
            "max_hr":                 safe_max(hr_arr),
            "avg_spm":                round(safe_mean(cadence_arr) * 2, 1) if safe_mean(cadence_arr) else None,
            "avg_speed_ms":           avg_speed_ms,
            "avg_speed_min_per_mile": avg_speed_min_per_mile,

            "elevation_gain_ft": round(
                (max(altitude_arr[i] for i in idxs if i < len(altitude_arr)) -
                 min(altitude_arr[i] for i in idxs if i < len(altitude_arr))) * 3.28084, 1
            ) if altitude_arr else None,

            "hr_series":  [hr_arr[i] for i in idxs if i < len(hr_arr)],
            "spm_series": [cadence_arr[i] * 2 for i in idxs if i < len(cadence_arr)],
        }

        # Attach audio features if available
        if audio_features and track["spotify_id"] in audio_features:
            feat = audio_features[track["spotify_id"]]
            entry.update(feat)
            if feat.get("bpm") and entry.get("avg_spm"):
                entry["cadence_to_bpm_ratio"] = round(entry["avg_spm"] / feat["bpm"], 3)

        matched.append(entry)

    return matched


def fmt_time(total_seconds):
    """Convert seconds to H:MM:SS string."""
    total_seconds = int(total_seconds)
    h = total_seconds // 3600
    m = (total_seconds % 3600) // 60
    s = total_seconds % 60
    return f"{h}:{m:02d}:{s:02d}"


def print_summary(matched):
    """Print a readable, aligned summary table of matched results."""

    # Column headers and widths
    time_w   = 19   # "0:12:34 - 0:15:22"
    track_w  = 28
    hr_w     = 6    # "142"
    spm_w    = 6    # "172"
    bpm_w    = 6    # "128"
    pace_w   = 8    # "8:32"

    header = (
        f"{'TIME RANGE':<{time_w}}  "
        f"{'SONG':<{track_w}}  "
        f"{'HR':>{hr_w}}  "
        f"{'SPM':>{spm_w}}  "
        f"{'BPM':>{bpm_w}}  "
        f"{'MIN/MI':>{pace_w}}"
    )
    divider = "-" * len(header)

    print(f"\n{divider}")
    print(header)
    print(divider)

    for m in matched:
        time_range = f"{fmt_time(m['offset_start_s'])} - {fmt_time(m['offset_end_s'])}"

        # HR: use avg_hr, fall back to first value in series if avg missing
        hr_val = m.get("avg_hr")
        if hr_val is None and m.get("hr_series"):
            hr_val = m["hr_series"][0]
        hr_str = str(int(hr_val)) if hr_val else "?"

        # SPM
        spm_str = str(int(m["avg_spm"])) if m.get("avg_spm") else "?"

        # BPM: round if present
        bpm_val = m.get("bpm")
        bpm_str = str(int(round(bpm_val))) if bpm_val else "?"

        # Pace as MM:SS per mile
        pace = m.get("avg_speed_min_per_mile")
        if pace:
            pace_min = int(pace)
            pace_sec = int(round((pace - pace_min) * 60))
            pace_str = f"{pace_min}:{pace_sec:02d}"
        else:
            pace_str = "?"

        print(
            f"{time_range:<{time_w}}  "
            f"{m['track'][:track_w]:<{track_w}}  "
            f"{hr_str:>{hr_w}}  "
            f"{spm_str:>{spm_w}}  "
            f"{bpm_str:>{bpm_w}}  "
            f"{pace_str:>{pace_w}}"
        )

    print(f"{divider}\n")