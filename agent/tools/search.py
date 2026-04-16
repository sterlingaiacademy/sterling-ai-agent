# agent/tools/search.py
"""
Real-time web search tool for the AI assistant.
Uses DuckDuckGo Instant Answer API (free, no key needed) as primary,
with a scraping fallback for richer results.
"""

import requests
import urllib.parse
import json

DDGO_API = "https://api.duckduckgo.com/"


async def search_web(query: str) -> str:
    """Search the internet and return concise, real-time results."""
    print(f"[Search] Querying: {query}")

    try:
        # ── DuckDuckGo Instant Answer (primary) ───────────────────────────
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1"
        }
        resp = requests.get(DDGO_API, params=params, timeout=10)
        data = resp.json()

        parts = []

        # Abstract (best single answer)
        abstract = data.get("AbstractText", "").strip()
        if abstract:
            parts.append(abstract)

        # Answer (e.g. "Delhi weather: 35°C")
        answer = data.get("Answer", "").strip()
        if answer and answer not in parts:
            parts.append(answer)

        # Related topics (up to 3)
        for topic in data.get("RelatedTopics", [])[:3]:
            text = topic.get("Text", "").strip()
            if text and text not in parts:
                parts.append(f"• {text}")

        if parts:
            result = "\n".join(parts)
            print(f"[Search] DDG result: {result[:200]}")
            return result

        # ── Fallback: DuckDuckGo HTML search scrape ───────────────────────
        fallback_resp = requests.get(
            "https://html.duckduckgo.com/html/",
            params={"q": query},
            headers={"User-Agent": "Mozilla/5.0 (compatible; SterlingBot/1.0)"},
            timeout=10
        )
        text = fallback_resp.text

        # Extract first few result snippets from raw HTML
        import re
        snippets = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', text, re.DOTALL)
        # Clean HTML tags
        clean = [re.sub(r"<[^>]+>", "", s).strip() for s in snippets[:3]]
        clean = [c for c in clean if len(c) > 20]

        if clean:
            result = "\n".join(f"• {c}" for c in clean)
            print(f"[Search] Fallback result: {result[:200]}")
            return result

        return f"I searched for \"{query}\" but couldn't find a clear answer. You may want to check Google directly."

    except Exception as e:
        print(f"[Search] Error: {e}")
        return f"Sorry, I wasn't able to search the web right now ({str(e)}). Please try again."
