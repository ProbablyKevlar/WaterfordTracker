"""
database.py - Database Schema, Conversions, and CRUD operations for Waterford Track & Field.
"""

import os
import sqlite3
import re
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Tuple

# Determine persistent database path (optimized for Synology NAS /app/data mount)
DB_DIR = os.getenv("DB_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data"))
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.getenv("DB_PATH", os.path.join(DB_DIR, "waterford_tracker.db"))


def get_connection() -> sqlite3.Connection:
    """Returns a SQLite connection with row factory enabled and busy timeout."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    return conn


# ==========================================
# UNIT CONVERSION & TIME PARSING HELPERS
# ==========================================

def format_time(seconds: Optional[float]) -> str:
    """Formats float seconds into standard track time string (e.g. 11.24, 2:04.15, 10:14.28)."""
    if seconds is None:
        return "--"
    try:
        val = float(seconds)
    except (ValueError, TypeError):
        return "--"
    
    if val < 60:
        return f"{val:.2f}"
    
    minutes = int(val // 60)
    remaining_sec = val % 60
    return f"{minutes}:{remaining_sec:05.2f}"


def parse_time(time_str: str) -> Optional[float]:
    """
    Parses various track time input strings to float seconds.
    Examples:
      '11.24' -> 11.24
      '2:04.15' -> 124.15
      '4:48' -> 288.0
      '10:15.50' -> 615.5
    """
    if not time_str:
        return None
    s = str(time_str).strip()
    if not s:
        return None
    
    try:
        if ":" in s:
            parts = s.split(":")
            if len(parts) == 2:
                mins = float(parts[0])
                secs = float(parts[1])
                return round(mins * 60 + secs, 2)
            elif len(parts) == 3:
                hrs = float(parts[0])
                mins = float(parts[1])
                secs = float(parts[2])
                return round(hrs * 3600 + mins * 60 + secs, 2)
        return round(float(s), 2)
    except Exception:
        return None


def meters_to_feet_inches(meters: Optional[float]) -> str:
    """Converts metric meters to Imperial feet and inches string, e.g. 38' 6.5\"."""
    if meters is None:
        return "--"
    try:
        m = float(meters)
    except (ValueError, TypeError):
        return "--"
    
    total_inches = m / 0.0254
    feet = int(total_inches // 12)
    inches = total_inches % 12
    return f"{feet}' {inches:.1f}\""


def feet_inches_to_meters(feet: float, inches: float) -> float:
    """Converts feet and inches into metric meters."""
    total_inches = float(feet) * 12 + float(inches)
    return round(total_inches * 0.0254, 4)


def parse_field_mark(mark_input: str) -> Optional[float]:
    """
    Parses either metric meters ('11.75') or imperial marks ('38\' 6.5"', '38-6.5', '38 6.5')
    and returns standardized metric meters.
    """
    if not mark_input:
        return None
    s = str(mark_input).strip()
    if not s:
        return None

    # Check for imperial notation like 38' 6.5" or 38'6" or 38-6.5
    imperial_match = re.match(r"^(\d+)\s*(?:'|-|ft\.?)\s*(\d+(?:\.\d+)?)\s*(?:\"|in\.?)?$", s, re.IGNORECASE)
    if imperial_match:
        feet = float(imperial_match.group(1))
        inches = float(imperial_match.group(2))
        return feet_inches_to_meters(feet, inches)
    
    # Just feet with tick, e.g. 130'
    just_feet = re.match(r"^(\d+)\s*(?:'|ft\.?)$", s, re.IGNORECASE)
    if just_feet:
        return feet_inches_to_meters(float(just_feet.group(1)), 0.0)

    try:
        # Assume direct metric meters input
        return round(float(s.replace("m", "").strip()), 4)
    except Exception:
        return None


def format_field_mark(meters: Optional[float], prefer_unit: str = "Imperial") -> str:
    """Formats a field mark showing both imperial and metric representations."""
    if meters is None:
        return "--"
    imp = meters_to_feet_inches(meters)
    met = f"{float(meters):.2f}m"
    if prefer_unit == "Imperial":
        return f"{imp} ({met})"
    return f"{met} ({imp})"


def format_result_display(event_type: str, value: Optional[float], prefer_field_unit: str = "Imperial") -> str:
    """Helper to format either track time or field distance appropriately."""
    if value is None:
        return "--"
    if event_type in ("Track", "Relay"):
        return format_time(value)
    else:
        return format_field_mark(value, prefer_field_unit)


def get_school_year(date_val: Any) -> str:
    """
    Computes high school academic season year string from a date.
    E.g.
      '2026-05-12' -> '2025-26' (Spring outdoor season)
      '2026-01-18' -> '2025-26' (Winter indoor season)
      '2025-12-07' -> '2025-26' (Early winter indoor season)
      '2026-10-10' -> '2026-27' (Fall cross country / early winter)
      '2025-05-15' -> '2024-25'
    """
    if not date_val:
        return "Unknown"
    try:
        if isinstance(date_val, str):
            dt = datetime.strptime(str(date_val)[:10], "%Y-%m-%d").date()
        elif isinstance(date_val, datetime):
            dt = date_val.date()
        else:
            dt = date_val
        year = dt.year
        month = dt.month
        # Academic year cuts over around July 1
        if month >= 7:
            start_yr = year
            end_yr = year + 1
        else:
            start_yr = year - 1
            end_yr = year
        return f"{start_yr}-{str(end_yr)[2:]}"
    except Exception:
        return "Unknown"


def get_all_season_years() -> List[str]:
    """Returns list of distinct academic season years present in the database, sorted descending."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT date FROM meets WHERE date IS NOT NULL ORDER BY date DESC")
        dates = [row[0] for row in cursor.fetchall() if row[0]]
    sy_set = set(get_school_year(d) for d in dates if d)
    sy_list = sorted([sy for sy in sy_set if sy != "Unknown"], reverse=True)
    for default_sy in ["2026-27", "2025-26"]:
        if default_sy not in sy_list:
            sy_list.append(default_sy)
    return sorted(list(set(sy_list)), reverse=True)


# ==========================================
# SCHEMA INITIALIZATION
# ==========================================

def init_db():
    """Initializes SQLite database schema and seeds initial data if needed."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Athletes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS athletes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                gender TEXT NOT NULL CHECK(gender IN ('M', 'F')),
                age INTEGER,
                grade_level INTEGER CHECK(grade_level BETWEEN 7 AND 12),
                active_status BOOLEAN NOT NULL DEFAULT 1
            );
        """)

        # 2. Venues
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS venues (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                season TEXT NOT NULL CHECK(season IN ('Indoor', 'Outdoor', 'Both')),
                lap_distance_meters REAL NOT NULL
            );
        """)

        # 3. Events
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                season TEXT NOT NULL CHECK(season IN ('Indoor', 'Outdoor')),
                event_name TEXT NOT NULL,
                event_type TEXT NOT NULL CHECK(event_type IN ('Track', 'Field', 'Relay')),
                distance_meters REAL,
                sort_order TEXT NOT NULL CHECK(sort_order IN ('ASC', 'DESC')),
                UNIQUE(season, event_name)
            );
        """)

        # 4. Meets
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                date DATE NOT NULL,
                venue_id INTEGER NOT NULL REFERENCES venues(id),
                season TEXT NOT NULL CHECK(season IN ('Indoor', 'Outdoor')),
                meet_type TEXT NOT NULL CHECK(meet_type IN ('Dual', 'Invitational', 'Championship', 'State Qualifier', 'Practice / Time Trial'))
            );
        """)

        # 5. Results (Individual Events)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                athlete_id INTEGER NOT NULL REFERENCES athletes(id) ON DELETE CASCADE,
                event_id INTEGER NOT NULL REFERENCES events(id),
                meet_id INTEGER NOT NULL REFERENCES meets(id) ON DELETE CASCADE,
                result_value REAL NOT NULL, -- seconds for track, meters for field
                timing_method TEXT NOT NULL DEFAULT 'FAT' CHECK(timing_method IN ('FAT', 'Hand')),
                is_official BOOLEAN NOT NULL DEFAULT 1,
                notes TEXT
            );
        """)

        # 6. Relay_Results
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relay_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id),
                meet_id INTEGER NOT NULL REFERENCES meets(id) ON DELETE CASCADE,
                total_time_seconds REAL NOT NULL,
                timing_method TEXT NOT NULL DEFAULT 'FAT' CHECK(timing_method IN ('FAT', 'Hand')),
                is_official BOOLEAN NOT NULL DEFAULT 1,
                notes TEXT
            );
        """)

        # 7. Relay_Legs (Normalized individual splits)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS relay_legs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                relay_result_id INTEGER NOT NULL REFERENCES relay_results(id) ON DELETE CASCADE,
                leg_number INTEGER NOT NULL CHECK(leg_number BETWEEN 1 AND 4),
                athlete_id INTEGER REFERENCES athletes(id) ON DELETE SET NULL,
                split_seconds REAL,
                notes TEXT
            );
        """)

        # 8. Standards (School Records & Qualifying Standards)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS standards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL REFERENCES events(id),
                gender TEXT NOT NULL CHECK(gender IN ('M', 'F')),
                standard_name TEXT NOT NULL,
                standard_value REAL NOT NULL,
                UNIQUE(event_id, gender, standard_name)
            );
        """)

        # 9. Wasaren League Rival & Waterford Marks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS wasaren_league_marks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                school_name TEXT NOT NULL,
                school_id INTEGER,
                athlete_name TEXT NOT NULL,
                athlete_id TEXT,
                gender TEXT NOT NULL CHECK(gender IN ('M', 'F')),
                event_code TEXT NOT NULL,
                event_name TEXT NOT NULL,
                event_type TEXT NOT NULL CHECK(event_type IN ('Track', 'Field', 'Relay', 'Other')),
                mark_display TEXT NOT NULL,
                mark_value REAL NOT NULL,
                meet_name TEXT,
                meet_date DATE,
                season TEXT NOT NULL CHECK(season IN ('Indoor', 'Outdoor')),
                season_year TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(school_name, athlete_name, event_name, season, season_year, mark_display)
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wasaren_event_lookup ON wasaren_league_marks(event_name, season, season_year, gender);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_wasaren_school_season ON wasaren_league_marks(school_name, season_year);")

        conn.commit()
    
    # Check if seed data is needed
    seed_initial_data_if_empty()


