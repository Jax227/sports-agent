
from dotenv import load_dotenv
load_dotenv(".env")
import requests, os

api_key = os.getenv("DEEPSEEK_API_KEY")
session = requests.Session()
session.trust_env = False

# Minimal test
resp = session.post(
    "https://api.deepseek.com/v1/chat/completions",
    headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    json={
        "model": "deepseek-v4-pro",
        "messages": [
            {"role": "user", "content": "Return only the JSON: {"test": "hello"}"},
        ],
        "temperature": 0.0,
        "max_tokens": 100,
    },
    timeout=60
)
print(f"HTTP {resp.status_code}")
data = resp.json()
print(f"Keys: {list(data.keys())}")
if "choices" in data:
    c = data["choices"][0]
    print(f"Finish reason: {c.get("finish_reason")}")
    print(f"Content: {repr(c["message"]["content"])}")
else:
    print(json.dumps(data, indent=2, ensure_ascii=False)[:500])
