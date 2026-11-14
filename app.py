import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import networkx as nx

from gbif_client import fetch_species_occurrences, resolve_species_name
from db_loader import upsert_occurrences, fetch_occurrences_by_species
from llm_service import (
    generate_conservation_report,
    answer_animal_question,
    generate_species_stats,
    generate_comparative_assessment,
    check_species_spelling
)

# Page Configuration
st.set_page_config(page_title="WildTrack | Species Explorer", layout="wide", page_icon="🌿")

# --- Option 4: Rainforest Canopy Styling (High-Contrast & Highly Legible) ---
st.markdown("""
<style>
    /* 1. App Background - Soft Sage Mist */
    .stApp {
        background: #e8ece9 !important;
        color: #052e16 !important;
    }

    /* 2. Sidebar - Crisp White with Deep Green Accents */
    [data-testid="stSidebar"] {
        background-color: #f3f6f4 !important;
        border-right: 1px solid rgba(20, 83, 45, 0.15) !important;
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

    /* 3. Top Header Bar */
    header[data-testid="stHeader"] {
        background-color: #e8ece9 !important;
    }

    /* 4. Top KPI Metric Cards (Solid White, Deep Borders, High Contrast) */
    .glass-card-kpi {
        background: #ffffff !important;
        border: 1px solid rgba(20, 83, 45, 0.18) !important;
        border-left: 5px solid #14532d !important;   /* Bold Rainforest Green accent */
        border-radius: 16px;
        padding: 16px 20px;
        box-shadow: 0 4px 20px rgba(5, 46, 22, 0.06);
        height: 120px !important;
        display: flex;
        flex-direction: column;
        justify_content: space-between;
        overflow: hidden;
        transition: transform 0.25s ease, box-shadow 0.25s ease;
    }
    .glass-card-kpi:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 24px rgba(5, 46, 22, 0.12);
        border-color: #15803d !important;
    }

    /* 5. Dynamic Content & Bio-Stat Cards */
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
        transition: transform 0.25s ease, box-shadow 0.25s ease;
    }
    .glass-card-content:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(5, 46, 22, 0.12);
        border-color: #15803d !important;
    }

    /* 6. Typography & Text Contrast */
    .kpi-title {
        color: #3f624d !important;                  /* Clear Muted Olive-Green */
        font-size: 0.8rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 2px;
    }

    .kpi-value {
        color: #052e16 !important;                  /* Deepest Black-Forest Green */
        font-size: 2rem;
        font-weight: 800;
        line-height: 1.1;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .kpi-value-sm {
        color: #15803d !important;                  /* Rich Emerald-Leaf Green */
        font-size: 1.35rem;
        font-weight: 800;
        line-height: 1.2;
        overflow: hidden;
        text-overflow: ellipsis;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
    }

    /* 7. Pill Badges - Sage Green with Forest Green Text */
    .pill-badge {
        background: #dcfce7 !important;
        border: 1px solid #86efac !important;
        color: #14532d !important;
        border-radius: 9999px;
        padding: 4px 14px;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.03em;
        display: inline-block;
        margin-bottom: 6px;
        box-shadow: 0 2px 6px rgba(20, 83, 45, 0.08);
    }

    /* 8. Tabs Styling */
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

    /* 9. Multiselect Selected Tags */
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
""", unsafe_allow_html=True)
# Species Catalog (Dynamic Session Storage)
DEFAULT_CATALOG = {
    "Cheetah": "Acinonyx jubatus",
    "Emperor Penguin": "Aptenodytes forsteri",
    "Peregrine Falcon": "Falco peregrinus",
    "Giraffe": "Giraffa camelopardalis",
    "Blue Whale": "Balaenoptera musculus",
    "Snow Leopard": "Panthera uncia",
    "Bald Eagle": "Haliaeetus leucocephalus",
    "Polar Bear": "Ursus maritimus",
    "African Elephant": "Loxodonta africana",
    "Koala": "Phascolarctos cinereus",
    "Tiger": "Panthera tigris",
    "Monarch Butterfly": "Danaus plexippus",
    "Loggerhead Sea Turtle": "Caretta caretta"
}

if "species_catalog" not in st.session_state:
    st.session_state.species_catalog = DEFAULT_CATALOG.copy()

if "emoji_cache" not in st.session_state:
    st.session_state.emoji_cache = {
        "Cheetah": "🐆", "Emperor Penguin": "🐧", "Peregrine Falcon": "🦅",
        "Giraffe": "🦒", "Blue Whale": "🐋", "Snow Leopard": "🐆",
        "Bald Eagle": "🦅", "Polar Bear": "🐻‍❄️", "African Elephant": "🐘",
        "Koala": "🐨", "Tiger": "🐅", "Monarch Butterfly": "🦋",
        "Loggerhead Sea Turtle": "🐢", "Gorilla": "🦍", "Jaguar": "🐆"
    }

