"""
sync_waterford_pro.py - Run full authenticated MileSplit PRO sync for Waterford-Halfmoon
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import time
import requests
import database as db
import milesplit_sync as ms

EMAIL = os.getenv("MILESPLIT_EMAIL", "")
PASSWORD = os.getenv("MILESPLIT_PASSWORD", "")
MIN_GRAD_YEAR = 2026

print(f"Connecting to MileSplit PRO as {EMAIL}...")
sess, msg = ms.login_milesplit(EMAIL, PASSWORD)
if not sess:
    print(f"ERROR: Failed to authenticate with MileSplit: {msg}")
    sys.exit(1)

print(f"SUCCESS: {msg}\n")

print(f"Fetching Waterford-Halfmoon roster for Class of {MIN_GRAD_YEAR} or later...")
roster = ms.fetch_waterford_roster(min_grad_year=MIN_GRAD_YEAR, session=sess)
print(f"Found {len(roster)} eligible student-athletes on the roster.")

added, updated = ms.sync_roster_to_db(roster)
print(f"Roster database sync: {added} new athletes added, {updated} updated.\n")

# Re-fetch local athletes to get database IDs
local_athletes = db.get_all_athletes(active_only=False)
local_map = {(a["first_name"].strip().lower(), a["last_name"].strip().lower()): a["id"] for a in local_athletes}

total_results_inserted = 0
total_athletes_synced = 0

print("--- Starting Full Meet History Sync ---")
for i, ath in enumerate(roster, start=1):
    name = f"{ath['first_name']} {ath['last_name']}"
    key = (ath["first_name"].strip().lower(), ath["last_name"].strip().lower())
    local_id = local_map.get(key)
    
    if not local_id:
        print(f"[{i}/{len(roster)}] Skipping {name} (not found in DB)")
        continue
        
    url = ath.get("athlete_url")
    if not url:
        print(f"[{i}/{len(roster)}] Skipping {name} (no profile URL)")
        continue
        
    try:
        records = ms.fetch_athlete_full_history(url, session=sess)
        count = 0
        if records:
            count = ms.sync_athlete_prs_to_db(local_id, records)
            total_results_inserted += count
            total_athletes_synced += 1
        print(f"[{i}/{len(roster)}] {name} (Class {ath['grad_year']}, Gr {ath['grade_level']}): {len(records)} performances found, {count} new/updated entries logged.")
    except Exception as e:
        print(f"[{i}/{len(roster)}] {name}: Error syncing - {e}")
        
    # Polite delay between profile requests
    time.sleep(0.4)

print("\n==========================================")
print("       MILESPLIT PRO SYNC COMPLETE        ")
print("==========================================")
print(f"Total Athletes Synced: {total_athletes_synced} / {len(roster)}")
print(f"Total Meet Performance Marks Ingested: {total_results_inserted}")
