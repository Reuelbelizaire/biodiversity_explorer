import requests

def fetch_species_occurrences(scientific_name: str, limit: int = 100) -> list[dict]:
    """
    Fetches animal occurrence records from the GBIF API and cleans the output.
    """
    url = "https://api.gbif.org/v1/occurrence/search"
    params = {
        "scientificName": scientific_name,
        "hasCoordinate": "true",
        "limit": limit
    }
    
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()  # Raises error if request failed
    
    data = response.json()
    raw_results = data.get("results", [])
    
    cleaned_records = []
    for item in raw_results:
        cleaned_records.append({
            "occurrence_id": str(item.get("key")),
            "scientific_name": item.get("scientificName", scientific_name),
            "country": item.get("country", "Unknown"),
            "latitude": item.get("decimalLatitude"),
            "longitude": item.get("decimalLongitude"),
            "event_date": item.get("eventDate"),
            "basis_of_record": item.get("basisOfRecord")
        })
        
    return cleaned_records

if __name__ == "__main__":
    # Test fetch for Cheetah (Acinonyx jubatus)
    test_animal = "Acinonyx jubatus"
    print(f"Fetching sightings for {test_animal}...")
    records = fetch_species_occurrences(test_animal, limit=5)
    
    print(f"Successfully fetched {len(records)} records!\n")
    for r in records:
        print(r)