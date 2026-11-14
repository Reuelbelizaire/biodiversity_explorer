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
    prompt = f"""
    You are an expert wildlife ecologist. Provide an executive conservation briefing for:
    - Species: {scientific_name}
    - Total Monitored Sightings: {payload.get('total_count')}
    - Key Observation Locations: {payload.get('top_countries')}
    - Date Range: {payload.get('date_range')}

    Keep it concise, rigorous, and structured in 3 paragraphs:
    1. Geographic footprint and current habitat dynamics.
    2. Primary environmental and anthropogenic threats.
    3. Actionable conservation priorities.
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Assessment generation unavailable: {str(e)}"

def answer_animal_question(scientific_name: str, question: str, context: dict) -> str:
    prompt = f"""
    You are a wildlife expert. Answer this question regarding {scientific_name}:
    Context: {context.get('total_count')} observations recorded across {context.get('top_countries')}.
    Question: {question}
    Provide a factual, engaging answer in 2-3 short paragraphs.
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            temperature=0.4
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Unable to retrieve answer: {str(e)}"

def generate_species_stats(common_name: str, scientific_name: str) -> dict:
    """Generates numerical 1-10 attributes and a signature skill for radar charts."""
    prompt = f"""
    Provide realistic biological RPG-style stat ratings on a strict 1 to 10 scale for the animal '{common_name}' ({scientific_name}).
    Return ONLY a valid JSON object with these exact keys:
    {{
        "strength": <integer 1-10>,
        "speed": <integer 1-10>,
        "endurance": <integer 1-10>,
        "stealth": <integer 1-10>,
        "threat_level": <integer 1-10>,
        "signature_skill": "<Short description of primary evolutionary ability, e.g., Burst Acceleration>"
    }}
    Do not include markdown fences, thoughts, or extra commentary. Output strictly JSON.
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
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
    """Compares ecological footprints and vulnerability between two species."""
    prompt = f"""
    Compare the following two species based on their ecological footprints and monitoring data:
    Species A: {spec_a} ({summary_a.get('count')} observations, primarily in {summary_a.get('top_loc')})
    Species B: {spec_b} ({summary_b.get('count')} observations, primarily in {summary_b.get('top_loc')})

    Deliver a structured 3-part comparative assessment:
    1. Trophic & Niche Comparison (Predator vs. Herbivore, marine vs. terrestrial).
    2. Range Resilience & Habitat Pressures (Which species faces greater immediate geographic fragmentation).
    3. Synergistic Conservation Recommendation.
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1500,
            temperature=0.3
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Comparative assessment unavailable: {str(e)}"

def check_species_spelling(query: str) -> str:
    """Interprets misspelled animal queries and returns the corrected common/binomial name."""
    prompt = f"""
    The user entered an animal search query: '{query}'.
    If it is misspelled or colloquial, identify the intended real animal common name and scientific binomial.
    Reply with ONLY the format: Common Name (Scientific Name).
    Example: 'cheta' -> 'Cheetah (Acinonyx jubatus)'.
    If the name is already valid or unrecognizable, return the best standard match. Do not explain.
    """
    try:
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=40,
            temperature=0.1
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return query