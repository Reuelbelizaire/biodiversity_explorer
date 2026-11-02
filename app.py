import streamlit as st
import pandas as pd
import plotly.express as px

from gbif_client import fetch_species_occurrences, resolve_species_name
from db_loader import upsert_occurrences, fetch_occurrences_by_species
from llm_service import generate_conservation_report, answer_animal_question
# Page Configuration
st.set_page_config(page_title="WildTrack | Biodiversity Explorer", layout="wide", page_icon="🌿")

# --- Frosted Glass & Light Mint Styling ---
st.markdown("""
<style>
    /* Smooth Transitions & Ambient Background */
    .stApp {
        background: radial-gradient(circle at 10% 20%, #f4fbf7 0%, #e8f5ee 50%, #dff2e7 100%);
        color: #1a382b;
    }

    /* Interactive Frosted Glass Cards */
    .glass-card {
        background: rgba(255, 255, 255, 0.65);
        backdrop-filter: blur(16px);
        -webkit-backdrop-filter: blur(16px);
        border: 1px solid rgba(110, 231, 183, 0.4);
        border-radius: 20px;
        padding: 20px 24px;
        box-shadow: 0 8px 32px 0 rgba(16, 185, 129, 0.06);
        transition: transform 0.25s ease, box-shadow 0.25s ease;
    }
    .glass-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 12px 36px 0 rgba(16, 185, 129, 0.12);
        border-color: rgba(5, 150, 105, 0.4);
    }

    /* Glowing Badge */
    .pill-badge {
        background: linear-gradient(135deg, #d1fae5, #a7f3d0);
        border: 1px solid #6ee7b7;
        color: #065f46;
        border-radius: 9999px;
        padding: 4px 14px;
        font-size: 0.75rem;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        display: inline-block;
        box-shadow: 0 2px 8px rgba(16, 185, 129, 0.15);
    }
</style>
""", unsafe_allow_html=True)
# Species Lookup Directory
SPECIES_CATALOG = {
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

# --- Sidebar: Ingestion & Filter Controls ---
st.sidebar.markdown("<div class='pill-badge'>🌿 Control Station</div>", unsafe_allow_html=True)
st.sidebar.header("Data Management")

# Ingestion Section: Dynamic Search + Catalog Fallback
search_query = st.sidebar.text_input("🔍 Search Any Animal:", placeholder="e.g., Squirrel, Bald Eagle, Caretta caretta")
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
            
            # Automatically add to directory so it can be selected in display filters
            if target_ingest_label not in SPECIES_CATALOG:
                SPECIES_CATALOG[target_ingest_label] = ingest_scientific
        else:
            st.sidebar.error("Species not found or unsupported by GBIF API.")
else:
    target_ingest_label = st.sidebar.selectbox("Or choose from catalog:", list(SPECIES_CATALOG.keys()))
    ingest_scientific = SPECIES_CATALOG[target_ingest_label]

if st.sidebar.button("Ingest from GBIF to Supabase", use_container_width=True):
    if ingest_scientific:
        with st.spinner(f"Querying GBIF API for {target_ingest_label}..."):
            new_records = fetch_species_occurrences(ingest_scientific, limit=fetch_count)
            if new_records:
                upsert_occurrences(new_records)
                st.sidebar.success(f"Saved {len(new_records)} sightings into Supabase!")
                st.rerun()
            else:
                st.sidebar.warning("No records found with valid GPS coordinates.")
    else:
        st.sidebar.warning("Please enter a valid animal name first.")

st.sidebar.write("---")
st.sidebar.subheader("Map & View Filters")

# Fall back to the first available catalog species if target_ingest_label is None or not found
catalog_options = list(SPECIES_CATALOG.keys())
safe_default = [target_ingest_label] if target_ingest_label in catalog_options else [catalog_options[0]]

selected_species_labels = st.sidebar.multiselect(
    "Active Species on Display:",
    options=catalog_options,
    default=safe_default
)

# --- Data Loading ---
all_records = []
for label in selected_species_labels:
    sci_name = SPECIES_CATALOG[label]
    species_data = fetch_occurrences_by_species(sci_name)
    for row in species_data:
        row["common_name"] = label
        all_records.append(row)

# Header Section
st.markdown("<div class='pill-badge'>🐾 Global Wildlife & Migration Intelligence</div>", unsafe_allow_html=True)
st.title("Biodiversity Analytics Studio")

if all_records:
    df = pd.DataFrame(all_records)
    df["latitude"] = pd.to_numeric(df["latitude"], errors="coerce")
    df["longitude"] = pd.to_numeric(df["longitude"], errors="coerce")
    df = df.dropna(subset=["latitude", "longitude"])

    # High-Level Metric Ribbon
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.markdown(f"""
        <div class="glass-card">
            <div class="kpi-title">Active Sightings</div>
            <div class="kpi-value">{len(df):,}</div>
        </div>
        """, unsafe_allow_html=True)
    with k2:
        st.markdown(f"""
        <div class="glass-card">
            <div class="kpi-title">Species Displayed</div>
            <div class="kpi-value">{df['common_name'].nunique()}</div>
        </div>
        """, unsafe_allow_html=True)
    with k3:
        st.markdown(f"""
        <div class="glass-card">
            <div class="kpi-title">Countries Covered</div>
            <div class="kpi-value">{df['country'].nunique()}</div>
        </div>
        """, unsafe_allow_html=True)
    with k4:
        top_nation = df['country'].value_counts().index[0] if not df['country'].empty else "N/A"
        st.markdown(f"""
        <div class="glass-card">
            <div class="kpi-title">Top Hotspot</div>
            <div class="kpi-value" style="font-size: 1.4rem;">{top_nation}</div>
        </div>
        """, unsafe_allow_html=True)

    # --- Multi-Tab Interface ---
    tab_map, tab_analytics, tab_llm = st.tabs([
        "🗺️ Geospatial Studio", 
        "📊 Interactive Chart Studio", 
        "🤖 AI Conservation Brief"
    ])

    # Plotly transparent styling helper
    def style_plotly_chart(fig):
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#1a382b", family="sans-serif"),
            margin=dict(l=10, r=10, t=35, b=10)
        )
        return fig

