"""Debug script for DeepSeek LLM query understanding."""
from dotenv import load_dotenv
load_dotenv(".env")
import requests, os, json, sys

api_key = os.getenv("DEEPSEEK_API_KEY")
session = requests.Session()
session.trust_env = False

# Test 1: Minimal prompt
print("=== Test 1: Minimal prompt ===")
resp = session.post(
    "https://api.deepseek.com/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    json={
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "user", "content": 'Return only the JSON: {"test": "hello"}'},
        ],
        "temperature": 0.0,
        "max_tokens": 100,
    },
    timeout=60,
)
print(f"HTTP {resp.status_code}")
data = resp.json()
if "choices" in data:
    c = data["choices"][0]
    print(f"Finish reason: {c.get('finish_reason')}")
    print(f"Content: {repr(c['message']['content'])}")
else:
    print(json.dumps(data, indent=2, ensure_ascii=False)[:500])

# Test 2: PICO decomposition with short system prompt
print("\n=== Test 2: PICO decomposition (short prompt) ===")
system_prompt = (
    "You are a sports science search specialist. "
    "Decompose research topics into PICO. Output ONLY valid JSON, no markdown, no explanation.\n"
    'Format: {"pico":{"population":{"english_terms":[]},"intervention_or_exposure":{"english_terms":[]},'
    '"comparator":{"english_terms":[]},"outcomes":{"english_terms":[]},"context":{"english_terms":[]}},'
    '"mandatory_terms":[],"optional_terms":[],"exclusion_terms":[],"pubmed_query":""}\n'
    "mandatory_terms: 2-5 must-match concepts. pubmed_query: use [Title/Abstract], AND/OR structure."
)

resp = session.post(
    "https://api.deepseek.com/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    json={
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "HIIT effects on VO2max in older adults"},
        ],
        "temperature": 0.1,
        "max_tokens": 1500,
    },
    timeout=60,
)
print(f"HTTP {resp.status_code}")
data = resp.json()
if "choices" in data:
    c = data["choices"][0]
    print(f"Finish reason: {c.get('finish_reason')}")
    content = c["message"]["content"]
    print(f"Content ({len(content)} chars):")
    print(content[:800])
    # Try to parse
    try:
        parsed = json.loads(content.strip())
        print("\nParsed OK!")
        print(f"  pico keys: {list(parsed.get('pico', {}).keys())}")
        print(f"  mandatory: {parsed.get('mandatory_terms', [])}")
        print(f"  query: {parsed.get('pubmed_query', '')[:200]}")
    except json.JSONDecodeError as e:
        print(f"\nJSON error: {e}")
        print(f"Content around error: ...{content[max(0,e.pos-50):e.pos+50]}...")
        # Try with common fixes
        import re
        fixed = re.sub(r',\s*(\}|\])', r'\1', content.strip())
        try:
            parsed = json.loads(fixed)
            print("Parsed after fixing trailing commas!")
        except Exception as e2:
            print(f"Still failed: {e2}")
else:
    print(json.dumps(data, indent=2, ensure_ascii=False)[:500])

# Test 3: Chinese input
print("\n=== Test 3: Chinese input ===")
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
        "max_tokens": 1500,
    },
    timeout=60,
)
print(f"HTTP {resp.status_code}")
data = resp.json()
if "choices" in data:
    c = data["choices"][0]
    print(f"Finish reason: {c.get('finish_reason')}")
    content = c["message"]["content"]
    print(f"Content ({len(content)} chars):")
    print(content[:800])
    try:
        parsed = json.loads(content.strip())
        print("\nParsed OK!")
        print(f"  mandatory: {parsed.get('mandatory_terms', [])}")
        print(f"  query: {parsed.get('pubmed_query', '')[:200]}")
    except json.JSONDecodeError as e:
        print(f"\nJSON error: {e}")
        import re
        fixed = re.sub(r',\s*(\}|\])', r'\1', content.strip())
        try:
            parsed = json.loads(fixed)
            print("Parsed after fixing trailing commas!")
            print(f"  mandatory: {parsed.get('mandatory_terms', [])}")
        except Exception as e2:
            print(f"Still failed: {e2}")
else:
    print(json.dumps(data, indent=2, ensure_ascii=False)[:500])

print("\nDone!")
