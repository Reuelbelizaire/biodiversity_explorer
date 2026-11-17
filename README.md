# 🌿 WildTrack | Biodiversity Explorer

**An AI-powered spatial data science and conservation intelligence web application built with Python, Streamlit, Plotly, Supabase (PostgreSQL), GBIF, and DeepSeek.**

WildTrack ingests live global wildlife occurrence records from the **Global Biodiversity Information Facility (GBIF) API**, persists cleaned geospatial sightings in a cloud-hosted **Supabase PostgreSQL** database, and pairs interactive geospatial and ecological analytics with an integrated **AI Wildlife Conservation Analyst**.

---

## ✨ Key Features

### 1. Live Automated Wildlife Ingestion (`gbif_client.py` & `llm_service.py`)
* **Smart Taxonomic Resolution:** Enter any common English animal name (e.g., *"Aardvark"*, *"Emperor Penguin"*, *"Cheetah"*). The app translates common names into exact Latin binomials or taxonomic clades and resolves GBIF `taxonKey` identifiers automatically—supporting both individual species and broader taxonomic families.
* **Paginated Cloud Persistence (`db_loader.py`):** Upserts deduplicated occurrence records into Supabase PostgreSQL and uses `.range()` batch pagination (`fetch_all_occurrences()`) to retrieve the full dataset seamlessly past Supabase's 1,000-row API default limit.

### 2. Global Geospatial Telemetry & Country Hotspots (Tab 1)
* **Interactive Sighting Maps:** Explore species distributions across global latitude/longitude coordinates with multi-species filtering, country hotspot rankings, and observation basis breakdowns.

### 3. Species Trends & Ecological Analytics (Tab 2)
* **12-Month Observation & Seasonality Matrix:** Monthly heatmap tracking observation density and migration seasonality across species.
* **Dynamic Biome & Habitat Distribution:** Automatically classifies every active species into its ecological biome (*Tropical Savannas & Rainforests*, *Temperate Grasslands & Forests*, *Arctic Tundra & Boreal*, *Polar & Subpolar Seas*, etc.) using mean GPS latitude and habitat classification—paired side-by-side with an interactive clickable Plotly Treemap and a scrollable **Species Biome & Habitat Roster** with Wikimedia field photos.
* **AI-Classified Trophic Diet & Food Roles:** Uses cached LLM ecological classification (`classify_species_diets`) to organize tracked species into trophic roles (*Apex Carnivore*, *Carnivore*, *Herbivore*, *Omnivore*, *Insectivore & Nectarivore*), paired side-by-side with a visual **Species Diet & Prey Roster**.
* **Population & Latitudinal Spread:** Compares recorded sighting volumes and North-vs.-South latitudinal habitat ranges relative to the Equator.

### 4. AI Wildlife Conservation Analyst & Species Profiles (Tab 3)
* **Visual Attribute & Evolutionary Trait Cards:** Displays high-resolution Wikimedia Commons field photography (automatically filtering out range maps and SVG diagrams) alongside a **Signature Evolutionary Trait** callout and 1–10 physical/ecological attribute bars (*Strength*, *Speed*, *Endurance*, *Stealth*, and *Threat Level*).
* **Automated Conservation Briefings & Interactive Q&A:** Synthesizes live database metrics into structured conservation status briefings and allows users to ask natural-language ecological questions grounded in active sighting data.

---

## 🛠️ Tech Stack

| Layer | Technologies |
| :--- | :--- |
| **Frontend & UI** | Python, Streamlit (Custom Rainforest Canopy Theme) |
| **Data Processing** | Pandas, NumPy |
| **Visualizations** | Plotly Express & Plotly Graph Objects (Treemaps, Heatmaps, Boxplots, Geospatial Maps) |
| **Cloud Database** | Supabase (PostgreSQL) via `supabase-py` |
| **External APIs** | GBIF Occurrence & Species API, Wikimedia Commons / Wikipedia REST API |
| **AI / LLM Engine** | DeepSeek API (`deepseek-chat` via OpenAI-compatible Python SDK) |

---

## 📂 Project Architecture

```text
WildTrack/
├── app.py              # Main Streamlit dashboard, Rainforest Canopy styling, & 3-tab UI
├── gbif_client.py      # GBIF API taxonomic lookup, clade fallback, & occurrence fetcher
├── db_loader.py        # Supabase PostgreSQL client, upsert logic, & paginated loader
├── llm_service.py      # DeepSeek integration (conservation reports, diet roles, trait cards, & Q&A)
├── requirements.txt    # Python dependencies
├── .env                # Local environment variables (excluded from version control)
└── README.md           # Project documentation
```

---

## 🚀 Getting Started

### 1. Clone the Repository
```bash
git clone https://github.com/<your-username>/<your-repo-name>.git
cd <your-repo-name>
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure Environment Variables
Create a `.env` file in the root directory and add your credentials:
```env
SUPABASE_URL=your_supabase_project_url
SUPABASE_KEY=your_supabase_anon_or_service_key
DEEPSEEK_API_KEY=your_deepseek_api_key
```

### 4. Set Up the Supabase Table
Run the following SQL in your **Supabase SQL Editor** to create the `occurrences` table:
```sql
CREATE TABLE IF NOT EXISTS public.occurrences (
    occurrence_id TEXT PRIMARY KEY,
    scientific_name TEXT NOT NULL,
    country TEXT,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    event_date TEXT,
    basis_of_record TEXT
);
```

### 5. Launch the Application
```bash
streamlit run app.py
```

---

## 💡 Usage Highlights for Live Exploration
1. **Filter or Compare Species:** Use the sidebar to isolate specific animals (e.g., comparing Arctic *Walrus* and Antarctic *Emperor Penguin* against *Cheetah* and *Loggerhead Sea Turtle*) or copy exact scientific names directly from the sidebar helper.
2. **Ingest a New Animal Live:** Type any common animal name into the sidebar ingestion bar and click **"➕ Add Your Animal Record to Database"** to fetch live GBIF sightings, store them in Supabase, and watch all maps, treemaps, and AI cards update automatically.
3. **Zoom Into Biomes & Food Webs:** In **Tab 2**, click any biome or trophic group inside the treemaps to zoom into its resident species, or browse the photo rosters on the right.