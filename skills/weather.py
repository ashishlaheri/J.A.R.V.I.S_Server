"""Weather skill — OpenWeatherMap free tier."""

import aiohttp
from config import settings

API_URL = "https://api.openweathermap.org/data/2.5/weather"
FORECAST_URL = "https://api.openweathermap.org/data/2.5/forecast"


async def get_weather(city: str = None) -> str:
    city = city or settings.WEATHER_CITY
    if not settings.OPENWEATHER_API_KEY:
        return "Weather API key not configured, Sir. Add OPENWEATHER_API_KEY to your .env file."
    try:
        async with aiohttp.ClientSession() as session:
            params = {"q": city, "appid": settings.OPENWEATHER_API_KEY, "units": "metric"}
            async with session.get(API_URL, params=params, timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status != 200:
                    return f"Could not fetch weather for {city}, Sir."
                data = await r.json()
                temp = round(data["main"]["temp"])
                feels = round(data["main"]["feels_like"])
                desc = data["weather"][0]["description"]
                humidity = data["main"]["humidity"]
                return (f"Currently {temp}°C and {desc} in {city}, Sir. "
                        f"Feels like {feels}°C with {humidity}% humidity.")
    except Exception as e:
        return f"Weather service unavailable, Sir. {e}"


async def get_forecast(city: str = None) -> str:
    city = city or settings.WEATHER_CITY
    if not settings.OPENWEATHER_API_KEY:
        return "Weather API key not configured, Sir."
    try:
        async with aiohttp.ClientSession() as session:
            params = {"q": city, "appid": settings.OPENWEATHER_API_KEY, "units": "metric", "cnt": 8}
            async with session.get(FORECAST_URL, params=params, timeout=aiohttp.ClientTimeout(total=8)) as r:
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
