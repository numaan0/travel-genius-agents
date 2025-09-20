# tools/destination_tools.py
import asyncio
from google.adk.tools import FunctionTool
from services.dynamic_ingestion_service import ingestion_service

def discover_new_destination(destination: str) -> dict:
    try:
        res = asyncio.get_event_loop().run_until_complete(
            ingestion_service.discover_missing_destination(destination))
        return res
    except Exception as e:
        return {"success": False, "error": str(e), "destination": destination}

def check_destination_exists(destination: str,
                             personality_type: str = "adventure") -> dict:
    try:
        ok = ingestion_service.db_integration.test_connection()
        return {
            "destination": destination,
            "exists": ok,
            "personality_match": personality_type,
            "needs_discovery": not ok
        }
    except Exception as e:
        return {"destination": destination, "exists": False, "error": str(e)}

destination_function_tools = [
    FunctionTool(func=discover_new_destination),
    FunctionTool(func=check_destination_exists),
]
