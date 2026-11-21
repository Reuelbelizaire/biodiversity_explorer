import os
import json
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com"
)

def generate_conservation_report(scientific_name: str, payload: dict) -> str:
    """Generates a tight 3-bullet conservation briefing (~60 words max)."""
    prompt = f"""
You are a concise wildlife telemetry analyst writing a field card for {scientific_name}.
Context: {payload.get('total_count')} sightings | Locations: {payload.get('top_countries')} | Period: {payload.get('date_range')}.

Write ONLY these 3 bullet points (MAX 18 words per bullet, NO intro or outro paragraphs):
- **Habitat & Footprint:** [Key biome + alignment with {payload.get('top_countries')}]
- **Primary Threat:** [Main environmental or human threat]
- **Conservation Priority:** [IUCN status + 1 concrete protection action]
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=160,
            temperature=0.2
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"- **Assessment Unavailable:** {str(e)}"

def answer_animal_question(scientific_name: str, question: str, context: dict) -> str:
    """Answers user wildlife questions in 2-3 punchy bullets (under 75 words total)."""
    prompt = f"""
You are a concise wildlife expert answering a question about {scientific_name}.
Context: {context.get('total_count')} observations across {context.get('top_countries')}.
Question: {question}

Rules:
- Reply in 2 to 3 short bullet points ONLY (MAX 75 words total).
- Start directly with the answer—no introductory fluff or filler.
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=140,
            temperature=0.3
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"- **Unable to retrieve answer:** {str(e)}"

def generate_species_stats(common_name: str, scientific_name: str) -> dict:
    """Generates numerical 1-10 attributes and a 2-4 word signature skill."""
    prompt = f"""
Provide realistic biological stat ratings on a strict 1 to 10 scale for '{common_name}' ({scientific_name}).
Return ONLY a valid JSON object with these exact keys:
{{
    "strength": <integer 1-10>,
    "speed": <integer 1-10>,
    "endurance": <integer 1-10>,
    "stealth": <integer 1-10>,
    "threat_level": <integer 1-10>,
    "signature_skill": "<2 to 4 word evolutionary ability, e.g., Burst Acceleration>"
}}
Output strictly JSON. No markdown fences or extra commentary.
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.2
        )
        raw = response.choices[0].message.content.strip().replace("```json", "").replace("```", "")
        return json.loads(raw)
    except Exception:
        return {
            "strength": 5, "speed": 5, "endurance": 5, "stealth": 5, "threat_level": 5,
            "signature_skill": "Adaptive Instinct"
        }

def generate_comparative_assessment(spec_a: str, spec_b: str, summary_a: dict, summary_b: dict) -> str:
    """Compares two species in 3 crisp bullets (~75 words max, down from 1500 tokens)."""
    prompt = f"""
Compare these two species based on their monitoring data:
- Species A: {spec_a} ({summary_a.get('count')} sightings, primarily in {summary_a.get('top_loc')})
- Species B: {spec_b} ({summary_b.get('count')} sightings, primarily in {summary_b.get('top_loc')})

Deliver ONLY these 3 short bullet points (MAX 22 words per bullet, NO intro/outro text):
- **Niche & Diet Contrast:** [Compare trophic role and habitat type]
- **Range Vulnerability:** [State which species faces tighter geographic fragmentation and why]
- **Conservation Takeaway:** [1 shared or targeted protection priority]
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=180,
            temperature=0.2
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"- **Comparative Assessment Unavailable:** {str(e)}"

def check_species_spelling(query: str) -> str:
    """Interprets misspelled animal queries and returns Common Name (Scientific Name)."""
    prompt = f"""
The user entered an animal search query: '{query}'.
If misspelled or colloquial, identify the intended real animal common name and scientific binomial.
Reply with ONLY the format: Common Name (Scientific Name).
Example: 'cheta' -> 'Cheetah (Acinonyx jubatus)'.
Do not explain.
"""
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=30,
            temperature=0.1
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return query

def translate_to_scientific_name(animal_query: str) -> str | None:
    """Converts a regular English animal name into its Latin scientific name."""
    prompt = (
        f"What is the exact Latin binomial scientific name for '{animal_query}'? "
        "Reply ONLY with the two-word Latin scientific name (e.g., Orycteropus afer). "
        "If not a real animal, reply ONLY with UNKNOWN."
    )
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=20,
        )
        result = response.choices[0].message.content.strip().strip('"').strip("'")
        if not result or "UNKNOWN" in result.upper() or len(result.split()) > 4:
            return None
        return result
    except Exception:
        return None

def classify_species_diets(species_list: list[str]) -> dict[str, dict]:
    """Classifies species into trophic diet roles with a strict 3-5 word diet summary."""
    if not species_list:
        return {}

    prompt = (
        "For each animal in this list, identify its primary trophic diet role "
        "(choose strictly one: 'Apex Carnivore', 'Carnivore', 'Herbivore', 'Omnivore', or 'Insectivore & Nectarivore') "
        "and a strict 3-5 word summary of its main diet.\n"
        f"Animals: {species_list}\n"
        'Return ONLY valid JSON mapping each exact animal string from the list to '
        '{"role": "...", "diet": "..."}. No markdown or extra text.'
    )
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=500,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw.strip())
    except Exception:
        return {}