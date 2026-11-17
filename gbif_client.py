import requests


def fetch_species_occurrences(
    scientific_name: str, limit: int = 150, taxon_key: int | None = None
) -> list[dict]:
    """
    Fetches raw occurrence data from the GBIF REST API for a given species or taxonKey,
    cleans missing coordinates, and standardizes field names.
    """
    endpoint = "https://api.gbif.org/v1/occurrence/search"
    params = {
        "hasCoordinate": "true",
        "hasGeospatialIssue": "false",
        "limit": limit,
    }
    if taxon_key:
        params["taxonKey"] = taxon_key
    else:
        params["scientificName"] = scientific_name

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
        cleaned_records.append(
            {
                "occurrence_id": str(item.get("key")),
                "scientific_name": scientific_name,
                "country": item.get("country", "Unknown"),
                "latitude": item.get("decimalLatitude"),
                "longitude": item.get("decimalLongitude"),
                "event_date": item.get("eventDate"),
                "basis_of_record": item.get("basisOfRecord"),
            }
        )

    return cleaned_records

def resolve_species_name(query_name: str, fallback_sci_name: str | None = None) -> dict | None:
    """
    Resolves common or scientific names via GBIF Taxonomy & Suggest APIs.
    If the regular English name (e.g., 'aardvark') isn't matched directly by GBIF,
    automatically retries using fallback_sci_name (e.g., 'Orycteropus afer').
    """
    candidates = [query_name.strip()]
    if fallback_sci_name and fallback_sci_name.strip().lower() != query_name.strip().lower():
        candidates.append(fallback_sci_name.strip())

    for candidate in candidates:
        # 1. Standard scientific / taxonomic matcher
        match_url = f"https://api.gbif.org/v1/species/match?verbose=false&name={candidate}"
        try:
            res = requests.get(match_url, timeout=5).json()
            match_type = res.get("matchType")
            if match_type in ["EXACT", "FUZZY"] and res.get("confidence", 0) > 60:
                sci = res.get("species") or res.get("canonicalName") or res.get("scientificName")
                if sci:
                    return {
                        "scientific_name": sci,
                        "canonical_name": res.get("canonicalName") or sci,
                        "family": res.get("family", "Unknown"),
                        "taxon_key": res.get("usageKey"),
                    }
        except Exception as e:
            print(f"Error in GBIF species match: {e}")

        # 2. Suggest endpoint fallback
        suggest_url = f"https://api.gbif.org/v1/species/suggest?q={candidate}&limit=5"
        try:
            suggestions = requests.get(suggest_url, timeout=5).json()
            for item in suggestions:
                if item.get("rank") in ["SPECIES", "GENUS", "FAMILY"] and item.get("canonicalName"):
                    return {
                        "scientific_name": item.get("canonicalName"),
                        "canonical_name": item.get("canonicalName"),
                        "family": item.get("family", "Unknown"),
                        "taxon_key": item.get("key"),
                    }
        except Exception as e:
            print(f"Error in GBIF species suggest: {e}")

    return None

def fetch_animal_photo(scientific_name: str, common_name: str = "") -> str | None:
    """
    Fetches a real photo URL of the animal from Wikipedia, automatically
    skipping range/distribution maps and SVG diagrams.
    """
    headers = {"User-Agent": "WildTrackBiodiversityExplorer/1.0 (student-capstone)"}
    bad_keywords = ["map", "range", "distribution", "area", "cladogram", "diagram", ".svg"]

    def is_valid_photo(url: str) -> bool:
        if not url:
            return False
        low = url.lower()
        return not any(word in low for word in bad_keywords)

    # 1. Try direct Wikipedia page summary for scientific name, then common name
    for query in [scientific_name, common_name]:
        clean = str(query).strip().replace(" ", "_")
        if not clean:
            continue
        try:
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{clean}"
            res = requests.get(url, headers=headers, timeout=5)
            if res.status_code == 200:
                data = res.json()
                for key in ["originalimage", "thumbnail"]:
                    img_url = data.get(key, {}).get("source")
                    if is_valid_photo(img_url):
                        return img_url
        except Exception:
            continue

    # 2. Fallback: Search Wikipedia articles (e.g. "Bottlenose dolphin") to get a real photo
    search_term = common_name if common_name and common_name.lower() != scientific_name.lower() else scientific_name
    try:
        search_res = requests.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "generator": "search",
                "gsrsearch": f"{search_term} animal",
                "gsrlimit": 5,
                "prop": "pageimages",
                "piprop": "original|thumbnail",
                "pithumbsize": 800,
                "format": "json",
            },
            headers=headers,
            timeout=5,
        ).json()

        pages = search_res.get("query", {}).get("pages", {})
        for page in pages.values():
            img_url = page.get("original", {}).get("source") or page.get("thumbnail", {}).get("source")
            if is_valid_photo(img_url):
                return img_url
    except Exception:
        pass

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