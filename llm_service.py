import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


def _get_client() -> OpenAI:
    """Build the client on demand so a missing key doesn't crash the whole app at import."""
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError(
            "DEEPSEEK_API_KEY is missing. Add it to .env (DEEPSEEK_API_KEY=...) and restart the app."
        )
    return OpenAI(api_key=api_key, base_url="https://api.deepseek.com")


def generate_conservation_report(species_name: str, stats: dict) -> str:
    """
    Sends aggregated occurrence data to DeepSeek to generate a 3-paragraph conservation brief.
    """
    client = _get_client()
    prompt = f"""
    You are a wildlife conservation biologist. Analyze the following sighting data for {species_name}:
    - Total Recorded Sightings: {stats.get('total_count', 0)}
    - Primary Observation Countries: {stats.get('top_countries', 'N/A')}
    - Earliest to Latest Recorded Dates: {stats.get('date_range', 'N/A')}

    Provide an executive conservation briefing structured into three sections:
    1. Geographic Distribution & Habitat Patterns
    2. Primary Ecological Vulnerabilities & Threats
    3. Actionable Field Recommendations for Conservationists
    """

    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "You are a professional ecological data analyst."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content

if __name__ == "__main__":
    print("Testing DeepSeek API handshake...")
    test_stats = {
        "total_count": 120,
        "top_countries": "Namibia, Botswana, South Africa",
        "date_range": "2015 to 2024"
    }
    report = generate_conservation_report("Acinonyx jubatus", test_stats)
    print("\n--- DEEPSEEK RESPONSE ---")
    print(report)