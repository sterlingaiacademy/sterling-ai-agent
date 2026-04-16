# agent/tools/search.py
"""
Real-time web search using OpenAI's native web_search_preview tool.
This gives the agent full internet access — same quality as browsing Chrome.
No extra API keys needed (uses the existing OPENAI_API_KEY).

Works for:
  - Latest news (BBC, CNN, etc.)
  - Live weather
  - Stock prices
  - Sports scores
  - Any real-time information
"""

import os
from openai import OpenAI

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


async def search_web(query: str) -> str:
    """
    Search the internet using OpenAI's built-in web search.
    Returns a detailed, real-time answer based on live web results.
    """
    print(f"[Search] Searching web for: {query}")

    try:
        # Use OpenAI Responses API with web_search_preview
        # This gives real-time internet access — reads actual websites
        response = _client.responses.create(
            model="gpt-4o-mini-search-preview",
            tools=[{"type": "web_search_preview"}],
            input=query,
        )

        result = response.output_text
        print(f"[Search] Got result ({len(result)} chars)")
        return result

    except Exception as primary_err:
        print(f"[Search] Primary search failed: {primary_err}")

        # Fallback: try with gpt-4o-search-preview
        try:
            response = _client.responses.create(
                model="gpt-4o-search-preview",
                tools=[{"type": "web_search_preview"}],
                input=query,
            )
            return response.output_text

        except Exception as fallback_err:
            print(f"[Search] Fallback also failed: {fallback_err}")
            return (
                f"I attempted to search for \"{query}\" but the web search "
                f"is temporarily unavailable. Error: {str(fallback_err)}"
            )
