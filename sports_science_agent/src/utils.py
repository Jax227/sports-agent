"""Utility functions for the Sports Science Research Agent."""

import json
import hashlib
import re
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from src.config import LOGS_DIR

LOG_FILE = LOGS_DIR / "agent.log"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("sports_science_agent")
    logger.setLevel(level)
    if not logger.handlers:
        fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)
        ch = logging.StreamHandler()
        ch.setLevel(level)
        ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        logger.addHandler(ch)
    return logger


logger = setup_logging()


def generate_paper_id(title: str, authors: str = "", year: str = "") -> str:
    raw = f"{title}|{authors}|{year}".lower().encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def safe_load_json(path: Path, default=None):
    if default is None:
        default = []
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError):
        logger.warning(f"Failed to load JSON: {path}")
        return default


def safe_save_json(data, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def safe_save_csv(df, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def normalize_doi(raw: str) -> Optional[str]:
    """Extract and normalize DOI from a string."""
    if not raw:
        return None
    raw = raw.strip()
    # Handle common DOI URL patterns
    for prefix in ["https://doi.org/", "http://doi.org/", "doi: ", "DOI: ", "doi:", "DOI:"]:
        if raw.lower().startswith(prefix.lower()):
            raw = raw[len(prefix):]
    # Remove trailing punctuation
    raw = raw.rstrip(".],;:")
    return raw if raw else None


def normalize_pmid(raw: str) -> Optional[str]:
    """Extract and normalize PMID."""
    if not raw:
        return None
    digits = re.sub(r"\D", "", str(raw))
    return digits if digits else None


def extract_pico(abstract: str) -> dict:
    """Naive PICO extraction from abstract using keyword heuristics."""
    pico = {"population": "", "intervention": "", "comparator": "", "outcome": ""}
    if not abstract:
        return pico
    text = abstract.lower()
    # Population
    pop_patterns = [
        r"(in|among|for)\s+([\w\s,;-]+?)\s*(?:,?\s*(?:we|a\s|the\s|this\s|undergo|receiv|perform|participat))",
    ]
    # Simple heuristic: first sentence often contains population
    sentences = re.split(r"[.!?]\s+", abstract)
    if sentences:
        pico["population"] = sentences[0][:200].strip()
    # Intervention
    interv_matches = re.findall(r"(intervention|treatment|training|protocol|program|supplement|exercise)\s+(?:was|is|consisted|included|comprised)[^.]*", text)
    if interv_matches:
        pico["intervention"] = interv_matches[0][:200].strip()
    # Comparator
    comp_matches = re.findall(r"(compar(?:ed|ison)|versus|vs\.?|control\s+group)[^.]*", text)
    if comp_matches:
        pico["comparator"] = comp_matches[0][:200].strip()
    # Outcome
    outcome_matches = re.findall(r"(outcome|endpoint|measured|assessed|evaluated|primary|secondary)[^.]*", text)
    if outcome_matches:
        pico["outcome"] = outcome_matches[0][:200].strip()
    return pico


def timestamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def truncate(text: str, max_len: int = 500) -> str:
    return text if len(text) <= max_len else text[:max_len] + "..."


# ── Translation ──────────────────────────────────────────────────

def translate_abstract(text: str) -> str:
    """Translate academic English abstract to Simplified Chinese.

    Uses DeepSeek V4 (primary), OpenAI (fallback), or Anthropic API.
    Returns the original text with a warning when no API key is configured.
    """
    if not text or not text.strip():
        return text

    # Strip excessive whitespace but preserve paragraphs
    cleaned = " ".join(line.strip() for line in text.splitlines() if line.strip())
    if len(cleaned) > 2500:
        cleaned = cleaned[:2500]  # Truncate very long abstracts

    import os
    deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
    openai_key = os.getenv("OPENAI_API_KEY", "")
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")

    if deepseek_key:
        return _translate_with_deepseek(cleaned, deepseek_key)
    elif openai_key:
        return _translate_with_openai(cleaned, openai_key)
    elif anthropic_key:
        return _translate_with_claude(cleaned, anthropic_key)
    else:
        logger.warning("No API key configured for translation — returning original text")
        return f"[翻译不可用：请在 .env 中配置 DEEPSEEK_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY]\n\n{text}"


def _translate_with_deepseek(text: str, api_key: str) -> str:
    """Translate using DeepSeek V4 API via direct REST call (no SDK needed)."""
    try:
        import requests

        # Use a session that bypasses Windows system proxy
        session = requests.Session()
        session.trust_env = False

        resp = session.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "deepseek-v4-pro",
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是一名运动科学领域的学术翻译专家。请将以下英文摘要翻译为简体中文。"
                            "要求：\n"
                            "1. 准确翻译学术术语（如 randomized controlled trial → 随机对照试验）\n"
                            "2. 保持原文的科学严谨性和数据精度\n"
                            "3. 保留统计量（p值、CI、效应量等）和数字精度\n"
                            "4. 译文流畅、符合中文学术写作规范\n"
                            "5. 只输出译文，不要添加任何说明或注释"
                        ),
                    },
                    {"role": "user", "content": text},
                ],
                "temperature": 0.1,
                "max_tokens": 2048,
            },
            timeout=60,
        )

        if resp.status_code != 200:
            logger.error(f"DeepSeek API HTTP {resp.status_code}: {resp.text[:200]}")
            return f"[翻译失败: HTTP {resp.status_code}]\n\n{text}"

        data = resp.json()
        translated = data["choices"][0]["message"]["content"].strip()
        logger.info(f"DeepSeek translated abstract ({len(text)} chars → {len(translated)} chars)")
        return translated
    except Exception as e:
        logger.error(f"DeepSeek translation failed: {e}")
        return f"[翻译失败: {type(e).__name__}]\n\n{text}"


def _translate_with_openai(text: str, api_key: str) -> str:
    """Translate using OpenAI API."""
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是一名运动科学领域的学术翻译专家。请将以下英文摘要翻译为简体中文。"
                        "要求：\n"
                        "1. 准确翻译学术术语（如 randomized controlled trial → 随机对照试验）\n"
                        "2. 保持原文的科学严谨性和数据精度\n"
                        "3. 保留统计量（p值、CI、效应量等）和数字精度\n"
                        "4. 译文流畅、符合中文学术写作规范\n"
                        "5. 只输出译文，不要添加任何说明或注释"
                    ),
                },
                {"role": "user", "content": text},
            ],
            temperature=0.1,
            max_tokens=2048,
        )
        translated = response.choices[0].message.content.strip()
        logger.info(f"Translated abstract ({len(text)} chars → {len(translated)} chars)")
        return translated
    except Exception as e:
        logger.error(f"OpenAI translation failed: {e}")
        return f"[翻译失败: {type(e).__name__}]\n\n{text}"


def _translate_with_claude(text: str, api_key: str) -> str:
    """Translate using Anthropic Claude API."""
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            temperature=0.1,
            system=(
                "你是一名运动科学领域的学术翻译专家。请将以下英文摘要翻译为简体中文。"
                "要求：准确翻译学术术语，保持科学严谨性和数据精度，保留统计量和数字，"
                "译文流畅符合中文学术规范。只输出译文，不要添加任何说明。"
            ),
            messages=[{"role": "user", "content": text}],
        )
        translated = message.content[0].text.strip()
        logger.info(f"Translated abstract ({len(text)} chars → {len(translated)} chars)")
        return translated
    except Exception as e:
        logger.error(f"Claude translation failed: {e}")
        return f"[翻译失败: {type(e).__name__}]\n\n{text}"
