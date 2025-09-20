# tools/common_tools.py
from google.adk.tools import FunctionTool
from utils.routing_helper import determine_intent

def determine_routing_intent(query: str,
                             has_existing_itinerary: bool = False) -> dict:
    try:
        return {"intent": determine_intent(query, has_existing_itinerary)}
    except Exception as e:
        return {"intent": "unknown", "error": str(e)}

common_function_tools = [FunctionTool(func=determine_routing_intent)]