def resolve_icon(common: str) -> str:
    if common in st.session_state.emoji_cache:
        return st.session_state.emoji_cache[common]
    name_low = common.lower()
    keyword_rules = {
        "bear": "🐻", "whale": "🐋", "shark": "🦈", "bird": "🐦",
        "eagle": "🦅", "turtle": "🐢", "wolf": "🐺", "cat": "🐆",
        "snake": "🐍", "owl": "🦉", "dolphin": "🐬", "fox": "🦊"
    }
    for kw, icon in keyword_rules.items():
        if kw in name_low:
            st.session_state.emoji_cache[common] = icon
            return icon
    st.session_state.emoji_cache[common] = "🐾"
    return "🐾"

def get_country_code(name: str) -> str:
    words = str(name).strip().split()
    if len(words) >= 2:
        return f"{words[0][0]}{words[1][0]}".upper()
    return str(name)[:2].upper()

# --- Sidebar: Data Ingestion & Search ---
st.sidebar.markdown("<div class='pill-badge'>🌿 Field Controls</div>", unsafe_allow_html=True)
st.sidebar.header("Data Management")

search_query = st.sidebar.text_input("🔍 Search Any Animal:", placeholder="e.g., Cheetah, Bald Eagle, Lynx")
fetch_count = st.sidebar.slider("Number of records to fetch:", min_value=50, max_value=300, value=150, step=25)

target_ingest_label = None
ingest_scientific = None

if search_query.strip():
    with st.spinner("Resolving taxonomy with GBIF..."):
        match_info = resolve_species_name(search_query)
        if match_info:
            target_ingest_label = match_info["canonical_name"]
            ingest_scientific = match_info["canonical_name"]
            st.sidebar.success(f"✓ Matched: **{target_ingest_label}** ({match_info['family']})")
            st.session_state.species_catalog[target_ingest_label] = ingest_scientific
        else:
            with st.spinner("Consulting ecological directory..."):
                suggestion = check_species_spelling(search_query)
                st.sidebar.warning(f"Did you mean: **{suggestion}**?")
                if st.sidebar.button(f"Search for '{suggestion}'"):
                    clean_sug = suggestion.split("(")[0].strip()
                    sug_info = resolve_species_name(clean_sug)
                    if sug_info:
                        target_ingest_label = sug_info["canonical_name"]
                        ingest_scientific = sug_info["canonical_name"]
                        st.session_state.species_catalog[target_ingest_label] = ingest_scientific
                        st.rerun()
else:
    target_ingest_label = st.sidebar.selectbox("Or choose from catalog:", list(st.session_state.species_catalog.keys()))
    ingest_scientific = st.session_state.species_catalog[target_ingest_label]

if st.sidebar.button("Ingest Records to Database", use_container_width=True):
    if ingest_scientific:
        with st.spinner(f"Querying global records for {target_ingest_label}..."):
            new_records = fetch_species_occurrences(ingest_scientific, limit=fetch_count)
            if new_records:
                upsert_occurrences(new_records)
                st.sidebar.success(f"Saved {len(new_records)} sightings successfully!")
                st.rerun()
            else:
                st.sidebar.warning("No records found with valid GPS coordinates.")
    else:
        st.sidebar.warning("Please enter a valid animal name first.")

st.sidebar.write("---")
st.sidebar.subheader("Map & View Filters")

catalog_options = list(st.session_state.species_catalog.keys())
safe_default = [target_ingest_label] if target_ingest_label in catalog_options else [catalog_options[0]]

selected_species_labels = st.sidebar.multiselect(
    "Active Species on Display:",
    options=catalog_options,
    default=safe_default
)

# --- Data Loading ---
all_records = []
for label in selected_species_labels:
    sci_name = st.session_state.species_catalog[label]
    species_data = fetch_occurrences_by_species(sci_name)
    for row in species_data:
        row["common_name"] = label
        row["scientific_name"] = sci_name
        all_records.append(row)

# Header Section
st.markdown("<div class='pill-badge'>🐾 Wildlife & Habitat Tracker</div>", unsafe_allow_html=True)
st.title("Species Explorer Dashboard")

