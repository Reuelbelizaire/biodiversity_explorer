import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Page Config (must be the first Streamlit call in the script)
st.set_page_config(page_title="WildTrack | Species Analytics", layout="wide", page_icon="🌿")

# Local modules are imported *after* set_page_config so that a broken or stale
# import can be reported in the UI instead of dumping a traceback on every rerun.
try:
    from gbif_client import fetch_species_occurrences
    from db_loader import (
        upsert_occurrences,
        fetch_occurrences_by_species,
        fetch_occurrences_by_species_list,
    )
    from llm_service import generate_conservation_report
except ImportError as exc:
    st.error(f"**The app could not load its own modules:** `{exc}`")
    if "fetch_occurrences_by_species_list" in str(exc):
        st.info(
            "`db_loader.py` on disk defines this function, but the running Streamlit "
            "process is still holding the copy it imported at startup. Stop the server "
            "(Ctrl+C in its terminal) and start it again with `streamlit run app.py`."
        )
    else:
        st.info(
            "A dependency is missing. Run `pip install -r requirements.txt` in the "
            "environment that launches Streamlit, then restart the server."
        )
    st.stop()


# Custom CSS for the Dark Forest Green Aesthetic
st.markdown("""
<style>
    /* Clean, soft modern background */
    .stApp {
        background: radial-gradient(circle at top left, #f4fbf7, #e8f5ee, #daf0e4);
        color: #1a382b;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }

    /* Igloo-style Frosted Glass Card */
    .metric-card {
        background: rgba(255, 255, 255, 0.75);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(134, 239, 172, 0.4);
        border-radius: 20px;
        padding: 22px;
        box-shadow: 0 10px 30px rgba(16, 185, 129, 0.08);
        transition: transform 0.2s ease;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 14px 35px rgba(16, 185, 129, 0.14);
    }

    /* Vibrant Mint Badges */
    .pill-badge {
        background: #d1fae5;
        border: 1px solid #6ee7b7;
        color: #065f46;
        border-radius: 50px;
        padding: 4px 14px;
        font-size: 0.8rem;
        font-weight: 600;
        display: inline-block;
    }

    .metric-title {
        color: #4b7a64;
        font-size: 0.85rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 8px;
    }
    .metric-val {
        color: #064e3b;
        font-size: 2.2rem;
        font-weight: 800;
    }

    /* Tab Styling */
    button[data-baseweb="tab"] {
        border-radius: 12px;
        padding: 8px 16px;
        color: #065f46;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)
# Species Directory
species_options = {
    "Cheetah (Acinonyx jubatus)": "Acinonyx jubatus",
    "Emperor Penguin (Aptenodytes forsteri)": "Aptenodytes forsteri",
    "Peregrine Falcon (Falco peregrinus)": "Falco peregrinus",
    "Giraffe (Giraffa camelopardalis)": "Giraffa camelopardalis"
}

# --- Map helpers -------------------------------------------------------------
# A fixed palette keeps every species the same colour on every rerun, no matter
# in which order Supabase returns the rows.
SPECIES_COLORS = {
    "Acinonyx jubatus": "#4ade80",        # cheetah - mint
    "Aptenodytes forsteri": "#38bdf8",    # emperor penguin - ice blue
    "Falco peregrinus": "#fbbf24",        # peregrine falcon - amber
    "Giraffa camelopardalis": "#f472b6",  # giraffe - rose
}
FALLBACK_COLORS = ["#a78bfa", "#fb7185", "#2dd4bf", "#f97316", "#c084fc", "#eab308"]

# Scientific name -> short label used inside the hover card
COMMON_NAMES = {
    "Acinonyx jubatus": "Cheetah",
    "Aptenodytes forsteri": "Emperor Penguin",
    "Falco peregrinus": "Peregrine Falcon",
    "Giraffa camelopardalis": "Giraffe",
}

# Hover card layout. %{customdata[i]} reads the columns built in
# build_sighting_map(); <extra></extra> hides Plotly's default trace-name box.
HOVER_TEMPLATE = (
    "<b>%{customdata[0]}</b>"
    "<br><span style='color:#8fd6b4; font-size:11px'>%{customdata[1]}</span>"
    "<br><br>📅  %{customdata[2]}"
    "<br>🌍  %{customdata[3]}"
    "<extra></extra>"
)


def _prepare_map_frame(records: list[dict]) -> pd.DataFrame:
    """Normalise coordinates, dates and display labels for the map."""
    frame = pd.DataFrame(records or [])
    if frame.empty:
        return frame

    frame["latitude"] = pd.to_numeric(frame["latitude"], errors="coerce")
    frame["longitude"] = pd.to_numeric(frame["longitude"], errors="coerce")
    frame = frame.dropna(subset=["latitude", "longitude"])
    # Guard against junk coordinates, which would otherwise wreck the fit.
    frame = frame[
        frame["latitude"].between(-90, 90) & frame["longitude"].between(-180, 180)
    ].copy()
    if frame.empty:
        return frame

    observed = pd.to_datetime(frame["event_date"], errors="coerce", format="mixed", utc=True)
    frame["date_label"] = observed.dt.strftime("%d %b %Y").fillna("date not recorded")
    frame["country_label"] = (
        frame["country"].fillna("Unknown country").replace("", "Unknown country").astype(str)
    )
    frame["common_name"] = (
        frame["scientific_name"].map(COMMON_NAMES).fillna(frame["scientific_name"]).astype(str)
    )
    return frame.reset_index(drop=True)


def _padded_span(low: float, high: float, min_span: float, pad: float,
                 floor: float, ceiling: float) -> list[float]:
    """Widen a [low, high] span so dots never sit on the map edge."""
    span = high - low
    if span < min_span:  # a single point (or a tight cluster) must not zoom to max
        middle = (low + high) / 2.0
        low, high = middle - min_span / 2.0, middle + min_span / 2.0
        span = min_span
    margin = min(span * pad, 20.0)  # cap so a near-global spread is not padded in vain
    return [max(low - margin, floor), min(high + margin, ceiling)]


def _fit_ranges(frame: pd.DataFrame, pad: float = 0.18,
                min_span: float = 6.0) -> tuple[list[float], list[float] | None]:
    """Padded lat/lon windows that contain every dot, or (lat, None) if global."""
    lat_low, lat_high = float(frame["latitude"].min()), float(frame["latitude"].max())
    lon_low, lon_high = float(frame["longitude"].min()), float(frame["longitude"].max())

    lat_range = _padded_span(lat_low, lat_high, min_span, pad, -90.0, 90.0)
    # A ~360 degree spread (circumpolar species) cannot be padded without leaving
    # valid coordinates, so hand framing back to Plotly's own fitter.
    if lon_high - lon_low >= 350.0:
        return lat_range, None
    return lat_range, _padded_span(lon_low, lon_high, min_span, pad, -180.0, 180.0)


def build_sighting_map(frame: pd.DataFrame, *, color_by_species: bool = True) -> go.Figure:
    """Global sighting map: one colour per species, auto-fit bounds, hover card."""
    hover_columns = ["common_name", "scientific_name", "date_label", "country_label"]

    color_kwargs = {"color_discrete_sequence": ["#4ade80"]}
    if color_by_species:
        species = list(dict.fromkeys(frame["scientific_name"].astype(str)))
        color_kwargs = {
            "color": "scientific_name",
            "color_discrete_map": {
                name: SPECIES_COLORS.get(name, FALLBACK_COLORS[i % len(FALLBACK_COLORS)])
                for i, name in enumerate(species)
            },
        }

    fig = px.scatter_geo(
        frame,
        lat="latitude",
        lon="longitude",
        projection="natural earth",
        **color_kwargs,
    )

    fig.update_traces(
        # customdata is set through the trace (not the px kwarg) so the block works
        # on both plotly 5.x and 6+/7, where the px kwarg was renamed.
        customdata=frame[hover_columns].to_numpy(),
        marker=dict(size=11, opacity=0.92, line=dict(width=1.1, color="rgba(9,21,16,0.85)")),
        hovertemplate=HOVER_TEMPLATE,
        hoverlabel=dict(
            bgcolor="#0e231b",
            bordercolor="#4ade80",
            font=dict(color="#eafff5", size=13, family="Segoe UI, Helvetica, sans-serif"),
            align="left",
        ),
    )

    fig.update_geos(
        bgcolor="#0e231b",
        showland=True, landcolor="#17382b",
        showocean=True, oceancolor="#091510",
        showlakes=True, lakecolor="#091510",
        showcountries=True, countrycolor="#2b5944",
        showcoastlines=True, coastlinecolor="#2b5944",
        showframe=False,
        lataxis=dict(showgrid=False),
        lonaxis=dict(showgrid=False),
    )

    lat_range, lon_range = _fit_ranges(frame)
    if lon_range is None:
        fig.update_geos(fitbounds="locations")  # Plotly handles the wrap-around
    else:
        fig.update_geos(lataxis_range=lat_range, lonaxis_range=lon_range)

    if color_by_species:
        fig.update_layout(
            legend=dict(
                title=dict(text="Species"),
                bgcolor="rgba(9,21,16,0.55)",
                bordercolor="#2b5944",
                borderwidth=1,
                font=dict(color="#d1fae5", size=12),
            )
        )

    # Fill the Streamlit container so the map is never clipped by the frame.
    fig.update_layout(height=620, margin=dict(l=0, r=0, t=8, b=0))
    return fig

# --- Sidebar Controls ---
st.sidebar.markdown("<div class='top-badge'>🌿 Control Center</div>", unsafe_allow_html=True)
st.sidebar.header("Data Ingestion")
selected_label = st.sidebar.selectbox("Choose Target Species", list(species_options.keys()))
scientific_name = species_options[selected_label]
record_limit = st.sidebar.slider("Records to Fetch", min_value=50, max_value=300, value=150, step=25)
map_scope = st.sidebar.radio(
    "Map Scope",
    ["Selected species", "All stored species"],
    help="'All stored species' feeds the map every species in Supabase and colours the dots by species.",
)

if st.sidebar.button("Ingest GBIF Records to Supabase", width="stretch"):
    with st.spinner(f"Harvesting sightings for {selected_label}..."):
        try:
            new_data = fetch_species_occurrences(scientific_name, limit=record_limit)
            if new_data:
                upsert_occurrences(new_data)
                st.sidebar.success(f"Added {len(new_data)} observations to Supabase!")
            else:
                st.sidebar.warning("No records returned with valid coordinates.")
        except Exception as exc:
            st.sidebar.error(f"Ingestion failed: {exc}")

# Load Active Records from Supabase
records = fetch_occurrences_by_species(scientific_name)

# The map can either follow the sidebar selection or show every species at once.
map_records = (
    fetch_occurrences_by_species_list(list(species_options.values()))
    if map_scope == "All stored species"
    else records
)
map_df = _prepare_map_frame(map_records)

# --- Top Header ---
st.markdown("<div class='top-badge'>🐾 Conservation Intelligence & Spatial Monitoring</div>", unsafe_allow_html=True)
st.title(f"Field Dashboard: {selected_label.split('(')[0].strip()}")

# Same cleaning as the map: numeric coordinates, parsed dates, display labels.
df = _prepare_map_frame(records)
has_records = not df.empty
has_map = not map_df.empty

countries = df["country"].dropna() if has_records else pd.Series(dtype="object")
countries = countries[countries.astype(str).str.strip() != ""]
total_sightings = len(df)
unique_countries = countries.nunique()
top_country = countries.value_counts().index[0] if not countries.empty else "N/A"

if has_records or has_map:
    if not has_records:
        st.info(
            f"No stored records for **{selected_label.split('(')[0].strip()}** yet. "
            "Ingest it from the sidebar, or switch **Map Scope** to 'All stored species'."
        )

    # --- KPI Card Row ---
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Total Verified Sightings</div>
            <div class="metric-val">{total_sightings:,}</div>
            <div class="pill-badge">Active In Supabase</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Nations Covered</div>
            <div class="metric-val">{unique_countries}</div>
            <div class="pill-badge">Geospatial Reach</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">Primary Stronghold</div>
            <div class="metric-val">{top_country}</div>
            <div class="pill-badge">Highest Density</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    # --- Interactive Visualization Studio (Your Chart & Metric Selector) ---
    st.markdown("### 📊 Interactive Visual Analytics Studio")

    studio_col1, studio_col2 = st.columns([1, 1])
    with studio_col1:
        metric_choice = st.selectbox(
            "Select Data Dimension",
            ["Geographic Coordinates (Global Occurrence)", "Country Distribution", "Observation Protocols (Basis of Record)"]
        )
    with studio_col2:
        chart_type = st.selectbox(
            "Select Chart Representation",
            ["Natural Earth Map", "Bar Breakdown", "Sunburst / Donut Ring"]
        )

    # Plotly custom green theme helper
    def apply_green_theme(fig, margin=None):
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color="#d1fae5"),
            margin=margin or dict(l=20, r=20, t=40, b=20)
        )
        return fig

    # Render selected chart
    chart_col, ai_col = st.columns([3, 2])

    with chart_col:
        if "Map" in chart_type:
            if map_df.empty:
                st.info("No records with usable coordinates yet — ingest more sightings to populate the map.")
            else:
                species_count = map_df["scientific_name"].nunique()
                fig = build_sighting_map(map_df, color_by_species=species_count > 1)
                st.plotly_chart(
                    apply_green_theme(fig, margin=dict(l=0, r=0, t=8, b=0)),
                    width="stretch",
                )
                caption = f"{len(map_df):,} sightings · {species_count} species mapped"
                if species_count == 1 and map_scope == "Selected species":
                    caption += " · switch Map Scope to 'All stored species' to compare species"
                st.caption(caption)

        elif not has_records:
            st.info("Ingest sightings for this species to populate this chart.")
        elif "Bar" in chart_type:
            target_col = "country" if "Country" in metric_choice else "basis_of_record"
            counts = df[target_col].value_counts().reset_index()
            counts.columns = [target_col, "count"]

            fig = px.bar(
                counts.head(10),
                x=target_col,
                y="count",
                color="count",
                color_continuous_scale=["#17382b", "#4ade80"]
            )
            st.plotly_chart(apply_green_theme(fig), width="stretch")

        elif "Sunburst" in chart_type or "Donut" in chart_type:
            target_col = "country" if "Country" in metric_choice else "basis_of_record"
            fig = px.pie(
                df,
                names=target_col,
                hole=0.45,
                color_discrete_sequence=["#1f4e3b", "#2e7d59", "#4ade80", "#86efac", "#a7f3d0"]
            )
            st.plotly_chart(apply_green_theme(fig), width="stretch")

    # --- AI Briefing Panel ---
    with ai_col:
        st.markdown(f"""
        <div class="metric-card">
            <h4 style="color:#6ee7b7; margin-top:0;">🤖 wildlife educator Conservation Brief</h4>
            <p style="color:#cbd5e1; font-size:0.85rem;">Synthesize regional sightings into structured conservation intelligence.</p>
        </div>
        """, unsafe_allow_html=True)

        clicked = st.button(
            "Generate AI Assessment",
            width="stretch",
            disabled=not has_records,
            help=None if has_records else "Ingest sightings for this species first.",
        )
        if clicked:
            top_3 = ", ".join(countries.value_counts().head(3).index.tolist()) or "N/A"
            observed = pd.to_datetime(df["event_date"], errors="coerce").dropna()
            first_year = observed.min().strftime("%Y") if not observed.empty else "N/A"
            summary_payload = {
                "total_count": total_sightings,
                "top_countries": top_3,
                "date_range": f"{first_year} - present",
            }
            with st.spinner("Conservationist is evaluating population patterns..."):
                try:
                    report = generate_conservation_report(scientific_name, summary_payload)
                except Exception as exc:
                    st.error(f"The AI briefing could not be generated: {exc}")
                else:
                    with st.container(border=True):
                        st.markdown(report)
else:
    st.info(
        f"No records stored for **{selected_label.split('(')[0].strip()}** yet. Click "
        "'Ingest GBIF Records to Supabase' in the sidebar to populate it, or switch "
        "**Map Scope** to 'All stored species' to see whatever is already stored."
    )
