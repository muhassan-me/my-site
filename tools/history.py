"""
History compaction utilities.
"""
from datetime import datetime, timedelta


def compact_history(history, new_snapshot, now):
    """
    Compact the history list with a new snapshot.

    - Skip appending if every country/location count equals the previous snapshot.
    - Keep full snapshots for the last 14 days.
    - For older snapshots keep one per day (the latest).
    """
    if not history:
        return [new_snapshot]

    # Compare with the last snapshot to decide if we should append
    last = history[-1]
    if _counts_equal(last, new_snapshot):
        return history

    history = history + [new_snapshot]

    # Separate recent (within 14 days) and older
    cutoff = now - timedelta(days=14)
    recent = []
    older = []
    for snap in history:
        ts = _parse_timestamp(snap.get('timestamp'))
        if ts is None:
            older.append(snap)
        elif ts >= cutoff:
            recent.append(snap)
        else:
            older.append(snap)

    # Compact older: keep one per day (the latest)
    compacted_older = _keep_one_per_day(older)

    return recent + compacted_older


def _counts_equal(a, b):
    """Check whether country/location counts and global-event counts are unchanged."""
    a_countries = a.get('countries', {})
    b_countries = b.get('countries', {})

    if set(a_countries.keys()) != set(b_countries.keys()):
        return False

    for country in a_countries:
        a_locs = a_countries[country]
        b_locs = b_countries[country]
        if len(a_locs) != len(b_locs):
            return False
        def signature(locations):
            return sorted(
                (loc.get('slug') or loc.get('name', ''), loc.get('participants', 0))
                for loc in locations
            )
        if signature(a_locs) != signature(b_locs):
            return False
    if a.get('globalEvents', []) != b.get('globalEvents', []):
        return False
    return True


def _parse_timestamp(ts_str):
    """Parse ISO timestamp string to datetime, return None if invalid."""
    if not isinstance(ts_str, str):
        return None
    try:
        # Handle 'Z' suffix
        if ts_str.endswith('Z'):
            ts_str = ts_str[:-1] + '+00:00'
        return datetime.fromisoformat(ts_str)
    except ValueError:
        return None


def _keep_one_per_day(snapshots):
    """Keep the latest snapshot per calendar day."""
    if not snapshots:
        return []
    by_day = {}
    for snap in snapshots:
        ts = _parse_timestamp(snap.get('timestamp'))
        if ts is None:
            # Use a fallback key for invalid timestamps
            day_key = 'invalid'
        else:
            day_key = ts.date().isoformat()
        # Keep the latest (overwrite)
        by_day[day_key] = snap
    # Sort by day key for deterministic output
    sorted_keys = sorted(by_day.keys())
    return [by_day[k] for k in sorted_keys]