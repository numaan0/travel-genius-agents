# utils/weather_helpers.py
import re
from typing import Dict, Any, List

def extract_destination_from_text(query: str) -> str:
    """Pure regex destination extractor (pulled from agent.py)."""
    query = re.sub(r'\b(the|in|at|for|weather|forecast|what|is|how|will|be)\b',
                   '', query, flags=re.IGNORECASE)
    patterns = [
        r'(?:weather|forecast).*?(?:in|at|for)\s+([A-Z][a-zA-Z\s]+?)(?:\?|$|\.)',
        r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
    ]
    for pattern in patterns:
        if (m := re.findall(pattern, query)):
            dest = m[0].strip()
            if len(dest) > 2 and dest.lower() not in ["tomorrow", "today", "next", "this"]:
                return dest
    for word in query.split():
        if word and word[0].isupper() and len(word) > 2:
            return word
    return ""

def analyze_weather_suitability(weather_result: dict, destination: str) -> dict:
    """Scoring + recommendations logic copied intact from agent.py."""
    score = weather_result.get("overall_weather_score", 6)
    recs = []
    if score >= 8:
        recs.append("Excellent weather expected - perfect for all outdoor activities!")
    elif score >= 6:
        recs.append("Good weather overall with some mixed conditions - plan flexible itinerary")
    else:
        recs.append("Challenging weather expected - focus on indoor attractions and cultural sites")
    alerts = weather_result.get("weather_alerts", [])
    if alerts:
        recs.append(f"Weather alerts: {len(alerts)} warnings for your travel dates")
    return {
        "destination": destination,
        "weather_suitable": score >= 6,
        "weather_score": score,
        "recommendations": recs,
        "daily_forecast": weather_result.get("daily_weather", [])[:7],
        "alerts": alerts,
    }
