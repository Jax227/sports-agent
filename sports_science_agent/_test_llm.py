
from dotenv import load_dotenv
load_dotenv(".env")
import requests, os, json

api_key = os.getenv("DEEPSEEK_API_KEY")
session = requests.Session()
session.trust_env = False

# Test with the actual function's prompt
from src.query_understanding import _llm_decompose
r = _llm_decompose("HIIT 对中老年人 VO2max 的影响")
print("pico keys:", list(r.get("pico", {}).keys()))
print("mandatory:", r.get("mandatory_terms", []))
print("exclusion:", r.get("exclusion_terms", [])[:5])
print("query length:", len(r.get("pubmed_query", "")))
print("query:", r.get("pubmed_query", "")[:300])
