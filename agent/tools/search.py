# agent/tools/search.py
"""
Real-time web search — multi-source, no extra API keys required.

Priority order:
  1. Weather queries  → wttr.in (free, instant, no auth)
  2. News queries     → BBC / Reuters / CNN RSS feeds (free, real headlines)
  3. OpenAI Responses API with web_search_preview (when available)
  4. DuckDuckGo HTML scrape fallback (always works)
"""

import re
import os
import xml.etree.ElementTree as ET
import httpx
from openai import OpenAI

# ── Keyword sets for routing ───────────────────────────────────────────────────
WEATHER_WORDS = {"weather", "temperature", "forecast", "rain", "sunny",
                 "cloudy", "humidity", "celsius", "fahrenheit", "hot", "cold"}

NEWS_WORDS = {"news", "bbc", "cnn", "reuters", "headline", "headlines",
              "latest", "breaking", "update", "today", "current events",
              "what happened", "happening"}

# ── RSS feed catalogue ─────────────────────────────────────────────────────────
RSS_FEEDS = {
    "bbc":          "https://feeds.bbci.co.uk/news/rss.xml",
    "bbc world":    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "bbc tech":     "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "bbc sport":    "https://feeds.bbci.co.uk/sport/rss.xml",
    "bbc business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "cnn":          "http://rss.cnn.com/rss/edition.rss",
    "reuters":      "https://feeds.reuters.com/reuters/topNews",
}


async def search_web(query: str) -> str:
    """Search the internet and return real-time results."""
    print(f"[Search] Query: {query}")
    ql = query.lower()

    # 1 ── Weather shortcut ────────────────────────────────────────────────────
    if any(w in ql for w in WEATHER_WORDS):
        result = await _weather(query)
        if result:
            return result

    # 2 ── News via RSS ────────────────────────────────────────────────────────
    if any(w in ql for w in NEWS_WORDS):
        result = await _news_rss(query)
        if result:
            return result

    # 3 ── OpenAI built-in web search (gpt-4o-search-preview) ─────────────────
    result = await _openai_search(query)
    if result:
        return result

    # 4 ── DuckDuckGo HTML scrape fallback ─────────────────────────────────────
    result = await _ddg_scrape(query)
    if result:
        return result

    return (
        f"I searched for \"{query}\" but couldn't retrieve live results right now. "
        "Please try rephrasing or ask me again in a moment."
    )


# ── Source 1: Weather via wttr.in ─────────────────────────────────────────────
async def _weather(query: str) -> str:
    # Strip common filler words to extract city
    city = re.sub(
        r'\b(weather|today|tomorrow|in|the|what|is|temperature|forecast|now|current|of|for|at)\b',
        '', query, flags=re.IGNORECASE
    ).strip()
    city = re.sub(r'\s+', '+', city) or "auto"

    try:
        async with httpx.AsyncClient(timeout=10) as h:
            r = await h.get(f"https://wttr.in/{city}?format=3",
                            follow_redirects=True)
            if r.status_code == 200 and r.text.strip():
                return f"🌤 *Current weather:* {r.text.strip()}"
    except Exception as e:
        print(f"[Search] Weather error: {e}")
    return ""


# ── Source 2: News via RSS ────────────────────────────────────────────────────
async def _news_rss(query: str) -> str:
    ql = query.lower()

    # Pick the most specific matching feed
    feed_url = RSS_FEEDS["bbc"]   # default
    for key, url in RSS_FEEDS.items():
        if key in ql:
            feed_url = url
            break

    try:
        async with httpx.AsyncClient(timeout=15) as h:
            r = await h.get(feed_url, follow_redirects=True)
            if r.status_code != 200:
                return ""

            root = ET.fromstring(r.content)
            items = root.findall(".//item")[:8]
            if not items:
                return ""

            lines = []
            for item in items:
                title = (item.findtext("title") or "").strip()
                desc  = (item.findtext("description") or "").strip()
                desc  = re.sub(r"<[^>]+>", "", desc)[:180]
                pub   = (item.findtext("pubDate") or "").strip()
                if title:
                    lines.append(f"📰 *{title}*\n{desc}\n🕐 {pub}")

            if lines:
                src = next(
                    (k.upper() for k in RSS_FEEDS if RSS_FEEDS[k] == feed_url), "NEWS"
                )
                return f"*Latest from {src}:*\n\n" + "\n\n".join(lines)

    except Exception as e:
        print(f"[Search] RSS error ({feed_url}): {e}")
    return ""


# ── Source 3: OpenAI Responses API (native web search) ───────────────────────
async def _openai_search(query: str) -> str:
    try:
        c = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        resp = c.responses.create(
            model="gpt-4o-search-preview",
            tools=[{"type": "web_search_preview"}],
            input=query,
        )
        text = getattr(resp, "output_text", "") or ""
        if len(text.strip()) > 30:
            print(f"[Search] OpenAI web search ok ({len(text)} chars)")
            return text
    except Exception as e:
        print(f"[Search] OpenAI web search error: {e}")
    return ""


# ── Source 4: DuckDuckGo HTML scrape ─────────────────────────────────────────
async def _ddg_scrape(query: str) -> str:
    try:
        async with httpx.AsyncClient(timeout=15) as h:
            r = await h.post(
                "https://html.duckduckgo.com/html/",
                data={"q": query},
                headers={"User-Agent": "Mozilla/5.0 (compatible; AssistantBot/1.0)"},
                follow_redirects=True,
            )
            html = r.text

        snippets = re.findall(
            r'class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL
        )
        titles = re.findall(
            r'class="result__a"[^>]*>(.*?)</a>', html, re.DOTALL
        )

        clean_s = [re.sub(r"<[^>]+>", "", s).strip() for s in snippets[:5]]
        clean_t = [re.sub(r"<[^>]+>", "", t).strip() for t in titles[:5]]

        results = []
        for title, snippet in zip(clean_t, clean_s):
            if snippet and len(snippet) > 20:
                entry = f"• *{title}*\n  {snippet}" if title else f"• {snippet}"
                results.append(entry)

        if results:
            print(f"[Search] DuckDuckGo returned {len(results)} results")
            return "\n\n".join(results)

    except Exception as e:
        print(f"[Search] DuckDuckGo error: {e}")
    return ""