##WORK IN PROGRESS
# TAB 1: Global Map with Cumulative Progressive Playback
    with tab_map:
        st.subheader("Global Species Distribution & Progressive Timeline")

        # 1. Parse and validate dates
        map_df = df.copy()
        map_df["parsed_date"] = pd.to_datetime(map_df["event_date"], errors="coerce")
        temporal_df = map_df.dropna(subset=["parsed_date"]).copy()

        # 2. Extract year (or 'year_month' if you want tighter monthly increments)
        temporal_df["timeline_step"] = temporal_df["parsed_date"].dt.year.astype(int)

        # Build progressive cumulative frames
        if not temporal_df.empty and temporal_df["timeline_step"].nunique() > 1:
            min_step = temporal_df["timeline_step"].min()
            max_step = temporal_df["timeline_step"].max()
            
            # Generate a continuous sequence including any empty intervening years
            all_steps = list(range(min_step, max_step + 1))

            cumulative_rows = []
            for current_step in all_steps:
                # Keep all observations recorded up to the current timeline step
                subset = temporal_df[temporal_df["timeline_step"] <= current_step].copy()
                if not subset.empty:
                    subset["animation_frame"] = str(current_step)
                    cumulative_rows.append(subset)

            if cumulative_rows:
                anim_df = pd.concat(cumulative_rows, ignore_index=True)
                anim_df = anim_df.sort_values(["animation_frame", "common_name"])

                fig_map = px.scatter_geo(
                    anim_df,
                    lat="latitude",
                    lon="longitude",
                    color="common_name",
                    hover_name="common_name",
                    hover_data={"country": True, "event_date": True, "latitude": False, "longitude": False},
                    animation_frame="animation_frame",
                    projection="natural earth",
                    color_discrete_sequence=["#059669", "#0284c7", "#d97706", "#7c3aed", "#e11d48", "#10b981"]
                )
            else:
                anim_df = None
        else:
            anim_df = None

        # Fallback to static scatter map if insufficient time-series spread exists
        if anim_df is None:
            fig_map = px.scatter_geo(
                df,
                lat="latitude",
                lon="longitude",
                color="common_name",
                hover_name="common_name",
                hover_data={"country": True, "event_date": True, "latitude": False, "longitude": False},
                projection="natural earth",
                color_discrete_sequence=["#059669", "#0284c7", "#d97706", "#7c3aed", "#e11d48", "#10b981"]
            )

        # Styling
        fig_map.update_geos(
            bgcolor="rgba(0,0,0,0)",
            showland=True, landcolor="#e7f4ed",
            showocean=True, oceancolor="#f0f9f5",
            showlakes=True, lakecolor="#f0f9f5",
            showcountries=True, countrycolor="#c2e5d3"
        )

        fig_map.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#1a382b", family="sans-serif"),
            margin=dict(l=10, r=10, t=35, b=10)
        )

        st.plotly_chart(fig_map, use_container_width=True)
    # TAB 2: Dynamic Chart Picker
    with tab_analytics:
        st.subheader("Custom Analytics Studio")
        
        c_spec, c_metric, c_chart = st.columns(3)
        with c_spec:
            spec_focus = st.selectbox("Focus Species", ["All Active"] + list(df["common_name"].unique()))
        with c_metric:
            metric_target = st.selectbox("Data Dimension", ["Country Distribution", "Observation Protocols (Basis)"])
        with c_chart:
            chart_style = st.selectbox("Chart Style", ["Horizontal Bar Chart", "Donut Breakdown", "Treemap"])

        chart_df = df if spec_focus == "All Active" else df[df["common_name"] == spec_focus]
        col_name = "country" if "Country" in metric_target else "basis_of_record"

        if not chart_df.empty:
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
                fig_c.update_layout(yaxis=dict(autorange="reversed"))
                st.plotly_chart(style_plotly_chart(fig_c), use_container_width=True)

            elif chart_style == "Donut Breakdown":
                fig_c = px.pie(
                    summary.head(8),
                    names=col_name,
                    values="count",
                    hole=0.45,
                    color_discrete_sequence=["#059669", "#34d399", "#6ee7b7", "#a7f3d0", "#cbf5dd"]
                )
                st.plotly_chart(style_plotly_chart(fig_c), use_container_width=True)

            elif chart_style == "Treemap":
                fig_c = px.treemap(
                    summary.head(15),
                    path=[col_name],
                    values="count",
                    color="count",
                    color_continuous_scale=["#a7f3d0", "#059669"]
                )
                st.plotly_chart(style_plotly_chart(fig_c), use_container_width=True)

    # TAB 3: DeepSeek Field Report
    # TAB 3: DeepSeek Field Report & Q&A
    with tab_llm:
        st.subheader("Automated Ecological Intelligence")
        
        target_llm_species = st.selectbox("Select Animal for Report:", options=df["common_name"].unique())
        sub_df = df[df["common_name"] == target_llm_species]
        
        # 1. Conservation Brief Button & Output
        if st.button("Generate Field Assessment", use_container_width=True):
            top_locs = ", ".join(sub_df["country"].value_counts().head(3).index.tolist())
            dates = sub_df["event_date"].dropna()
            date_range = f"{dates.min()[:4]} - {dates.max()[:4]}" if not dates.empty else "N/A"
            
            payload = {
                "total_count": len(sub_df),
                "top_countries": top_locs if top_locs else "Global Waters / Unassigned",
                "date_range": date_range
            }
            
            with st.spinner("DeepSeek is evaluating population density and threats..."):
                report = generate_conservation_report(SPECIES_CATALOG[target_llm_species], payload)
                st.markdown(f"""
                <div class="glass-card" style="line-height:1.7; font-size:0.95rem; border-left: 4px solid #059669;">
                    {report}
                </div>
                """, unsafe_allow_html=True)

        st.write("---")

        # 2. Ask Animal Facts / Interactive Q&A
        st.subheader(f"💬 Ask an Expert About {target_llm_species}")
        user_query = st.text_input(
            "Ask anything (diet, behavior, threats, or why they appear in certain locations):",
            placeholder=f"e.g., Why do {target_llm_species}s thrive in this region?"
        )

        if st.button("Ask an AI conservationist", use_container_width=False):
            if user_query.strip():
                with st.spinner("Consulting ecological records..."):
                    qa_context = {
                        "total_count": len(sub_df),
                        "top_countries": ", ".join(sub_df["country"].value_counts().head(3).index.tolist())
                    }
                    answer = answer_animal_question(SPECIES_CATALOG[target_llm_species], user_query, qa_context)
                    st.markdown(f"""
                    <div class="glass-card" style="margin-top: 15px; border-left: 4px solid #10b981;">
                        <strong>Q: {user_query}</strong><br><br>
                        {answer}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.warning("Please type a question first.")
                
else:
    st.info("No records are currently loaded in your database for these species. Use the sidebar to fetch initial records from GBIF into Supabase.")