# agent/tools/search.py
"""
Real-time web search — multi-source, reliable.

Priority order:
  1. Weather queries  → wttr.in (free, instant, no auth)
  2. DuckDuckGo via ddgs package — reliable, free, always works
  3. OpenAI gpt-4o as smart summarizer on top of DDG results
"""

import re
import os
import asyncio
import httpx
from openai import OpenAI

# ── Keyword sets for routing ───────────────────────────────────────────────────
WEATHER_WORDS = {"weather", "temperature", "forecast", "rain", "sunny",
                 "cloudy", "humidity", "celsius", "fahrenheit", "hot", "cold"}


async def search_web(query: str) -> str:
    """Search the internet and return real-time results."""
    print(f"[Search] Query: {query}")
    ql = query.lower()

    # 1 ── Weather shortcut ────────────────────────────────────────────────────
    if any(w in ql for w in WEATHER_WORDS):
        result = await _weather(query)
        if result:
            return result

    # 2 ── DuckDuckGo search (primary, always runs) ───────────────────────────
    ddg_results = await _ddg_search(query)
    if ddg_results:
        # 3 ── Use OpenAI to synthesize a clean answer from the search results
        smart_answer = await _synthesize_with_openai(query, ddg_results)
        if smart_answer:
            return smart_answer
        # If OpenAI synthesis fails, return raw DDG results
        return ddg_results

    # 4 ── Last resort: OpenAI from training knowledge (with disclaimer) ───────
    return await _openai_fallback(query)


# ── Source 1: Weather via wttr.in ─────────────────────────────────────────────
async def _weather(query: str) -> str:
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


# ── Source 2: DuckDuckGo via duckduckgo-search package ───────────────────────
async def _ddg_search(query: str) -> str:
    """Use the duckduckgo-search Python package for reliable results."""
    try:
        # Run in thread pool since DDGS is synchronous
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _ddg_sync, query)
        return results
    except Exception as e:
        print(f"[Search] DuckDuckGo error: {e}")
    return ""


def _ddg_sync(query: str) -> str:
    """Synchronous DuckDuckGo search using the ddgs package."""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=6))

        if not results:
            return ""

        lines = []
        for r in results:
            title = r.get("title", "").strip()
            body  = r.get("body", "").strip()[:300]
            href  = r.get("href", "").strip()
            if body:
                lines.append(f"• *{title}*\n  {body}\n  🔗 {href}")

        if lines:
            print(f"[Search] DuckDuckGo returned {len(lines)} results")
            return "\n\n".join(lines)

    except Exception as e:
        print(f"[Search] DuckDuckGo sync error: {e}")
    return ""


# ── Source 3: OpenAI synthesizes DDG results into a clean answer ──────────────
async def _synthesize_with_openai(query: str, raw_results: str) -> str:
    """Use GPT-4o to write a clean, direct answer based on the DDG search results."""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return ""

        c = OpenAI(api_key=api_key)
        loop = asyncio.get_event_loop()

        def _call():
            return c.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful assistant. The user asked a question and we fetched "
                            "live web search results. Synthesize these results into a clear, concise, "
                            "direct answer. Use bullet points or short paragraphs. "
                            "Include key facts, numbers and dates. "
                            "Do NOT say you can't access the internet — you have the results below."
                        )
                    },
                    {
                        "role": "user",
                        "content": f"Question: {query}\n\nSearch results:\n{raw_results}"
                    }
                ],
                max_tokens=600,
            )

        resp = await loop.run_in_executor(None, _call)
        text = resp.choices[0].message.content or ""
        if len(text.strip()) > 20:
            print(f"[Search] OpenAI synthesis ok ({len(text)} chars)")
            return text.strip()

    except Exception as e:
        print(f"[Search] OpenAI synthesis error: {e}")
    return ""


# ── Source 4: OpenAI fallback (knowledge only, with disclaimer) ───────────────
async def _openai_fallback(query: str) -> str:
    """Last resort: use OpenAI training knowledge with a disclaimer."""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return f"I couldn't retrieve live results for \"{query}\" right now. Please try again in a moment."

        c = OpenAI(api_key=api_key)
        loop = asyncio.get_event_loop()

        def _call():
            return c.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Answer the user's question as best you can. "
                            "If you're not sure about recent facts, say so and give what you know. "
                            "Be direct and helpful."
                        )
                    },
                    {"role": "user", "content": query}
                ],
                max_tokens=500,
            )

        resp = await loop.run_in_executor(None, _call)
        text = resp.choices[0].message.content or ""
        if text.strip():
            return text.strip()

    except Exception as e:
        print(f"[Search] OpenAI fallback error: {e}")

    return f"I searched for \"{query}\" but couldn't retrieve live results right now. Please try again in a moment."
