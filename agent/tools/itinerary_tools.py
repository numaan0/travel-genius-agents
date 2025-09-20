# tools/itinerary_tools.py
import json
from google.adk.tools import FunctionTool
from utils.itinerary_helper import (
    create_weather_optimized_itinerary
)

def parse_and_structure_itinerary(weather_data_json: str,
                                  user_input_json: str,
                                  agent_text: str) -> dict:
    try:
        weather = json.loads(weather_data_json) if weather_data_json else {}
        user    = json.loads(user_input_json)   if user_input_json   else {}
        itinerary = create_weather_optimized_itinerary(weather, user, agent_text)
        return {"success": True, "itinerary": itinerary}
    except Exception as e:
        return {"success": False, "error": str(e)}

itinerary_function_tools = [
    FunctionTool(func=parse_and_structure_itinerary)
]
