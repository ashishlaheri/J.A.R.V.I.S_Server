"""News skill — fetches headlines from BBC."""

import aiohttp
from bs4 import BeautifulSoup


async def get_headlines(count: int = 5) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://www.bbc.com/news",
                timeout=aiohttp.ClientTimeout(total=10),
                headers={"User-Agent": "Mozilla/5.0"}
            ) as r:
                html = await r.text()
                soup = BeautifulSoup(html, "html.parser")
                headlines = []
                for h in soup.find("body").find_all("h3"):
                    text = h.text.strip()
                    if text and len(text) > 10:
                        headlines.append(text)
                    if len(headlines) >= count:
                        break
                if not headlines:
                    return "Could not find any headlines, Sir."
                numbered = ". ".join(headlines)
                return f"Here are the top headlines, Sir. {numbered}."
    except Exception as e:
        return f"News service unavailable, Sir. {e}"
