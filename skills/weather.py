"""Weather skill — uses Open-Meteo (100% free, no API key, works everywhere).

Open-Meteo is a free, open-source weather API:
- No API key required
- No registration
- No rate limits for personal use
- Works from any server (AWS, Docker, etc.)
- Returns JSON reliably

Fallback chain: Open-Meteo → wttr.in → OpenWeatherMap (if key configured)
"""

import aiohttp
from config import settings

# Open-Meteo API (100% free, no key needed, works from data centers)
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

# WMO Weather interpretation codes → human descriptions
WMO_CODES = {
    0: "clear sky", 1: "mainly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "freezing fog",
    51: "light drizzle", 53: "moderate drizzle", 55: "dense drizzle",
    61: "slight rain", 63: "moderate rain", 65: "heavy rain",
    71: "slight snow", 73: "moderate snow", 75: "heavy snow",
    77: "snow grains", 80: "slight rain showers", 81: "moderate rain showers",
    82: "violent rain showers", 85: "slight snow showers", 86: "heavy snow showers",
    95: "thunderstorm", 96: "thunderstorm with slight hail", 99: "thunderstorm with heavy hail",
}

# Cache city → coordinates to avoid repeated geocoding
_geo_cache: dict[str, tuple[float, float]] = {}


async def _geocode(session: aiohttp.ClientSession, city: str) -> tuple[float, float, str] | None:
    """Convert city name to latitude/longitude using Open-Meteo geocoding."""
    # Check cache first
    city_lower = city.lower().strip()
    if city_lower in _geo_cache:
        lat, lon = _geo_cache[city_lower]
        return lat, lon, city

    try:
        params = {"name": city, "count": 1, "language": "en", "format": "json"}
        async with session.get(GEOCODE_URL, params=params, timeout=aiohttp.ClientTimeout(total=5)) as r:
            if r.status != 200:
                return None
            data = await r.json()
            results = data.get("results", [])
            if not results:
                return None
            loc = results[0]
            lat = loc["latitude"]
            lon = loc["longitude"]
            name = loc.get("name", city)
            _geo_cache[city_lower] = (lat, lon)
            return lat, lon, name
    except Exception as e:
        print(f"[WEATHER] Geocode error for '{city}': {e}")
        return None


async def _get_weather_openmeteo(city: str) -> str | None:
    """Get current weather from Open-Meteo (free, no API key, reliable)."""
    try:
        async with aiohttp.ClientSession() as session:
            # Step 1: Geocode the city name
            geo = await _geocode(session, city)
            if not geo:
                return None
            lat, lon, resolved_name = geo

            # Step 2: Get weather data
            params = {
                "latitude": lat,
                "longitude": lon,
                "current_weather": "true",
                "hourly": "relativehumidity_2m,apparent_temperature",
                "forecast_days": 1,
                "timezone": "auto",
            }
            async with session.get(
                WEATHER_URL, params=params,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as r:
                if r.status != 200:
                    print(f"[WEATHER] Open-Meteo returned status {r.status}")
                    return None
                data = await r.json()

                current = data.get("current_weather", {})
                temp = round(current.get("temperature", 0))
                wind = round(current.get("windspeed", 0))
                code = current.get("weathercode", 0)
                desc = WMO_CODES.get(code, "unknown conditions")

                # Get humidity and feels-like from hourly (closest hour)
                hourly = data.get("hourly", {})
                humidity_list = hourly.get("relativehumidity_2m", [])
                feels_list = hourly.get("apparent_temperature", [])

                # Use the most recent available value
                humidity = humidity_list[0] if humidity_list else "N/A"
                feels = round(feels_list[0]) if feels_list else temp

                return (
                    f"Currently {temp}°C and {desc} in {resolved_name}, Sir. "
                    f"Feels like {feels}°C with {humidity}% humidity and wind at {wind} km/h."
                )
    except Exception as e:
        print(f"[WEATHER] Open-Meteo error: {e}")
        return None


async def _get_weather_wttr(city: str) -> str | None:
    """Fallback: free weather via wttr.in."""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://wttr.in/{city}?format=j1"
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=6),
                headers={
                    "User-Agent": "curl/7.68.0",
                    "Accept": "application/json"
                }
            ) as r:
                if r.status != 200:
                    return None
                text = await r.text()
                # wttr.in sometimes returns HTML from data centers
                if text.strip().startswith("<") or "<!DOCTYPE" in text[:100]:
                    return None
                import json
                data = json.loads(text)
                current = data["current_condition"][0]
                temp = current["temp_C"]
                feels = current["FeelsLikeC"]
                desc = current["weatherDesc"][0]["value"].lower()
                humidity = current["humidity"]
                return (f"Currently {temp}°C and {desc} in {city}, Sir. "
                        f"Feels like {feels}°C with {humidity}% humidity.")
    except Exception as e:
        print(f"[WEATHER] wttr.in error: {e}")
        return None


