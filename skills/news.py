"""News skill — fetches headlines from multiple reliable RSS feeds."""

import aiohttp
import xml.etree.ElementTree as ET

# Multiple RSS sources for reliability
RSS_FEEDS = [
    ("BBC", "http://feeds.bbci.co.uk/news/rss.xml"),
    ("Reuters", "https://feeds.reuters.com/reuters/topNews"),
    ("Google News", "https://news.google.com/rss?hl=en-IN&gl=IN&ceid=IN:en"),
]


async def _fetch_rss(session: aiohttp.ClientSession, url: str, count: int) -> list[str]:
    """Parse an RSS feed and return headline strings."""
    try:
        async with session.get(
            url,
            timeout=aiohttp.ClientTimeout(total=8),
            headers={"User-Agent": "Mozilla/5.0 JARVIS/3.1"}
        ) as r:
            if r.status != 200:
                return []
            xml_text = await r.text()
            root = ET.fromstring(xml_text)
            headlines = []
            for item in root.findall(".//item"):
                title_el = item.find("title")
                if title_el is not None and title_el.text:
                    title = title_el.text.strip()
                    # Skip generic/boilerplate titles
                    if len(title) > 10 and title.lower() not in ("top stories", "breaking news"):
                        headlines.append(title)
                if len(headlines) >= count:
                    break
            return headlines
    except Exception:
        return []


async def get_headlines(count: int = 5) -> str:
    """Fetch top news headlines. Tries multiple RSS feeds for reliability."""
    try:
        async with aiohttp.ClientSession() as session:
            for source_name, feed_url in RSS_FEEDS:
                headlines = await _fetch_rss(session, feed_url, count)
                if headlines:
                    numbered = ". ".join(
                        f"{i+1}, {h}" for i, h in enumerate(headlines)
                    )
                    return f"Here are the top headlines, Sir. {numbered}."

            return "Could not fetch news from any source right now, Sir."
    except Exception as e:
        return f"News service unavailable, Sir. {e}"


async def get_headlines_list(count: int = 5) -> list[str]:
    """Return headlines as a list (for API use)."""
    try:
        async with aiohttp.ClientSession() as session:
            for _, feed_url in RSS_FEEDS:
                headlines = await _fetch_rss(session, feed_url, count)
                if headlines:
                    return headlines
            return []
    except Exception:
        return []
