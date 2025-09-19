# utils/response_helpers.py
import json
from typing import Dict, Any, List
from utils.itinerary_helper import create_weather_optimized_itinerary

def parse_adk_response_data(adk_response: list,
                            user_input: dict = None) -> dict:
    """Collects tool outputs + text and returns structured itinerary."""
    final_text, weather_data = "", None
    for turn in adk_response:
        for part in turn.get("content", {}).get("parts", []):
            if "text" in part:
                final_text += part["text"] + "\n"
            elif "functionResponse" in part:
                resp = part["functionResponse"]
                if resp.get("name") in ["get_weather_analysis",
                                        "get_current_weather_report"]:
                    weather_data = resp["response"]

    if not user_input:
        user_input = {"destination": "Goa", "days": 5, "budget": 50_000}

    itinerary = create_weather_optimized_itinerary(weather_data,
                                                   user_input,
                                                   final_text)

    return {
        "success": True,
        "itinerary": itinerary,
        "conversational_response": final_text.strip(),
        "weather_data": weather_data
    }

# -------- Pretty printer (copied verbatim) --------
def format_weather_response_text(weather_report: Dict[str, Any]) -> str:
    if not weather_report.get("success"):
        return f"Sorry, couldn't get weather information: {weather_report.get('error','Unknown error')}"
    destination  = weather_report["destination"]
    current      = weather_report["current"]
    overall      = weather_report["overall_weather_score"]

    out = (f"🌤️ Weather Report for {destination}:\n\n"
           f"📍 Current Conditions:\n"
           f"{current['condition']}, {current['temperature']}°C "
           f"(feels like {current['feels_like']}°C)\n\n"
           f"📅 7-Day Travel Outlook (Weather Score: {overall}/10):\n")

    for d in weather_report["daily_weather"]:
        out += (f"\n• {d['date']}: {d['condition']}, "
                f"{d['min_temp']}-{d['max_temp']}°C\n"
                f"  Outdoor {d['outdoor_score']}/10, "
                f"Indoor {d['indoor_score']}/10 → {d['activity_recommendation']}")

    if (alerts := weather_report.get("weather_alerts")):
        out += "\n\n⚠️ Weather Alerts:"
        for a in alerts[:2]:
            out += f"\n• {a.get('message','Alert active')}"
    return out + "\n\n💡 Need a full itinerary? Just ask!"