async def _get_weather_owm(city: str) -> str | None:
    """Weather via OpenWeatherMap (requires API key)."""
    if not settings.OPENWEATHER_API_KEY:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            params = {"q": city, "appid": settings.OPENWEATHER_API_KEY, "units": "metric"}
            async with session.get(
                "https://api.openweathermap.org/data/2.5/weather",
                params=params, timeout=aiohttp.ClientTimeout(total=8)
            ) as r:
                if r.status != 200:
                    return None
                data = await r.json()
                temp = round(data["main"]["temp"])
                feels = round(data["main"]["feels_like"])
                desc = data["weather"][0]["description"]
                humidity = data["main"]["humidity"]
                return (f"Currently {temp}°C and {desc} in {city}, Sir. "
                        f"Feels like {feels}°C with {humidity}% humidity.")
    except Exception as e:
        print(f"[WEATHER] OWM error: {e}")
        return None


async def get_weather(city: str = None) -> str:
    """Get weather with triple-fallback: Open-Meteo → wttr.in → OWM."""
    city = city or settings.WEATHER_CITY
    print(f"[WEATHER] Fetching weather for: {city}")

    # 1. Open-Meteo (most reliable from data centers)
    result = await _get_weather_openmeteo(city)
    if result:
        return result

    # 2. wttr.in (sometimes blocked from AWS)
    result = await _get_weather_wttr(city)
    if result:
        return result

    # 3. OpenWeatherMap (requires API key)
    result = await _get_weather_owm(city)
    if result:
        return result

    return f"Could not fetch weather for {city} right now, Sir. All three weather sources are unavailable."


async def get_forecast(city: str = None) -> str:
    """Get 3-day forecast from Open-Meteo."""
    city = city or settings.WEATHER_CITY

    try:
        async with aiohttp.ClientSession() as session:
            geo = await _geocode(session, city)
            if not geo:
                return f"Could not find location '{city}', Sir."
            lat, lon, resolved_name = geo

            params = {
                "latitude": lat,
                "longitude": lon,
                "daily": "temperature_2m_max,temperature_2m_min,weathercode",
                "forecast_days": 3,
                "timezone": "auto",
            }
            async with session.get(
                WEATHER_URL, params=params,
                timeout=aiohttp.ClientTimeout(total=8)
            ) as r:
                if r.status != 200:
                    return f"Forecast unavailable for {city}, Sir."
                data = await r.json()
                daily = data.get("daily", {})
                dates = daily.get("time", [])
                max_temps = daily.get("temperature_2m_max", [])
                min_temps = daily.get("temperature_2m_min", [])
                codes = daily.get("weathercode", [])

                parts = []
                for i in range(min(3, len(dates))):
                    desc = WMO_CODES.get(codes[i], "unknown")
                    parts.append(
                        f"{dates[i]}: {round(min_temps[i])}-{round(max_temps[i])}°C, {desc}"
                    )

                if parts:
                    return f"Forecast for {resolved_name}, Sir. " + ". ".join(parts) + "."
                return f"Forecast data unavailable for {city}, Sir."
    except Exception as e:
        print(f"[WEATHER] Forecast error: {e}")
        return f"Forecast unavailable, Sir. {e}"