# ==========================================
# SEED DATA GENERATOR
# ==========================================

def seed_initial_data_if_empty():
    """Seeds default venues, events, standards, and demo athletes/results if database is empty."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Check venues
        cursor.execute("SELECT COUNT(*) FROM venues")
        if cursor.fetchone()[0] == 0:
            venues = [
                ("Outdoor Track", "Outdoor", 400.0),
                ("HVCC Indoor", "Indoor", 160.93),
                ("Union Fieldhouse", "Indoor", 160.0),
            ]
            cursor.executemany("INSERT INTO venues (name, season, lap_distance_meters) VALUES (?, ?, ?)", venues)
            conn.commit()

        # Check events
        cursor.execute("SELECT COUNT(*) FROM events")
        if cursor.fetchone()[0] == 0:
            events = [
                # Indoor Track
                ("Indoor", "55m", "Track", 55.0, "ASC"),
                ("Indoor", "55m Hurdles", "Track", 55.0, "ASC"),
                ("Indoor", "300m", "Track", 300.0, "ASC"),
                ("Indoor", "600m", "Track", 600.0, "ASC"),
                ("Indoor", "1000m", "Track", 1000.0, "ASC"),
                ("Indoor", "1500m", "Track", 1500.0, "ASC"),
                ("Indoor", "1600m", "Track", 1600.0, "ASC"),
                ("Indoor", "3000m", "Track", 3000.0, "ASC"),
                ("Indoor", "3200m", "Track", 3200.0, "ASC"),
                # Indoor Relays
                ("Indoor", "4x200m Relay", "Relay", 800.0, "ASC"),
                ("Indoor", "4x400m Relay", "Relay", 1600.0, "ASC"),
                ("Indoor", "4x800m Relay", "Relay", 3200.0, "ASC"),
                ("Indoor", "1600m Sprint Medley (SMR)", "Relay", 1600.0, "ASC"),
                ("Indoor", "Distance Medley (DMR)", "Relay", 4000.0, "ASC"),
                # Indoor Field
                ("Indoor", "Shot Put", "Field", None, "DESC"),
                ("Indoor", "High Jump", "Field", None, "DESC"),
                ("Indoor", "Pole Vault", "Field", None, "DESC"),
                ("Indoor", "Long Jump", "Field", None, "DESC"),
                ("Indoor", "Triple Jump", "Field", None, "DESC"),
                ("Indoor", "Weight Throw", "Field", None, "DESC"),

                # Outdoor Track
                ("Outdoor", "100m", "Track", 100.0, "ASC"),
                ("Outdoor", "100m Hurdles (Girls)", "Track", 100.0, "ASC"),
                ("Outdoor", "110m Hurdles (Boys)", "Track", 110.0, "ASC"),
                ("Outdoor", "200m", "Track", 200.0, "ASC"),
                ("Outdoor", "400m", "Track", 400.0, "ASC"),
                ("Outdoor", "400m Hurdles", "Track", 400.0, "ASC"),
                ("Outdoor", "800m", "Track", 800.0, "ASC"),
                ("Outdoor", "1500m", "Track", 1500.0, "ASC"),
                ("Outdoor", "1600m", "Track", 1600.0, "ASC"),
                ("Outdoor", "3000m", "Track", 3000.0, "ASC"),
                ("Outdoor", "3200m", "Track", 3200.0, "ASC"),
                ("Outdoor", "2000m Steeplechase", "Track", 2000.0, "ASC"),
                ("Outdoor", "3000m Steeplechase", "Track", 3000.0, "ASC"),
                # Outdoor Relays
                ("Outdoor", "4x100m Relay", "Relay", 400.0, "ASC"),
                ("Outdoor", "4x400m Relay", "Relay", 1600.0, "ASC"),
                ("Outdoor", "4x800m Relay", "Relay", 3200.0, "ASC"),
                ("Outdoor", "1600m Sprint Medley (SMR)", "Relay", 1600.0, "ASC"),
                ("Outdoor", "Distance Medley (DMR)", "Relay", 4000.0, "ASC"),
                # Outdoor Field
                ("Outdoor", "Shot Put", "Field", None, "DESC"),
                ("Outdoor", "Discus", "Field", None, "DESC"),
                ("Outdoor", "High Jump", "Field", None, "DESC"),
                ("Outdoor", "Pole Vault", "Field", None, "DESC"),
                ("Outdoor", "Long Jump", "Field", None, "DESC"),
                ("Outdoor", "Triple Jump", "Field", None, "DESC"),
                ("Outdoor", "Javelin", "Field", None, "DESC"),
            ]
            cursor.executemany("""
                INSERT INTO events (season, event_name, event_type, distance_meters, sort_order)
                VALUES (?, ?, ?, ?, ?)
            """, events)
            conn.commit()

        # Check athletes
        cursor.execute("SELECT COUNT(*) FROM athletes")
        if cursor.fetchone()[0] == 0:
            athletes = [
                ("Maya", "Jenkins", "F", 16, 11, 1),      # 16-yo female junior sprinter/jumper
                ("Liam", "O'Connor", "M", 14, 9, 1),       # 14-yo male freshman distance
                ("Marcus", "Davis", "M", 17, 12, 1),      # 17-yo senior sprinter (400m)
                ("Sophia", "Rodriguez", "F", 15, 10, 1),  # 15-yo sophomore mid-distance
                ("Carter", "Smith", "M", 16, 11, 1),      # 16-yo junior distance
                ("Emma", "Bennett", "F", 17, 12, 1),      # 17-yo senior thrower
                ("Lucas", "Miller", "M", 15, 10, 1),      # 15-yo sophomore hurdler/jumper
                ("Ava", "Taylor", "F", 14, 9, 1),         # 14-yo freshman sprinter
            ]
            cursor.executemany("""
                INSERT INTO athletes (first_name, last_name, gender, age, grade_level, active_status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, athletes)
            conn.commit()

        # Check standards
        cursor.execute("SELECT COUNT(*) FROM standards")
        if cursor.fetchone()[0] == 0:
            # Look up event IDs
            cursor.execute("SELECT id, season, event_name FROM events")
            event_map = {(r["season"], r["event_name"]): r["id"] for r in cursor.fetchall()}
            
            standards_data = []
            # Boys 1600m
            if ("Outdoor", "1600m") in event_map:
                eid = event_map[("Outdoor", "1600m")]
                standards_data.extend([
                    (eid, "M", "School Record", 268.50),        # 4:28.50
                    (eid, "M", "Section 2 Standard", 278.00),    # 4:38.00
                    (eid, "M", "State Qualifier", 264.14),       # 4:24.14
                ])
            # Girls 100m
            if ("Outdoor", "100m") in event_map:
                eid = event_map[("Outdoor", "100m")]
                standards_data.extend([
                    (eid, "F", "School Record", 12.40),
                    (eid, "F", "Section 2 Standard", 13.10),
                    (eid, "F", "State Qualifier", 12.64),
                ])
            # Boys 400m
            if ("Outdoor", "400m") in event_map:
                eid = event_map[("Outdoor", "400m")]
                standards_data.extend([
                    (eid, "M", "School Record", 50.80),
                    (eid, "M", "Section 2 Standard", 52.50),
                    (eid, "M", "State Qualifier", 50.40),
                ])
            # Girls Shot Put (meters)
            if ("Outdoor", "Shot Put") in event_map:
                eid = event_map[("Outdoor", "Shot Put")]
                standards_data.extend([
                    (eid, "F", "School Record", 10.97),        # ~36' 0"
                    (eid, "F", "Section 2 Standard", 9.75),    # ~32' 0"
                    (eid, "F", "State Qualifier", 11.28),      # ~37' 0"
                ])
            # Girls Long Jump
            if ("Outdoor", "Long Jump") in event_map:
                eid = event_map[("Outdoor", "Long Jump")]
                standards_data.extend([
                    (eid, "F", "School Record", 5.25),         # ~17' 2.75"
                    (eid, "F", "Section 2 Standard", 4.80),    # ~15' 9"
                    (eid, "F", "State Qualifier", 5.15),       # ~16' 10.75"
                ])
            
            cursor.executemany("""
                INSERT OR IGNORE INTO standards (event_id, gender, standard_name, standard_value)
                VALUES (?, ?, ?, ?)
            """, standards_data)
            conn.commit()

        # Check meets & results
        cursor.execute("SELECT COUNT(*) FROM meets")
        if cursor.fetchone()[0] == 0:
            cursor.execute("SELECT id, name FROM venues")
            venue_map = {r["name"]: r["id"] for r in cursor.fetchall()}
            
            meets = [
                ("Union Winter Classic", "2026-01-10", venue_map.get("Union Fieldhouse", 3), "Indoor", "Invitational"),
                ("HVCC League Meet #1", "2026-01-24", venue_map.get("HVCC Indoor", 2), "Indoor", "Dual"),
                ("Wasaren Indoor Championships", "2026-02-07", venue_map.get("HVCC Indoor", 2), "Indoor", "Championship"),
                ("Section 2 State Qualifier", "2026-02-21", venue_map.get("HVCC Indoor", 2), "Indoor", "State Qualifier"),
                ("Waterford Spring Time Trial", "2026-04-04", venue_map.get("Outdoor Track", 1), "Outdoor", "Practice / Time Trial"),
                ("Dual Meet vs Stillwater", "2026-04-18", venue_map.get("Outdoor Track", 1), "Outdoor", "Dual"),
                ("Wasaren League Championships", "2026-05-09", venue_map.get("Outdoor Track", 1), "Outdoor", "Championship"),
                ("Section 2 Group 4 Championships", "2026-05-23", venue_map.get("Outdoor Track", 1), "Outdoor", "Championship"),
            ]
            cursor.executemany("""
                INSERT INTO meets (name, date, venue_id, season, meet_type)
                VALUES (?, ?, ?, ?, ?)
            """, meets)
            conn.commit()

            # Seed realistic results showing progression
            cursor.execute("SELECT id, first_name, last_name FROM athletes")
            ath_map = {f"{r['first_name']} {r['last_name']}": r["id"] for r in cursor.fetchall()}
            
            cursor.execute("SELECT id, season, event_name FROM events")
            ev_map = {(r["season"], r["event_name"]): r["id"] for r in cursor.fetchall()}

            cursor.execute("SELECT id, name FROM meets")
            meet_id_map = {r["name"]: r["id"] for r in cursor.fetchall()}

            results_data = [
                # Maya Jenkins (Sprinter/Jumper)
                # Indoor 55m
                (ath_map["Maya Jenkins"], ev_map[("Indoor", "55m")], meet_id_map["Union Winter Classic"], 7.82, "FAT", 1, "Good start"),
                (ath_map["Maya Jenkins"], ev_map[("Indoor", "55m")], meet_id_map["HVCC League Meet #1"], 7.74, "FAT", 1, "New PR!"),
                (ath_map["Maya Jenkins"], ev_map[("Indoor", "55m")], meet_id_map["Wasaren Indoor Championships"], 7.68, "FAT", 1, "League 2nd place! PR"),
                # Maya Outdoor 100m
                (ath_map["Maya Jenkins"], ev_map[("Outdoor", "100m")], meet_id_map["Waterford Spring Time Trial"], 13.05, "Hand", 0, "Practice time trial"),
                (ath_map["Maya Jenkins"], ev_map[("Outdoor", "100m")], meet_id_map["Dual Meet vs Stillwater"], 12.92, "FAT", 1, "Dual meet winner"),
                (ath_map["Maya Jenkins"], ev_map[("Outdoor", "100m")], meet_id_map["Wasaren League Championships"], 12.75, "FAT", 1, "PR! 1st Place"),
                (ath_map["Maya Jenkins"], ev_map[("Outdoor", "100m")], meet_id_map["Section 2 Group 4 Championships"], 12.60, "FAT", 1, "School Record & State Qual Standard!"),
                # Maya Outdoor Long Jump (meters)
                (ath_map["Maya Jenkins"], ev_map[("Outdoor", "Long Jump")], meet_id_map["Dual Meet vs Stillwater"], 4.88, "FAT", 1, "16' 0\""),
                (ath_map["Maya Jenkins"], ev_map[("Outdoor", "Long Jump")], meet_id_map["Wasaren League Championships"], 5.05, "FAT", 1, "16' 6.75\" PR!"),
                
                # Liam O'Connor (14yo Freshman Distance)
                # Indoor 1000m
                (ath_map["Liam O'Connor"], ev_map[("Indoor", "1000m")], meet_id_map["Union Winter Classic"], 188.40, "FAT", 1, "3:08.40"),
                (ath_map["Liam O'Connor"], ev_map[("Indoor", "1000m")], meet_id_map["HVCC League Meet #1"], 182.20, "FAT", 1, "3:02.20 PR"),
                # Outdoor 1600m
                (ath_map["Liam O'Connor"], ev_map[("Outdoor", "1600m")], meet_id_map["Waterford Spring Time Trial"], 305.00, "Hand", 0, "5:05.00 intra-squad"),
                (ath_map["Liam O'Connor"], ev_map[("Outdoor", "1600m")], meet_id_map["Dual Meet vs Stillwater"], 294.80, "FAT", 1, "4:54.80 first sub-5:00!"),
                (ath_map["Liam O'Connor"], ev_map[("Outdoor", "1600m")], meet_id_map["Wasaren League Championships"], 286.20, "FAT", 1, "4:46.20 Freshman PR!"),
                (ath_map["Liam O'Connor"], ev_map[("Outdoor", "1600m")], meet_id_map["Section 2 Group 4 Championships"], 281.50, "FAT", 1, "4:41.50 Sectional Top 5!"),
                # Outdoor 3200m
                (ath_map["Liam O'Connor"], ev_map[("Outdoor", "3200m")], meet_id_map["Dual Meet vs Stillwater"], 642.00, "FAT", 1, "10:42.00"),
                (ath_map["Liam O'Connor"], ev_map[("Outdoor", "3200m")], meet_id_map["Wasaren League Championships"], 618.40, "FAT", 1, "10:18.40 PR!"),

                # Marcus Davis (Senior 400m)
                (ath_map["Marcus Davis"], ev_map[("Outdoor", "400m")], meet_id_map["Dual Meet vs Stillwater"], 53.40, "FAT", 1, "Controlled win"),
                (ath_map["Marcus Davis"], ev_map[("Outdoor", "400m")], meet_id_map["Wasaren League Championships"], 51.90, "FAT", 1, "League Champion"),
                (ath_map["Marcus Davis"], ev_map[("Outdoor", "400m")], meet_id_map["Section 2 Group 4 Championships"], 50.75, "FAT", 1, "New School Record!"),

                # Emma Bennett (Senior Thrower - Shot Put meters)
                (ath_map["Emma Bennett"], ev_map[("Outdoor", "Shot Put")], meet_id_map["Dual Meet vs Stillwater"], 9.90, "FAT", 1, "32' 5.75\""),
                (ath_map["Emma Bennett"], ev_map[("Outdoor", "Shot Put")], meet_id_map["Wasaren League Championships"], 10.45, "FAT", 1, "34' 3.5\" PR!"),
                (ath_map["Emma Bennett"], ev_map[("Outdoor", "Shot Put")], meet_id_map["Section 2 Group 4 Championships"], 10.82, "FAT", 1, "35' 6\" 1st Place"),
            ]
            cursor.executemany("""
                INSERT INTO results (athlete_id, event_id, meet_id, result_value, timing_method, is_official, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, results_data)
            conn.commit()

            # Seed Relays
            # Girls 4x100m Outdoor Relay at Wasaren League Championships
            cursor.execute("""
                INSERT INTO relay_results (event_id, meet_id, total_time_seconds, timing_method, is_official, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ev_map[("Outdoor", "4x100m Relay")], meet_id_map["Wasaren League Championships"], 51.40, "FAT", 1, "Gold medal relay!"))
            relay1_id = cursor.lastrowid

            relay1_legs = [
                (relay1_id, 1, ath_map["Ava Taylor"], 13.20, "Lead-off"),
                (relay1_id, 2, ath_map["Sophia Rodriguez"], 12.90, "Smooth 2nd leg"),
                (relay1_id, 3, ath_map["Emma Bennett"], 13.10, "Strong backstretch"),
                (relay1_id, 4, ath_map["Maya Jenkins"], 12.20, "Blazing anchor split"),
            ]
            cursor.executemany("""
                INSERT INTO relay_legs (relay_result_id, leg_number, athlete_id, split_seconds, notes)
                VALUES (?, ?, ?, ?, ?)
            """, relay1_legs)

            # Boys 4x400m Outdoor Relay at Section 2 Group 4 Championships
            cursor.execute("""
                INSERT INTO relay_results (event_id, meet_id, total_time_seconds, timing_method, is_official, notes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ev_map[("Outdoor", "4x400m Relay")], meet_id_map["Section 2 Group 4 Championships"], 214.60, "FAT", 1, "3:34.60 Sectional runner-up"))
            relay2_id = cursor.lastrowid

            relay2_legs = [
                (relay2_id, 1, ath_map["Lucas Miller"], 55.40, "Strong start"),
                (relay2_id, 2, ath_map["Liam O'Connor"], 54.80, "Great freshman middle leg"),
                (relay2_id, 3, ath_map["Carter Smith"], 54.20, "Passed two runners"),
                (relay2_id, 4, ath_map["Marcus Davis"], 50.20, "Anchor split PR!"),
            ]
            cursor.executemany("""
                INSERT INTO relay_legs (relay_result_id, leg_number, athlete_id, split_seconds, notes)
                VALUES (?, ?, ?, ?, ?)
            """, relay2_legs)

            conn.commit()


# ==========================================
# CRUD & QUERY OPERATIONS
# ==========================================

# --- Athletes ---
def get_all_athletes(active_only: bool = False) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM athletes"
        if active_only:
            query += " WHERE active_status = 1"
        query += " ORDER BY last_name, first_name"
        cursor.execute(query)
        return [dict(r) for r in cursor.fetchall()]


def get_athlete_by_id(athlete_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM athletes WHERE id = ?", (athlete_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def add_athlete(first_name: str, last_name: str, gender: str, age: int, grade_level: int, active_status: bool = True) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO athletes (first_name, last_name, gender, age, grade_level, active_status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (first_name.strip(), last_name.strip(), gender, age, grade_level, 1 if active_status else 0))
        conn.commit()
        return cursor.lastrowid


def update_athlete(athlete_id: int, first_name: str, last_name: str, gender: str, age: int, grade_level: int, active_status: bool):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE athletes 
            SET first_name = ?, last_name = ?, gender = ?, age = ?, grade_level = ?, active_status = ?
            WHERE id = ?
        """, (first_name.strip(), last_name.strip(), gender, age, grade_level, 1 if active_status else 0, athlete_id))
        conn.commit()


