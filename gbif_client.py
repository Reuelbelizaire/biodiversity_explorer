import requests


def fetch_species_occurrences(scientific_name: str, limit: int = 150) -> list[dict]:
    """
    Fetches raw occurrence data from the GBIF REST API for a given species,
    cleans missing coordinates, and standardizes field names.
    """
    endpoint = "https://api.gbif.org/v1/occurrence/search"
    params = {
        "scientificName": scientific_name,
        "hasCoordinate": "true",
        "hasGeospatialIssue": "false",
        "limit": limit,
    }

    try:
        response = requests.get(endpoint, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        raw_results = data.get("results", [])
    except Exception as e:
        print(f"Error fetching from GBIF API: {e}")
        return []

    cleaned_records = []
    for item in raw_results:
        # Standardize and map directly to Supabase schema
        cleaned_records.append(
            {
                "occurrence_id": str(item.get("key")),
                "scientific_name": scientific_name,  # Clean canonical name without author tags
                "country": item.get("country", "Unknown"),
                "latitude": item.get("decimalLatitude"),
                "longitude": item.get("decimalLongitude"),
                "event_date": item.get("eventDate"),
                "basis_of_record": item.get("basisOfRecord"),
            }
        )

    return cleaned_records


def resolve_species_name(query_name: str) -> dict | None:
    """
    Resolves common or scientific names via GBIF Taxonomy & Suggest APIs.
    """
    cleaned_query = query_name.strip()

    # 1. First attempt: Standard scientific / taxonomic matcher
    match_url = f"https://api.gbif.org/v1/species/match?verbose=false&name={cleaned_query}"
    try:
        res = requests.get(match_url, timeout=5).json()
        match_type = res.get("matchType")
        if match_type in ["EXACT", "FUZZY"] and res.get("confidence", 0) > 60:
            return {
                "scientific_name": res.get("species") or res.get("scientificName"),
                "canonical_name": res.get("canonicalName") or res.get("species"),
                "family": res.get("family", "Unknown"),
                "taxon_key": res.get("usageKey"),
            }
    except Exception as e:
        print(f"Error in GBIF species match: {e}")

    # 2. Fallback: Search endpoint (resolves vernacular / common names like 'Jaguar')
    suggest_url = f"https://api.gbif.org/v1/species/suggest?q={cleaned_query}&limit=5"
    try:
        suggestions = requests.get(suggest_url, timeout=5).json()
        for item in suggestions:
            # Look for species-rank results
            if item.get("rank") == "SPECIES" and item.get("canonicalName"):
                return {
                    "scientific_name": item.get("canonicalName"),
                    "canonical_name": item.get("canonicalName"),
                    "family": item.get("family", "Unknown"),
                    "taxon_key": item.get("key"),
                }
    except Exception as e:
        print(f"Error in GBIF species suggest: {e}")

    return None


def fetch_english_name_and_habitat(scientific_name: str) -> tuple[str, str]:
    """
    Looks up the regular English name and habitat icon ('🪽', '🌊', '🐾')
    from GBIF's taxon & vernacularNames endpoints for any newly added animal.
    """
    clean_sci = str(scientific_name).strip()
    try:
        match_res = requests.get(
            "https://api.gbif.org/v1/species/match",
            params={"name": clean_sci},
            timeout=5,
        ).json()

        usage_key = match_res.get("usageKey")
        tax_class = str(match_res.get("class", "")).lower()
        tax_order = str(match_res.get("order", "")).lower()

        if tax_class in ["aves", "insecta", "chiroptera"] or tax_order in [
            "chiroptera",
            "lepidoptera",
            "odonata",
        ]:
            habitat_icon = "🪽"
        elif tax_class in [
            "actinopterygii",
            "chondrichthyes",
            "cephalopoda",
            "malacostraca",
            "anthozoa",
        ] or tax_order in ["cetacea", "sirenia", "testudines", "pinnipedia"]:
            habitat_icon = "🌊"
        else:
            habitat_icon = "🐾"

        if usage_key:
            vern_res = requests.get(
                f"https://api.gbif.org/v1/species/{usage_key}/vernacularNames",
                timeout=5,
            ).json()
            for item in vern_res.get("results", []):
                if item.get("language") in ["eng", "en"] and item.get("vernacularName"):
                    common = item["vernacularName"].strip().title()
                    return (common, habitat_icon)

        return (clean_sci, habitat_icon)
    except Exception:
        return (clean_sci, "🐾")