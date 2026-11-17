import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env file.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def upsert_occurrences(records: list[dict]):
    """
    Inserts or updates sighting records in the 'occurrences' table.
    """
    if not records:
        print("No records to upload.")
        return []

    response = supabase.table("occurrences").upsert(
        records,
        on_conflict="occurrence_id"
    ).execute()

    return response.data


def fetch_occurrences_by_species(scientific_name: str) -> list[dict]:
    """Queries stored sightings for an animal from Supabase."""
    response = (
        supabase.table("occurrences")
        .select("*")
        .ilike("scientific_name", f"%{scientific_name}%")
        .execute()
    )
    return response.data


def fetch_occurrences_by_species_list(scientific_names: list[str]) -> list[dict]:
    """
    Queries stored sightings for several animals in a single round-trip.
    Used by the comparison map, which colours dots by species.
    """
    if not scientific_names:
        return []

    response = (
        supabase.table("occurrences")
        .select("*")
        .in_("scientific_name", scientific_names)
        .execute()
    )
    return response.data


def fetch_all_occurrences(batch_size: int = 1000) -> list[dict]:
    """Fetches all rows from Supabase by paginating past the 1,000-row API default limit."""
    all_rows = []
    start = 0
    while True:
        res = (
            supabase.table("occurrences")
            .select("*")
            .range(start, start + batch_size - 1)
            .execute()
        )
        batch = res.data or []
        all_rows.extend(batch)
        if len(batch) < batch_size:
            break
        start += batch_size
    return all_rows


if __name__ == "__main__":
    # Test with a single mock record to verify connection
    test_record = [{
        "occurrence_id": "test-999",
        "scientific_name": "Acinonyx jubatus",
        "country": "Namibia",
        "latitude": -22.56,
        "longitude": 17.08,
        "event_date": "2024-01-01",
        "basis_of_record": "HUMAN_OBSERVATION"
    }]
    print("Testing Supabase upsert...")
    res = upsert_occurrences(test_record)
    print("Upsert successful:", res)