if all_records:
    df = pd.DataFrame(all_records)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])

    # High-Level Metric Ribbon
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
        <div class="glass-card-kpi">
            <div class="kpi-title">Active Sightings</div>
            <div class="kpi-value">{len(df):,}</div>
        </div>
        """, unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div class="glass-card-kpi">
            <div class="kpi-title">Species Displayed</div>
            <div class="kpi-value">{df['common_name'].nunique()}</div>
        </div>
        """, unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div class="glass-card-kpi">
            <div class="kpi-title">Countries Covered</div>
            <div class="kpi-value">{df['country'].nunique()}</div>
        </div>
        """, unsafe_allow_html=True)
    with k4:
        top_nation = df['country'].value_counts().index[0] if not df['country'].empty else "N/A"
        st.markdown(f"""
        <div class="glass-card-kpi">
            <div class="kpi-title">Top Hotspot</div>
            <div class="kpi-value-sm" title="{top_nation}">{top_nation}</div>
        </div>
        """, unsafe_allow_html=True)

    tab_map, tab_analytics, tab_llm = st.tabs([
        "🗺️ Global 3D Map", 
        "📊 Species Trends & Charts", 
        "🌿 Wildlife Preservation & Field Reports"
    ])

    # ------------------------------------------------------------------
    # TAB 1: Global 3D Map & Country Lookup
    # ------------------------------------------------------------------
    with tab_map:
        st.subheader("🌍 Global Sightings & Country Map")

        globe_fig = go.Figure()
        pts_df = df.copy()

        # 1. State / Country Initials Stamped Centrally on Territory
        country_geo = pts_df.groupby("country").agg(
            lat_center=("latitude", "mean"),
            lon_center=("longitude", "mean"),
            total_records=("occurrence_id", "count"),
            species_count=("common_name", "nunique")
        ).reset_index()

        country_geo["code"] = country_geo["country"].apply(get_country_code)

        globe_fig.add_trace(go.Scattergeo(
            lat=country_geo["lat_center"],
            lon=country_geo["lon_center"],
            mode="text",
            name="Territory Initials",
            text=[f"<b>{row['code']}</b>" for _, row in country_geo.iterrows()],
            textposition="middle center",
            textfont=dict(
                family="Arial Black, Impact, sans-serif",
                size=12,
                color="#ffffff"
            ),
            hovertext=[
                f"<b>🌐 {row['country']} ({row['code']})</b><br>"
                f"• Verified Observations: {row['total_records']}<br>"
                f"• Monitored Taxa: {row['species_count']} species"
                for _, row in country_geo.iterrows()
            ],
            hoverinfo="text",
            showlegend=False
        ))

        # 2. Localized Cluster Density Halos
        pts_df["lat_cluster"] = pts_df["latitude"].round(1)
        pts_df["lon_cluster"] = pts_df["longitude"].round(1)

        cluster_summary = pts_df.groupby(["lat_cluster", "lon_cluster"]).agg(
            cluster_count=("occurrence_id", "count"),
            lat_mean=("latitude", "mean"),
            lon_mean=("longitude", "mean")
        ).reset_index()

        halo_colors = []
        halo_sizes = []
        for count in cluster_summary["cluster_count"]:
            if count >= 15:
                halo_colors.append("rgba(239, 68, 68, 0.45)")
                halo_sizes.append(28)
            elif count >= 5:
                halo_colors.append("rgba(245, 158, 11, 0.40)")
                halo_sizes.append(18)
            else:
                halo_colors.append("rgba(16, 185, 129, 0.35)")
                halo_sizes.append(12)

        globe_fig.add_trace(go.Scattergeo(
            lat=cluster_summary["lat_mean"],
            lon=cluster_summary["lon_mean"],
            mode="markers",
            name="Density Halos",
            marker=dict(
                size=halo_sizes,
                color=halo_colors,
                symbol="circle"
            ),
            hoverinfo="none",
            showlegend=False
        ))

        # 3. Species Markers with Dynamic Icons & Rich Tooltips
        for spec_name in pts_df["common_name"].unique():
            spec_sub = pts_df[pts_df["common_name"] == spec_name]
            icon = resolve_icon(spec_name)

            hover_cards = []
            for _, row in spec_sub.iterrows():
                card = (
                    f"<b>{icon} {row['common_name']}</b><br>"
                    f"<i>Taxonomy:</i> {row.get('scientific_name', 'Verified Binomial')}<br>"
                    f"<i>Country:</i> {row.get('country', 'Natural Habitat')}<br>"
                    f"<i>Coordinates:</i> {row['latitude']:.2f}°, {row['longitude']:.2f}°<br>"
                    f"<i>Observed:</i> {str(row.get('event_date', 'N/A'))[:10]}<br>"
                    f"<b>── Ecological Details ──</b><br>"
                    f"• Monitoring Status: Active Record<br>"
                    f"• Basis: {row.get('basis_of_record', 'Observation')}"
                )
                hover_cards.append(card)

            globe_fig.add_trace(go.Scattergeo(
                lat=spec_sub["latitude"],
                lon=spec_sub["longitude"],
                mode="markers+text",
                name=f"{icon} {spec_name}",
                text=[icon] * len(spec_sub),
                textposition="middle center",
                textfont=dict(size=13),
                hovertext=hover_cards,
                hoverinfo="text",
                marker=dict(
                    size=14,
                    color="#ffffff",
                    opacity=0.92,
                    line=dict(color="#0f172a", width=1.4)
                )
            ))

        # 4. Realistic Earth Globe Styling
        globe_fig.update_geos(
            projection_type="orthographic",
            fitbounds=False,
            projection_scale=0.92,
            visible=True,
            showocean=True,
            oceancolor="#154284",
            showland=True,
            landcolor="#2d6a4f",
            showlakes=True,
            lakecolor="#154284",
            showrivers=True,
            rivercolor="#154284",
            showcountries=True,
            countrycolor="rgba(255, 255, 255, 0.45)",
            showcoastlines=True,
            coastlinecolor="rgba(255, 255, 255, 0.8)",
            framecolor="rgba(0,0,0,0)",
            bgcolor="rgba(0,0,0,0)",
            resolution=110
        )

        globe_fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#052e16", family="sans-serif"),
            margin=dict(l=0, r=0, t=10, b=10),
            height=660,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=0.01,
                xanchor="center",
                x=0.5,
                bgcolor="rgba(255, 255, 255, 0.75)",
                bordercolor="rgba(110, 231, 183, 0.5)",
                borderwidth=1,
                font=dict(color="#052e16", size=12)
            )
        )

        st.plotly_chart(globe_fig, use_container_width=True)

        # 5. Territorial Inspection Panel
        st.markdown("<hr style='border: 0.5px solid rgba(110, 231, 183, 0.4); margin: 25px 0;'>", unsafe_allow_html=True)
        st.markdown("<div class='pill-badge'>🔎 Geographic Drill-Down</div>", unsafe_allow_html=True)
        st.subheader("Country Wildlife Lookup")

        available_countries = sorted([c for c in df["country"].dropna().unique() if c != "Unknown"])
        
        c_select, c_kpi1, c_kpi2 = st.columns([2, 1, 1])
        with c_select:
            selected_country = st.selectbox(
                "Select a Country to Inspect Wildlife Presence:",
                options=["All Active Nations"] + available_countries,
                key="drilldown_country_select"
            )

        country_sub = df if selected_country == "All Active Nations" else df[df["country"] == selected_country]

        with c_kpi1:
            st.metric("Total Sightings in Territory", f"{len(country_sub):,}")
        with c_kpi2:
            st.metric("Unique Species Logged", f"{country_sub['common_name'].nunique()}")

        if selected_country == "All Active Nations":
            st.markdown("#### 🌐 Global Territory Sighting Leaderboard")
            global_summary = country_sub.groupby("country").agg(
                Sightings=("occurrence_id", "count"),
                Species_Count=("common_name", "nunique")
            ).reset_index().sort_values("Sightings", ascending=False)
            global_summary.columns = ["Territory / Country", "Total Recorded Sightings", "Unique Species Observed"]
            st.dataframe(global_summary, use_container_width=True, hide_index=True)
        else:
            st.markdown(f"#### 🐾 Wildlife Documented in **{selected_country}**")
            spec_summary = country_sub.groupby("common_name").agg(
                Sightings=("occurrence_id", "count"),
                First_Seen=("event_date", "min"),
                Latest_Seen=("event_date", "max")
            ).reset_index().sort_values("Sightings", ascending=False)
            spec_summary.columns = ["Species", "Recorded Sightings", "Earliest Date", "Most Recent Date"]
            st.dataframe(spec_summary, use_container_width=True, hide_index=True)

        with st.expander(f"📋 View Full Georeferenced Sightings ({selected_country})"):
            display_cols = ["common_name", "scientific_name", "latitude", "longitude", "event_date", "basis_of_record"]
            clean_table = country_sub[[c for c in display_cols if c in country_sub.columns]].copy()
            st.dataframe(clean_table, use_container_width=True, hide_index=True)

    # ------------------------------------------------------------------
    # TAB 2: Species Trends & Charts
    # ------------------------------------------------------------------
    with tab_analytics:
        st.subheader("📊 Species Trends & Ecological Distributions")

        studio_mode = st.radio(
            "Select Analysis View:",
            ["🕸️ Food Web & Ecosystem Links", "📈 Where Sightings Occur", "📅 Seasonal Sighting Trends"],
            horizontal=True
        )

        st.markdown("<hr style='border: 0.5px solid rgba(110, 231, 183, 0.4); margin: 15px 0;'>", unsafe_allow_html=True)

        if studio_mode == "🕸️ Food Web & Ecosystem Links":
            st.markdown("#### 🕸️ Food Web & Trophic Network")
            st.caption("Visualizing ecological feeding dependencies and primary producers across active monitored species.")

            ECOLOGICAL_EDGES = [
                ("Cheetah", "Giraffe", "Preys on calves"),
                ("Cheetah", "Savanna Herbivores", "Apex predation"),
                ("Savanna Herbivores", "Acacia & Grasslands", "Primary grazing"),
                ("Giraffe", "Acacia & Grasslands", "Browsing vegetation"),
                ("African Elephant", "Acacia & Grasslands", "Keystone herbivory"),
                ("Polar Bear", "Pinnipeds / Seals", "Primary predator"),
                ("Pinnipeds / Seals", "Arctic Marine Fish", "Foraging"),
                ("Arctic Marine Fish", "Marine Phytoplankton", "Primary feeding"),
                ("Blue Whale", "Krill & Plankton", "Filter feeding"),
                ("Emperor Penguin", "Antarctic Krill & Squid", "Secondary consumer"),
                ("Antarctic Krill & Squid", "Marine Phytoplankton", "Primary consumption"),
                ("Loggerhead Sea Turtle", "Jellyfish & Crabs", "Omnivorous foraging"),
                ("Jellyfish & Crabs", "Marine Phytoplankton", "Planktonic feeding"),
                ("Tiger", "Wild Ungulates & Boars", "Apex predation"),
                ("Wild Ungulates & Boars", "Forest Flora", "Herbivory"),
                ("Snow Leopard", "Mountain Ungulates", "Alpine apex predation"),
                ("Mountain Ungulates", "Alpine Shrubs", "Browsing"),
                ("Bald Eagle", "Freshwater / Estuary Fish", "Opportunistic predation"),
                ("Peregrine Falcon", "Small Migratory Birds", "Aerial predation"),
                ("Small Migratory Birds", "Seeds & Insects", "Foraging"),
                ("Koala", "Eucalyptus Foliage", "Specialized folivory"),
                ("Monarch Butterfly", "Milkweed & Nectar", "Pollination / Feeding")
            ]

            G = nx.DiGraph()
            active_species_set = set(df["common_name"].unique())

            for source, target, relationship in ECOLOGICAL_EDGES:
                if source in active_species_set or any(active in source for active in active_species_set):
                    G.add_edge(source, target, label=relationship)

            if len(G.nodes) == 0:
                for spec in active_species_set:
                    G.add_edge(spec, "Local Trophic Base", label="Ecosystem interaction")

            pos = nx.spring_layout(G, k=0.85, seed=42)

            edge_x, edge_y = [], []
            for edge in G.edges():
                x0, y0 = pos[edge[0]]
                x1, y1 = pos[edge[1]]
                edge_x.extend([x0, x1, None])
                edge_y.extend([y0, y1, None])

            edge_trace = go.Scatter(
                x=edge_x, y=edge_y,
                line=dict(width=1.5, color="rgba(5, 150, 105, 0.45)"),
                hoverinfo="none",
                mode="lines"
            )

            node_x, node_y, node_color, node_text, node_size = [], [], [], [], []
            for node in G.nodes():
                x, y = pos[node]
                node_x.append(x)
                node_y.append(y)
                
                if node in active_species_set:
                    node_size.append(26)
                    node_color.append("#059669")
                    count = len(df[df["common_name"] == node])
                    node_text.append(f"<b>🐾 Active Monitored Species: {node}</b><br>• Local Observations: {count:,}<br>• Status: Key Consumer")
                else:
                    node_size.append(16)
                    node_color.append("#10b981")
                    node_text.append(f"<b>🌿 Ecosystem Connector: {node}</b><br>• Role: Trophic Base / Forage Target")

            node_trace = go.Scatter(
                x=node_x, y=node_y,
                mode="markers+text",
                hoverinfo="text",
                text=[n for n in G.nodes()],
                textposition="top center",
                textfont=dict(size=11, family="sans-serif", color="#1a382b"),
                hovertext=node_text,
                marker=dict(
                    color=node_color,
                    size=node_size,
                    line=dict(width=2, color="#ffffff")
                )
            )

            fig_web = go.Figure(
                data=[edge_trace, node_trace],
                layout=go.Layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    showlegend=False,
                    hovermode="closest",
                    margin=dict(b=20, l=10, r=10, t=20),
                    xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                    height=520
                )
            )
            st.plotly_chart(fig_web, use_container_width=True)

        elif studio_mode == "📈 Where Sightings Occur":
            c_spec, c_metric, c_chart = st.columns(3)
            with c_spec:
                spec_focus = st.selectbox("Focus Species:", ["All Active"] + list(df["common_name"].unique()), key="analytics_spec_focus")
            with c_metric:
                metric_target = st.selectbox("Data Dimension:", ["Country Distribution", "Observation Protocols (Basis)"], key="analytics_metric_target")
            with c_chart:
                chart_style = st.selectbox("Chart Style:", ["Horizontal Bar Chart", "Donut Breakdown", "Treemap", "Latitudinal Gradient Ridge"], key="analytics_chart_style")

            chart_df = df if spec_focus == "All Active" else df[df["common_name"] == spec_focus]
            col_name = "country" if "Country" in metric_target else "basis_of_record"

            if not chart_df.empty:
                if chart_style == "Latitudinal Gradient Ridge":
                    st.markdown("#### 🌐 Latitudinal Distribution Profile (Equator vs. Poles)")
                    st.caption("Distribution of sightings from South Pole (-90°) through Equator (0°) to North Pole (+90°).")
                    
                    fig_ridge = px.histogram(
                        chart_df,
                        x="latitude",
                        color="common_name",
                        nbins=35,
                        marginal="box",
                        color_discrete_sequence=["#059669", "#0284c7", "#d97706", "#7c3aed", "#e11d48"],
                        labels={"latitude": "Latitude Coordinate (Degrees)"}
                    )
                    fig_ridge.update_layout(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(color="#052e16", family="sans-serif"),
                        margin=dict(l=10, r=10, t=30, b=10),
                        height=440
                    )
                    st.plotly_chart(fig_ridge, use_container_width=True)

                else:
                    summary = chart_df[col_name].value_counts().reset_index()
                    summary.columns = [col_name, "count"]

                    if chart_style == "Horizontal Bar Chart":
                        fig_c = px.bar(
                            summary.head(10),
                            x="count",
                            y=col_name,
                            orientation="h",
                            color="count",
                            color_continuous_scale=["#6ee7b7", "#059669"]
                        )
                        fig_c.update_layout(
                            yaxis=dict(autorange="reversed"),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#052e16", family="sans-serif"),
                            margin=dict(l=10, r=10, t=20, b=10),
                            height=440
                        )
                        st.plotly_chart(fig_c, use_container_width=True)

                    elif chart_style == "Donut Breakdown":
                        fig_c = px.pie(
                            summary.head(8),
                            names=col_name,
                            values="count",
                            hole=0.45,
                            color_discrete_sequence=["#059669", "#34d399", "#6ee7b7", "#a7f3d0", "#cbf5dd"]
                        )
                        fig_c.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#052e16", family="sans-serif"),
                            margin=dict(l=10, r=10, t=20, b=10),
                            height=440
                        )
                        st.plotly_chart(fig_c, use_container_width=True)

                    elif chart_style == "Treemap":
                        fig_c = px.treemap(
                            summary.head(15),
                            path=[col_name],
                            values="count",
                            color="count",
                            color_continuous_scale=["#a7f3d0", "#059669"]
                        )
                        fig_c.update_layout(
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(color="#052e16", family="sans-serif"),
                            margin=dict(l=10, r=10, t=20, b=10),
                            height=440
                        )
                        st.plotly_chart(fig_c, use_container_width=True)

        elif studio_mode == "📅 Seasonal Sighting Trends":
            st.markdown("#### 📅 12-Month Sighting & Migration Patterns")
            st.caption("Tracking observation frequency across all 12 calendar months to highlight seasonal peaks.")

            season_df = df.copy()
            season_df["parsed_date"] = pd.to_datetime(season_df["event_date"], errors="coerce")
            valid_season = season_df.dropna(subset=["parsed_date"]).copy()

            if not valid_season.empty:
                valid_season["Month"] = valid_season["parsed_date"].dt.strftime("%b")
                valid_season["Month_Num"] = valid_season["parsed_date"].dt.month

                month_order = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
                pivot_counts = valid_season.groupby(["common_name", "Month", "Month_Num"]).size().reset_index(name="sightings")
                
                heatmap_matrix = pivot_counts.pivot(index="common_name", columns="Month", values="sightings").fillna(0)
                for m in month_order:
                    if m not in heatmap_matrix.columns:
                        heatmap_matrix[m] = 0
                heatmap_matrix = heatmap_matrix[month_order]

                fig_season = px.imshow(
                    heatmap_matrix,
                    labels=dict(x="Calendar Month", y="Species", color="Sightings"),
                    x=month_order,
                    y=heatmap_matrix.index,
                    color_continuous_scale=["#f0fdf4", "#a7f3d0", "#10b981", "#047857"]
                )
                fig_season.update_layout(
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font=dict(color="#052e16", family="sans-serif"),
                    margin=dict(l=10, r=10, t=25, b=10),
                    height=380
                )
                st.plotly_chart(fig_season, use_container_width=True)
            else:
                st.info("Insufficient observation timestamps available to construct annual seasonal trends.")

    # ------------------------------------------------------------------
    # TAB 3: Wildlife Preservation & Field Reports
    # ------------------------------------------------------------------
    with tab_llm:
        st.subheader("🌿 Wildlife Preservation & Habitat Insights")

        llm_mode = st.radio(
            "Select Preservation Analysis:",
            ["🧬 Species Vitality & Trait Ratings (1–10)", "⚖️ Interspecies Habitat & Range Comparison", "📋 Field Conservation Brief & Q&A"],
            horizontal=True
        )

        st.markdown("<hr style='border: 0.5px solid rgba(110, 231, 183, 0.4); margin: 15px 0;'>", unsafe_allow_html=True)

        # --------------------------------------------------------------
        # MODULE 1: Species Vitality & Trait Ratings (1-10 Scale)
        # --------------------------------------------------------------
        if llm_mode == "🧬 Species Vitality & Trait Ratings (1–10)":
            st.markdown("#### 🧬 Biological Trait Radar & Ability Profile")
            st.caption("Ecological ratings on a 1–10 scale reflecting physical attributes and evolutionary adaptations.")

            stat_target = st.selectbox("Select Animal to Evaluate:", options=df["common_name"].unique(), key="stat_target_spec")
            sci_target = st.session_state.species_catalog[stat_target]

            col_radar, col_meta = st.columns([1.2, 1])

            with st.spinner(f"Evaluating ecological attributes for {stat_target}..."):
                stats_data = generate_species_stats(stat_target, sci_target)

            with col_radar:
                categories = ["Strength", "Speed", "Endurance", "Stealth", "Habitat Threat"]
                values = [
                    stats_data.get("strength", 5),
                    stats_data.get("speed", 5),
                    stats_data.get("endurance", 5),
                    stats_data.get("stealth", 5),
                    stats_data.get("threat_level", 5)
                ]

                # Close radar polygon loop
                categories.append(categories[0])
                values.append(values[0])

                fig_radar = go.Figure()
                fig_radar.add_trace(go.Scatterpolar(
                    r=values,
                    theta=categories,
                    fill='toself',
                    fillcolor="rgba(16, 185, 129, 0.35)",
                    line=dict(color="#059669", width=2),
                    name=stat_target
                ))

                fig_radar.update_layout(
                    polar=dict(
                        radialaxis=dict(
                            visible=True,
                            range=[0, 10],
                            tickfont=dict(color="#4b7a64", size=10),
                            gridcolor="rgba(110, 231, 183, 0.4)"
                        ),
                        angularaxis=dict(
                            tickfont=dict(color="#052e16", size=12, family="sans-serif"),
                            gridcolor="rgba(110, 231, 183, 0.4)"
                        )
                    ),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    margin=dict(l=30, r=30, t=25, b=25),
                    height=380,
                    showlegend=False
                )
                st.plotly_chart(fig_radar, use_container_width=True)

            with col_meta:
                # Flexible Card Container (No text cutoff)
                st.markdown(f"""
                <div class="glass-card-content" style="border-left: 4px solid #10b981; margin-bottom: 15px;">
                    <div class="kpi-title">Signature Evolutionary Trait</div>
                    <div style="font-size: 1.15rem; font-weight: 800; color: #064e3b; margin: 4px 0;">
                        ✨ {stats_data.get('signature_skill', 'Natural Resilience')}
                    </div>
                    <div style="font-size: 0.85rem; color: #4b7a64;">
                        Taxonomic Target: <i>{sci_target}</i>
                    </div>
                </div>
                """, unsafe_allow_html=True)

                st.write("**Attribute Breakdown (1–10 Scale):**")
                for cat, val in zip(["Strength", "Speed", "Endurance", "Stealth", "Habitat Threat Level"], values[:-1]):
                    st.write(f"• **{cat}:** `{val}/10`")
                    st.progress(val / 10)

        # --------------------------------------------------------------
        # MODULE 2: Interspecies Habitat & Range Comparison
        # --------------------------------------------------------------
        elif llm_mode == "⚖️ Interspecies Habitat & Range Comparison":
            st.markdown("#### ⚖️ Side-by-Side Species Range Comparison")
            st.caption("Compare ecological footprints, dietary niches, and habitat pressures between two monitored species.")

            unique_species = list(df["common_name"].unique())
            if len(unique_species) >= 2:
                col_a, col_b = st.columns(2)
                with col_a:
                    spec_a = st.selectbox("Species A:", options=unique_species, index=0, key="cmp_spec_a")
                with col_b:
                    spec_b = st.selectbox("Species B:", options=unique_species, index=1, key="cmp_spec_b")

                if st.button("Generate Comparative Range Brief", use_container_width=True):
                    sub_a = df[df["common_name"] == spec_a]
                    sub_b = df[df["common_name"] == spec_b]

                    summary_a = {
                        "count": len(sub_a),
                        "top_loc": sub_a["country"].value_counts().index[0] if not sub_a["country"].empty else "Global Waters"
                    }
                    summary_b = {
                        "count": len(sub_b),
                        "top_loc": sub_b["country"].value_counts().index[0] if not sub_b["country"].empty else "Global Waters"
                    }

                    with st.spinner(f"Evaluating ecological footprints between {spec_a} and {spec_b}..."):
                        audit_result = generate_comparative_assessment(spec_a, spec_b, summary_a, summary_b)
                        st.markdown(f"""
                        <div class="glass-card-content" style="border-left: 4px solid #0284c7; line-height: 1.7; font-size: 0.95rem; margin-top: 15px;">
                            {audit_result}
                        </div>
                        """, unsafe_allow_html=True)
            else:
                st.info("Select or search for at least 2 distinct species in the sidebar to enable comparative reviews.")

        # --------------------------------------------------------------
        # MODULE 3: Field Conservation Brief & Q&A
        # --------------------------------------------------------------
        elif llm_mode == "📋 Field Conservation Brief & Q&A":
            target_llm_species = st.selectbox("Select Animal for Briefing:", options=df["common_name"].unique(), key="llm_select_animal")
            sub_df = df[df["common_name"] == target_llm_species]
            
            if st.button("Generate Preservation Briefing", use_container_width=True, key="btn_field_assessment"):
                top_locs = ", ".join(sub_df["country"].value_counts().head(3).index.tolist())
                dates = sub_df["event_date"].dropna()
                date_range = f"{dates.min()[:4]} - {dates.max()[:4]}" if not dates.empty else "N/A"
                
                payload = {
                    "total_count": len(sub_df),
                    "top_countries": top_locs if top_locs else "Global Waters / Unassigned",
                    "date_range": date_range
                }
                
                with st.spinner("Reviewing population trends and habitat pressures..."):
                    report = generate_conservation_report(st.session_state.species_catalog[target_llm_species], payload)
                    st.markdown(f"""
                    <div class="glass-card-content" style="border-left: 4px solid #059669; line-height: 1.7; font-size: 0.95rem;">
                        {report}
                    </div>
                    """, unsafe_allow_html=True)

            st.write("---")

            st.subheader(f"💬 Ask a Specialist About {target_llm_species}")
            user_query = st.text_input(
                "Ask a question regarding diet, behavior, range shifts, or habitat protection:",
                placeholder=f"e.g., Why do {target_llm_species}s thrive in this region?",
                key="user_animal_query"
            )

            if st.button("Consult Ecological Specialist", use_container_width=False, key="btn_ask_expert"):
                if user_query.strip():
                    with st.spinner("Consulting field records..."):
                        qa_context = {
                            "total_count": len(sub_df),
                            "top_countries": ", ".join(sub_df["country"].value_counts().head(3).index.tolist())
                        }
                        answer = answer_animal_question(st.session_state.species_catalog[target_llm_species], user_query, qa_context)
                        st.markdown(f"""
                        <div class="glass-card-content" style="border-left: 4px solid #10b981; line-height: 1.7; font-size: 0.95rem; margin-top: 15px;">
                            <strong>Q: {user_query}</strong><br><br>
                            {answer}
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.warning("Please enter a question first.")
                
else:
    st.info("No records are currently loaded in your database for these species. Use the sidebar to fetch initial records from GBIF into Supabase.")