def delete_athlete(athlete_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM athletes WHERE id = ?", (athlete_id,))
        conn.commit()


# --- Venues ---
def get_all_venues(season: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        if season and season != "All":
            cursor.execute("SELECT * FROM venues WHERE season = ? OR season = 'Both' ORDER BY name", (season,))
        else:
            cursor.execute("SELECT * FROM venues ORDER BY name")
        return [dict(r) for r in cursor.fetchall()]


def add_venue(name: str, season: str, lap_distance_meters: float) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO venues (name, season, lap_distance_meters)
            VALUES (?, ?, ?)
        """, (name.strip(), season, lap_distance_meters))
        conn.commit()
        return cursor.lastrowid


def delete_venue(venue_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM venues WHERE id = ?", (venue_id,))
        conn.commit()


# --- Events ---
def get_all_events(season: Optional[str] = None, event_type: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM events WHERE 1=1"
        params = []
        if season and season != "All":
            query += " AND season = ?"
            params.append(season)
        if event_type and event_type != "All":
            query += " AND event_type = ?"
            params.append(event_type)
        query += " ORDER BY season, event_type, distance_meters, event_name"
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def get_event_by_id(event_id: int) -> Optional[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM events WHERE id = ?", (event_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


# --- Meets ---
def get_all_meets(season: Optional[str] = None, season_year: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT m.*, v.name as venue_name, v.lap_distance_meters
            FROM meets m
            JOIN venues v ON m.venue_id = v.id
            WHERE 1=1
        """
        params = []
        if season and season != "All":
            query += " AND m.season = ?"
            params.append(season)
        if season_year and season_year != "ALL":
            try:
                start_yr = int(season_year.split("-")[0])
                query += " AND m.date >= ? AND m.date <= ?"
                params.extend([f"{start_yr}-07-01", f"{start_yr+1}-06-30"])
            except Exception:
                pass
        query += " ORDER BY m.date DESC, m.name"
        cursor.execute(query, params)
        meets = [dict(r) for r in cursor.fetchall()]
        for m in meets:
            m["season_year"] = get_school_year(m["date"])
        return meets


def add_meet(name: str, meet_date: str, venue_id: int, season: str, meet_type: str) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO meets (name, date, venue_id, season, meet_type)
            VALUES (?, ?, ?, ?, ?)
        """, (name.strip(), meet_date, venue_id, season, meet_type))
        conn.commit()
        return cursor.lastrowid


def delete_meet(meet_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM meets WHERE id = ?", (meet_id,))
        conn.commit()


# --- Results (Individual) ---
def add_result(athlete_id: int, event_id: int, meet_id: int, result_value: float,
               timing_method: str = "FAT", is_official: bool = True, notes: str = "") -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO results (athlete_id, event_id, meet_id, result_value, timing_method, is_official, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (athlete_id, event_id, meet_id, result_value, timing_method, 1 if is_official else 0, notes.strip()))
        conn.commit()
        return cursor.lastrowid


def update_result(result_id: int, result_value: float, timing_method: str, is_official: bool, notes: str):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE results
            SET result_value = ?, timing_method = ?, is_official = ?, notes = ?
            WHERE id = ?
        """, (result_value, timing_method, 1 if is_official else 0, notes.strip(), result_id))
        conn.commit()


def delete_result(result_id: int):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM results WHERE id = ?", (result_id,))
        conn.commit()


def get_results_by_athlete(athlete_id: int, season_year: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all historical individual results for a given athlete, chronologically."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT r.*, e.event_name, e.event_type, e.season, e.sort_order,
                   m.name as meet_name, m.date as meet_date, m.meet_type,
                   v.name as venue_name
            FROM results r
            JOIN events e ON r.event_id = e.id
            JOIN meets m ON r.meet_id = m.id
            JOIN venues v ON m.venue_id = v.id
            WHERE r.athlete_id = ?
        """
        params = [athlete_id]
        if season_year and season_year != "ALL":
            try:
                start_yr = int(season_year.split("-")[0])
                query += " AND m.date >= ? AND m.date <= ?"
                params.extend([f"{start_yr}-07-01", f"{start_yr+1}-06-30"])
            except Exception:
                pass
        query += " ORDER BY m.date ASC, r.id ASC"
        cursor.execute(query, params)
        results = [dict(r) for r in cursor.fetchall()]
        for r in results:
            r["season_year"] = get_school_year(r["meet_date"])
        return results


def get_athlete_pr_map(athlete_id: int, season_year: Optional[str] = None) -> Dict[int, Dict[str, Any]]:
    """
    Computes all-time Personal Records (PR) or Season Bests (SB) for an athlete per event.
    If season_year is provided (e.g. '2025-26'), computes Season Best for that season.
    Returns dict: {event_id: {'pr_value': float, 'date': str, 'meet_name': str, 'season_year': str}}
    """
    results = get_results_by_athlete(athlete_id, season_year=season_year)
    pr_map = {}
    for r in results:
        eid = r["event_id"]
        val = r["result_value"]
        order = r["sort_order"]
        if eid not in pr_map:
            pr_map[eid] = {"pr_value": val, "date": r["meet_date"], "meet_name": r["meet_name"], "season_year": r.get("season_year", "")}
        else:
            current_best = pr_map[eid]["pr_value"]
            if (order == "ASC" and val < current_best) or (order == "DESC" and val > current_best):
                pr_map[eid] = {"pr_value": val, "date": r["meet_date"], "meet_name": r["meet_name"], "season_year": r.get("season_year", "")}
    return pr_map


def get_results_for_meet_event(meet_id: int, event_id: int) -> List[Dict[str, Any]]:
    """Gets results for a specific meet and event (useful for bulk editing)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT r.*, a.first_name, a.last_name, a.gender, a.grade_level
            FROM results r
            JOIN athletes a ON r.athlete_id = a.id
            WHERE r.meet_id = ? AND r.event_id = ?
            ORDER BY a.last_name, a.first_name
        """
        cursor.execute(query, (meet_id, event_id))
        return [dict(r) for r in cursor.fetchall()]


# --- Relays ---
def add_relay_result(event_id: int, meet_id: int, total_time_seconds: float,
                     timing_method: str = "FAT", is_official: bool = True, notes: str = "",
                     legs: Optional[List[Dict[str, Any]]] = None) -> int:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO relay_results (event_id, meet_id, total_time_seconds, timing_method, is_official, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (event_id, meet_id, total_time_seconds, timing_method, 1 if is_official else 0, notes.strip()))
        relay_id = cursor.lastrowid

        if legs:
            for leg in legs:
                cursor.execute("""
                    INSERT INTO relay_legs (relay_result_id, leg_number, athlete_id, split_seconds, notes)
                    VALUES (?, ?, ?, ?, ?)
                """, (relay_id, leg.get("leg_number"), leg.get("athlete_id"), leg.get("split_seconds"), leg.get("notes", "")))
        conn.commit()
        return relay_id


def get_relay_splits_by_athlete(athlete_id: int) -> List[Dict[str, Any]]:
    """Gets all relay appearances and split times for a given athlete."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT rl.*, rr.total_time_seconds, rr.timing_method, rr.is_official,
                   e.event_name, e.season,
                   m.name as meet_name, m.date as meet_date,
                   v.name as venue_name
            FROM relay_legs rl
            JOIN relay_results rr ON rl.relay_result_id = rr.id
            JOIN events e ON rr.event_id = e.id
            JOIN meets m ON rr.meet_id = m.id
            JOIN venues v ON m.venue_id = v.id
            WHERE rl.athlete_id = ?
            ORDER BY m.date DESC, rl.leg_number ASC
        """
        cursor.execute(query, (athlete_id,))
        return [dict(r) for r in cursor.fetchall()]


def get_all_relay_results(season: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all relay results with legs expanded."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT rr.*, e.event_name, e.season,
                   m.name as meet_name, m.date as meet_date,
                   v.name as venue_name
            FROM relay_results rr
            JOIN events e ON rr.event_id = e.id
            JOIN meets m ON rr.meet_id = m.id
            JOIN venues v ON m.venue_id = v.id
            WHERE 1=1
        """
        params = []
        if season and season != "All":
            query += " AND e.season = ?"
            params.append(season)
        query += " ORDER BY m.date DESC, rr.total_time_seconds ASC"
        cursor.execute(query, params)
        relays = [dict(r) for r in cursor.fetchall()]

        # Attach legs
        for r in relays:
            cursor.execute("""
                SELECT rl.*, a.first_name, a.last_name
                FROM relay_legs rl
                LEFT JOIN athletes a ON rl.athlete_id = a.id
                WHERE rl.relay_result_id = ?
                ORDER BY rl.leg_number ASC
            """, (r["id"],))
            r["legs"] = [dict(l) for l in cursor.fetchall()]
        return relays


# --- Leaderboards & Honor Roll ---
def get_event_leaderboard(event_id: int, gender: Optional[str] = None, official_only: bool = True, limit: int = 10, season_year: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Computes top performances for an event (best mark per athlete).
    Uses proper ASC (track) or DESC (field) sorting.
    Can filter by specific academic season year (e.g. '2025-26', '2026-27', or 'ALL').
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        # Get sort order
        cursor.execute("SELECT sort_order, event_type FROM events WHERE id = ?", (event_id,))
        ev = cursor.fetchone()
        if not ev:
            return []
        
        sort_dir = ev["sort_order"]
        agg_func = "MIN" if sort_dir == "ASC" else "MAX"

        query = f"""
            SELECT a.id as athlete_id, a.first_name, a.last_name, a.gender, a.grade_level,
                   {agg_func}(r.result_value) as best_mark,
                   r.timing_method, m.date as meet_date, m.name as meet_name, v.name as venue_name
            FROM results r
            JOIN athletes a ON r.athlete_id = a.id
            JOIN meets m ON r.meet_id = m.id
            JOIN venues v ON m.venue_id = v.id
            WHERE r.event_id = ?
        """
        params = [event_id]
        if gender and gender != "All":
            query += " AND a.gender = ?"
            params.append(gender)
        if official_only:
            query += " AND r.is_official = 1"
        if season_year and season_year != "ALL":
            try:
                start_yr = int(season_year.split("-")[0])
                query += " AND m.date >= ? AND m.date <= ?"
                params.extend([f"{start_yr}-07-01", f"{start_yr+1}-06-30"])
            except Exception:
                pass
        
        query += f"""
            GROUP BY a.id
            ORDER BY best_mark {sort_dir}
            LIMIT ?
        """
        params.append(limit)
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


# --- Standards ---
def get_standards(event_id: Optional[int] = None, gender: Optional[str] = None) -> List[Dict[str, Any]]:
    with get_connection() as conn:
        cursor = conn.cursor()
        query = """
            SELECT s.*, e.event_name, e.event_type, e.season, e.sort_order
            FROM standards s
            JOIN events e ON s.event_id = e.id
            WHERE 1=1
        """
        params = []
        if event_id:
            query += " AND s.event_id = ?"
            params.append(event_id)
        if gender and gender != "All":
            query += " AND s.gender = ?"
            params.append(gender)
        query += " ORDER BY e.season, e.event_name, s.standard_name"
        cursor.execute(query, params)
        return [dict(r) for r in cursor.fetchall()]


def add_or_update_standard(event_id: int, gender: str, standard_name: str, standard_value: float):
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO standards (event_id, gender, standard_name, standard_value)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(event_id, gender, standard_name)
            DO UPDATE SET standard_value = excluded.standard_value
        """, (event_id, gender, standard_name.strip(), standard_value))
        conn.commit()


# --- Database Maintenance & Reset ---
def reset_database():
    """Drops all tables and re-seeds cleanly."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA foreign_keys = OFF;")
        cursor.execute("DROP TABLE IF EXISTS wasaren_league_marks;")
        cursor.execute("DROP TABLE IF EXISTS relay_legs;")
        cursor.execute("DROP TABLE IF EXISTS relay_results;")
        cursor.execute("DROP TABLE IF EXISTS results;")
        cursor.execute("DROP TABLE IF EXISTS standards;")
        cursor.execute("DROP TABLE IF EXISTS meets;")
        cursor.execute("DROP TABLE IF EXISTS events;")
        cursor.execute("DROP TABLE IF EXISTS venues;")
        cursor.execute("DROP TABLE IF EXISTS athletes;")
        conn.commit()
    init_db()


# ==========================================
# WASAREN LEAGUE SCOUTING & COMPARISON CRUD
# ==========================================

def upsert_wasaren_mark(
    school_name: str,
    school_id: Optional[int],
    athlete_name: str,
    athlete_id: Optional[str],
    gender: str,
    event_code: str,
    event_name: str,
    event_type: str,
    mark_display: str,
    mark_value: float,
    meet_name: Optional[str],
    meet_date: Optional[str],
    season: str,
    season_year: str
):
    """Inserts or updates a rival/league mark in the wasaren_league_marks table."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO wasaren_league_marks (
                school_name, school_id, athlete_name, athlete_id, gender,
                event_code, event_name, event_type, mark_display, mark_value,
                meet_name, meet_date, season, season_year, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(school_name, athlete_name, event_name, season, season_year, mark_display)
            DO UPDATE SET
                mark_value = excluded.mark_value,
                meet_name = excluded.meet_name,
                meet_date = excluded.meet_date,
                updated_at = CURRENT_TIMESTAMP
        """, (
            school_name.strip(), school_id, athlete_name.strip(), athlete_id, gender,
            event_code.strip(), event_name.strip(), event_type.strip(),
            mark_display.strip(), float(mark_value),
            meet_name.strip() if meet_name else None,
            meet_date[:10] if meet_date else None,
            season.strip(), season_year.strip()
        ))
        conn.commit()


def clear_wasaren_marks(school_name: Optional[str] = None):
    """Clears wasaren league marks (optionally for a specific school)."""
    with get_connection() as conn:
        cursor = conn.cursor()
        if school_name:
            cursor.execute("DELETE FROM wasaren_league_marks WHERE school_name = ?", (school_name.strip(),))
        else:
            cursor.execute("DELETE FROM wasaren_league_marks;")
        conn.commit()


def get_wasaren_season_years() -> List[str]:
    """Returns list of distinct season years available in wasaren_league_marks."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT season_year FROM wasaren_league_marks WHERE season_year IS NOT NULL ORDER BY season_year DESC")
        years = [row[0] for row in cursor.fetchall() if row[0]]
    for def_yr in ["2026-27", "2025-26"]:
        if def_yr not in years:
            years.append(def_yr)
    return sorted(list(set(years)), reverse=True)


def get_wasaren_events(season: Optional[str] = None, season_year: Optional[str] = None, gender: Optional[str] = None) -> List[str]:
    """Returns distinct event names available in wasaren_league_marks, ordered logically."""
    with get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT DISTINCT event_name FROM wasaren_league_marks WHERE 1=1"
        params = []
        if season and season != "Both":
            query += " AND season = ?"
            params.append(season)
        if season_year and season_year != "ALL":
            query += " AND season_year = ?"
            params.append(season_year)
        if gender and gender != "All":
            query += " AND gender = ?"
            params.append(gender)
        cursor.execute(query, params)
        rows = [r[0] for r in cursor.fetchall() if r[0]]

    order_priority = [
        "55m", "100m", "200m", "300m", "400m", "600m", "800m", "1000m", "1500m", "1600m", "1 Mile", "3000m", "3200m",
        "55m Hurdles", "100m Hurdles", "100m Hurdles (Girls)", "110m Hurdles", "110m Hurdles (Boys)", "400m Hurdles",
        "2000m Steeplechase", "3000m Steeplechase",
        "4x100m Relay", "4x200m Relay", "4x400m Relay", "4x800m Relay", "1600m Sprint Medley (SMR)", "Distance Medley (DMR)",
        "High Jump", "Pole Vault", "Long Jump", "Triple Jump", "Shot Put", "Discus", "Weight Throw", "Javelin", "Pentathlon"
    ]
    def sort_key(name):
        try:
            return order_priority.index(name)
        except ValueError:
            return 999
    return sorted(rows, key=sort_key)


def get_wasaren_league_leaderboard(
    event_name: str,
    season: Optional[str] = None,
    season_year: Optional[str] = None,
    gender: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """
    Returns ranked leaderboard for an event across all Wasaren League schools.
    Selects the single best mark per athlete (or per school for relays).
    Calculates rank and margin/gap to the #1 league mark.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Check event_type
        cursor.execute("SELECT event_type FROM wasaren_league_marks WHERE event_name = ? LIMIT 1", (event_name,))
        ev_type_row = cursor.fetchone()
        event_type = ev_type_row[0] if ev_type_row else "Track"
        
        is_asc = (event_type in ("Track", "Relay"))
        agg_fn = "MIN" if is_asc else "MAX"
        order_dir = "ASC" if is_asc else "DESC"
        
        query = f"""
            SELECT 
                school_name,
                athlete_name,
                gender,
                event_name,
                event_type,
                {agg_fn}(mark_value) as best_value,
                mark_display,
                meet_name,
                meet_date,
                season,
                season_year
            FROM wasaren_league_marks
            WHERE event_name = ?
        """
        params: List[Any] = [event_name]
        
        if season and season != "Both":
            query += " AND season = ?"
            params.append(season)
        if season_year and season_year != "ALL":
            query += " AND season_year = ?"
            params.append(season_year)
        if gender and gender != "All":
            query += " AND gender = ?"
            params.append(gender)
            
        if event_type == "Relay":
            query += " GROUP BY school_name"
        else:
            query += " GROUP BY school_name, athlete_name"
            
        query += f" ORDER BY best_value {order_dir} LIMIT ?"
        params.append(limit)
        
        cursor.execute(query, params)
        raw_rows = cursor.fetchall()
        
    if not raw_rows:
        return []
        
    leader_val = raw_rows[0]["best_value"]
    results = []
    
    for idx, row in enumerate(raw_rows):
        r_dict = dict(row)
        r_dict["rank"] = idx + 1
        r_dict["is_waterford"] = bool("waterford" in r_dict["school_name"].lower())
        
        # Calculate gap to leader
        val = r_dict["best_value"]
        if is_asc:
            diff = val - leader_val
            r_dict["gap"] = f"+{diff:.2f}s" if diff > 0.001 else "LEADER"
        else:
            diff = leader_val - val
            if diff > 0.001:
                diff_in = diff / 0.0254
                if diff_in >= 12:
                    diff_ft = int(diff_in // 12)
                    rem_in = diff_in % 12
                    r_dict["gap"] = f"-{diff_ft}' {rem_in:.1f}\""
                else:
                    r_dict["gap"] = f"-{diff_in:.1f}\""
            else:
                r_dict["gap"] = "LEADER"
                
        results.append(r_dict)
        
    return results


def get_wasaren_virtual_meet_scores(
    season: Optional[str] = None,
    season_year: Optional[str] = None,
    gender: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Simulates a virtual Wasaren League championship meet.
    Awards 10-8-6-4-2-1 points to top 6 marks in each event.
    Applies standard high school rule: max 2 scoring individuals per school per event (1 per relay).
    """
    events = get_wasaren_events(season, season_year, gender)
    if not events:
        return []

    school_scores: Dict[str, Dict[str, Any]] = {}
    
    point_scale = [10, 8, 6, 4, 2, 1]
    
    for ev in events:
        leaderboard = get_wasaren_league_leaderboard(ev, season, season_year, gender, limit=20)
        if not leaderboard:
            continue
            
        is_relay = (leaderboard[0]["event_type"] == "Relay")
        max_per_school = 1 if is_relay else 2
        
        school_count: Dict[str, int] = {}
        place_idx = 0
        
        for item in leaderboard:
            school = item["school_name"]
            curr_count = school_count.get(school, 0)
            if curr_count >= max_per_school:
                continue
                
            school_count[school] = curr_count + 1
            pts = point_scale[place_idx] if place_idx < len(point_scale) else 0
            
            if school not in school_scores:
                school_scores[school] = {
                    "school_name": school,
                    "total_points": 0,
                    "gold_medals": 0,
                    "silver_medals": 0,
                    "bronze_medals": 0,
                    "scoring_finishes": 0,
                    "events_entered": 0
                }
                
            school_scores[school]["total_points"] += pts
            school_scores[school]["scoring_finishes"] += 1
            if place_idx == 0:
                school_scores[school]["gold_medals"] += 1
            elif place_idx == 1:
                school_scores[school]["silver_medals"] += 1
            elif place_idx == 2:
                school_scores[school]["bronze_medals"] += 1
                
            place_idx += 1
            if place_idx >= len(point_scale):
                break
                
    # Sort descending by total_points, then gold_medals
    sorted_scores = sorted(
        school_scores.values(),
        key=lambda s: (s["total_points"], s["gold_medals"], s["silver_medals"]),
        reverse=True
    )
    for idx, s in enumerate(sorted_scores):
        s["rank"] = idx + 1
        s["is_waterford"] = bool("waterford" in s["school_name"].lower())
        
    return sorted_scores


def get_wasaren_waterford_contenders(
    season: Optional[str] = None,
    season_year: Optional[str] = None,
    gender: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Returns all Waterford athletes/relays currently in top 8 in any Wasaren League event."""
    events = get_wasaren_events(season, season_year, gender)
    contenders = []
    point_scale = {1: 10, 2: 8, 3: 6, 4: 4, 5: 2, 6: 1}
    
    for ev in events:
        leaderboard = get_wasaren_league_leaderboard(ev, season, season_year, gender, limit=15)
        for row in leaderboard:
            if row["is_waterford"]:
                rank = row["rank"]
                pts = point_scale.get(rank, 0)
                contenders.append({
                    "event_name": ev,
                    "event_type": row["event_type"],
                    "athlete_name": row["athlete_name"],
                    "gender": row["gender"],
                    "rank": rank,
                    "mark_display": row["mark_display"],
                    "gap": row["gap"],
                    "projected_points": pts,
                    "status": "🥇 #1 Seed (Gold)" if rank == 1 else (
                              "🥈 Podium (Silver)" if rank == 2 else (
                              "🥉 Podium (Bronze)" if rank == 3 else (
                              "⭐ Scoring (Top 6)" if rank <= 6 else "👀 On Bubble (7th-8th)"
                              ))),
                    "meet_name": row.get("meet_name"),
                    "meet_date": row.get("meet_date")
                })
                
    return sorted(contenders, key=lambda c: (c["rank"], -c["projected_points"]))


def get_wasaren_schools_summary() -> List[Dict[str, Any]]:
    """Returns summary counts of marks stored for each Wasaren League school."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                school_name,
                COUNT(*) as total_marks,
                COUNT(DISTINCT event_name) as events_covered,
                COUNT(DISTINCT athlete_name) as athletes_count,
                MAX(meet_date) as latest_meet_date
            FROM wasaren_league_marks
            GROUP BY school_name
            ORDER BY total_marks DESC
        """)
        return [dict(r) for r in cursor.fetchall()]


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DB_PATH)

