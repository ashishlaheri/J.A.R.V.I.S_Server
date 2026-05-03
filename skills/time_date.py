"""Time, date, and greeting utilities."""

import datetime


def get_time() -> str:
    return f"The time is {datetime.datetime.now().strftime('%I:%M %p')}, Sir."


def get_date() -> str:
    return datetime.datetime.now().strftime("Today is %A, %B %d, %Y, Sir.")


def get_greeting() -> str:
    hour = datetime.datetime.now().hour
    if hour < 12:
        return "Good morning"
    elif hour < 18:
        return "Good afternoon"
    return "Good evening"


def get_briefing_intro() -> str:
    return f"{get_greeting()}, Sir. Jarvis online — all systems ready."
