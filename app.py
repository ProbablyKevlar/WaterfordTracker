"""
app.py - Waterford Track & Field Performance Tracking Dashboard.
Streamlit application featuring mobile-responsive performance tracking,
pace calculations, relay builders, honor rolls, and coach data entry.
"""

import os
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import math
import importlib

import database as db
importlib.reload(db)
import auth
import milesplit_sync as ms
importlib.reload(ms)

# ---------------------------------------------------------
# PAGE CONFIGURATION & CUSTOM MOBILE-RESPONSIVE CSS
# ---------------------------------------------------------
LOGO_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Waterford-Halfmoon.webp")

st.set_page_config(
    page_title="Waterford-Halfmoon Track & Field",
    page_icon=LOGO_PATH if os.path.exists(LOGO_PATH) else "🏃",
    layout="wide",
    initial_sidebar_state="auto"
)

# Initialize Database Schema & Seed Data
db.init_db()

# Mobile-optimized styling
st.markdown("""
<style>
    /* Responsive card containers */
    .metric-card {
        background-color: #1e293b;
        border: 1px solid #334155;
        border-radius: 10px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .metric-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #94a3b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .metric-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #38bdf8;
        margin-top: 4px;
    }
    .metric-subtitle {
        font-size: 0.8rem;
        color: #cbd5e1;
        margin-top: 2px;
    }
    .badge-pr {
        background-color: #10b981;
        color: #ffffff;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    .badge-sr {
        background-color: #f59e0b;
        color: #ffffff;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 700;
    }
    /* Touch friendly form inputs */
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
        padding: 0.5rem 1rem;
    }
</style>
""", unsafe_allow_html=True)


def render_header(title: str, subtitle: str = ""):
    """Renders an aesthetically pleasing banner header with the Waterford-Halfmoon logo and school colors."""
    col_h_logo, col_h_text = st.columns([1, 7], vertical_alignment="center")
    with col_h_logo:
        if os.path.exists(LOGO_PATH):
            st.image(LOGO_PATH, width=95)
        else:
            st.markdown("<div style='font-size: 3rem;'>🏃</div>", unsafe_allow_html=True)
    with col_h_text:
        st.markdown(f"""
        <div style='display: flex; flex-direction: column; justify-content: center; padding-left: 8px;'>
            <div style='font-size: 0.85rem; font-weight: 700; color: #ef4444; letter-spacing: 0.08em; text-transform: uppercase;'>
                Waterford-Halfmoon Fordians • Track & Field
            </div>
            <h1 style='margin: 0; padding: 2px 0; font-size: 2.1rem; font-weight: 800; color: #f8fafc; line-height: 1.15;'>
                {title}
            </h1>
            <p style='margin: 2px 0 0 0; padding: 0; color: #94a3b8; font-size: 0.95rem; font-weight: 400;'>
                {subtitle}
            </p>
        </div>
        """, unsafe_allow_html=True)
    st.divider()


# ---------------------------------------------------------
# SIDEBAR NAVIGATION & AUTH
# ---------------------------------------------------------
if os.path.exists(LOGO_PATH):
    st.sidebar.image(LOGO_PATH, width=120)
st.sidebar.title("Waterford-Halfmoon")
st.sidebar.caption("Track & Field Performance")

nav_choice = st.sidebar.radio(
    "Navigation",
    [
        "🏃 Athlete Profiles & PRs",
        "🏆 Team Honor Roll & Records",
        "⚔️ Wasaren League Scouting & Comparison",
        "⏱️ Pace & Lap Calculator",
        "🤝 Relay Lineup & Splits",
        "📋 Meet Results Log",
        "🔒 Coach Admin Hub"
    ],
    index=0
)

# Render Authentication in sidebar
auth.render_auth_sidebar()
is_coach = auth.is_coach_authenticated()


