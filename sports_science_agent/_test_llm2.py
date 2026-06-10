
from dotenv import load_dotenv
load_dotenv(".env")
import requests, os, json

api_key = os.getenv("DEEPSEEK_API_KEY")
session = requests.Session()
session.trust_env = False

# Use simplified prompt
system_prompt = """You are a sports science information retrieval specialist. Decompose the user's research topic into a structured search plan.

Output ONLY valid JSON (no markdown, no explanation):
{
  "pico": {
    "population": {"raw": "", "english_terms": [], "required": false},
    "intervention_or_exposure": {"raw": "", "english_terms": [], "required": true},
    "comparator": {"raw": "", "english_terms": [], "required": false},
    "outcomes": {"raw": "", "english_terms": [], "required": false},
    "context": {"raw": "sports science", "english_terms": ["exercise", "training", "sport"], "required": false}
  },
  "mandatory_terms": [],
  "optional_terms": [],
  "exclusion_terms": [],
  "pubmed_query": ""
}

Rules:
- mandatory_terms: 2-5 core concepts that MUST appear in title/abstract
- optional_terms: synonyms for broader recall
- exclusion_terms: terms that indicate irrelevance (animal, rat, mouse, in vitro, etc.)
- pubmed_query: use [Title/Abstract] field, AND between concept groups, OR within groups
- Translate Chinese to English
- The pubmed_query MUST contain the core English terms"""

resp = session.post(
    "https://api.deepseek.com/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    json={
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "HIIT 对中老年人 VO2max 的影响"},
        ],
        "temperature": 0.1,
        "max_tokens": 2048,
    },
    timeout=60
)

print(f"HTTP {resp.status_code}")
content = resp.json()["choices"][0]["message"]["content"]
print(f"Full content ({len(content)} chars):")
print(content)
print("---END---")
