# Waterford Track & Field Performance Tracking Dashboard

A mobile-responsive track and field performance tracking application built with Python, Streamlit, SQLite, and Docker. Designed for high school coaches, athletes, and parents to monitor training marks, competition PRs, and championship standards.

---

## 🏃 Key Features

1. **Athlete Profiles & Progression:**
   - **Academic Season Year Filter:** Dynamic dropdown filter (`ALL`, `2026-27`, `2025-26`, `2024-25`, etc.) to isolate events, Season Bests (SB), and progression curves for a specific school year or view complete career PRs.
   - Multi-meet performance progression charts (Plotly) with personal record (PR) stars and championship standard reference lines.
   - Automated Personal Record (PR) and Season Best (SB) summary cards.
   - Individual relay split history tracking.

2. **Team Honor Roll & Records:**
   - Top 10 rankings by event, gender, and school year season (`ALL` for All-Time or specific season years like `2025-26`).
   - Proximity tracking to Section 2, State Qualifier, and School Record standards.

3. **Pace & Lap Split Calculator:**
   - Calibrated for varying track venues:
     - **Outdoor Track:** 400m
     - **HVCC Indoor:** 160.93m (1/10th mile)
     - **Union Fieldhouse:** 160m
   - Calculates exact lap paces, 100m splits, and generates a **clipboard-ready stopwatch split table** for race-day coaching.

4. **Relay Lineup Builder & Simulator:**
   - Select 4 runners from the active roster.
   - Projects team relay finish time using historical splits or open PRs with running-start discounts.

5. **Coach Admin Hub (Role-Based Access Control):**
   - **Single Result Entry:** Dynamic season filters, imperial-to-metric conversions for field events (`38' 6.5"` -> `11.75m`), and practice vs. official meet toggles.
   - **Bulk Quick-Entry Grid:** `st.data_editor` interactive matrix to enter results for entire heats or flights in one click.
   - **Relay Entry Form:** Log team times with individual leg assignments and splits.
   - **Roster & Standards Management:** Add/edit athletes and qualification standards.
   - **🌐 MileSplit Auto-Sync & Importer:** 1-click live sync pulling all 60+ Waterford-Halfmoon athletes directly from MileSplit, automatic extraction of official indoor & outdoor PR marks, and a meet results clipboard importer.

---

## 🚀 Running Locally

1. Clone or navigate to the repository:
   ```bash
   cd WaterfordTracker
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Launch the Streamlit application:
   ```bash
   streamlit run app.py
   ```
   The dashboard will automatically open in your default browser at `http://localhost:8501`.

---

## 🐳 Synology NAS Container Manager Deployment

1. **Create Data Directory on Synology:**
   Using File Station, create a folder for persistent database storage, for example:
   `/volume1/docker/waterford_tracker/data`

2. **Deploy via Container Manager (Project / Compose):**
   - In Synology **Container Manager**, navigate to **Project** -> **Create**.
   - Set the project name (e.g., `waterford-tracker`).
   - Upload or paste the [`docker-compose.yml`](file:///C:/Gemini/WaterfordTracker/docker-compose.yml) file.
   - Ensure the volume path matches your Synology directory:
     ```yaml
     volumes:
       - /volume1/docker/waterford_tracker/data:/app/data
     ```
   - Click **Done** to build and launch the container.

3. **Access the Application:**
   Open `http://<YOUR_SYNOLOGY_IP>:8501` on any mobile phone, tablet, or PC connected to your network.

---

## 🔐 Default Credentials

- **Role:** Head Coach / Admin
- **Username:** `coach`
- **Password:** `waterford2026`
*(Public users and athletes can view all dashboards and tools without logging in).*

---

## 📁 Project Structure

| File | Description |
| :--- | :--- |
| [`app.py`](file:///C:/Gemini/WaterfordTracker/app.py) | Main multi-page Streamlit application |
| [`database.py`](file:///C:/Gemini/WaterfordTracker/database.py) | SQLite schema, seed data, unit converters, and CRUD operations |
| [`auth.py`](file:///C:/Gemini/WaterfordTracker/auth.py) | Streamlit-authenticator bcrypt management & session state |
| [`milesplit_sync.py`](file:///C:/Gemini/WaterfordTracker/milesplit_sync.py) | MileSplit web scraper & auto-sync engine for roster & PR stats |
| [`requirements.txt`](file:///C:/Gemini/WaterfordTracker/requirements.txt) | Pinned Python dependencies |
| [`Dockerfile`](file:///C:/Gemini/WaterfordTracker/Dockerfile) | Production Docker image with `/app/data` persistent volume |
| [`docker-compose.yml`](file:///C:/Gemini/WaterfordTracker/docker-compose.yml) | Synology NAS Container Manager service configuration |