# =========================================================
# PAGE 1: ATHLETE PROFILES & PROGRESSION
# =========================================================
if nav_choice == "🏃 Athlete Profiles & PRs":
    render_header("Athlete Profiles & Performance Trends", "Track individual personal records, multi-meet trends, and relay splits.")

    athletes = db.get_all_athletes(active_only=False)
    if not athletes:
        st.warning("No athletes found in the database. Please initialize seed data in the Coach Admin Hub.")
        st.stop()

    # Athlete and Season Selector
    col_ath_sel, col_season_sel = st.columns([3, 2])
    with col_ath_sel:
        ath_labels = {f"{a['last_name']}, {a['first_name']} (Gr. {a['grade_level']}, {a['gender']})": a["id"] for a in athletes}
        selected_label = st.selectbox("Select Athlete", list(ath_labels.keys()), index=0)
        selected_ath_id = ath_labels[selected_label]
        ath = db.get_athlete_by_id(selected_ath_id)
    with col_season_sel:
        season_year_opts = ["ALL"] + db.get_all_season_years()
        selected_season_year = st.selectbox(
            "Filter Season",
            season_year_opts,
            index=0,
            help="Filter to display only events and performances for the selected season (2025-26, 2026-27, ALL)."
        )

    # Athlete Info Banner
    col_info1, col_info2, col_info3, col_info4 = st.columns([2, 1, 1, 1])
    with col_info1:
        grade_desc = {9: "Freshman", 10: "Sophomore", 11: "Junior", 12: "Senior"}.get(ath["grade_level"], f"Grade {ath['grade_level']}")
        st.subheader(f"{ath['first_name']} {ath['last_name']}")
        st.caption(f"{grade_desc} • Age: {ath['age']} • Gender: {'Female' if ath['gender'] == 'F' else 'Male'}")
    with col_info2:
        status_color = "🟢 Active" if ath["active_status"] else "⚪ Inactive"
        st.metric("Roster Status", status_color)
    
    # Query Results filtered by season
    results = db.get_results_by_athlete(selected_ath_id, season_year=selected_season_year)
    relay_splits = db.get_relay_splits_by_athlete(selected_ath_id)
    if selected_season_year != "ALL":
        relay_splits = [rs for rs in relay_splits if db.get_school_year(rs["meet_date"]) == selected_season_year]
    pr_map = db.get_athlete_pr_map(selected_ath_id, season_year=selected_season_year)

    with col_info3:
        st.metric("Events Logged", len(results))
    with col_info4:
        pr_label = "Season Bests" if selected_season_year != "ALL" else "PRs Achieved"
        st.metric(pr_label, len(pr_map))

    st.markdown("---")

    # PR / Season Best Showcase
    title_suffix = f" — {selected_season_year} Season" if selected_season_year != "ALL" else " (Career All-Time)"
    st.markdown(f"### 🥇 {'Season Best Marks (SB)' if selected_season_year != 'ALL' else 'Personal Records (PR)'}{title_suffix}")
    if pr_map:
        pr_cards = []
        for eid, pr_info in pr_map.items():
            ev = db.get_event_by_id(eid)
            if ev:
                formatted_mark = db.format_result_display(ev["event_type"], pr_info["pr_value"])
                pr_cards.append({
                    "Season": ev["season"],
                    "Event": ev["event_name"],
                    "Best Mark": formatted_mark,
                    "Meet": pr_info["meet_name"],
                    "Date": pr_info["date"]
                })
        pr_df = pd.DataFrame(pr_cards)
        st.dataframe(pr_df, use_container_width=True, hide_index=True)
    else:
        st.info(f"No individual marks logged for this athlete in the {selected_season_year} season.")

    # Performance Progression Charts
    if results:
        st.markdown(f"### 📈 Performance Progression Over Time{title_suffix}")
        
        # Unique events for this athlete in the selected season
        athlete_events = sorted(list({r["event_name"] for r in results}))
        selected_event_name = st.selectbox(
            f"Select Event to Chart ({len(athlete_events)} event{'s' if len(athlete_events) != 1 else ''} in {selected_season_year})",
            athlete_events
        )

        event_results = [r for r in results if r["event_name"] == selected_event_name]
        event_meta = event_results[0]
        event_type = event_meta["event_type"]
        sort_order = event_meta["sort_order"]

        chart_data = []
        best_so_far = None
        for r in event_results:
            val = r["result_value"]
            # Track if PR
            is_pr = False
            if best_so_far is None:
                is_pr = True
                best_so_far = val
            else:
                if (sort_order == "ASC" and val < best_so_far) or (sort_order == "DESC" and val > best_so_far):
                    is_pr = True
                    best_so_far = val
            
            display_mark = db.format_result_display(event_type, val)
            chart_data.append({
                "Date": r["meet_date"],
                "Value": val,
                "Display Mark": display_mark,
                "Meet": r["meet_name"],
                "Timing": r["timing_method"],
                "Official": "Official Meet" if r["is_official"] else "Practice / Time Trial",
                "Is_PR": is_pr,
                "Notes": r["notes"] or ""
            })
        
        cdf = pd.DataFrame(chart_data)

        # Plotly chart
        fig = go.Figure()

        # Progression Line
        fig.add_trace(go.Scatter(
            x=cdf["Date"],
            y=cdf["Value"],
            mode="lines+markers",
            name="Performance",
            line=dict(color="#38bdf8", width=3),
            marker=dict(size=9, color="#0284c7"),
            text=cdf.apply(lambda row: f"<b>{row['Display Mark']}</b><br>{row['Meet']}<br>{row['Timing']} ({row['Official']})<br>{row['Notes']}", axis=1),
            hoverinfo="text"
        ))

        # Highlight PRs with star markers
        pr_rows = cdf[cdf["Is_PR"] == True]
        if not pr_rows.empty:
            fig.add_trace(go.Scatter(
                x=pr_rows["Date"],
                y=pr_rows["Value"],
                mode="markers",
                name="New PR Mark",
                marker=dict(size=14, color="#10b981", symbol="star"),
                text=pr_rows.apply(lambda row: f"⭐ <b>PR: {row['Display Mark']}</b><br>{row['Meet']}", axis=1),
                hoverinfo="text"
            ))

        # Check for standards (School Record or Sectional) to draw reference line
        standards = db.get_standards(event_id=event_meta["event_id"], gender=ath["gender"])
        for s in standards:
            line_color = "#f59e0b" if "Record" in s["standard_name"] else "#a855f7"
            fig.add_hline(
                y=s["standard_value"],
                line_dash="dash",
                line_color=line_color,
                annotation_text=f"{s['standard_name']}: {db.format_result_display(event_type, s['standard_value'])}",
                annotation_position="bottom right"
            )

        fig.update_layout(
            title=f"{ath['first_name']} {ath['last_name']} - {selected_event_name} Trend",
            xaxis_title="Meet Date",
            template="plotly_dark",
            margin=dict(l=50, r=40, t=50, b=40),
            hovermode="closest",
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )

        # Custom Y-Axis tick formatting in minutes & seconds (or feet & inches for field)
        all_vals = list(cdf["Value"])
        for s in standards:
            all_vals.append(s["standard_value"])
        min_val = min(all_vals)
        max_val = max(all_vals)
        span = max(max_val - min_val, 0.4)

        if event_type in ("Track", "Relay"):
            if max_val >= 60:
                # Distance events (>= 1 min): Format ticks as mm:ss
                candidates = [1, 2, 5, 10, 15, 30, 60, 120]
                step = min(candidates, key=lambda c: abs(c - span / 6))
                start_tick = math.floor(min_val / step) * step
                end_tick = math.ceil(max_val / step) * step
                num_ticks = max(int(round((end_tick - start_tick) / step)) + 1, 2)
                tickvals = [start_tick + i * step for i in range(num_ticks)]

                def fmt_track_axis(sec):
                    mins = int(sec // 60)
                    rem = sec % 60
                    if step >= 1 and abs(rem - round(rem)) < 0.01:
                        return f"{mins}:{int(round(rem)):02d}"
                    return f"{mins}:{rem:05.2f}"

                ticktext = [fmt_track_axis(t) for t in tickvals]
                fig.update_yaxes(
                    tickvals=tickvals,
                    ticktext=ticktext,
                    autorange="reversed",
                    title_text="Time (Minutes:Seconds — Faster ↑)"
                )
            else:
                # Sprint events (< 60s): Format ticks as seconds
                candidates = [0.05, 0.1, 0.2, 0.5, 1.0, 2.0]
                step = min(candidates, key=lambda c: abs(c - span / 6))
                start_tick = math.floor(min_val / step) * step
                end_tick = math.ceil(max_val / step) * step
                num_ticks = max(int(round((end_tick - start_tick) / step)) + 1, 2)
                tickvals = [round(start_tick + i * step, 3) for i in range(num_ticks)]
                ticktext = [f"{t:.2f}s" if step < 1 else f"{t:.1f}s" for t in tickvals]
                fig.update_yaxes(
                    tickvals=tickvals,
                    ticktext=ticktext,
                    autorange="reversed",
                    title_text="Time (Seconds — Faster ↑)"
                )
        else:
            # Field events: Format ticks with Imperial feet & inches
            candidates = [0.1, 0.25, 0.5, 1.0, 2.0]
            step = min(candidates, key=lambda c: abs(c - span / 6))
            start_tick = math.floor(min_val / step) * step
            end_tick = math.ceil(max_val / step) * step
            num_ticks = max(int(round((end_tick - start_tick) / step)) + 1, 2)
            tickvals = [round(start_tick + i * step, 3) for i in range(num_ticks)]
            ticktext = [f"{db.meters_to_feet_inches(t)} ({t:.2f}m)" for t in tickvals]
            fig.update_yaxes(
                tickvals=tickvals,
                ticktext=ticktext,
                title_text="Distance (Feet & Inches — Higher ↑)"
            )

        st.plotly_chart(fig, use_container_width=True, config={"responsive": True, "displayModeBar": False})
    else:
        st.info(f"ℹ️ No meet performances recorded for **{ath['first_name']} {ath['last_name']}** during the **{selected_season_year}** season. Select another season or 'ALL' to view career progression.")

    # Relay Splits History
    if relay_splits:
        st.markdown("### 🤝 Relay Split Performances")
        st.caption("Individual leg splits recorded across team relays.")
        splits_list = []
        for rs in relay_splits:
            splits_list.append({
                "Date": rs["meet_date"],
                "Meet": rs["meet_name"],
                "Relay Event": rs["event_name"],
                "Leg #": f"Leg {rs['leg_number']}",
                "Split Time": db.format_time(rs["split_seconds"]),
                "Team Total": db.format_time(rs["total_time_seconds"]),
                "Notes": rs["notes"] or ""
            })
        st.dataframe(pd.DataFrame(splits_list), use_container_width=True, hide_index=True)

    # Complete History Log
    with st.expander("📜 View Complete Results History Log", expanded=False):
        all_hist = []
        for r in results:
            all_hist.append({
                "Date": r["meet_date"],
                "Meet": r["meet_name"],
                "Season": r["season"],
                "Event": r["event_name"],
                "Mark": db.format_result_display(r["event_type"], r["result_value"]),
                "Timing": r["timing_method"],
                "Type": "Official" if r["is_official"] else "Practice/TT",
                "Notes": r["notes"] or ""
            })
        st.dataframe(pd.DataFrame(all_hist), use_container_width=True, hide_index=True)


# =========================================================
# PAGE 2: TEAM HONOR ROLL & RECORDS
# =========================================================
elif nav_choice == "🏆 Team Honor Roll & Records":
    render_header("Team Honor Roll & Records", "All-time team rankings, current season leaders, and championship standards.")

    col_flt1, col_flt2, col_flt3, col_flt4 = st.columns([1, 1, 1, 1])
    with col_flt1:
        season_filter = st.selectbox("Season Track", ["Outdoor", "Indoor"], index=0)
    with col_flt2:
        season_year_opts = ["ALL"] + db.get_all_season_years()
        selected_season_year = st.selectbox("Season Year", season_year_opts, index=0)
    with col_flt3:
        gender_filter = st.selectbox("Gender", ["F", "M"], format_func=lambda x: "Girls (F)" if x == "F" else "Boys (M)")
    
    events = db.get_all_events(season=season_filter)
    # Exclude Relay events from individual leaderboard
    indiv_events = [e for e in events if e["event_type"] != "Relay"]
    with col_flt4:
        ev_options = {e["event_name"]: e["id"] for e in indiv_events}
        selected_ev_name = st.selectbox("Event", list(ev_options.keys()))
        selected_ev_id = ev_options[selected_ev_name]
    
    target_event = db.get_event_by_id(selected_ev_id)

    # Leaderboard Table filtered by season year
    leaderboard = db.get_event_leaderboard(selected_ev_id, gender=gender_filter, limit=10, season_year=selected_season_year)

    # Standards for this event
    standards = db.get_standards(event_id=selected_ev_id, gender=gender_filter)
    record_mark = None
    sec2_mark = None
    state_mark = None
    for s in standards:
        if "School Record" in s["standard_name"]:
            record_mark = s["standard_value"]
        elif "Section 2" in s["standard_name"]:
            sec2_mark = s["standard_value"]
        elif "State" in s["standard_name"]:
            state_mark = s["standard_value"]

    # Top Metric Banner
    col_rec1, col_rec2, col_rec3 = st.columns(3)
    with col_rec1:
        disp_rec = db.format_result_display(target_event["event_type"], record_mark) if record_mark else "None Set"
        st.metric("School Record", disp_rec)
    with col_rec2:
        disp_sec2 = db.format_result_display(target_event["event_type"], sec2_mark) if sec2_mark else "None Set"
        st.metric("Section 2 Standard", disp_sec2)
    with col_rec3:
        leader_label = "Season Leader" if selected_season_year != "ALL" else "All-Time Leader"
        team_leader = leaderboard[0]["first_name"] + " " + leaderboard[0]["last_name"] if leaderboard else "None"
        team_leader_mark = db.format_result_display(target_event["event_type"], leaderboard[0]["best_mark"]) if leaderboard else "--"
        st.metric(leader_label, team_leader, team_leader_mark)

    st.markdown("---")
    board_title = f"Top 10 All-Time: {selected_ev_name}" if selected_season_year == "ALL" else f"Top 10 Leaders ({selected_season_year}): {selected_ev_name}"
    st.subheader(f"{board_title} ({'Girls' if gender_filter == 'F' else 'Boys'})")

    if leaderboard:
        board_rows = []
        for rank, r in enumerate(leaderboard, start=1):
            mark_str = db.format_result_display(target_event["event_type"], r["best_mark"])
            board_rows.append({
                "Rank": f"#{rank}",
                "Athlete": f"{r['first_name']} {r['last_name']}",
                "Grade": f"Gr. {r['grade_level']}",
                "Best Mark": mark_str,
                "Timing": r["timing_method"],
                "Meet": r["meet_name"],
                "Date": r["meet_date"],
                "Venue": r["venue_name"]
            })
        st.dataframe(pd.DataFrame(board_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No official performances recorded yet for this event and gender.")

    # Championship Qualification Standards Status
    if standards and leaderboard:
        st.markdown("### 🎯 Championship Standards Proximity")
        st.caption("How team leaders compare against championship qualifying benchmarks.")
        for s in standards:
            s_val = s["standard_value"]
            s_disp = db.format_result_display(target_event["event_type"], s_val)
            st.markdown(f"**{s['standard_name']} Target:** `{s_disp}`")
            for leader in leaderboard[:3]:
                l_val = leader["best_mark"]
                l_name = f"{leader['first_name']} {leader['last_name']}"
                l_disp = db.format_result_display(target_event["event_type"], l_val)
                
                # Check percentage
                if target_event["sort_order"] == "ASC": # Lower is better
                    # If l_val <= s_val, 100%+ qualified
                    pct = min(100.0, (s_val / l_val) * 100)
                    qualified = l_val <= s_val
                else: # Higher is better
                    pct = min(100.0, (l_val / s_val) * 100)
                    qualified = l_val >= s_val
                
                status_txt = "✅ **QUALIFIED!**" if qualified else f"{pct:.1f}% of Standard"
                st.write(f"- {l_name}: **{l_disp}** — {status_txt}")


# =========================================================
# PAGE: WASAREN LEAGUE SCOUTING & COMPARISON
# =========================================================
elif nav_choice == "⚔️ Wasaren League Scouting & Comparison":
    render_header(
        "Wasaren League Scouting & Championship Comparison",
        "Compare Waterford marks against top marks from rival Wasaren League schools: Cambridge, Greenwich, Hoosic Valley, Hoosick Falls, Mechanicville, Saratoga Catholic, Stillwater, and Tamarac."
    )

    # Check if league marks exist
    summary = db.get_wasaren_schools_summary()
    total_league_marks = sum(s["total_marks"] for s in summary) if summary else 0

    if total_league_marks == 0:
        st.warning("⚠️ No Wasaren League rival marks found in the local database.")
        st.info("Click the button below to fetch current season marks from MileSplit for all 8 Wasaren League rivals + Waterford-Halfmoon.")
        if st.button("🔄 Sync Wasaren League Marks from MileSplit", type="primary", use_container_width=True):
            with st.spinner("Connecting to MileSplit and extracting marks for all 9 Wasaren schools..."):
                active_sess = st.session_state.get("ms_pro_session")
                res = ms.sync_wasaren_league_marks(session=active_sess)
                st.success(f"🎉 Successfully synced {res['total_synced']} marks across {res['schools_synced']} Wasaren League schools!")
                st.rerun()
        st.stop()

    # Top Filter Bar
    col_sy, col_season, col_gender = st.columns(3)
    with col_sy:
        sy_opts = ["ALL"] + db.get_wasaren_season_years()
        default_sy_idx = 1 if len(sy_opts) > 1 and "2025-26" in sy_opts else 0
        selected_sy = st.selectbox("Academic Year", sy_opts, index=default_sy_idx, key="wasaren_sy")
    with col_season:
        season_filter = st.selectbox("Season", ["Outdoor", "Indoor", "Both"], index=0, key="wasaren_season")
    with col_gender:
        gender_filter = st.selectbox("Division / Gender", ["Boys (M)", "Girls (F)", "All"], index=0, key="wasaren_gender")
        gender_code = "M" if "Boys" in gender_filter else ("F" if "Girls" in gender_filter else "All")

    # Navigation Tabs
    scout_tab1, scout_tab2, scout_tab3, scout_tab4 = st.tabs([
        "🏆 Event Head-to-Head & Leaderboard",
        "📊 Virtual Championship Meet (Team Scoring)",
        "🎯 Waterford Medal & Scoring Contenders",
        "🏫 School Profiles & Coverage"
    ])

    # -----------------------------------------------------
    # TAB 1: EVENT HEAD-TO-HEAD LEADERBOARDS
    # -----------------------------------------------------
    with scout_tab1:
        st.subheader("Event Head-to-Head Leaderboards")
        st.caption(f"Filtered by: Season = **{season_filter}**, Academic Year = **{selected_sy}**, Division = **{gender_filter}**")

        avail_events = db.get_wasaren_events(season=season_filter, season_year=selected_sy, gender=gender_code)
        if not avail_events:
            st.warning(f"No events found for {season_filter} ({selected_sy}, {gender_filter}). Try adjusting filters above.")
        else:
            selected_event_name = st.selectbox("Select Track & Field Event", avail_events, index=0, key="wasaren_event_sel")
            leaderboard = db.get_wasaren_league_leaderboard(
                selected_event_name,
                season=season_filter,
                season_year=selected_sy,
                gender=gender_code,
                limit=50
            )

            if not leaderboard:
                st.info("No marks logged for this event under the current filters.")
            else:
                # Top Summary Metric Cards
                ev_type = leaderboard[0]["event_type"]
                leader = leaderboard[0]
                wat_entries = [r for r in leaderboard if r["is_waterford"]]
                top_wat = wat_entries[0] if wat_entries else None
                podium_cutoff = leaderboard[2] if len(leaderboard) >= 3 else None
                scoring_cutoff = leaderboard[5] if len(leaderboard) >= 6 else None

                col_m1, col_m2, col_m3, col_m4 = st.columns(4)
                with col_m1:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">🥇 League Leader (#1)</div>
                        <div class="metric-value">{leader['mark_display']}</div>
                        <div style="font-size:0.8rem; color:#94a3b8; margin-top:2px;">{leader['athlete_name']} ({leader['school_name']})</div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_m2:
                    if top_wat:
                        wat_rank_disp = f"#{top_wat['rank']} in League"
                        wat_gap_disp = f"Gap: {top_wat['gap']}"
                        wat_val_disp = top_wat['mark_display']
                        wat_ath_disp = top_wat['athlete_name']
                    else:
                        wat_rank_disp = "Not Ranked"
                        wat_gap_disp = "No mark logged"
                        wat_val_disp = "--"
                        wat_ath_disp = "Waterford-Halfmoon"
                    st.markdown(f"""
                    <div class="metric-card" style="border-left: 4px solid #ef4444;">
                        <div class="metric-label" style="color:#ef4444;">🔴 Waterford Top Mark</div>
                        <div class="metric-value">{wat_val_disp}</div>
                        <div style="font-size:0.8rem; color:#94a3b8; margin-top:2px;">{wat_ath_disp} • <b>{wat_rank_disp}</b> ({wat_gap_disp})</div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_m3:
                    bronze_disp = podium_cutoff['mark_display'] if podium_cutoff else "--"
                    bronze_ath = f"#{podium_cutoff['rank']} {podium_cutoff['school_name']}" if podium_cutoff else "Open"
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">🥉 Podium Cutoff (3rd Place)</div>
                        <div class="metric-value">{bronze_disp}</div>
                        <div style="font-size:0.8rem; color:#94a3b8; margin-top:2px;">{bronze_ath}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_m4:
                    pts_disp = scoring_cutoff['mark_display'] if scoring_cutoff else "--"
                    pts_ath = f"#{scoring_cutoff['rank']} {scoring_cutoff['school_name']}" if scoring_cutoff else "Open"
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-label">⭐ Scoring Cutoff (6th Place)</div>
                        <div class="metric-value">{pts_disp}</div>
                        <div style="font-size:0.8rem; color:#94a3b8; margin-top:2px;">{pts_ath}</div>
                    </div>
                    """, unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                # School Head-to-Head Comparison Chart (Top Mark Per School)
                school_bests = {}
                is_track_ev = (ev_type in ("Track", "Relay"))
                for row in leaderboard:
                    s_name = row["school_name"]
                    if s_name not in school_bests:
                        school_bests[s_name] = row

                chart_data = list(school_bests.values())
                # Sort schools best-to-worst
                if is_track_ev:
                    chart_data = sorted(chart_data, key=lambda x: x["best_value"])
                else:
                    chart_data = sorted(chart_data, key=lambda x: x["best_value"], reverse=True)

                c_schools = [d["school_name"] for d in chart_data]
                c_marks = [d["mark_display"] for d in chart_data]
                c_values = [d["best_value"] for d in chart_data]
                c_athletes = [d["athlete_name"] for d in chart_data]
                c_colors = ["#b91c1c" if d["is_waterford"] else "#475569" for d in chart_data]

                fig_h2h = go.Figure(go.Bar(
                    x=c_values,
                    y=c_schools,
                    orientation='h',
                    marker_color=c_colors,
                    text=c_marks,
                    textposition='auto',
                    customdata=c_athletes,
                    hovertemplate='<b>%{y}</b><br>Athlete: %{customdata}<br>Mark: %{text}<extra></extra>'
                ))

                fig_h2h.update_layout(
                    title=f"School Season Bests: {selected_event_name} ({season_filter})",
                    plot_bgcolor="rgba(15, 23, 42, 0.6)",
                    paper_bgcolor="rgba(15, 23, 42, 0.0)",
                    font=dict(color="#f8fafc"),
                    xaxis=dict(
                        title="Time in Seconds" if is_track_ev else "Distance / Height in Meters",
                        autorange="reversed" if is_track_ev else True,
                        showgrid=True,
                        gridcolor="#334155"
                    ),
                    yaxis=dict(
                        autorange="reversed",
                        showgrid=False
                    ),
                    height=max(280, len(c_schools) * 40 + 80),
                    margin=dict(l=10, r=20, t=40, b=30)
                )
                st.plotly_chart(fig_h2h, use_container_width=True)

                # Full Interactive Leaderboard Table
                st.markdown("#### Full Wasaren League Rankings")
                table_rows = []
                for row in leaderboard:
                    is_wat = row["is_waterford"]
                    school_badge = f"🔴 **{row['school_name']}**" if is_wat else row["school_name"]
                    ath_badge = f"**{row['athlete_name']}**" if is_wat else row["athlete_name"]
                    table_rows.append({
                        "Rank": f"#{row['rank']}",
                        "Athlete": ath_badge,
                        "School": school_badge,
                        "Mark": row["mark_display"],
                        "Gap to #1": row["gap"],
                        "Meet": row.get("meet_name") or "--",
                        "Date": row.get("meet_date") or "--"
                    })

                df_lb = pd.DataFrame(table_rows)
                st.dataframe(df_lb, use_container_width=True, hide_index=True)

    # -----------------------------------------------------
    # TAB 2: VIRTUAL CHAMPIONSHIP MEET SCORING
    # -----------------------------------------------------
    with scout_tab2:
        st.subheader("Wasaren League Championship Simulator")
        st.markdown("""
        > **Scoring Rules:** Standard NY Section 2 Championship meet scoring: **10-8-6-4-2-1** points awarded to the top 6 league finishers in each event.
        > In accordance with championship regulations, maximum 2 scoring athletes per team in individual events (1 per relay).
        """)

        scores = db.get_wasaren_virtual_meet_scores(season=season_filter, season_year=selected_sy, gender=gender_code)
        if not scores:
            st.warning("No scoring events found for the selected season and division.")
        else:
            # Metrics
            champ = scores[0]
            wat_score = next((s for s in scores if s["is_waterford"]), None)

            c_sc1, c_sc2, c_sc3, c_sc4 = st.columns(4)
            with c_sc1:
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">🏆 Projected Champion</div>
                    <div class="metric-value" style="font-size:1.4rem;">{champ['school_name']}</div>
                    <div style="font-size:0.8rem; color:#94a3b8; margin-top:2px;"><b>{champ['total_points']} pts</b> ({champ['gold_medals']} Golds)</div>
                </div>
                """, unsafe_allow_html=True)
            with c_sc2:
                if wat_score:
                    st.markdown(f"""
                    <div class="metric-card" style="border-left: 4px solid #ef4444;">
                        <div class="metric-label" style="color:#ef4444;">🔴 Waterford Standings</div>
                        <div class="metric-value">#{wat_score['rank']} of {len(scores)}</div>
                        <div style="font-size:0.8rem; color:#94a3b8; margin-top:2px;"><b>{wat_score['total_points']} Points</b> Projected</div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.markdown("""
                    <div class="metric-card">
                        <div class="metric-label">🔴 Waterford Standings</div>
                        <div class="metric-value">0 pts</div>
                        <div style="font-size:0.8rem; color:#94a3b8;">No scorers logged</div>
                    </div>
                    """, unsafe_allow_html=True)
            with c_sc3:
                wat_golds = wat_score['gold_medals'] if wat_score else 0
                wat_silvers = wat_score['silver_medals'] if wat_score else 0
                wat_bronzes = wat_score['bronze_medals'] if wat_score else 0
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">🥇 Top-3 Medal Finishes</div>
                    <div class="metric-value">{wat_golds + wat_silvers + wat_bronzes}</div>
                    <div style="font-size:0.8rem; color:#94a3b8; margin-top:2px;">{wat_golds} 🥇 • {wat_silvers} 🥈 • {wat_bronzes} 🥉</div>
                </div>
                """, unsafe_allow_html=True)
            with c_sc4:
                wat_scorers = wat_score['scoring_finishes'] if wat_score else 0
                st.markdown(f"""
                <div class="metric-card">
                    <div class="metric-label">⭐ Total Scoring Finishes</div>
                    <div class="metric-value">{wat_scorers}</div>
                    <div style="font-size:0.8rem; color:#94a3b8; margin-top:2px;">Top 6 League Performances</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # Virtual Standings Bar Chart
            s_names = [s["school_name"] for s in scores]
            s_pts = [s["total_points"] for s in scores]
            s_colors = ["#b91c1c" if s["is_waterford"] else "#475569" for s in scores]

            fig_scores = go.Figure(go.Bar(
                x=s_pts,
                y=s_names,
                orientation='h',
                marker_color=s_colors,
                text=[f"{p} pts" for p in s_pts],
                textposition='auto',
                hovertemplate='<b>%{y}</b><br>Projected Points: %{x}<extra></extra>'
            ))
            fig_scores.update_layout(
                title=f"Virtual Meet Team Scores: Wasaren League ({season_filter}, {gender_filter})",
                plot_bgcolor="rgba(15, 23, 42, 0.6)",
                paper_bgcolor="rgba(15, 23, 42, 0.0)",
                font=dict(color="#f8fafc"),
                xaxis=dict(title="Total Projected Team Points", showgrid=True, gridcolor="#334155"),
                yaxis=dict(autorange="reversed", showgrid=False),
                height=max(280, len(scores) * 42 + 80),
                margin=dict(l=10, r=20, t=40, b=30)
            )
            st.plotly_chart(fig_scores, use_container_width=True)

            # Standings Table
            st.markdown("#### Championship Points Table")
            score_table = []
            for s in scores:
                is_wat = s["is_waterford"]
                school_str = f"🔴 **{s['school_name']}**" if is_wat else s["school_name"]
                pts_str = f"**{s['total_points']} pts**" if is_wat else f"{s['total_points']} pts"
                score_table.append({
                    "Rank": f"#{s['rank']}",
                    "School": school_str,
                    "Total Points": pts_str,
                    "🥇 Gold (1st)": s["gold_medals"],
                    "🥈 Silver (2nd)": s["silver_medals"],
                    "🥉 Bronze (3rd)": s["bronze_medals"],
                    "⭐ Scoring Finishes": s["scoring_finishes"]
                })
            st.dataframe(pd.DataFrame(score_table), use_container_width=True, hide_index=True)

    # -----------------------------------------------------
    # TAB 3: WATERFORD MEDAL & SCORING CONTENDERS
    # -----------------------------------------------------
    with scout_tab3:
        st.subheader("Waterford-Halfmoon Medal & Scoring Contenders")
        st.caption(f"Athletes currently holding top 8 ranking marks in the Wasaren League ({season_filter}, {selected_sy}, {gender_filter})")

        contenders = db.get_wasaren_waterford_contenders(season=season_filter, season_year=selected_sy, gender=gender_code)

        if not contenders:
            st.info("No Waterford athletes currently ranked in the top 8 for this category. Adjust filters or sync new meet results.")
        else:
            golds = [c for c in contenders if c["rank"] == 1]
            silvers = [c for c in contenders if c["rank"] == 2]
            bronzes = [c for c in contenders if c["rank"] == 3]
            top6 = [c for c in contenders if c["rank"] <= 6]
            bubble = [c for c in contenders if c["rank"] > 6]

            st.write(
                f"**{len(top6)}** Waterford performances are currently in scoring position (Top 6), "
                f"with **{len(golds) + len(silvers) + len(bronzes)}** in podium contention and "
                f"**{len(bubble)}** on the scoring bubble (7th-8th)."
            )

            c_table = []
            for c in contenders:
                c_table.append({
                    "Event": c["event_name"],
                    "Athlete": c["athlete_name"],
                    "Wasaren Rank": f"#{c['rank']}",
                    "Mark": c["mark_display"],
                    "Status": c["status"],
                    "Gap to #1": c["gap"],
                    "Projected Points": f"+{c['projected_points']} pts" if c["projected_points"] > 0 else "0 pts",
                    "Meet": c.get("meet_name") or "--"
                })

            st.dataframe(pd.DataFrame(c_table), use_container_width=True, hide_index=True)

    # -----------------------------------------------------
    # TAB 4: SCHOOL PROFILES & COVERAGE
    # -----------------------------------------------------
    with scout_tab4:
        st.subheader("Wasaren League Coverage & Sync Overview")
        st.caption("Active schools and mark counts currently tracked in the Waterford Track & Field scouting database.")

        summary_data = db.get_wasaren_schools_summary()
        sum_table = []
        for s in summary_data:
            is_wat = bool("waterford" in s["school_name"].lower())
            sum_table.append({
                "School": f"🔴 **{s['school_name']}**" if is_wat else s["school_name"],
                "Season Best Marks": s["total_marks"],
                "Events Covered": s["events_covered"],
                "Athletes Logged": s["athletes_count"],
                "Latest Meet Date": s["latest_meet_date"] or "--"
            })
        st.dataframe(pd.DataFrame(sum_table), use_container_width=True, hide_index=True)

        st.markdown("---")
        col_ref1, col_ref2 = st.columns([2, 1])
        with col_ref1:
            st.markdown("#### Refresh League Data from MileSplit")
            st.write("Fetch updated marks for all Wasaren League schools (Cambridge, Greenwich, Hoosic Valley, Hoosick Falls, Mechanicville, Saratoga Catholic, Stillwater, Tamarac, Waterford).")
        with col_ref2:
            if st.button("🔄 Refresh League Marks", type="primary", use_container_width=True):
                with st.spinner("Updating league marks from MileSplit..."):
                    active_sess = st.session_state.get("ms_pro_session")
                    res = ms.sync_wasaren_league_marks(session=active_sess)
                    st.success(f"🎉 Updated {res['total_synced']} marks across {res['schools_synced']} schools!")
                    st.rerun()


# =========================================================
# PAGE 3: PACE & LAP CALCULATOR
# =========================================================
elif nav_choice == "⏱️ Pace & Lap Calculator":
    render_header("Pace & Lap Calculator", "Plan race splits and generate clipboard-ready lap target tables for any track venue.")

    col_p1, col_p2, col_p3 = st.columns(3)
    with col_p1:
        venues = db.get_all_venues()
        venue_options = {}
        for v in venues:
            dist_disp = f"{v['lap_distance_meters']:.2f}".rstrip('0').rstrip('.')
            venue_options[f"{v['name']} ({dist_disp}m lap - {v['season']})"] = v
        selected_v_label = st.selectbox("Track Venue", list(venue_options.keys()), index=0)
        selected_venue = venue_options[selected_v_label]
        lap_dist = selected_venue["lap_distance_meters"]

    with col_p2:
        dist_options = [400, 600, 800, 1000, 1500, 1600, 3000, 3200]
        selected_dist = st.selectbox("Race Distance (meters)", dist_options, index=5) # 1600m default

    with col_p3:
        target_time_input = st.text_input("Target Finish Time (e.g. 4:48.00 or 52.5)", value="4:48.00")

    target_seconds = db.parse_time(target_time_input)

    if not target_seconds or target_seconds <= 0:
        st.error("Please enter a valid target time in format 'mm:ss.xx' or 'ss.xx'.")
    else:
        # Pacing Calculations
        total_laps = selected_dist / lap_dist
        pace_per_lap = target_seconds / total_laps
        pace_per_100 = target_seconds / (selected_dist / 100.0)
        pace_per_400 = pace_per_100 * 4.0

        st.markdown("### 📊 Pacing Summary")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st.metric("Total Laps", f"{total_laps:.2f} Laps")
        with col_m2:
            lap_disp = f"{lap_dist:.2f}".rstrip('0').rstrip('.')
            st.metric(f"Pace / {lap_disp}m Lap", db.format_time(pace_per_lap))
        with col_m3:
            st.metric("Pace / 100m", f"{pace_per_100:.2f}s")
        with col_m4:
            st.metric("400m Equivalent", db.format_time(pace_per_400))

        st.markdown("---")
        st.subheader("📋 Clipboard Lap Split Breakdown (Stopwatch Targets)")
        st.caption(f"Cumulative watch splits at **{selected_venue['name']}** to execute a **{db.format_time(target_seconds)}** finish.")

        lap_rows = []
        full_laps = int(total_laps)
        has_partial = (total_laps - full_laps) > 0.001

        cum_dist = 0.0
        cum_time = 0.0
        for l in range(1, full_laps + 1):
            cum_dist += lap_dist
            cum_time = l * pace_per_lap
            lap_rows.append({
                "Lap #": f"Lap {l}",
                "Split Distance": f"{cum_dist:.0f}m",
                "Lap Split": db.format_time(pace_per_lap),
                "Stopwatch (Cumulative)": db.format_time(cum_time),
                "Pace Notes": "Target split"
            })
        
        if has_partial:
            rem_dist = selected_dist - cum_dist
            rem_time = target_seconds - cum_time
            lap_rows.append({
                "Lap #": f"Final Kick ({rem_dist:.0f}m)",
                "Split Distance": f"{selected_dist:.0f}m",
                "Lap Split": db.format_time(rem_time),
                "Stopwatch (Cumulative)": db.format_time(target_seconds),
                "Pace Notes": "Finish line kick"
            })

        lap_df = pd.DataFrame(lap_rows)
        st.dataframe(lap_df, use_container_width=True, hide_index=True)

        # Race Strategy Pacing Guide
        with st.expander("💡 Pacing Strategy Presets (Even vs Negative Split)", expanded=False):
            st.write("""
            - **Even Pacing:** Maintaining the exact lap average above has been shown to produce the fastest physiological energy efficiency for 800m through 3200m.
            - **High School 800m Model:** First 200m should be ~1-2s faster than average pace to establish lane positioning, settling into target split by 400m.
            - **Negative Split (Distance):** Aim for 51% of total time over the first half and 49% over the second half for a lethal finish.
            """)


# =========================================================
# PAGE 4: RELAY LINEUP BUILDER & SPLITS
# =========================================================
elif nav_choice == "🤝 Relay Lineup & Splits":
    render_header("Relay Lineup & Splits", "Construct relay squads, simulate projected team times, and review past relay performances.")

    tab_builder, tab_history = st.tabs(["⚡ Relay Lineup Simulator", "📜 Historical Relays & Splits"])

    with tab_builder:
        st.subheader("Simulate 4-Runner Relay Squad")
        col_re1, col_re2 = st.columns(2)
        with col_re1:
            relay_events = db.get_all_events(event_type="Relay")
            rel_options = {f"{r['season']} {r['event_name']}": r for r in relay_events}
            selected_r_label = st.selectbox("Select Relay Event", list(rel_options.keys()))
            target_relay = rel_options[selected_r_label]
        
        with col_re2:
            gender_select = st.selectbox("Squad Gender", ["Girls", "Boys"], index=0)
            gender_code = "F" if gender_select == "Girls" else "M"

        # Filter athletes
        active_athletes = [a for a in db.get_all_athletes(active_only=True) if a["gender"] == gender_code]
        if len(active_athletes) < 4:
            st.warning("At least 4 active athletes of this gender are required to assemble a relay team.")
        else:
            ath_options = {f"{a['first_name']} {a['last_name']} (Gr. {a['grade_level']})": a["id"] for a in active_athletes}
            
            st.markdown("#### Assign Runners (Legs 1 - 4)")
            col_l1, col_l2, col_l3, col_l4 = st.columns(4)
            ath_keys = list(ath_options.keys())
            with col_l1:
                leg1_label = st.selectbox("Leg 1 (Lead-off)", ath_keys, index=0)
                leg1_id = ath_options[leg1_label]
            with col_l2:
                leg2_label = st.selectbox("Leg 2", ath_keys, index=min(1, len(ath_keys)-1))
                leg2_id = ath_options[leg2_label]
            with col_l3:
                leg3_label = st.selectbox("Leg 3", ath_keys, index=min(2, len(ath_keys)-1))
                leg3_id = ath_options[leg3_label]
            with col_l4:
                leg4_label = st.selectbox("Leg 4 (Anchor)", ath_keys, index=min(3, len(ath_keys)-1))
                leg4_id = ath_options[leg4_label]

            # Estimate splits
            # Leg 1 is blocks (no running start). Legs 2-4 get standard 0.5s running start discount.
            legs_selected = [(1, leg1_id, leg1_label), (2, leg2_id, leg2_label), (3, leg3_id, leg3_label), (4, leg4_id, leg4_label)]
            
            # Estimate base split from individual PRs or relay split history
            projected_splits = []
            for leg_num, aid, aname in legs_selected:
                # Check if athlete has logged relay splits for this event
                past_splits = [s["split_seconds"] for s in db.get_relay_splits_by_athlete(aid) if s["event_name"] == target_relay["event_name"] and s["split_seconds"]]
                if past_splits:
                    est = min(past_splits)
                    basis = "Best Relay Split"
                else:
                    # Estimate based on individual equivalent distance
                    pr_map = db.get_athlete_pr_map(aid)
                    # For 4x100 -> 100m, 4x400 -> 400m, 4x800 -> 800m
                    leg_dist = target_relay["distance_meters"] / 4.0 if target_relay["distance_meters"] else 100.0
                    # Match event by distance
                    matched_evs = [e for e in db.get_all_events() if e["distance_meters"] == leg_dist and e["event_type"] == "Track" and e["id"] in pr_map]
                    if matched_evs:
                        open_pr = pr_map[matched_evs[0]["id"]]["pr_value"]
                        est = open_pr if leg_num == 1 else max(open_pr - 0.5, 5.0) # -0.5s running start
                        basis = f"Open {matched_evs[0]['event_name']} PR"
                    else:
                        # Fallback heuristic
                        est = 13.0 if "100" in target_relay["event_name"] else 55.0 if "400" in target_relay["event_name"] else 135.0
                        basis = "Team Baseline Estimate"
                
                projected_splits.append({"Leg": f"Leg {leg_num}", "Runner": aname, "Projected Split": db.format_time(est), "Seconds": est, "Basis": basis})
            
            proj_df = pd.DataFrame(projected_splits)
            total_proj_seconds = sum(p["Seconds"] for p in projected_splits)

            st.markdown("---")
            col_res1, col_res2 = st.columns([1, 2])
            with col_res1:
                st.metric("Projected Relay Time", db.format_time(total_proj_seconds))
                st.caption("Includes standard ~0.5s running start acceleration on Legs 2, 3, and 4.")
            with col_res2:
                st.dataframe(proj_df[["Leg", "Runner", "Projected Split", "Basis"]], use_container_width=True, hide_index=True)

    with tab_history:
        st.subheader("Official Relay Results & Leg Splits")
        all_relays = db.get_all_relay_results()
        if not all_relays:
            st.info("No relay results recorded yet.")
        else:
            for r in all_relays:
                with st.container():
                    st.markdown(f"#### 🏅 {r['event_name']} — **{db.format_time(r['total_time_seconds'])}**")
                    st.caption(f"Meet: **{r['meet_name']}** ({r['meet_date']}) • Venue: {r['venue_name']} • Timing: {r['timing_method']} • {r['notes'] or ''}")
                    if r.get("legs"):
                        legs_disp = []
                        for l in r["legs"]:
                            ath_name = f"{l['first_name']} {l['last_name']}" if l.get("first_name") else "Unassigned"
                            legs_disp.append({
                                "Leg": f"Leg {l['leg_number']}",
                                "Runner": ath_name,
                                "Split Time": db.format_time(l["split_seconds"]),
                                "Notes": l["notes"] or ""
                            })
                        st.dataframe(pd.DataFrame(legs_disp), use_container_width=True, hide_index=True)
                    st.divider()


# =========================================================
# PAGE 5: MEET RESULTS LOG
# =========================================================
elif nav_choice == "📋 Meet Results Log":
    render_header("Meet Results & Competition Log", "Review full results and heat sheets from Waterford track meets.")

    col_meet_flt1, col_meet_flt2 = st.columns([1, 3])
    with col_meet_flt1:
        season_year_opts = ["ALL"] + db.get_all_season_years()
        selected_season_year = st.selectbox("Season Year", season_year_opts, index=0)
    with col_meet_flt2:
        meets = db.get_all_meets(season_year=selected_season_year)
        if not meets:
            st.info(f"No meets recorded for the {selected_season_year} season.")
            st.stop()
        meet_map = {f"{m['date']} - {m['name']} ({m['season']} @ {m['venue_name']})": m for m in meets}
        selected_meet_label = st.selectbox(f"Select Meet ({len(meets)} meets)", list(meet_map.keys()), index=0)
        selected_meet = meet_map[selected_meet_label]

    col_m1, col_m2, col_m3 = st.columns(3)
    with col_m1:
        st.metric("Date", str(selected_meet["date"]))
    with col_m2:
        st.metric("Venue", f"{selected_meet['venue_name']} ({selected_meet['lap_distance_meters']:.0f}m)")
    with col_m3:
        st.metric("Meet Type", selected_meet["meet_type"])

    st.markdown("---")
    
    # Query all results for this meet
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT r.*, a.first_name, a.last_name, a.gender, a.grade_level,
                   e.event_name, e.event_type, e.sort_order
            FROM results r
            JOIN athletes a ON r.athlete_id = a.id
            JOIN events e ON r.event_id = e.id
            WHERE r.meet_id = ?
            ORDER BY e.event_type, e.event_name, 
                     CASE WHEN e.sort_order = 'ASC' THEN r.result_value END ASC,
                     CASE WHEN e.sort_order = 'DESC' THEN r.result_value END DESC
        """, (selected_meet["id"],))
        meet_results = [dict(row) for row in cursor.fetchall()]

    if not meet_results:
        st.info("No individual results entered for this meet yet.")
    else:
        # Group by event
        ev_groups = {}
        for r in meet_results:
            ev_groups.setdefault(r["event_name"], []).append(r)

        for ev_name, rows in ev_groups.items():
            st.markdown(f"### 📍 {ev_name}")
            disp_rows = []
            for rank, r in enumerate(rows, start=1):
                disp_rows.append({
                    "Place": f"#{rank}",
                    "Athlete": f"{r['first_name']} {r['last_name']}",
                    "Gender": r["gender"],
                    "Grade": f"Gr. {r['grade_level']}",
                    "Result Mark": db.format_result_display(r["event_type"], r["result_value"]),
                    "Timing": r["timing_method"],
                    "Status": "Official" if r["is_official"] else "Practice/TT",
                    "Notes": r["notes"] or ""
                })
            st.dataframe(pd.DataFrame(disp_rows), use_container_width=True, hide_index=True)


# =========================================================
# PAGE 6: COACH ADMIN HUB (DATA ENTRY & CRUD)
# =========================================================
elif nav_choice == "🔒 Coach Admin Hub":
    render_header("Coach Admin Hub", "Manage roster, record individual and relay meet results, and configure team standards.")

    if not is_coach:
        st.warning("⚠️ **Coach Authentication Required**")
        st.info("Please expand the **'🔐 Coach Login'** section in the left sidebar to log in. (Default credentials: `coach` / `waterford2026`)")
        st.stop()

    st.success(f"Welcome, Coach! You have full administrative CRUD permissions.")

    admin_tabs = st.tabs([
        "⚡ Single Result Entry",
        "📊 Bulk Meet Entry Grid",
        "🤝 Relay Results Entry",
        "🏟️ Meets & Venues",
        "👥 Roster & Standards",
        "🌐 MileSplit Auto-Sync",
        "⚙️ Database Tools"
    ])

    # --- TAB 1: SINGLE RESULT ENTRY ---
    with admin_tabs[0]:
        st.subheader("Log Individual Result")
        with st.form("single_result_form", clear_on_submit=False):
            col_r1, col_r2 = st.columns(2)
            with col_r1:
                season_choice = st.selectbox("Season", ["Outdoor", "Indoor"], key="single_res_season")
                meets = db.get_all_meets(season=season_choice)
                if not meets:
                    st.error("No meets found for this season. Please add a meet in the 'Meets & Venues' tab first.")
                    st.stop()
                meet_opts = {f"{m['date']} - {m['name']}": m["id"] for m in meets}
                meet_label = st.selectbox("Select Meet", list(meet_opts.keys()))
                meet_id = meet_opts[meet_label]
            
            with col_r2:
                athletes = db.get_all_athletes(active_only=True)
                ath_opts = {f"{a['last_name']}, {a['first_name']} ({a['gender']})": a["id"] for a in athletes}
                ath_label = st.selectbox("Select Athlete", list(ath_opts.keys()))
                athlete_id = ath_opts[ath_label]

            events = [e for e in db.get_all_events(season=season_choice) if e["event_type"] != "Relay"]
            ev_opts = {f"{e['event_name']} ({e['event_type']})": e for e in events}
            ev_label = st.selectbox("Select Event", list(ev_opts.keys()))
            selected_event = ev_opts[ev_label]

            col_val1, col_val2, col_val3 = st.columns(3)
            parsed_value = None
            if selected_event["event_type"] == "Track":
                with col_val1:
                    time_raw = st.text_input("Track Time", placeholder="e.g. 11.45, 2:04.12, 10:15.5", help="Enter in seconds or mm:ss.xx")
                    if time_raw:
                        parsed_value = db.parse_time(time_raw)
                        if parsed_value:
                            st.caption(f"Parsed: **{db.format_time(parsed_value)}** ({parsed_value:.2f}s)")
                        else:
                            st.error("Invalid time format.")
            else:
                # Field Event: Toggle Metric vs Imperial
                with col_val1:
                    field_mode = st.radio("Entry Unit", ["Imperial (Feet & Inches)", "Metric (Meters)"], horizontal=True)
                with col_val2:
                    if field_mode == "Imperial (Feet & Inches)":
                        imp_input = st.text_input("Distance", placeholder="e.g. 38' 6.5\" or 38-6.5", help="Feet and inches format")
                        if imp_input:
                            parsed_value = db.parse_field_mark(imp_input)
                            if parsed_value:
                                st.caption(f"Parsed: **{parsed_value:.2f}m** ({db.meters_to_feet_inches(parsed_value)})")
                    else:
                        met_input = st.number_input("Meters", min_value=0.0, max_value=100.0, step=0.01, format="%.2f")
                        parsed_value = float(met_input) if met_input > 0 else None

            with col_val2:
                timing_method = st.selectbox("Timing Method", ["FAT", "Hand"], index=0)
            with col_val3:
                is_official = st.checkbox("Official Competition Mark", value=True, help="Uncheck for practice time trials / intra-squad marks")

            notes = st.text_input("Notes / Heat / Conditions", placeholder="e.g. PR! +1.2 wind, finals")

            submitted = st.form_submit_button("💾 Save Result", use_container_width=True)
            if submitted:
                if parsed_value is None or parsed_value <= 0:
                    st.error("Please enter a valid numeric time or distance.")
                else:
                    new_id = db.add_result(
                        athlete_id=athlete_id,
                        event_id=selected_event["id"],
                        meet_id=meet_id,
                        result_value=parsed_value,
                        timing_method=timing_method,
                        is_official=is_official,
                        notes=notes
                    )
                    st.success(f"✅ Result logged successfully (ID #{new_id})!")
                    st.balloons()

    # --- TAB 2: BULK MEET ENTRY GRID ---
    with admin_tabs[1]:
        st.subheader("📊 Bulk Quick-Entry Grid")
        st.caption("Enter results for multiple roster athletes at once using an interactive table.")

        col_b1, col_b2 = st.columns(2)
        with col_b1:
            bulk_season = st.selectbox("Season", ["Outdoor", "Indoor"], key="bulk_season")
            bulk_meets = db.get_all_meets(season=bulk_season)
            if not bulk_meets:
                st.warning("No meets found for this season.")
                st.stop()
            bulk_meet_opts = {f"{m['date']} - {m['name']}": m["id"] for m in bulk_meets}
            bulk_meet_label = st.selectbox("Select Meet", list(bulk_meet_opts.keys()), key="bulk_meet")
            bulk_meet_id = bulk_meet_opts[bulk_meet_label]
        with col_b2:
            bulk_events = [e for e in db.get_all_events(season=bulk_season) if e["event_type"] != "Relay"]
            bulk_ev_opts = {f"{e['event_name']} ({e['event_type']})": e for e in bulk_events}
            bulk_ev_label = st.selectbox("Select Event", list(bulk_ev_opts.keys()), key="bulk_event")
            bulk_event = bulk_ev_opts[bulk_ev_label]

        # Load existing results or blank roster
        existing_results = db.get_results_for_meet_event(bulk_meet_id, bulk_event["id"])
        existing_by_ath = {r["athlete_id"]: r for r in existing_results}

        athletes = db.get_all_athletes(active_only=True)
        table_rows = []
        for a in athletes:
            r = existing_by_ath.get(a["id"])
            mark_str = ""
            timing = "FAT"
            is_off = True
            notes = ""
            if r:
                mark_str = db.format_time(r["result_value"]) if bulk_event["event_type"] == "Track" else f"{r['result_value']:.2f}"
                timing = r["timing_method"]
                is_off = bool(r["is_official"])
                notes = r["notes"] or ""
            
            table_rows.append({
                "Athlete ID": a["id"],
                "Athlete Name": f"{a['last_name']}, {a['first_name']}",
                "Gender": a["gender"],
                "Grade": a["grade_level"],
                "Mark (Time or Meters)": mark_str,
                "Timing": timing,
                "Official": is_off,
                "Notes": notes
            })
        
        bulk_df = pd.DataFrame(table_rows)
        edited_df = st.data_editor(
            bulk_df,
            column_config={
                "Athlete ID": st.column_config.NumberColumn(disabled=True),
                "Athlete Name": st.column_config.TextColumn(disabled=True),
                "Gender": st.column_config.TextColumn(disabled=True),
                "Grade": st.column_config.NumberColumn(disabled=True),
                "Mark (Time or Meters)": st.column_config.TextColumn(help="e.g. 11.24, 2:04.15, or 10.50"),
                "Timing": st.column_config.SelectboxColumn(options=["FAT", "Hand"]),
                "Official": st.column_config.CheckboxColumn(),
                "Notes": st.column_config.TextColumn()
            },
            hide_index=True,
            use_container_width=True,
            key="bulk_editor"
        )

        if st.button("💾 Save All Bulk Entries", use_container_width=True):
            saved_count = 0
            for _, row in edited_df.iterrows():
                val_str = str(row["Mark (Time or Meters)"]).strip()
                if val_str and val_str != "nan":
                    val_num = db.parse_time(val_str) if bulk_event["event_type"] == "Track" else db.parse_field_mark(val_str)
                    if val_num and val_num > 0:
                        aid = int(row["Athlete ID"])
                        if aid in existing_by_ath:
                            db.update_result(
                                result_id=existing_by_ath[aid]["id"],
                                result_value=val_num,
                                timing_method=row["Timing"],
                                is_official=row["Official"],
                                notes=row["Notes"] or ""
                            )
                        else:
                            db.add_result(
                                athlete_id=aid,
                                event_id=bulk_event["id"],
                                meet_id=bulk_meet_id,
                                result_value=val_num,
                                timing_method=row["Timing"],
                                is_official=row["Official"],
                                notes=row["Notes"] or ""
                            )
                        saved_count += 1
            st.success(f"✅ Successfully processed and saved {saved_count} athlete marks!")
            st.rerun()

    # --- TAB 3: RELAY RESULTS ENTRY ---
    with admin_tabs[2]:
        st.subheader("🤝 Log Relay Result")
        with st.form("relay_entry_form"):
            col_rel1, col_rel2 = st.columns(2)
            with col_rel1:
                rel_season = st.selectbox("Season", ["Outdoor", "Indoor"], key="rel_form_season")
                rel_meets = db.get_all_meets(season=rel_season)
                if not rel_meets:
                    st.warning("No meets available.")
                    st.stop()
                rel_meet_opts = {f"{m['date']} - {m['name']}": m["id"] for m in rel_meets}
                rel_meet_label = st.selectbox("Select Meet", list(rel_meet_opts.keys()), key="rel_form_meet")
                rel_meet_id = rel_meet_opts[rel_meet_label]
            
            with col_rel2:
                rel_events = db.get_all_events(season=rel_season, event_type="Relay")
                rel_ev_opts = {r["event_name"]: r["id"] for r in rel_events}
                rel_ev_label = st.selectbox("Select Relay Event", list(rel_ev_opts.keys()), key="rel_form_event")
                rel_event_id = rel_ev_opts[rel_ev_label]

            col_t1, col_t2, col_t3 = st.columns(3)
            with col_t1:
                total_time_str = st.text_input("Total Team Time", placeholder="e.g. 51.40 or 3:34.60")
            with col_t2:
                rel_timing = st.selectbox("Timing", ["FAT", "Hand"], index=0, key="rel_timing")
            with col_t3:
                rel_official = st.checkbox("Official Meet", value=True, key="rel_official")

            st.markdown("#### Optional Individual Leg Splits")
            st.caption("Assign roster athletes and splits to legs 1 through 4.")
            
            athletes = db.get_all_athletes(active_only=True)
            ath_choices = {"-- Unassigned --": None}
            ath_choices.update({f"{a['last_name']}, {a['first_name']}": a["id"] for a in athletes})
            
            legs_input = []
            col_leg1, col_leg2, col_leg3, col_leg4 = st.columns(4)
            with col_leg1:
                l1_ath = st.selectbox("Leg 1 Runner", list(ath_choices.keys()), index=0, key="l1_ath")
                l1_split = st.text_input("Leg 1 Split", placeholder="e.g. 13.20", key="l1_split")
                legs_input.append((1, ath_choices[l1_ath], l1_split))
            with col_leg2:
                l2_ath = st.selectbox("Leg 2 Runner", list(ath_choices.keys()), index=0, key="l2_ath")
                l2_split = st.text_input("Leg 2 Split", placeholder="e.g. 12.90", key="l2_split")
                legs_input.append((2, ath_choices[l2_ath], l2_split))
            with col_leg3:
                l3_ath = st.selectbox("Leg 3 Runner", list(ath_choices.keys()), index=0, key="l3_ath")
                l3_split = st.text_input("Leg 3 Split", placeholder="e.g. 13.10", key="l3_split")
                legs_input.append((3, ath_choices[l3_ath], l3_split))
            with col_leg4:
                l4_ath = st.selectbox("Leg 4 Runner", list(ath_choices.keys()), index=0, key="l4_ath")
                l4_split = st.text_input("Leg 4 Split", placeholder="e.g. 12.20", key="l4_split")
                legs_input.append((4, ath_choices[l4_ath], l4_split))

            rel_notes = st.text_input("Relay Notes", placeholder="e.g. Gold medal, Sectional Champions")
            submit_relay = st.form_submit_button("💾 Save Relay Result", use_container_width=True)

            if submit_relay:
                tot_seconds = db.parse_time(total_time_str)
                if not tot_seconds or tot_seconds <= 0:
                    st.error("Please enter a valid total team time.")
                else:
                    legs_data = []
                    for leg_num, aid, split_raw in legs_input:
                        split_sec = db.parse_time(split_raw) if split_raw else None
                        legs_data.append({
                            "leg_number": leg_num,
                            "athlete_id": aid,
                            "split_seconds": split_sec,
                            "notes": ""
                        })
                    
                    db.add_relay_result(
                        event_id=rel_event_id,
                        meet_id=rel_meet_id,
                        total_time_seconds=tot_seconds,
                        timing_method=rel_timing,
                        is_official=rel_official,
                        notes=rel_notes,
                        legs=legs_data
                    )
                    st.success("✅ Relay result and splits saved successfully!")
                    st.rerun()

    # --- TAB 4: MEETS & VENUES ---
    with admin_tabs[3]:
        st.subheader("🏟️ Manage Meets & Venues")
        
        col_madd, col_vadd = st.columns(2)
        with col_madd:
            st.markdown("#### Add New Meet")
            with st.form("add_meet_form"):
                m_name = st.text_input("Meet Name", placeholder="e.g. Section 2 Championship")
                m_date = st.date_input("Meet Date", value=date.today())
                m_season = st.selectbox("Season", ["Outdoor", "Indoor"])
                venues = db.get_all_venues()
                ven_opts = {v["name"]: v["id"] for v in venues}
                ven_label = st.selectbox("Venue", list(ven_opts.keys()))
                m_venue_id = ven_opts[ven_label]
                m_type = st.selectbox("Meet Type", ["Dual", "Invitational", "Championship", "State Qualifier", "Practice / Time Trial"])
                
                sub_meet = st.form_submit_button("Add Meet")
                if sub_meet and m_name:
                    db.add_meet(m_name, str(m_date), m_venue_id, m_season, m_type)
                    st.success("Meet added!")
                    st.rerun()

        with col_vadd:
            st.markdown("#### Add New Venue / Track")
            with st.form("add_venue_form"):
                v_name = st.text_input("Venue Name", placeholder="e.g. Albany High 400m")
                v_season = st.selectbox("Season", ["Outdoor", "Indoor", "Both"])
                v_lap = st.number_input("Lap Distance (Meters)", value=400.0, step=10.0)
                sub_ven = st.form_submit_button("Add Venue")
                if sub_ven and v_name:
                    db.add_venue(v_name, v_season, v_lap)
                    st.success("Venue added!")
                    st.rerun()

        with st.expander("🗑️ Delete a Meet or Venue", expanded=False):
            col_dm, col_dv = st.columns(2)
            with col_dm:
                del_meets = db.get_all_meets()
                if del_meets:
                    dm_opts = {f"{m['date']} - {m['name']}": m["id"] for m in del_meets}
                    dm_label = st.selectbox("Select Meet to Delete", list(dm_opts.keys()), key="del_meet_select")
                    if st.button("Delete Meet", type="secondary", key="del_meet_btn"):
                        db.delete_meet(dm_opts[dm_label])
                        st.success("Meet deleted!")
                        st.rerun()
                else:
                    st.caption("No meets to delete.")
            with col_dv:
                del_venues = db.get_all_venues()
                if del_venues:
                    dv_opts = {v["name"]: v["id"] for v in del_venues}
                    dv_label = st.selectbox("Select Venue to Delete", list(dv_opts.keys()), key="del_venue_select")
                    if st.button("Delete Venue", type="secondary", key="del_venue_btn"):
                        db.delete_venue(dv_opts[dv_label])
                        st.success("Venue deleted!")
                        st.rerun()
                else:
                    st.caption("No venues to delete.")

    # --- TAB 5: ROSTER & STANDARDS ---
    with admin_tabs[4]:
        st.subheader("👥 Roster Management")
        col_radd, col_rman = st.columns(2)
        with col_radd:
            st.markdown("#### ➕ Add New Athlete")
            with st.form("add_athlete_form"):
                af_first = st.text_input("First Name")
                af_last = st.text_input("Last Name")
                af_gender = st.selectbox("Gender", ["F", "M"], format_func=lambda x: "Female" if x == "F" else "Male")
                af_age = st.number_input("Age", min_value=12, max_value=20, value=15)
                af_grade = st.number_input("Grade Level", min_value=7, max_value=12, value=10)
                af_active = st.checkbox("Active", value=True)
                
                sub_ath = st.form_submit_button("Add Athlete to Roster")
                if sub_ath and af_first and af_last:
                    db.add_athlete(af_first, af_last, af_gender, af_age, af_grade, af_active)
                    st.success(f"Added {af_first} {af_last} to roster!")
                    st.rerun()

        with col_rman:
            st.markdown("#### ✏️ Edit or 🗑️ Delete Athlete")
            all_athletes = db.get_all_athletes(active_only=False)
            if all_athletes:
                man_opts = {f"{a['last_name']}, {a['first_name']} (Gr. {a['grade_level']}, ID #{a['id']})": a for a in all_athletes}
                man_label = st.selectbox("Select Athlete to Edit / Delete", list(man_opts.keys()), key="man_ath_select")
                target_ath = man_opts[man_label]

                with st.form("edit_athlete_form"):
                    ed_first = st.text_input("First Name", value=target_ath["first_name"])
                    ed_last = st.text_input("Last Name", value=target_ath["last_name"])
                    ed_gender = st.selectbox("Gender", ["F", "M"], index=0 if target_ath["gender"] == "F" else 1, format_func=lambda x: "Female" if x == "F" else "Male")
                    ed_age = st.number_input("Age", min_value=12, max_value=20, value=target_ath["age"] or 15)
                    ed_grade = st.number_input("Grade Level", min_value=7, max_value=12, value=target_ath["grade_level"] or 9)
                    ed_active = st.checkbox("Active Roster Status", value=bool(target_ath["active_status"]))

                    sub_edit = st.form_submit_button("💾 Update Athlete Info", use_container_width=True)
                    if sub_edit:
                        db.update_athlete(target_ath["id"], ed_first, ed_last, ed_gender, ed_age, ed_grade, ed_active)
                        st.success(f"Updated {ed_first} {ed_last} successfully!")
                        st.rerun()

                with st.expander("⚠️ Danger Zone: Delete Athlete", expanded=False):
                    st.caption("Deleting an athlete removes them and all associated individual results.")
                    confirm_del = st.checkbox(f"Confirm deletion of {target_ath['first_name']} {target_ath['last_name']}", key=f"confirm_del_{target_ath['id']}")
                    if st.button("🗑️ Delete Athlete Permanently", type="primary", disabled=not confirm_del, key=f"btn_del_{target_ath['id']}"):
                        db.delete_athlete(target_ath["id"])
                        st.success(f"Athlete {target_ath['first_name']} {target_ath['last_name']} deleted.")
                        st.rerun()
            else:
                st.info("No athletes currently in database.")

        st.markdown("---")
        st.subheader("🎯 Championship & Qualifying Standards")
        with st.form("add_standard_form"):
            col_s1, col_s2 = st.columns(2)
            with col_s1:
                s_events = [e for e in db.get_all_events() if e["event_type"] != "Relay"]
                s_ev_opts = {f"{e['season']} {e['event_name']}": e for e in s_events}
                s_ev_label = st.selectbox("Event", list(s_ev_opts.keys()))
                s_event = s_ev_opts[s_ev_label]
                s_gender = st.selectbox("Gender", ["F", "M"], format_func=lambda x: "Female (F)" if x == "F" else "Male (M)")
            with col_s2:
                s_name = st.selectbox("Standard Type", ["School Record", "Section 2 Standard", "State Qualifier", "League Champion Mark"])
                s_val_raw = st.text_input("Standard Mark", placeholder="e.g. 4:28.50, 12.40, or 38' 6\"")
            
            sub_std = st.form_submit_button("Save Standard")
            if sub_std and s_val_raw:
                s_val = db.parse_time(s_val_raw) if s_event["event_type"] == "Track" else db.parse_field_mark(s_val_raw)
                if s_val:
                    db.add_or_update_standard(s_event["id"], s_gender, s_name, s_val)
                    st.success("Standard saved!")
                    st.rerun()
                else:
                    st.error("Invalid mark format.")

    # --- TAB 6: MILESPLIT AUTO-SYNC ---
    with admin_tabs[5]:
        st.subheader("🌐 MileSplit Auto-Sync & Importer")
        st.caption("Automatically populate real Waterford High School athletes, indoor/outdoor seasons, and official PRs/meet histories from MileSplit.")

        # PRO Authentication Card
        with st.expander("⭐ MileSplit PRO / FloSports Account Login (Unlocks Complete Meet Histories)", expanded=True):
            st.write("Logging in with your paid MileSplit PRO account unlocks detailed meet-by-meet histories, exact meet names, and past seasons for all athletes graduating in 2026 or later.")
            col_pro1, col_pro2 = st.columns(2)
            with col_pro1:
                pro_email = st.text_input("MileSplit Email", value=st.session_state.get("ms_pro_email", ""), placeholder="coach@waterford.k12.ny.us", key="pro_email_inp")
            with col_pro2:
                pro_pass = st.text_input("MileSplit Password", value="", type="password", placeholder="••••••••", key="pro_pass_inp")

            col_btn1, col_btn2 = st.columns([1, 1])
            with col_btn1:
                if st.button("🔑 Log In to MileSplit PRO", type="primary", use_container_width=True):
                    if pro_email and pro_pass:
                        with st.spinner("Authenticating with MileSplit / FloSports API..."):
                            session, msg = ms.login_milesplit(pro_email, pro_pass)
                            if session:
                                st.session_state["ms_pro_session"] = session
                                st.session_state["ms_pro_email"] = pro_email
                                st.success("✅ " + msg)
                                st.rerun()
                            else:
                                st.error("❌ " + msg)
                    else:
                        st.warning("Please enter your MileSplit email and password.")

            with col_btn2:
                if "ms_pro_session" in st.session_state and st.session_state["ms_pro_session"]:
                    st.success(f"🔓 Logged in as `{st.session_state.get('ms_pro_email')}` (PRO Active)")
                    if st.button("Logout of MileSplit", type="secondary", use_container_width=True):
                        st.session_state.pop("ms_pro_session", None)
                        st.session_state.pop("ms_pro_email", None)
                        st.rerun()
                else:
                    st.info("ℹ️ Without PRO login, public PR marks and rosters will be imported.")

        st.markdown("---")
        sync_col1, sync_col2 = st.columns([1, 1])

        with sync_col1:
            st.markdown("#### 1. Sync Official Waterford Roster")
            st.write("Extracts active Waterford-Halfmoon athletes directly from the live MileSplit team page.")
            ms_team_url = st.text_input("MileSplit Roster URL", value=ms.DEFAULT_ROSTER_URL, key="ms_roster_input")
            min_grad_year = st.number_input("Minimum Graduation Year (e.g. 2026+)", min_value=2020, max_value=2035, value=2026, step=1, key="min_grad_year_inp")
            
            if st.button("🔄 Sync Team Roster from MileSplit", type="primary", use_container_width=True):
                with st.spinner("Connecting to MileSplit and extracting roster..."):
                    try:
                        active_sess = st.session_state.get("ms_pro_session")
                        roster = ms.fetch_waterford_roster(ms_team_url, min_grad_year=min_grad_year, session=active_sess)
                        added, updated = ms.sync_roster_to_db(roster)
                        st.success(f"✅ Roster synced! Added {added} new athletes, updated {updated} existing athletes ({len(roster)} total, Class of {min_grad_year}+).")
                        st.balloons()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error syncing roster: {e}")

        with sync_col2:
            st.markdown("#### 2. Sync Athlete Performance Marks")
            st.write("Visits athlete profiles to extract all meet records (or official PRs) into SQLite.")
            
            sync_limit = st.slider("Number of athletes to sync:", min_value=5, max_value=60, value=60, step=5, help="Fetching each athlete takes ~0.5s to respect MileSplit rate limits.")
            
            btn_sync_label = "⚡ Sync Meet Stats from MileSplit (PRO)" if st.session_state.get("ms_pro_session") else "⚡ Sync Athlete PRs from MileSplit"
            if st.button(btn_sync_label, type="secondary", use_container_width=True):
                prog_bar = st.progress(0)
                status_text = st.empty()

                def update_prog(current, total, name):
                    prog_bar.progress(current / total)
                    status_text.caption(f"Syncing [{current}/{total}]: **{name}**...")

                try:
                    active_sess = st.session_state.get("ms_pro_session")
                    summary = ms.sync_all_from_milesplit(
                        max_athletes_with_prs=sync_limit,
                        progress_callback=update_prog,
                        min_grad_year=min_grad_year,
                        session=active_sess
                    )
                    prog_bar.progress(1.0)
                    status_text.empty()
                    st.success(f"🎉 Complete! Synced {summary['athletes_prs_synced']} athletes and inserted {summary['total_results_inserted']} performance marks into SQLite.")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error during sync: {e}")

        st.markdown("---")
        st.markdown("#### 3. Sync Wasaren League Rival Marks")
        st.write("Extracts season-best marks across all 9 schools in the Wasaren League (Cambridge, Greenwich, Hoosic Valley, Hoosick Falls, Mechanicville, Saratoga Catholic, Stillwater, Tamarac, Waterford).")
        
        col_wl_sync1, col_wl_sync2 = st.columns([2, 1])
        with col_wl_sync1:
            wl_sum = db.get_wasaren_schools_summary()
            total_wl_marks = sum(s["total_marks"] for s in wl_sum) if wl_sum else 0
            st.caption(f"Current Cache: **{total_wl_marks} marks** across **{len(wl_sum)} schools**.")
        with col_wl_sync2:
            if st.button("⚔️ Sync All Wasaren League Rival Marks", type="primary", use_container_width=True):
                wl_prog = st.progress(0)
                wl_status = st.empty()
                def update_wl_prog(cur, tot, s_name):
                    wl_prog.progress(cur / tot)
                    wl_status.caption(f"Syncing [{cur}/{tot}]: **{s_name}**...")
                try:
                    active_sess = st.session_state.get("ms_pro_session")
                    wl_res = ms.sync_wasaren_league_marks(session=active_sess, progress_callback=update_wl_prog)
                    wl_prog.progress(1.0)
                    wl_status.empty()
                    st.success(f"🎉 Complete! Synced {wl_res['total_synced']} marks across {wl_res['schools_synced']} schools.")
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Error syncing league marks: {e}")

        st.markdown("---")
        st.markdown("#### 4. Quick Results Text / CSV Paste Importer")
        st.caption("Paste lines of meet results copied from MileSplit, Athletic.net, or local timing sheets to bulk-import marks.")
        with st.expander("📝 Open Text Importer", expanded=False):
            with st.form("quick_paste_form"):
                meets = db.get_all_meets()
                if meets:
                    m_opts = {f"{m['date']} - {m['name']}": m["id"] for m in meets}
                    m_lbl = st.selectbox("Assign to Meet", list(m_opts.keys()))
                    p_meet_id = m_opts[m_lbl]
                else:
                    p_meet_id = None
                raw_paste = st.text_area("Paste Result Lines (e.g. '100m, Blake Bombard, 11.60' or 'Shot Put, Max Burniche, 35-4')", height=150)
                sub_paste = st.form_submit_button("Import Lines")
                if sub_paste and raw_paste and p_meet_id:
                    lines = [l.strip() for l in raw_paste.split("\n") if l.strip()]
                    imported_cnt = 0
                    athletes_all = db.get_all_athletes(active_only=False)
                    ath_name_map = {(a["first_name"].lower() + " " + a["last_name"].lower()): a["id"] for a in athletes_all}
                    ath_name_map.update({(a["last_name"].lower() + " " + a["first_name"].lower()): a["id"] for a in athletes_all})
                    ath_name_map.update({(a["last_name"].lower() + ", " + a["first_name"].lower()): a["id"] for a in athletes_all})

                    for line in lines:
                        parts = [p.strip() for p in re.split(r"[,|\t]", line)]
                        if len(parts) >= 3:
                            ev_name, ath_name, mark_str = parts[0], parts[1], parts[2]
                            matched_aid = ath_name_map.get(ath_name.lower())
                            if matched_aid:
                                ath_obj = db.get_athlete_by_id(matched_aid)
                                ev_obj = ms.resolve_or_create_event(ev_name, "Outdoor", ath_obj["gender"] if ath_obj else "M")
                                if ev_obj:
                                    val = db.parse_time(mark_str) if ev_obj["event_type"] == "Track" else db.parse_field_mark(mark_str)
                                    if val:
                                        db.add_result(matched_aid, ev_obj["id"], p_meet_id, val, "FAT", True, "Pasted import")
                                        imported_cnt += 1
                    st.success(f"Imported {imported_cnt} valid results from pasted text!")
                    st.rerun()

    # --- TAB 7: DATABASE TOOLS ---
    with admin_tabs[6]:
        st.subheader("⚙️ Database Maintenance & Demo Seed")
        st.write(f"Active SQLite Database File: `{db.DB_PATH}`")
        if st.button("⚠️ Reset & Re-Seed Database with Demo Data", type="secondary"):
            db.reset_database()
            st.success("Database has been reset and freshly seeded with demo athletes, meets, and records!")
            st.rerun()
