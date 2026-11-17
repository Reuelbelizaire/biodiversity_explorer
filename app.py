import os
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
from dotenv import load_dotenv

# Import functions from your helper files
from gbif_client import (
    fetch_species_occurrences,
    resolve_species_name,
    fetch_english_name_and_habitat,
    fetch_animal_photo,
)
from db_loader import (
    supabase,
    upsert_occurrences,
    fetch_occurrences_by_species,
    fetch_occurrences_by_species_list,
    fetch_all_occurrences,
)
from llm_service import (
    generate_conservation_report,
    answer_animal_question,
    generate_species_stats,
    generate_comparative_assessment,
    check_species_spelling,
    translate_to_scientific_name,
    classify_species_diets,
)

# Load environment variables (.env for local runs)
load_dotenv()

# ==============================================================================
# 1. PAGE CONFIG & OPTION 4 ("RAINFOREST CANOPY") STYLING
# ==============================================================================
st.set_page_config(
    page_title="WildTrack | Biodiversity & Species Explorer",
    page_icon="🌿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# High-contrast green & white theme so text and cards are easy to read
st.markdown(
    """
<style>
    /* Main background - soft sage */
    .stApp {
        background: #e8ece9 !important;
        color: #052e16 !important;
    }

    /* Sidebar - crisp light surface with dark evergreen text */
    [data-testid="stSidebar"] {
        background-color: #f3f6f4 !important;
        border-right: 1px solid rgba(20, 83, 45, 0.18) !important;
    }
    [data-testid="stSidebar"] * {
        color: #052e16 !important;
    }
    [data-testid="stSidebar"] input,
    [data-testid="stSidebar"] div[data-baseweb="select"] {
        background-color: #ffffff !important;
        color: #052e16 !important;
        border: 1px solid rgba(20, 83, 45, 0.25) !important;
        border-radius: 10px !important;
    }

    /* Top bar */
    header[data-testid="stHeader"] {
        background-color: #e8ece9 !important;
    }

    /* Top 4 KPI Metric Cards */
    .glass-card-kpi {
        background: #ffffff !important;
        border: 1px solid rgba(20, 83, 45, 0.18) !important;
        border-left: 5px solid #14532d !important;
        border-radius: 16px;
        padding: 16px 20px;
        box-shadow: 0 4px 20px rgba(5, 46, 22, 0.06);
        height: 120px !important;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        overflow: hidden;
        transition: transform 0.2s ease, box-shadow 0.2s ease;
    }
    .glass-card-kpi:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(5, 46, 22, 0.12);
        border-color: #15803d !important;
    }

    /* Content & AI Report Cards */
    .glass-card-content {
        background: #ffffff !important;
        border: 1px solid rgba(20, 83, 45, 0.18) !important;
        border-left: 5px solid #14532d !important;
        border-radius: 16px;
        padding: 20px 24px;
        box-shadow: 0 4px 20px rgba(5, 46, 22, 0.06);
        height: auto !important;
        min-height: 110px;
        color: #052e16 !important;
    }

    /* Typography */
    .kpi-title {
        color: #3f624d !important;
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 2px;
    }
    .kpi-value {
        color: #052e16 !important;
        font-size: 2rem;
        font-weight: 800;
        line-height: 1.1;
    }
    .kpi-value-sm {
        color: #15803d !important;
        font-size: 1.35rem;
        font-weight: 800;
        line-height: 1.2;
    }

    /* Top Pill Badge */
    .pill-badge {
        background: #dcfce7 !important;
        border: 1px solid #86efac !important;
        color: #14532d !important;
        border-radius: 9999px;
        padding: 4px 14px;
        font-size: 0.78rem;
        font-weight: 700;
        display: inline-block;
        margin-bottom: 6px;
    }

    /* Tabs */
    button[data-baseweb="tab"] {
        background: transparent !important;
        border-radius: 10px;
        color: #4b6b58 !important;
        font-weight: 600;
        padding: 10px 18px;
    }
    button[aria-selected="true"] {
        background: #ffffff !important;
        box-shadow: 0 3px 12px rgba(5, 46, 22, 0.1) !important;
        color: #14532d !important;
        font-weight: 700 !important;
        border: 1px solid rgba(20, 83, 45, 0.2) !important;
    }

    /* Sidebar Selected Animal Tags (replaces bright red pills with sage green) */
    span[data-baseweb="tag"] {
        background-color: #dcfce7 !important;
        border: 1px solid #86efac !important;
        border-radius: 8px !important;
    }
    span[data-baseweb="tag"] * {
        color: #14532d !important;
        font-weight: 600 !important;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ==============================================================================
# 2. SMART SPECIES NAME, HABITAT EMOJI & TAXON CLEANER
# ==============================================================================
# Prefix lookup: catches base species AND subspecies/author tags like "(Linnaeus, 1758)"
# Format: "Latin prefix": ("Regular English Name", "Map Pin Emoji", "Habitat Key Emoji")
SPECIES_CATALOG = {
    "Acinonyx jubatus": ("Cheetah", "🐆", "🐾"),
    "Aptenodytes forsteri": ("Emperor Penguin", "🐧", "🌊"),
    "Falco peregrinus": ("Peregrine Falcon", "🦅", "🪽"),
    "Giraffa camelopardalis": ("Giraffe", "🦒", "🐾"),
    "Balaenoptera musculus": ("Blue Whale", "🐋", "🌊"),
    "Varanus komodoensis": ("Komodo Dragon", "🦎", "🐾"),
    "Danaus plexippus": ("Monarch Butterfly", "🦋", "🪽"),
    "Panthera leo": ("African Lion", "🦁", "🐾"),
    "Panthera onca": ("Jaguar", "🐆", "🐾"),
    "Panthera tigris": ("Tiger", "🐅", "🐾"),
    "Ursus maritimus": ("Polar Bear", "🐻‍❄️", "🐾"),
    "Chelonia mydas": ("Green Sea Turtle", "🐢", "🌊"),
    "Caretta caretta": ("Loggerhead Sea Turtle", "🐢", "🌊"),
    "Ornithorhynchus anatinus": ("Platypus", "🦫", "🌊"),
    "Odobenus rosmarus": ("Walrus", "🦭", "🌊"),
    "Haliaeetus leucocephalus": ("Bald Eagle", "🦅", "🪽"),
    "Lynx canadensis": ("Canada Lynx", "🐈", "🐾"),
}

# Center coordinates for country initials so they sit cleanly on the map
COUNTRY_CENTROIDS = {
    "United States of America": ("US", 39.8, -98.5),
    "United States": ("US", 39.8, -98.5),
    "Namibia": ("NA", -22.5, 17.0),
    "South Africa": ("ZA", -30.5, 22.9),
    "Kenya": ("KE", -0.02, 37.9),
    "Tanzania": ("TZ", -6.3, 34.8),
    "Botswana": ("BW", -22.3, 24.6),
    "Indonesia": ("ID", -2.5, 118.0),
    "Australia": ("AU", -25.2, 133.7),
    "Antarctica": ("AQ", -75.0, 0.0),
    "Canada": ("CA", 56.1, -106.3),
    "Mexico": ("MX", 23.6, -102.5),
    "Brazil": ("BR", -14.2, -51.9),
    "Spain": ("ES", 40.4, -3.7),
    "United Kingdom": ("UK", 55.3, -3.4),
}

def strip_author_tag(sci_name: str) -> str:
    """Cleans 'Caretta caretta (Linnaeus, 1758)' -> 'Caretta caretta' for cleaner display."""
    parts = str(sci_name).strip().split()
    # Keep Genus + species (and subspecies if lowercase, stopping before Capitalized author names)
    clean_parts = []
    for i, word in enumerate(parts):
        if i == 0:
            clean_parts.append(word)
        elif word.startswith("(") or word[0].isupper() or word.isdigit():
            break
        else:
            clean_parts.append(word)
    return " ".join(clean_parts) if clean_parts else str(sci_name).strip()


@st.cache_data(show_spinner=False)
def auto_resolve_species_meta(clean_latin: str) -> tuple[str, str, str]:
    """Automatically fetches English name + habitat icon for any species not hardcoded."""
    common, habitat_icon = fetch_english_name_and_habitat(clean_latin)
    pin_emoji = "🕷️" if "theraphosidae" in clean_latin.lower() else habitat_icon
    return (common, pin_emoji, habitat_icon)


def lookup_species_meta(sci_name: str) -> tuple[str, str, str]:
    """Checks manual catalog first, then auto-resolves any new animal via GBIF."""
    raw = str(sci_name).strip()
    for prefix, meta in SPECIES_CATALOG.items():
        if raw.lower().startswith(prefix.lower()):
            return meta

    clean_latin = strip_author_tag(raw)
    return auto_resolve_species_meta(clean_latin)


def get_common_name(sci_name: str) -> str:
    return lookup_species_meta(sci_name)[0]


def get_species_emoji(sci_name: str) -> str:
    return lookup_species_meta(sci_name)[1]


def format_species_label(sci_name: str) -> str:
    """Formats as '🪽 Monarch Butterfly (Danaus plexippus)' with habitat emoji + English name."""
    common, _, habitat_icon = lookup_species_meta(sci_name)
    clean_latin = strip_author_tag(sci_name)
    if common.lower() != clean_latin.lower():
        return f"{habitat_icon} {common} ({clean_latin})"
    return f"{habitat_icon} {clean_latin}"

# ==============================================================================
# 3. CACHED SUPABASE DATA LOADER
# ==============================================================================
@st.cache_data(ttl=60)
def load_all_saved_wildlife() -> pd.DataFrame:
    """Pulls every distinct species and occurrence stored in Supabase."""
    records = fetch_all_occurrences()

    if not records:
        return pd.DataFrame()

    df = pd.DataFrame(records)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude", "scientific_name"])
    df["scientific_name"] = df["scientific_name"].astype(str).str.strip()
    df["country"] = df["country"].fillna("Unknown").astype(str).str.strip()
    df["common_name"] = df["scientific_name"].apply(get_common_name)
    df["display_name"] = df["scientific_name"].apply(format_species_label)
    df["emoji"] = df["scientific_name"].apply(get_species_emoji)
    return df

@st.cache_data(ttl=3600)
def get_cached_diet_roles(species_tuple: tuple[str, ...]) -> dict[str, dict]:
    return classify_species_diets(list(species_tuple))
# ==============================================================================
# 4. SIDEBAR: LIVE GBIF INGESTION & DYNAMIC SPECIES FILTER
# ==============================================================================
with st.sidebar:
    st.markdown('<div class="pill-badge">🌿 Field Controls</div>', unsafe_allow_html=True)
    st.header("Data Management")

    search_query = st.text_input(
        "🔍 Search Any Animal:",
        placeholder="e.g., Aardvark, Cheetah, Danaus plexippus",
    )

    record_limit = st.slider(
        "Number of records to fetch:",
        min_value=25,
        max_value=300,
        value=150,
        step=25,
    )

    # Track search & warning states so notifications clear automatically on tab switches
    if "last_failed_query" not in st.session_state:
        st.session_state.last_failed_query = ""
    if "no_records_msg" not in st.session_state:
        st.session_state.no_records_msg = ""

    resolved_info = None
    clean_q = search_query.strip()

    # Clear the "no records" warning automatically if the user changes the search text
    if clean_q != st.session_state.get("last_searched_for_records", ""):
        st.session_state.no_records_msg = ""

    if clean_q:
        corrected_query = check_species_spelling(clean_q)
        # First try GBIF directly; if not found, auto-translate to Latin scientific name and retry
        resolved_info = resolve_species_name(corrected_query)
        if not resolved_info:
            auto_sci = translate_to_scientific_name(corrected_query)
            if auto_sci:
                resolved_info = resolve_species_name(corrected_query, fallback_sci_name=auto_sci)

        if resolved_info:
            sci = resolved_info.get("scientific_name", corrected_query)
            fam = resolved_info.get("family", "Unknown")
            st.success(f"✓ Matched GBIF Taxon ({fam}):")
            st.code(sci, language=None)
            st.session_state.last_failed_query = ""
        else:
            if clean_q != st.session_state.last_failed_query:
                st.session_state.last_failed_query = clean_q
                st.toast(f"'{clean_q}' couldn't be found within GBIF.", icon="⚠️")

    if st.button("➕ Add Your Animal Record to Database", use_container_width=True):
        st.session_state.last_searched_for_records = clean_q
        if not clean_q:
            st.toast("Type an animal name first!", icon="⚠️")
        elif not resolved_info:
            st.session_state.no_records_msg = f"Sorry, we couldn't find '{clean_q}' within GBIF."
        else:
            target_sci = resolved_info.get("scientific_name")
            target_key = resolved_info.get("taxon_key")
            with st.spinner(f"Fetching {record_limit} sightings for {target_sci}..."):
                new_records = fetch_species_occurrences(
                    target_sci, limit=record_limit, taxon_key=target_key
                )
                if new_records:
                    st.session_state.no_records_msg = ""
                    upsert_occurrences(new_records)
                    st.cache_data.clear()
                    st.toast(f"Added {len(new_records)} records for {target_sci}!", icon="✅")
                    st.rerun()
                else:
                    st.session_state.no_records_msg = (
                        f"Sorry, we couldn't find any GPS-tagged records for **{target_sci}** in GBIF."
                    )

    if st.session_state.no_records_msg:
        st.warning(st.session_state.no_records_msg)
        st.session_state.no_records_msg = ""

    st.divider()
    st.header("Map & View Filters")

# Load everything currently saved in Supabase
df = load_all_saved_wildlife()

if df.empty:
    st.warning("No wildlife sightings found in Supabase yet. Use the sidebar to pull your first species!")
    st.stop()

# Automatically lists EVERY species in Supabase (including newly pulled ones like Danaus plexippus)
all_display_species = sorted(df["display_name"].unique().tolist())

with st.sidebar:
    selected_species = st.multiselect(
        "Active Species on Display:",
        options=all_display_species,
        default=all_display_species,  # Keeps newly ingested animals visible right away!
    )

filtered_df = df[df["display_name"].isin(selected_species)].copy()

if filtered_df.empty:
    st.info("Pick at least one species in the sidebar filter to view the dashboard.")
    st.stop()

# ==============================================================================
# 5. DASHBOARD HEADER & TOP 4 KPI CARDS
# ==============================================================================
st.markdown('<div class="pill-badge">🐾 Wildlife & Habitat Tracker</div>', unsafe_allow_html=True)
st.title("Species Explorer Dashboard")

total_sightings = len(filtered_df)
species_count = filtered_df["display_name"].nunique()
countries_count = filtered_df[filtered_df["country"] != "Unknown"]["country"].nunique()
top_country = (
    filtered_df[filtered_df["country"] != "Unknown"]["country"].mode()[0]
    if countries_count > 0
    else "Global / Ocean"
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(
        f"""
        <div class="glass-card-kpi">
            <div class="kpi-title">Active Sightings</div>
            <div class="kpi-value">{total_sightings:,}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        f"""
        <div class="glass-card-kpi">
            <div class="kpi-title">Species Displayed</div>
            <div class="kpi-value">{species_count}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        f"""
        <div class="glass-card-kpi">
            <div class="kpi-title">Countries Covered</div>
            <div class="kpi-value">{countries_count}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col4:
    st.markdown(
        f"""
        <div class="glass-card-kpi">
            <div class="kpi-title">Top Hotspot</div>
            <div class="kpi-value-sm">{top_country}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.write("")

# ==============================================================================
# 6. MAIN TABS: 3D GLOBE | TRENDS & SEASONALITY | CONSERVATION & AI REPORTS
# ==============================================================================
tab1, tab2, tab3 = st.tabs(
    [
        "🗺️ Global 3D Map",
        "📊 Species Trends & Charts",
        "🌿 Wildlife Preservation & Field Reports",
    ]
)

# ------------------------------------------------------------------------------
# TAB 1: 3D GLOBE + COUNTRY LOOKUP
# ------------------------------------------------------------------------------
with tab1:
    st.subheader("🌍 Global Sightings & Country Map")

    globe_fig = go.Figure()

    # 1. Cluster Density Halos (glowing rings where sightings group together)
    cluster_df = (
        filtered_df.assign(
            lat_bin=filtered_df["latitude"].round(0),
            lon_bin=filtered_df["longitude"].round(0),
        )
        .groupby(["lat_bin", "lon_bin"])
        .size()
        .reset_index(name="cluster_size")
    )
    hotspots = cluster_df[cluster_df["cluster_size"] >= 3]
    if not hotspots.empty:
        halo_colors = [
            "rgba(220, 38, 38, 0.35)" if c >= 15 else
            "rgba(217, 119, 6, 0.35)" if c >= 7 else
            "rgba(22, 163, 74, 0.35)"
            for c in hotspots["cluster_size"]
        ]
        globe_fig.add_trace(
            go.Scattergeo(
                lat=hotspots["lat_bin"],
                lon=hotspots["lon_bin"],
                mode="markers",
                marker=dict(
                    size=hotspots["cluster_size"].clip(upper=35) + 12,
                    color=halo_colors,
                    line=dict(width=0),
                ),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # 2. Individual Animal Pins with Common + Scientific Name in Hover Tooltip
    for sp_label, group in filtered_df.groupby("display_name"):
        emoji_icon = group["emoji"].iloc[0]
        date_series = (
            group["event_date"].fillna("Unknown")
            if "event_date" in group.columns
            else pd.Series(["Unknown"] * len(group))
        )
        globe_fig.add_trace(
            go.Scattergeo(
                lat=group["latitude"],
                lon=group["longitude"],
                mode="text",
                text=[emoji_icon] * len(group),
                textfont=dict(size=18),
                name=sp_label,
                customdata=np.stack(
                    [group["display_name"], group["country"], date_series],
                    axis=-1,
                ),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Country: %{customdata[1]}<br>"
                    "Date: %{customdata[2]}<br>"
                    "Coords: (%{lat:.2f}, %{lon:.2f})<extra></extra>"
                ),
            )
        )

    # 3. Centered Country Initials (US, NA, AU, etc.)
    active_countries = filtered_df["country"].unique()
    code_lats, code_lons, code_texts = [], [], []
    for c_name in active_countries:
        if c_name in COUNTRY_CENTROIDS:
            iso, c_lat, c_lon = COUNTRY_CENTROIDS[c_name]
            code_texts.append(iso)
            code_lats.append(c_lat)
            code_lons.append(c_lon)

    if code_texts:
        globe_fig.add_trace(
            go.Scattergeo(
                lat=code_lats,
                lon=code_lons,
                mode="text",
                text=code_texts,
                textfont=dict(size=11, color="#052e16", family="Arial Black"),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    globe_fig.update_geos(
        projection_type="orthographic",
        showland=True,
        landcolor="#4d7c5b",
        showocean=True,
        oceancolor="#1e4e68",
        showcountries=True,
        countrycolor="rgba(255, 255, 255, 0.65)",
        countrywidth=0.8,
        showcoastlines=True,
        coastlinecolor="rgba(255, 255, 255, 0.8)",
        bgcolor="rgba(0,0,0,0)",
    )
    globe_fig.update_layout(
        height=560,
        margin=dict(l=0, r=0, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#052e16", family="sans-serif", size=12),
        legend=dict(
            title=dict(text="<b>Species Key</b><br>🪽 Air | 🌊 Sea | 🐾 Land"),
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.01,
            bgcolor="rgba(255,255,255,0.92)",
            bordercolor="rgba(20,83,45,0.25)",
            borderwidth=1,
            itemsizing="constant",
        ),
    )
    st.plotly_chart(globe_fig, use_container_width=True)

    # Country Drill-Down Table below the globe
    st.markdown("### 🔎 Country Wildlife Lookup")
    country_options = ["All Active Nations"] + sorted(
        [c for c in filtered_df["country"].unique() if c != "Unknown"]
    )
    selected_country = st.selectbox("Select a Country to Inspect:", country_options)

    if selected_country == "All Active Nations":
        summary_tbl = (
            filtered_df.groupby(["country", "display_name"])
            .size()
            .reset_index(name="Sightings")
            .sort_values("Sightings", ascending=False)
        )
        st.dataframe(summary_tbl, use_container_width=True, hide_index=True)
    else:
        country_subset = filtered_df[filtered_df["country"] == selected_country]
        st.info(
            f"**{selected_country}** has **{len(country_subset)}** recorded sightings across "
            f"**{country_subset['display_name'].nunique()}** species."
        )
        with st.expander("View Full GPS Sightings Table"):
            cols_to_show = [
                c
                for c in ["occurrence_id", "display_name", "latitude", "longitude", "event_date"]
                if c in country_subset.columns
            ]
            st.dataframe(country_subset[cols_to_show], use_container_width=True, hide_index=True)

# ------------------------------------------------------------------------------
# TAB 2: 12-MONTH SEASONALITY MATRIX, FOOD WEB & DISTRIBUTIONS
# ------------------------------------------------------------------------------
with tab2:
    st.subheader("📊 Species Trends & Ecosystem Analytics")

    chart_choice = st.radio(
        "Choose Visualization:",
        [
            "📅 12-Month Observation & Seasonality Matrix",
            "🌿 Biome & Habitat Distribution",
            "🥩 Trophic Diet & Food Roles",
            "📈 Population & Latitudinal Distributions",
        ],
        horizontal=True,
    )

    # 1. RESTORED 12-Month Observation & Seasonality Matrix
    if chart_choice == "📅 12-Month Observation & Seasonality Matrix":
        date_col = "event_date" if "event_date" in filtered_df.columns else None
        if date_col:
            season_df = filtered_df.copy()
            season_df["parsed_date"] = pd.to_datetime(season_df[date_col], errors="coerce")
            season_df = season_df.dropna(subset=["parsed_date"])

            if not season_df.empty:
                season_df["month_abbr"] = season_df["parsed_date"].dt.strftime("%b")
                month_order = [
                    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
                    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
                ]
                pivot_matrix = (
                    season_df.groupby(["display_name", "month_abbr"])
                    .size()
                    .unstack(fill_value=0)
                    .reindex(columns=month_order, fill_value=0)
                )

                fig_season = px.imshow(
                    pivot_matrix,
                    labels=dict(x="Month of Observation", y="Species", color="Sightings"),
                    x=month_order,
                    y=pivot_matrix.index,
                    color_continuous_scale="Greens",
                    text_auto=True,
                    aspect="auto",
                    title="12-Month Observation & Migration Seasonality Matrix",
                )
                fig_season.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#052e16", family="sans-serif"),
                    height=440,
                )
                st.plotly_chart(fig_season, use_container_width=True)
            else:
                st.warning("None of the currently selected records have valid dates to plot by month.")
        else:
            st.warning("No `event_date` column found in the dataset.")

# 2A. Dynamic Biome & Habitat Distribution (Side-by-Side: Chart + Visual Habitat Cards)
    elif chart_choice == "🌿 Biome & Habitat Distribution":
        def classify_dynamic_biome(row) -> str:
            abs_lat = abs(row["avg_lat"])
            emoji = str(row["emoji"])

            if "🌊" in emoji:
                return "Polar & Subpolar Seas" if abs_lat >= 55 else "Temperate & Tropical Oceans"
            if "🪽" in emoji:
                return "Boreal & Temperate Flyways" if abs_lat >= 45 else "Tropical & Migratory Flyways"

            if abs_lat >= 55:
                return "Arctic Tundra & Boreal"
            elif abs_lat >= 23.5:
                return "Temperate Grasslands & Forests"
            else:
                return "Tropical Savannas & Rainforests"

        biome_df = (
            filtered_df.groupby(["display_name", "scientific_name", "emoji"], as_index=False)
            .agg(
                sightings=("latitude", "count"),
                avg_lat=("latitude", "mean"),
                top_country=("country", lambda s: s.mode().iloc[0] if not s.mode().empty else "Global"),
            )
        )
        biome_df["biome"] = biome_df.apply(classify_dynamic_biome, axis=1)
        biome_df["short_label"] = biome_df["display_name"].apply(lambda s: s.split(" (")[0])

        col_chart, col_cards = st.columns([1.4, 1], gap="large")

        with col_chart:
            fig_biome = px.treemap(
                biome_df,
                path=["biome", "short_label"],
                values="sightings",
                color="biome",
                maxdepth=2,
                custom_data=["display_name"],
                title="Dynamic Species-to-Biome Habitat Distribution (Click to Zoom)",
                color_discrete_sequence=["#14532d", "#166534", "#0f766e", "#15803d", "#047857"],
            )
            fig_biome.update_traces(
                textinfo="label+value+percent parent",
                textfont=dict(family="Inter, Segoe UI, Arial, sans-serif", size=15, color="#ffffff"),
                marker=dict(line=dict(color="#e8ece9", width=3)),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Active Sightings: %{value}<br>"
                    "Share of Biome: %{percentParent:.1%}<extra></extra>"
                ),
            )
            fig_biome.update_layout(
                margin=dict(t=50, l=5, r=5, b=5),
                height=560,
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, Segoe UI, Arial, sans-serif", color="#052e16", size=14),
            )
            st.plotly_chart(fig_biome, use_container_width=True)

        with col_cards:
            st.markdown("#### 🌍 Species Biome & Habitat Roster")
            selected_biome = st.selectbox(
                "Filter roster by ecological biome:",
                ["All Biomes"] + sorted(biome_df["biome"].unique().tolist()),
                key="biome_roster_filter",
            )
            roster_df = (
                biome_df
                if selected_biome == "All Biomes"
                else biome_df[biome_df["biome"] == selected_biome]
            )

            with st.container(height=470):
                for _, row in roster_df.iterrows():
                    photo_url = fetch_animal_photo(row["scientific_name"])
                    hemisphere = "N" if row["avg_lat"] >= 0 else "S"
                    c_img, c_txt = st.columns([1, 2.2])
                    with c_img:
                        if photo_url:
                            st.image(photo_url, use_container_width=True)
                    with c_txt:
                        st.markdown(f"**{row['short_label']}** · `{row['biome']}`")
                        st.caption(
                            f"📍 **Top Hotspot:** {row['top_country']} ({abs(row['avg_lat']):.1f}°{hemisphere}) · "
                            f"**{row['sightings']}** sightings"
                        )
                    st.divider()

# 2B. AI-Classified Trophic Diet & Food Roles (Side-by-Side: Chart + Visual Prey Cards)
    elif chart_choice == "🥩 Trophic Diet & Food Roles":
        diet_df = (
            filtered_df.groupby(["display_name", "scientific_name"], as_index=False)
            .size()
            .rename(columns={"size": "sightings"})
        )
        diet_df["short_label"] = diet_df["display_name"].apply(lambda s: s.split(" (")[0])

        with st.spinner("Classifying ecological diet roles..."):
            diet_map = get_cached_diet_roles(tuple(sorted(diet_df["short_label"].unique())))

        diet_df["trophic_role"] = diet_df["short_label"].apply(
            lambda x: diet_map.get(x, {}).get("role", "Omnivore")
        )
        diet_df["primary_diet"] = diet_df["short_label"].apply(
            lambda x: diet_map.get(x, {}).get("diet", "Varied natural diet")
        )

        col_chart, col_cards = st.columns([1.4, 1], gap="large")

        with col_chart:
            fig_diet = px.treemap(
                diet_df,
                path=["trophic_role", "short_label"],
                values="sightings",
                color="trophic_role",
                maxdepth=2,
                custom_data=["display_name", "primary_diet"],
                title="Trophic Diet & Ecological Food Roles (Click to Zoom)",
                color_discrete_sequence=["#7f1d1d", "#9a3412", "#14532d", "#0f766e", "#1d4ed8"],
            )
            fig_diet.update_traces(
                textinfo="label+value",
                textfont=dict(family="Inter, Segoe UI, Arial, sans-serif", size=15, color="#ffffff"),
                marker=dict(line=dict(color="#e8ece9", width=3)),
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Primary Diet: %{customdata[1]}<br>"
                    "Active Sightings: %{value}<extra></extra>"
                ),
            )
            fig_diet.update_layout(
                margin=dict(t=50, l=5, r=5, b=5),
                height=560,
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, Segoe UI, Arial, sans-serif", color="#052e16", size=14),
            )
            st.plotly_chart(fig_diet, use_container_width=True)

        with col_cards:
            st.markdown("#### 🍽️ Species Diet & Prey Roster")
            selected_role = st.selectbox(
                "Filter roster by trophic group:",
                ["All Roles"] + sorted(diet_df["trophic_role"].unique().tolist()),
                key="diet_role_filter",
            )
            roster_df = (
                diet_df
                if selected_role == "All Roles"
                else diet_df[diet_df["trophic_role"] == selected_role]
            )

            with st.container(height=470):
                for _, row in roster_df.iterrows():
                    photo_url = fetch_animal_photo(row["scientific_name"])
                    c_img, c_txt = st.columns([1, 2.2])
                    with c_img:
                        if photo_url:
                            st.image(photo_url, use_container_width=True)
                    with c_txt:
                        st.markdown(f"**{row['short_label']}** · `{row['trophic_role']}`")
                        st.caption(f"🥗 **Eats:** {row['primary_diet']} ({row['sightings']} sightings)")
                    st.divider()

    # 3. Population Counts & Latitudinal Distribution
    else:
        c1, c2 = st.columns(2)
        with c1:
            counts_df = (
                filtered_df.groupby("display_name")
                .size()
                .reset_index(name="Sightings")
                .sort_values("Sightings", ascending=True)
            )
            fig_bar = px.bar(
                counts_df,
                x="Sightings",
                y="display_name",
                orientation="h",
                title="Recorded Sightings per Species",
                color_discrete_sequence=["#15803d"],
            )
            fig_bar.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#052e16"),
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        with c2:
            fig_lat = px.box(
                filtered_df,
                x="display_name",
                y="latitude",
                title="Latitudinal Habitat Spread (North vs. South)",
                color_discrete_sequence=["#14532d"],
            )
            fig_lat.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color="#052e16"),
                xaxis_title="",
            )
            st.plotly_chart(fig_lat, use_container_width=True)

# ------------------------------------------------------------------------------
# TAB 3: WILDLIFE PRESERVATION, RADAR TRAITS & AI FIELD REPORTS
# ------------------------------------------------------------------------------
with tab3:
    st.subheader("🌿 Wildlife Preservation & Habitat Insights")

    analysis_mode = st.radio(
        "Select Preservation Analysis:",
        [
            "🧬 Species Vitality & Trait Ratings (1–10)",
            "⚖️ Interspecies Habitat & Range Comparison",
            "📋 Field Conservation Brief & Q&A",
        ],
        horizontal=True,
    )

    # Map display label -> raw scientific_name & common_name for your llm_service functions
    label_to_sci = dict(zip(filtered_df["display_name"], filtered_df["scientific_name"]))
    label_to_common = dict(zip(filtered_df["display_name"], filtered_df["common_name"]))
    species_options = sorted(list(label_to_sci.keys()))

    # Mode 1: Animal Photo on Left + Signature Trait & 1-10 Progress Breakdown on Right
    if analysis_mode == "🧬 Species Vitality & Trait Ratings (1–10)":
        target_label = st.selectbox("Select Species for Trait Profile:", species_options)
        if st.button("Generate Trait Profile"):
            sci_name = label_to_sci[target_label]
            com_name = label_to_common[target_label]
            with st.spinner(f"Loading field photo and trait ratings for {target_label}..."):
                stats_dict = generate_species_stats(com_name, sci_name)
                photo_url = fetch_animal_photo(sci_name, com_name)

                # Separate numeric 1-10 scores from text fields (e.g., signature_trait)
                numeric_traits = {
                    k: float(v)
                    for k, v in stats_dict.items()
                    if isinstance(v, (int, float))
                }
                text_notes = {
                    k: str(v)
                    for k, v in stats_dict.items()
                    if not isinstance(v, (int, float))
                }

                # Grab the signature trait title if present
                sig_trait = next(iter(text_notes.values()), "Apex Ecological Adaptation")

                # Side-by-side 2-column layout (Animal Photo on left, Signature Card + Bars on right)
                col_photo, col_breakdown = st.columns([1.05, 1])

                with col_photo:
                    if photo_url:
                        st.image(
                            photo_url,
                            caption=f"{com_name} ({sci_name})",
                            use_container_width=True,
                        )
                    else:
                        # Fallback card if Wikipedia doesn't have a photo for that taxon
                        st.markdown(
                            f"""
                            <div class="glass-card-content" style="text-align: center; padding: 60px 20px;">
                                <div style="font-size: 4rem;">{get_species_emoji(sci_name)}</div>
                                <div class="kpi-value-sm" style="margin-top: 10px;">{com_name}</div>
                                <div style="color: #3f624d;"><i>{sci_name}</i></div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                with col_breakdown:
                    # 1. Top Signature Evolutionary Trait Card
                    st.markdown(
                        f"""
                        <div class="glass-card-content" style="margin-bottom: 18px;">
                            <div class="kpi-title">SIGNATURE EVOLUTIONARY TRAIT</div>
                            <div class="kpi-value-sm" style="margin: 6px 0;">✨ {sig_trait}</div>
                            <div style="font-size: 0.88rem; color: #3f624d;">
                                Taxonomic Target: <i>{sci_name}</i>
                            </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    # 2. Attribute Breakdown (1-10 Scale) with Progress Bars
                    st.markdown("**Attribute Breakdown (1–10 Scale):**")
                    for raw_key, score in numeric_traits.items():
                        clean_label = raw_key.replace("_", " ").title()
                        st.markdown(f"• **{clean_label}:** `{int(score)}/10`")
                        st.progress(min(max(score / 10.0, 0.0), 1.0))

    # Mode 2: Side-by-Side Comparison using generate_comparative_assessment(...)
    elif analysis_mode == "⚖️ Interspecies Habitat & Range Comparison":
        if len(species_options) < 2:
            st.info("Add at least two species to compare them side by side.")
        else:
            col_a, col_b = st.columns(2)
            with col_a:
                sp1_label = st.selectbox("Species A:", species_options, index=0)
            with col_b:
                sp2_label = st.selectbox("Species B:", species_options, index=1)

            if st.button("Compare Species"):
                sci_a, sci_b = label_to_sci[sp1_label], label_to_sci[sp2_label]
                sub_a = filtered_df[filtered_df["scientific_name"] == sci_a]
                sub_b = filtered_df[filtered_df["scientific_name"] == sci_b]

                summary_a = {
                    "sightings": len(sub_a),
                    "countries": sub_a["country"].unique().tolist(),
                    "avg_lat": round(float(sub_a["latitude"].mean()), 2),
                }
                summary_b = {
                    "sightings": len(sub_b),
                    "countries": sub_b["country"].unique().tolist(),
                    "avg_lat": round(float(sub_b["latitude"].mean()), 2),
                }

                with st.spinner(f"Comparing {sp1_label} vs. {sp2_label}..."):
                    comp_text = generate_comparative_assessment(
                        sp1_label, sp2_label, summary_a, summary_b
                    )
                    st.markdown(
                        f'<div class="glass-card-content">{comp_text}</div>',
                        unsafe_allow_html=True,
                    )

    # Mode 3: Field Conservation Brief & Q&A using generate_conservation_report & answer_animal_question
    else:
        brief_label = st.selectbox("Select Animal for Briefing:", species_options)
        sci_brief = label_to_sci[brief_label]
        sp_subset = filtered_df[filtered_df["scientific_name"] == sci_brief]

        payload = {
            "common_name": label_to_common[brief_label],
            "total_sightings": len(sp_subset),
            "countries": sp_subset["country"].unique().tolist(),
            "lat_range": [
                round(float(sp_subset["latitude"].min()), 2),
                round(float(sp_subset["latitude"].max()), 2),
            ],
        }

        if st.button("Generate Field Conservation Brief"):
            with st.spinner(f"Writing conservation report for {brief_label}..."):
                report = generate_conservation_report(sci_brief, payload)
                st.markdown(
                    f'<div class="glass-card-content">{report}</div>',
                    unsafe_allow_html=True,
                )

        st.divider()
        user_q = st.text_input(
            f"Ask a field question about {brief_label}:",
            placeholder="e.g., What are the biggest threats to their migration routes?",
        )
        if user_q.strip():
            with st.spinner("Analyzing field data..."):
                answer = answer_animal_question(sci_brief, user_q, payload)
                st.markdown(
                    f'<div class="glass-card-content">{answer}</div>',
                    unsafe_allow_html=True,
                )