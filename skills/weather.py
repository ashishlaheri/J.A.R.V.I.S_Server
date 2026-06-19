"""Weather skill — free weather via wttr.in (no API key) + OpenWeatherMap (with key)."""

import aiohttp
from config import settings

OWM_URL = "https://api.openweathermap.org/data/2.5/weather"
OWM_FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"
WTTR_URL = "https://wttr.in"  # Free, no API key needed


async def _get_weather_free(city: str) -> str:
    """Free weather via wttr.in — no API key needed."""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{WTTR_URL}/{city}?format=j1"
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=8),
                headers={"User-Agent": "JARVIS/3.1"}
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                current = data["current_condition"][0]
                temp = current["temp_C"]
                feels = current["FeelsLikeC"]
                desc = current["weatherDesc"][0]["value"].lower()
                humidity = current["humidity"]
                return (f"Currently {temp}°C and {desc} in {city}, Sir. "
                        f"Feels like {feels}°C with {humidity}% humidity.")
    except Exception:
        return None


async def _get_weather_owm(city: str) -> str:
    """Weather via OpenWeatherMap (requires API key)."""
    if not settings.OPENWEATHER_API_KEY:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            params = {"q": city, "appid": settings.OPENWEATHER_API_KEY, "units": "metric"}
            async with session.get(OWM_URL, params=params, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                temp = round(data["main"]["temp"])
                feels = round(data["main"]["feels_like"])
                desc = data["weather"][0]["description"]
                humidity = data["main"]["humidity"]
                return (f"Currently {temp}°C and {desc} in {city}, Sir. "
                        f"Feels like {feels}°C with {humidity}% humidity.")
    except Exception:
        return None


async def get_weather(city: str = None) -> str:
    """Get weather — tries OpenWeatherMap first, falls back to wttr.in."""
    city = city or settings.WEATHER_CITY

    # Try OpenWeatherMap first (if API key configured)
    result = await _get_weather_owm(city)
    if result:
        return result

    # Fallback to free wttr.in
    result = await _get_weather_free(city)
    if result:
        return result

    return f"Could not fetch weather for {city} right now, Sir. Please try again."


async def get_forecast(city: str = None) -> str:
    city = city or settings.WEATHER_CITY

    # Try wttr.in forecast (free)
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{WTTR_URL}/{city}?format=j1"
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=8),
                headers={"User-Agent": "JARVIS/3.1"}
            ) as r:
                if r.status == 200:
                    data = await r.json()
                    forecasts = data.get("weather", [])[:3]
                    parts = []
                    for day in forecasts:
                        date = day["date"]
                        max_temp = day["maxtempC"]
                        min_temp = day["mintempC"]
                        desc = day["hourly"][4]["weatherDesc"][0]["value"].lower()
                        parts.append(f"{date}: {min_temp}-{max_temp}°C, {desc}")
                    if parts:
                        return f"Forecast for {city}, Sir. " + ". ".join(parts) + "."
    except Exception:
        pass

    # Fallback to OWM
    if not settings.OPENWEATHER_API_KEY:
        return f"Forecast unavailable for {city} right now, Sir."
    try:
        async with aiohttp.ClientSession() as session:
            params = {"q": city, "appid": settings.OPENWEATHER_API_KEY, "units": "metric", "cnt": 8}
            async with session.get(OWM_FORECAST_URL, params=params, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status != 200:
                    return f"Could not fetch forecast for {city}, Sir."
                data = await r.json()
                items = data.get("list", [])[:3]
                parts = []
                for item in items:
                    time_str = item["dt_txt"].split(" ")[1][:5]
                    temp = round(item["main"]["temp"])
                    desc = item["weather"][0]["description"]
                    parts.append(f"{time_str} — {temp}°C, {desc}")
                return f"Forecast for {city}: " + ". ".join(parts) + "."
    except Exception as e:
        return f"Forecast unavailable, Sir. {e}"
