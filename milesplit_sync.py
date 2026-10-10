"""
milesplit_sync.py - Automated MileSplit Roster & PR Sync Engine for Waterford Track & Field.
Extracts live roster and PR statistics from https://ny.milesplit.com/teams/11784-waterford-central
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import base64
from datetime import datetime, date
from typing import List, Dict, Any, Tuple, Optional

import database as db

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://ny.milesplit.com/teams/11784-waterford-central'
}

DEFAULT_ROSTER_URL = "https://ny.milesplit.com/teams/11784-waterford-central/roster"

# Mapping from MileSplit event names to internal standard event names
EVENT_NAME_MAPPINGS = {
    "55m": ("55m", "Track"),
    "55mH": ("55m Hurdles", "Track"),
    "55m Hurdles": ("55m Hurdles", "Track"),
    "50mH": ("55m Hurdles", "Track"),
    "100m": ("100m", "Track"),
    "110mH": ("110m Hurdles (Boys)", "Track"),
    "100mH": ("100m Hurdles (Girls)", "Track"),
    "200m": ("200m", "Track"),
    "300m": ("300m", "Track"),
    "400m": ("400m", "Track"),
    "400mH": ("400m Hurdles", "Track"),
    "600m": ("600m", "Track"),
    "800m": ("800m", "Track"),
    "1000m": ("1000m", "Track"),
    "1500m": ("1500m", "Track"),
    "1600m": ("1600m", "Track"),
    "3000m": ("3000m", "Track"),
    "3200m": ("3200m", "Track"),
    "3K Steeple": ("3000m Steeplechase", "Track"),
    "2K Steeple": ("2000m Steeplechase", "Track"),
    "Long Jump": ("Long Jump", "Field"),
    "Triple Jump": ("Triple Jump", "Field"),
    "High Jump": ("High Jump", "Field"),
    "Shot Put": ("Shot Put", "Field"),
    "Discus": ("Discus", "Field"),
    "Pole Vault": ("Pole Vault", "Field"),
    "Weight Throw": ("Weight Throw", "Field"),
    "Javelin": ("Javelin", "Field"),
}


def grad_year_to_grade(grad_year: int, current_academic_year: int = 2026) -> int:
    """Converts high school graduation year to grade level (7-12)."""
    # 2026 = 12 (Senior), 2027 = 11 (Junior), 2028 = 10 (Soph), 2029 = 9 (Freshman)
    diff = grad_year - current_academic_year
    grade = 12 - diff
    return max(7, min(12, grade))


def parse_milesplit_date(date_str: str) -> str:
    """Parses 'Jan 31, 2026' to '2026-01-31'."""
    s = str(date_str).strip()
    try:
        dt = datetime.strptime(s, "%b %d, %Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        # Fallback to current date
        return date.today().strftime("%Y-%m-%d")


def fetch_waterford_roster(
    roster_url: str = DEFAULT_ROSTER_URL,
    min_grad_year: int = 2026,
    session: Optional[requests.Session] = None
) -> List[Dict[str, Any]]:
    """
    Scrapes the Waterford-Halfmoon roster from MileSplit.
    Filters athletes by graduation year >= min_grad_year (e.g. 2026+).
    """
    requester = session if session else requests
    resp = requester.get(roster_url, headers=HEADERS, timeout=12)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    rows = soup.select('.athlete-row')

    athletes = []
    for row in rows:
        name_el = row.select_one('a')
        if not name_el:
            continue
        raw_name = name_el.text.strip()
        # Name is usually "Last, First"
        if "," in raw_name:
            parts = [p.strip() for p in raw_name.split(",", 1)]
            last_name = parts[0]
            first_name = parts[1]
        else:
            parts = raw_name.split()
            first_name = parts[0]
            last_name = " ".join(parts[1:]) if len(parts) > 1 else ""

        gender_el = row.select_one('.column-gender')
        gender = gender_el.text.strip().upper() if gender_el else "M"
        if gender not in ("M", "F"):
            gender = "M"

        grad_el = row.select_one('.column-grad-year')
        try:
            grad_year = int(grad_el.text.strip()) if grad_el else 2028
        except ValueError:
            grad_year = 2028

        # Filter: only keep athletes graduating in min_grad_year (2026) or later
        if min_grad_year and grad_year and grad_year < min_grad_year:
            continue

        grade_level = grad_year_to_grade(grad_year)
        age = grade_level + 5
        athlete_url = name_el.get('href', '')

        athletes.append({
            "first_name": first_name,
            "last_name": last_name,
            "gender": gender,
            "grad_year": grad_year,
            "grade_level": grade_level,
            "age": age,
            "athlete_url": athlete_url,
            "active_status": True
        })

    return athletes


def sync_roster_to_db(athletes: List[Dict[str, Any]]) -> Tuple[int, int]:
    """
    Upserts scraped athletes into the SQLite database.
    Returns (num_added, num_updated).
    """
    existing = db.get_all_athletes(active_only=False)
    # Map by (first_name.lower(), last_name.lower())
    existing_map = {(a["first_name"].strip().lower(), a["last_name"].strip().lower()): a for a in existing}

    added = 0
    updated = 0

    for a in athletes:
        key = (a["first_name"].strip().lower(), a["last_name"].strip().lower())
        if key in existing_map:
            match = existing_map[key]
            db.update_athlete(
                athlete_id=match["id"],
                first_name=match["first_name"],
                last_name=match["last_name"],
                gender=a["gender"],
                age=a["age"],
                grade_level=a["grade_level"],
                active_status=True
            )
            updated += 1
        else:
            db.add_athlete(
                first_name=a["first_name"],
                last_name=a["last_name"],
                gender=a["gender"],
                age=a["age"],
                grade_level=a["grade_level"],
                active_status=True
            )
            added += 1

    return added, updated


def login_milesplit(email: str, password: str) -> Tuple[Optional[requests.Session], str]:
    """
    Authenticates with FloSports / MileSplit API and establishes a logged-in web session.
    Returns (session, message).
    """
    if not email or not password:
        return None, "Email and password are required."

    session = requests.Session()
    session.headers.update(HEADERS)
    
    token_url = "https://api30.milesplit.com/api/tokens"
    try:
        resp = session.post(
            token_url,
            json={"email": email.strip(), "password": password.strip()},
            headers={
                "User-Agent": HEADERS["User-Agent"],
                "Content-Type": "application/json"
            },
            timeout=12
        )
        if resp.status_code not in (200, 201):
            try:
                err_msg = resp.json().get("message", "Authentication failed. Check credentials.")
            except Exception:
                err_msg = f"HTTP {resp.status_code} authentication error."
            return None, err_msg
            
        data = resp.json()
        token = data.get("token")
        if not token:
            return None, "No auth token returned by MileSplit API."
            
        token_obj = {
            "flo_id": data.get("user_id"),
            "jwt_token": token,
            "jwt_token_expire": data.get("exp"),
            "jwt_refresh_token": data.get("refresh_token"),
            "jwt_refresh_token_expire": data.get("refresh_token_exp"),
        }
        user_b64 = base64.b64encode(json.dumps(token_obj).encode()).decode()
        
        # Post to ny.milesplit.com/login to establish website cookies
        session.post(
            "https://ny.milesplit.com/login",
            data={"user": user_b64, "next": "https://ny.milesplit.com"},
            allow_redirects=True,
            timeout=12
        )
        session.headers["Authorization"] = f"Bearer {token}"
        session.headers["userToken"] = token
        return session, "Authenticated successfully with MileSplit PRO!"
    except Exception as e:
        return None, f"Network error during login: {str(e)}"


def fetch_athlete_full_history(athlete_url: str, session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
    """
    Fetches meet-by-meet performances from an athlete page.
    If authenticated with MileSplit PRO, extracts unlocked marks, meet names, and dates.
    Falls back to personal records table (#prTable) if meet rows are locked or unavailable.
    """
    if not athlete_url:
        return []
    try:
        requester = session if session else requests
        resp = requester.get(athlete_url, headers=HEADERS, timeout=12)
        if resp.status_code != 200:
            return []
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 1. Try to extract meet-by-meet rows (.record.row)
        records = []
        for row in soup.select('.record.row'):
            # If the mask is present, this specific row is locked
            if row.select_one('.mask'):
                continue
            seed_el = row.select_one('.seed')
            loc_el = row.select_one('.location')
            date_el = row.select_one('.date')
            ev_raw = row.get('data-event', '').strip()
            season_raw = row.get('data-season', 'outdoor').strip()
            
            if not seed_el or not loc_el or not date_el or not ev_raw:
                continue
                
            mark_text = seed_el.text.strip()
            meet_name = loc_el.text.strip()
            date_text = date_el.text.strip()
            
            if mark_text and date_text:
                records.append({
                    "event_raw": ev_raw,
                    "mark_raw": mark_text,
                    "date_raw": date_text,
                    "meet_name": meet_name or f"Meet ({date_text})",
                    "season_mode": season_raw
                })

        if records:
            return records

        # 2. Fallback to PR table (#prTable)
        pr_table = soup.select_one('#prTable')
        if pr_table:
            for tr in pr_table.select('tbody tr'):
                ev_el = tr.select_one('.pr-td-event')
                mark_el = tr.select_one('.pr-td-mark')
                dt_el = tr.select_one('.pr-td-date')
                if ev_el and mark_el and dt_el:
                    records.append({
                        "event_raw": ev_el.text.strip(),
                        "mark_raw": mark_el.text.strip(),
                        "date_raw": dt_el.text.strip(),
                        "meet_name": f"MileSplit PR Meet ({dt_el.text.strip()})",
                        "season_mode": tr.get('data-pr-mode', 'all')
                    })
        return records
    except Exception:
        return []


def fetch_athlete_prs(athlete_url: str, session: Optional[requests.Session] = None) -> List[Dict[str, Any]]:
    """
    Fetches performances for an athlete (defaults to full history if available, or PR table).
    """
    return fetch_athlete_full_history(athlete_url, session=session)


def resolve_or_create_event(event_raw: str, season: str, gender: str, conn: Optional[Any] = None) -> Optional[Dict[str, Any]]:
    """
    Resolves a MileSplit event name to a database event ID.
    If gender-specific (e.g. hurdles), picks appropriate version.
    """
    # Clean up event name
    clean_ev = event_raw.replace('"', '').strip()
    
    # Check mapping
    standard_name = clean_ev
    ev_type = "Track"
    if clean_ev in EVENT_NAME_MAPPINGS:
        standard_name, ev_type = EVENT_NAME_MAPPINGS[clean_ev]
    else:
        # Detect field vs track
        if any(w in clean_ev.lower() for w in ["jump", "put", "throw", "discus", "vault", "javelin"]):
            ev_type = "Field"

    # Specific hurdles by gender
    if standard_name in ("110m Hurdles (Boys)", "100m Hurdles (Girls)"):
        standard_name = "100m Hurdles (Girls)" if gender == "F" else "110m Hurdles (Boys)"

    def _lookup(c):
        cursor = c.cursor()
        cursor.execute("SELECT * FROM events WHERE season = ? AND event_name = ?", (season, standard_name))
        row = cursor.fetchone()
        if row:
            return dict(row)
        
        # Try finding across seasons
        cursor.execute("SELECT * FROM events WHERE event_name = ?", (standard_name,))
        row = cursor.fetchone()
        if row:
            return dict(row)

        # Create new event if missing
        sort_order = "DESC" if ev_type == "Field" else "ASC"
        dist_match = re.search(r"(\d+)", standard_name)
        dist = float(dist_match.group(1)) if (dist_match and ev_type == "Track") else None
        cursor.execute("""
            INSERT INTO events (season, event_name, event_type, distance_meters, sort_order)
            VALUES (?, ?, ?, ?, ?)
        """, (season, standard_name, ev_type, dist, sort_order))
        c.commit()
        cursor.execute("SELECT * FROM events WHERE id = ?", (cursor.lastrowid,))
        return dict(cursor.fetchone())

    if conn is not None:
        return _lookup(conn)
    else:
        with db.get_connection() as local_conn:
            return _lookup(local_conn)


def sync_athlete_prs_to_db(athlete_id: int, prs: List[Dict[str, Any]]) -> int:
    """
    Saves scraped PRs into the results table for the athlete.
    Returns number of newly inserted results.
    """
    ath = db.get_athlete_by_id(athlete_id)
    if not ath:
        return 0

    venues = db.get_all_venues()
    outdoor_vid = venues[0]["id"] if venues else 1
    indoor_vid = venues[1]["id"] if len(venues) > 1 else outdoor_vid

    inserted_count = 0

    with db.get_connection() as conn:
        cursor = conn.cursor()

        for p in prs:
            mode = p["season_mode"].lower()
            season = "Indoor" if mode == "indoor" else "Outdoor"
            ev = resolve_or_create_event(p["event_raw"], season, ath["gender"], conn=conn)
            if not ev:
                continue

            # Parse value
            parsed_val = None
            if ev["event_type"] == "Track":
                parsed_val = db.parse_time(p["mark_raw"])
            else:
                parsed_val = db.parse_field_mark(p["mark_raw"])

            if not parsed_val or parsed_val <= 0:
                continue

            iso_date = parse_milesplit_date(p["date_raw"])
            meet_name = p.get("meet_name") or f"MileSplit Meet ({p['date_raw']})"
            venue_id = indoor_vid if season == "Indoor" else outdoor_vid

            # Find or create meet
            cursor.execute("SELECT id FROM meets WHERE name = ? AND date = ?", (meet_name, iso_date))
            m_row = cursor.fetchone()
            if m_row:
                meet_id = m_row["id"]
            else:
                cursor.execute("""
                    INSERT INTO meets (name, date, venue_id, season, meet_type)
                    VALUES (?, ?, ?, ?, ?)
                """, (meet_name, iso_date, venue_id, season, "Invitational"))
                meet_id = cursor.lastrowid

            # Check if this athlete result already exists
            cursor.execute("""
                SELECT id FROM results 
                WHERE athlete_id = ? AND event_id = ? AND meet_id = ?
            """, (athlete_id, ev["id"], meet_id))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO results (athlete_id, event_id, meet_id, result_value, timing_method, is_official, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (athlete_id, ev["id"], meet_id, parsed_val, "FAT", 1, "Imported from MileSplit"))
                inserted_count += 1

        conn.commit()

    return inserted_count


def sync_all_from_milesplit(
    max_athletes_with_prs: int = 60,
    progress_callback=None,
    min_grad_year: int = 2026,
    session: Optional[requests.Session] = None,
    **kwargs
) -> Dict[str, Any]:
    """
    High-level orchestrator:
    1. Scrapes complete roster from MileSplit filtered by grad_year >= min_grad_year.
    2. Syncs athletes to SQLite.
    3. Scrapes and imports all meet histories (or PRs) using optional PRO session.
    """
    if "max_athletes" in kwargs:
        max_athletes_with_prs = kwargs["max_athletes"]
    roster = fetch_waterford_roster(min_grad_year=min_grad_year, session=session)
    added, updated = sync_roster_to_db(roster)

    # Re-fetch local athletes to get their local IDs
    local_athletes = db.get_all_athletes(active_only=False)
    local_map = {(a["first_name"].strip().lower(), a["last_name"].strip().lower()): a["id"] for a in local_athletes}

    total_results_synced = 0
    athletes_synced = 0

    to_sync = roster[:max_athletes_with_prs]
    total_count = len(to_sync)

    for i, a in enumerate(to_sync, start=1):
        key = (a["first_name"].strip().lower(), a["last_name"].strip().lower())
        local_id = local_map.get(key)
        if local_id and a.get("athlete_url"):
            records = fetch_athlete_full_history(a["athlete_url"], session=session)
            if records:
                cnt = sync_athlete_prs_to_db(local_id, records)
                total_results_synced += cnt
            athletes_synced += 1

        if progress_callback:
            progress_callback(i, total_count, a["first_name"] + " " + a["last_name"])

    return {
        "roster_total": len(roster),
        "athletes_added": added,
        "athletes_updated": updated,
        "athletes_prs_synced": athletes_synced,
        "total_results_inserted": total_results_synced
    }


# ==========================================
# WASAREN LEAGUE SCOUTING SYNC
# ==========================================

WASAREN_LEAGUE_TEAMS_CONFIG = [
    {"name": "Cambridge-Salem", "team_id": 69761, "display_name": "Cambridge-Salem"},
    {"name": "Greenwich", "team_id": 11276, "display_name": "Greenwich"},
    {"name": "Hoosic Valley", "team_id": 11330, "display_name": "Hoosic Valley"},
    {"name": "Mechanicville", "team_id": 11467, "display_name": "Mechanicville"},
    {"name": "Saratoga Central Catholic", "team_id": 11654, "display_name": "Saratoga Catholic"},
    {"name": "Stillwater", "team_id": 11726, "display_name": "Stillwater"},
    {"name": "Tamarac-Hoosick Falls", "team_id": 11739, "display_name": "Tamarac / Hoosick Falls"},
    {"name": "Waterford-Halfmoon", "team_id": 11784, "display_name": "Waterford-Halfmoon"},
]

WASAREN_EVENT_CODE_MAP = {
    "55m": ("55m", "Track"),
    "55mH": ("55m Hurdles", "Track"),
    "100m": ("100m", "Track"),
    "100mH": ("100m Hurdles (Girls)", "Track"),
    "110mH": ("110m Hurdles (Boys)", "Track"),
    "200m": ("200m", "Track"),
    "300m": ("300m", "Track"),
    "400m": ("400m", "Track"),
    "400mH": ("400m Hurdles", "Track"),
    "600m": ("600m", "Track"),
    "800m": ("800m", "Track"),
    "1000m": ("1000m", "Track"),
    "1500m": ("1500m", "Track"),
    "1600m": ("1600m", "Track"),
    "1 Mile": ("1600m", "Track"),
    "Mile": ("1600m", "Track"),
    "3000m": ("3000m", "Track"),
    "3200m": ("3200m", "Track"),
    "2000mSC": ("2000m Steeplechase", "Track"),
    "3000mSC": ("3000m Steeplechase", "Track"),
    "4x100m": ("4x100m Relay", "Relay"),
    "4x200m": ("4x200m Relay", "Relay"),
    "4x400m": ("4x400m Relay", "Relay"),
    "4x800m": ("4x800m Relay", "Relay"),
    "SMR": ("1600m Sprint Medley (SMR)", "Relay"),
    "DMR": ("Distance Medley (DMR)", "Relay"),
    "HJ": ("High Jump", "Field"),
    "High Jump": ("High Jump", "Field"),
    "LJ": ("Long Jump", "Field"),
    "Long Jump": ("Long Jump", "Field"),
    "TJ": ("Triple Jump", "Field"),
    "Triple Jump": ("Triple Jump", "Field"),
    "PV": ("Pole Vault", "Field"),
    "Pole Vault": ("Pole Vault", "Field"),
    "SP": ("Shot Put", "Field"),
    "Shot Put": ("Shot Put", "Field"),
    "D": ("Discus", "Field"),
    "Discus": ("Discus", "Field"),
    "WT": ("Weight Throw", "Field"),
    "Weight Throw": ("Weight Throw", "Field"),
    "Pent": ("Pentathlon", "Field"),
    "Pentathlon": ("Pentathlon", "Field"),
}


def sync_wasaren_league_marks(
    session: Optional[requests.Session] = None,
    progress_callback=None
) -> Dict[str, Any]:
    """
    Fetches and synchronizes season-best marks across all 9 Wasaren League schools
    for both Indoor and Outdoor track & field, Male and Female.
    """
    requester = session if session else requests
    api_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'application/json'
    }
    
    total_synced = 0
    schools_synced = 0
    total_schools = len(WASAREN_LEAGUE_TEAMS_CONFIG)
    per_school_counts: Dict[str, int] = {}
    
    for idx, school in enumerate(WASAREN_LEAGUE_TEAMS_CONFIG, start=1):
        s_name = school["display_name"]
        tid = school["team_id"]
        school_count = 0
        
        if progress_callback:
            progress_callback(idx, total_schools, f"Syncing {s_name}...")
            
        for season_api in ['outdoor', 'indoor']:
            season_label = "Outdoor" if season_api == "outdoor" else "Indoor"
            for g in ['M', 'F']:
                url = f"https://ny.milesplit.com/api/v1/teams/{tid}/best?season={season_api}&gender={g}&grade=all"
                try:
                    resp = requester.get(url, headers=api_headers, timeout=12)
                    if resp.status_code != 200:
                        continue
                    data = resp.json().get('data', {}).get('eventGroups', {})
                    if not isinstance(data, dict):
                        continue
                        
                    for group_key, group_val in data.items():
                        if not isinstance(group_val, dict):
                            continue
                        perfs = group_val.get('performances', [])
                        for p in perfs:
                            code = str(p.get('eventCode') or p.get('eventShortName') or '')
                            ev_tuple = WASAREN_EVENT_CODE_MAP.get(code) or WASAREN_EVENT_CODE_MAP.get(str(p.get('eventShortName') or ''))
                            if ev_tuple:
                                ev_name, ev_type = ev_tuple
                            else:
                                ev_name = str(p.get('eventShortName') or code or 'Unknown Event')
                                ev_type = group_key if group_key in ['Track', 'Field', 'Relay'] else 'Other'
                                
                            raw_mark = str(p.get('mark') or '').strip()
                            if not raw_mark:
                                continue
                                
                            # Parse mark
                            val = None
                            if ev_type in ('Track', 'Relay'):
                                val = db.parse_time(raw_mark)
                            elif ev_type == 'Field':
                                val = db.parse_field_mark(raw_mark)
                            else:
                                try:
                                    val = float(raw_mark)
                                except ValueError:
                                    val = db.parse_time(raw_mark) or db.parse_field_mark(raw_mark)
                                    
                            if val is None:
                                continue
                                
                            first = str(p.get('firstName') or '').strip()
                            last = str(p.get('lastName') or '').strip()
                            athlete_full = f"{first} {last}".strip()
                            if not athlete_full:
                                if ev_type == 'Relay':
                                    athlete_full = f"{s_name} Relay"
                                else:
                                    athlete_full = f"{s_name} Athlete"
                                    
                            meet_date = p.get('meetStartDate')
                            sy = db.get_school_year(meet_date)
                            if sy == "Unknown":
                                sy = "2025-26"
                                
                            db.upsert_wasaren_mark(
                                school_name=s_name,
                                school_id=tid,
                                athlete_name=athlete_full,
                                athlete_id=str(p.get('athleteId') or ''),
                                gender=g,
                                event_code=code,
                                event_name=ev_name,
                                event_type=ev_type,
                                mark_display=raw_mark,
                                mark_value=val,
                                meet_name=p.get('meetName'),
                                meet_date=meet_date,
                                season=season_label,
                                season_year=sy
                            )
                            school_count += 1
                            total_synced += 1
                except Exception:
                    pass
                    
        per_school_counts[s_name] = school_count
        schools_synced += 1

    return {
        "total_synced": total_synced,
        "schools_synced": schools_synced,
        "per_school": per_school_counts
    }

