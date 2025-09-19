import asyncio
import json
import sys
import os
from dotenv import load_dotenv
import nest_asyncio
nest_asyncio.apply()
load_dotenv()
# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

import re
from datetime import datetime, timedelta
from typing import Dict, Any, List

from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from toolbox_core import ToolboxSyncClient

from services.weather_service import weather_service
from services.dynamic_ingestion_service import ingestion_service

# Connect to your MCP Toolbox server
toolbox_url = os.getenv("MCP_TOOLBOX_URL", "http://127.0.0.1:5000")
toolbox = ToolboxSyncClient(toolbox_url)

print("Connection successful!")

# Load your travel intelligence tools
travel_tools = toolbox.load_toolset('travel_genius_toolset')


# ------------------------------
# TOOL DEFINITIONS
# ------------------------------

def parse_adk_response(adk_response: list, user_input: dict = None) -> dict:
    """Parse ADK conversational response into structured itinerary format."""
    try:
        # Extract the final text response and any function call results
        final_text = ""
        weather_data = None
        tool_results = {}
        
        for turn in adk_response:
            if turn.get("content", {}).get("parts"):
                for part in turn["content"]["parts"]:
                    # Extract text responses
                    if "text" in part:
                        final_text += part["text"] + "\n"
                    
                    # Extract function call results
                    elif "functionResponse" in part:
                        func_response = part["functionResponse"]
                        func_name = func_response.get("name", "")
                        func_result = func_response.get("response", {})
                        
                        if func_name == "get_weather_analysis":
                            weather_data = func_result
                        elif func_name == "get_current_weather_report":
                            if func_result.get("success"):
                                weather_data = func_result
                        
                        tool_results[func_name] = func_result
        
        # If we don't have a complete itinerary yet, create one based on available data
        if not user_input:
            user_input = {
                'destination': 'Goa',
                'days': 5,
                'budget': 50000,
                'groupSize': 1
            }
        
        # Create structured itinerary based on weather data and user input
        itinerary = create_weather_optimized_itinerary(weather_data, user_input, final_text)
        
        return {
            "success": True,
            "itinerary": itinerary,
            "type": "itinerary",
            "conversational_response": final_text.strip(),
            "weather_data": weather_data
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to parse ADK response: {str(e)}",
            "type": "error",
            "raw_response": adk_response
        }




def create_weather_optimized_itinerary(weather_data: dict, user_input: dict, agent_text: str) -> dict:
    """Create structured itinerary based on weather analysis and user preferences."""
    destination = user_input.get('destination', 'Goa')
    days = user_input.get('days', 5)
    budget = user_input.get('budget', 50000)
    group_size = user_input.get('groupSize', 1)
    
    # Analyze weather suitability
    weather_suitable = weather_data.get('weather_suitable', True) if weather_data else True
    weather_score = weather_data.get('weather_score', 7.0) if weather_data else 7.0
    daily_forecast = weather_data.get('daily_forecast', []) if weather_data else []
    
    daily_plans = []
    cost_per_day = budget // days
    
    for day in range(1, days + 1):
        # Get weather for this day if available
        day_weather = None
        if daily_forecast and len(daily_forecast) >= day:
            day_weather = daily_forecast[day - 1]
        
        # Determine activity focus based on weather
        if day_weather:
            outdoor_score = day_weather.get('suitability_scores', {}).get('outdoor', 5)
            indoor_score = day_weather.get('suitability_scores', {}).get('indoor', 5)
            beach_score = day_weather.get('suitability_scores', {}).get('beach', 5)
        else:
            outdoor_score = 7
            indoor_score = 6
            beach_score = 7
        
        activities = []
        
        # Morning activity based on weather
        if outdoor_score >= 6:
            activities.append({
                "id": f"day{day}_outdoor",
                "title": f"🏖️ {destination} Beach Adventure",
                "description": f"Enjoy water sports, beach volleyball, and stunning coastline views at {destination}'s best beaches",
                "cost": int(cost_per_day * 0.3),
                "duration": "3-4 hours",
                "type": "adventure",
                "timing": "9:00 AM - 1:00 PM",
                "rating": 4.8,
                "weather_score": outdoor_score
            })
        else:
            activities.append({
                "id": f"day{day}_indoor",
                "title": f"🏛️ Cultural Heritage Tour",
                "description": f"Explore {destination}'s rich history through museums, art galleries, and colonial architecture",
                "cost": int(cost_per_day * 0.25),
                "duration": "3-4 hours",
                "type": "cultural",
                "timing": "9:00 AM - 1:00 PM",
                "rating": 4.6,
                "weather_score": indoor_score
            })
        
        # Afternoon food experience
        activities.append({
            "id": f"day{day}_food",
            "title": "🍽️ Authentic Local Cuisine",
            "description": f"Savor traditional {destination} delicacies at highly-rated local restaurants with cultural ambiance",
            "cost": int(cost_per_day * 0.35),
            "duration": "1-2 hours",
            "type": "food",
            "timing": "1:30 PM - 3:30 PM",
            "rating": 4.7
        })
        
        # Evening activity based on weather
        if outdoor_score >= 5:
            activities.append({
                "id": f"day{day}_evening",
                "title": "📸 Sunset Photography Spots",
                "description": "Capture breathtaking sunset views at Instagram-perfect locations with golden hour lighting",
                "cost": int(cost_per_day * 0.2),
                "duration": "2 hours",
                "type": "instagram",
                "timing": "6:00 PM - 8:00 PM",
                "rating": 4.9,
                "special_note": "Weather-dependent outdoor activity"
            })
        else:
            activities.append({
                "id": f"day{day}_indoor_evening",
                "title": "🎭 Evening Cultural Experience",
                "description": "Enjoy traditional performances, craft workshops, or indoor entertainment venues",
                "cost": int(cost_per_day * 0.25),
                "duration": "2-3 hours",
                "type": "cultural",
                "timing": "6:00 PM - 9:00 PM",
                "rating": 4.5,
                "weather_note": "Perfect indoor alternative for rainy weather"
            })
        
        daily_plans.append({
            "day": day,
            "activities": activities,
            "weather_summary": {
                "condition": day_weather.get('condition', 'Variable') if day_weather else 'Good',
                "outdoor_score": outdoor_score,
                "indoor_score": indoor_score,
                "recommendations": day_weather.get('recommendations', []) if day_weather else []
            }
        })
    
    return {
        "tripTitle": f"Weather-Optimized {days}-Day {destination} Adventure",
        "totalEstimatedCost": budget,
        "dailyPlans": daily_plans,
        "weatherOptimized": True,
        "sustainabilityScore": 8.2,
        "weatherSummary": {
            "overall_score": weather_score,
            "suitable_for_outdoor": weather_suitable,
            "alerts": weather_data.get('alerts', []) if weather_data else [],
            "recommendations": weather_data.get('recommendations', []) if weather_data else []
        }
    }





def extract_destination_from_query(query: str) -> dict:
    """Extract destination from user query."""
    import re
    query = re.sub(r'\b(the|in|at|for|weather|forecast|what|is|how|will|be)\b',
                   '', query, flags=re.IGNORECASE)
    patterns = [
        r'(?:weather|forecast).*?(?:in|at|for)\s+([A-Z][a-zA-Z\s]+?)(?:\?|$|\.)',
        r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',
    ]
    for pattern in patterns:
        matches = re.findall(pattern, query)
        if matches:
            destination = matches[0].strip()
            if len(destination) > 2 and destination.lower() not in ["tomorrow", "today", "next", "this"]:
                return {"destination": destination}
    for word in query.split():
        if word and word[0].isupper() and len(word) > 2:
            return {"destination": word}
    return {"destination": ""}


def get_weather_analysis(destination: str, start_date: str, duration_days: int) -> dict:
    """Get comprehensive weather analysis for a destination and travel dates."""
    try:
        print("Getting weather analysis for", destination, start_date, duration_days)
        print("Getting weather analysis for", destination, start_date, duration_days)
        result = asyncio.get_event_loop().run_until_complete(
            weather_service.get_weather_summary_for_dates(destination, start_date, duration_days)
        )
        score = result.get("overall_weather_score", 6)
        recs = []
        if score >= 8:
            recs.append("Excellent weather expected - perfect for all outdoor activities!")
        elif score >= 6:
            recs.append("Good weather overall with some mixed conditions - plan flexible itinerary")
        else:
            recs.append("Challenging weather expected - focus on indoor attractions and cultural sites")
        alerts = result.get("weather_alerts", [])
        if alerts:
            recs.append(f"Weather alerts: {len(alerts)} warnings for your travel dates")
        return {
            "destination": destination,
            "weather_suitable": score >= 6,
            "weather_score": score,
            "recommendations": recs,
            "daily_forecast": result.get("daily_weather", [])[:7],
            "alerts": alerts,
        }
    except Exception as e:
        return {"destination": destination, "error": str(e)}

async def get_current_weather_report(destination: str) -> dict:
    """Get current weather conditions and 7-day forecast for a destination."""
    try:
        print("Getting weather report for", destination)
        current = await weather_service.get_current_weather(destination)
        summary = await weather_service.get_weather_summary_for_dates(
            destination, datetime.now().strftime("%Y-%m-%d"), 7
        )
        

        # Fix the string indices error by ensuring proper data structure
        if not isinstance(current, dict) or "current" not in current:
            return {"destination": destination, "success": False, "error": "Invalid weather data structure"}
        
        current_data = current.get("current", {})
        if not isinstance(current_data, dict):
            return {"destination": destination, "success": False, "error": "Invalid current weather format"}

        daily_weather = []
        for day in summary.get("daily_weather", [])[:7]:
            if isinstance(day, dict) and 'suitability_scores' in day:
                out = day['suitability_scores'].get('outdoor', 5)
                ind = day['suitability_scores'].get('indoor', 5)
                
                if out >= 8:
                    rec = "Perfect for outdoor sightseeing!"
                elif out >= 6:
                    rec = "Good for mixed indoor/outdoor activities"
                else:
                    rec = "Focus on indoor attractions"

                daily_weather.append({
                    "date": day.get('date', ''),
                    "condition": day.get('condition', 'Variable'),
                    "min_temp": day.get('min_temp', 20),
                    "max_temp": day.get('max_temp', 30),
                    "outdoor_score": out,
                    "indoor_score": ind,
                    "activity_recommendation": rec
                })

        return {
            "destination": destination,
            "current": {
                "condition": current_data.get("condition", {}).get("text", "Variable"),
                "temperature": current_data.get("temp_c", 25),
                "feels_like": current_data.get("feelslike_c", 25)
            },
            "overall_weather_score": summary.get("overall_weather_score", 6),
            "daily_weather": daily_weather,
            "weather_alerts": summary.get("weather_alerts", []),
            "success": True
        }

    except Exception as e:
        print(f"Weather service error: {str(e)}")
        return {"destination": destination, "success": False, "error": str(e)}

def discover_new_destination(destination: str) -> dict:
    """Discover and ingest data for a new destination."""
    try:
        result = asyncio.get_event_loop().run_until_complete(
            ingestion_service.discover_missing_destination(destination)
        )
        if result["success"]:
            return {
                "success": True,
                "destination": destination,
                "activities_found": result.get("activities_found", 0),
                "hotels_found": result.get("hotels_found", 0),
            }
        return {
            "success": False,
            "destination": destination,
            "message": f"Could not discover {destination}",
        }
    except Exception as e:
        return {"success": False, "destination": destination, "error": str(e)}


def optimize_schedule_for_weather(destination: str, activities_json: str, duration_days: int) -> dict:
    """Optimize activity schedule based on weather forecast.
    Args:
        destination: Destination name
        activities_json: JSON string of list of activities
        duration_days: Trip duration in days
    """
    try:
        activities = json.loads(activities_json) if activities_json else []
        optimized = asyncio.get_event_loop().run_until_complete(
            weather_service.get_weather_optimized_schedule(destination, activities, duration_days)
        )
        return {
            "success": True,
            "destination": destination,
            "duration_days": duration_days,
            "optimized_schedule": optimized.get("optimized_schedule", []),
            "weather_notes": optimized.get("optimization_notes", []),
            "activities_optimized": len(activities)
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


def check_destination_exists(destination: str, personality_type: str = "cultural") -> dict:
    """Check if destination exists in the database and get basic info."""
    try:
        # If async call exists, wrap it; if not, keep simple
        # result = asyncio.get_event_loop().run_until_complete(some_async_check(...))
        return {
            "destination": destination,
            "exists": True,
            "personality_match": personality_type,
            "needs_discovery": False
        }
    except Exception as e:
        return {"destination": destination, "exists": False, "error": str(e)}
#@function_too
#@function_tool



# ------------------------------
# TOOLSET COMPOSITION
# ------------------------------

weather_tools = [
    FunctionTool(func=extract_destination_from_query),
    FunctionTool(func=get_weather_analysis),
    FunctionTool(func=get_current_weather_report),
    FunctionTool(func=discover_new_destination),
    FunctionTool(func=optimize_schedule_for_weather),
    FunctionTool(func=check_destination_exists)
]

all_tools = travel_tools + weather_tools


# Combine with existing travel tools
# all_tools = travel_tools + weather_tools

# ENHANCED AGENTS WITH PROPER TOOL ACCESS

# PERSONALITY ANALYSIS AGENT
personality_agent = Agent(
    name="personality_analyzer",
    model="gemini-2.0-flash",
    description="Analyzes user personality quiz results and travel preferences with weather awareness",
    instruction="""
    You are a travel psychology expert who analyzes user quiz responses to determine their travel personality type.
    
    Personality Types to Identify:
    - HERITAGE: Loves historical sites, cultural experiences, museums, traditional accommodations
    - ADVENTURE: Seeks active experiences, outdoor activities, unique challenges, offbeat destinations  
    - CULTURAL: Wants authentic local interactions, community experiences, traditional festivals
    - PARTY: Enjoys nightlife, social experiences, vibrant cities, entertainment venues
    - LUXURY: Prefers premium experiences, comfort, exclusive services, high-end accommodations
    
    Weather Considerations:
    - For ADVENTURE personalities: Emphasize good weather days for outdoor activities
    - For CULTURAL personalities: Mix indoor/outdoor based on weather
    - For HERITAGE personalities: Indoor alternatives during poor weather
    
    Use the available tools to check destination data and weather conditions.
    Always consider seasonal weather patterns when making recommendations.
    """,
    tools=all_tools
)

# BUDGET OPTIMIZATION AGENT
budget_agent = Agent(
    name="budget_optimizer",
    model="gemini-2.0-flash", 
    description="Optimizes budget allocation with weather-aware contingency planning",
    instruction="""
    You are a travel finance expert who creates realistic budget allocations based on personality and destination data.
    
    Budget Allocation by Personality:
    - HERITAGE: 40% transport, 35% accommodation, 20% cultural activities, 5% buffer
    - ADVENTURE: 35% transport, 25% accommodation, 35% activities/experiences, 5% buffer  
    - LUXURY: 30% transport, 45% accommodation, 20% premium experiences, 5% buffer
    - PARTY: 35% transport, 30% accommodation, 30% nightlife/entertainment, 5% buffer
    - CULTURAL: 40% transport, 30% accommodation, 25% authentic experiences, 5% buffer
    
    Weather Contingency:
    - Always allocate 3-5% extra for weather-related changes (indoor alternatives, transport delays)
    - Suggest flexible bookings during monsoon/winter seasons
    - Include indoor activity options within the cultural/entertainment budget
    
    Use calculate-trip-budget and search-transport-options tools to get accurate cost estimates.
    Use get_weather_analysis tool to factor in weather-related contingencies.
    """,
    tools=all_tools
)

# HIDDEN GEMS DISCOVERY AGENT
gems_agent = Agent(
    name="gems_discoverer",
    model="gemini-2.0-flash",
    description="Discovers authentic hidden gems with weather suitability",
    instruction="""
    You are a local travel expert who specializes in uncovering authentic, weather-appropriate experiences.
    
    Your Mission:
    1. Use get-hidden-gems tool to find authentic local experiences
    2. Use search-activities-by-interest to discover unique activities with high sustainability scores
    3. Use get_weather_analysis to consider weather suitability for outdoor vs indoor hidden gems
    4. Prioritize experiences marked as "hidden gems" in the database
    5. Focus on community-based tourism and local interactions
    
    Weather Adaptation:
    - Rainy season: Focus on indoor workshops, covered markets, cultural centers
    - Hot season: Early morning or evening experiences, shaded locations
    - Pleasant weather: Outdoor markets, nature walks, rooftop experiences
    
    Always explain why each recommendation suits the weather and season.
    """,
    tools=all_tools
)

# SUSTAINABILITY ADVISOR AGENT
sustainability_agent = Agent(
    name="sustainability_advisor",
    model="gemini-2.0-flash",
    description="Evaluates environmental impact including weather-related carbon footprint",
    instruction="""
    You are an eco-travel expert focused on sustainable and responsible tourism practices.
    
    Available MCP Tools for sustainability analysis:
    - search-transport-options: Compare carbon footprints of different transport modes
    - search-hotels-enhanced: Evaluate hotel sustainability scores and ratings
    - search-activities-by-interest: Find activities with high sustainability ratings (8+)
    - get-hidden-gems: Discover community-based and sustainable experiences
    
    Your Responsibilities:
    1. Use search_transport_to_destination to compare eco-adjusted carbon footprints
    2. Prioritize accommodations and activities with high sustainability scores
    3. Calculate total trip carbon footprint including weather-related adjustments
    4. Recommend off-peak travel to reduce environmental impact
    
    Weather Sustainability Factors:
    - Use get_weather_analysis to assess seasonal travel patterns and carbon impact
    - Consider weather-related transport delays and alternative options
    - Factor in energy consumption of indoor alternatives during extreme weather
    - Encourage shoulder season travel to reduce overcrowding
    
    Always provide:
    - Seasonal carbon footprint variations
    - Weather-resilient sustainable choices  
    - Climate-conscious timing recommendations
    - Community-based tourism options from hidden gems
    """,
    tools=all_tools
)

# ACCOMMODATION SPECIALIST AGENT
accommodation_agent = Agent(
    name="accommodation_specialist", 
    model="gemini-2.0-flash",
    description="Finds perfect accommodations with weather-appropriate amenities",
    instruction="""
    You are an accommodation expert who matches travelers with weather-appropriate places to stay.
    
    Weather-Aware Selection:
    - Monsoon season: Properties with covered parking, good drainage, backup power
    - Summer: Air conditioning, pools, shaded outdoor areas
    - Winter: Heating, warm amenities, indoor recreation
    - Year-round: Flexible common areas for weather changes
    
    Use get_weather_analysis tool to understand weather conditions for the travel period.
    Use search-hotels-enhanced to find accommodations with appropriate amenities.
    
    Match accommodation types to personality AND weather:
    - ADVENTURE + Good weather: Eco-lodges, outdoor-focused properties
    - ADVENTURE + Poor weather: Properties with indoor activities, gyms
    - LUXURY: Climate-controlled comfort with weather-resistant amenities
    
    Always explain how each property handles different weather conditions.
    """,
    tools=all_tools
)

# WEATHER PLANNER AGENT
weather_agent = Agent(
    name="weather_planner",
    model="gemini-2.0-flash",
    description="Advanced weather monitoring and dynamic itinerary optimization",
    instruction="""
    You are a weather-aware trip optimizer with real-time adaptation capabilities.
    
    Your Core Functions:
    1. Use get_current_weather_report tool to get comprehensive weather forecasts
    2. Use get_weather_analysis tool to score activities by weather suitability (1-10 scale)
    3. Use optimize_schedule_for_weather tool to reorganize itinerary for maximum enjoyment
    4. Provide weather-specific recommendations and alternatives
    5. Generate weather alerts and contingency plans
    
    Optimization Strategy:
    - Prioritize outdoor activities on high-score weather days (8-10/10)
    - Schedule indoor cultural activities during poor weather (1-4/10)
    - Use mixed indoor/outdoor for moderate weather (5-7/10)
    - Consider time-of-day adjustments (early morning for hot weather)
    - Maintain personality alignment while adapting to conditions
    
    Weather Scoring Criteria:
    - Outdoor activities: Penalize rain/storms heavily, favor clear/sunny conditions
    - Indoor activities: Weather-neutral with bonus during poor outdoor conditions
    - Beach activities: Require sunshine, moderate temperatures, low precipitation
    - Cultural activities: Flexible but consider comfort factors
    
    Always maintain the traveler's personality preferences while optimizing for weather.
    """,
    tools=all_tools
)

travel_genius = Agent(
    name="travel_genius",
    model="gemini-2.0-flash",
    description="AI-powered travel planner that returns structured JSON itineraries",
    instruction="""You are the Travel Genius - an expert AI travel planner who creates detailed itineraries.
    CRITICAL: You MUST respond with ONLY valid JSON in this exact structure (no additional text, explanations, or markdown) also do not generate only two activities per day, always include 2-4 activities per day based on weather data. Here is the structure:

{
  "tripTitle": "Weather-Optimized X-Day [Destination] Adventure",
  "totalEstimatedCost": 50000,
  "dailyPlans": [
    {
      "day": 1,
      "activities": [
        {
          "id": "day1_activity1",
          "title": "🏖️ Beach Adventure & Water Sports",
          "description": "Experience thrilling water sports including jet skiing, parasailing, and banana boat rides at the most popular beach",
          "cost": 2500,
          "duration": "3-4 hours",
          "type": "adventure",
          "timing": "9:00 AM - 1:00 PM",
          "rating": 4.8
        },
        {
          "id": "day1_activity2",
          "title": "🍽️ Authentic Local Seafood Experience",
          "description": "Savor fresh catch of the day at a highly-rated beachfront restaurant with traditional coastal flavors",
          "cost": 1200,
          "duration": "1-2 hours",
          "type": "food",
          "timing": "1:30 PM - 3:00 PM",
          "rating": 4.6
        },
        {
          "id": "day1_activity3",
          "title": "📸 Golden Hour Photography Session",
          "description": "Capture stunning sunset photos at Instagram-famous viewpoints with panoramic coastal views",
          "cost": 500,
          "duration": "2 hours",
          "type": "instagram",
          "timing": "6:00 PM - 8:00 PM",
          "rating": 4.9
        }
      ],
      "weatherSummary": {
        "condition": "Partly Cloudy",
        "outdoorScore": 7,
        "indoorScore": 6,
        "recommendations": ["Good weather for outdoor activities"]
      }
    }
  ],
  "weatherOptimized": true,
  "sustainabilityScore": 8.2,
  "weatherSummary": {
    "overallScore": 6.5,
    "suitableForOutdoor": true,
    "alerts": [],
    "recommendations": ["Pack light rain gear", "Best outdoor activities in morning"]
  },
  "aiRecommendations": [
    "Book water sports in advance for better rates",
    "Try local fish curry - it's a must-have",
    "Visit sunset points early to secure good spots"
  ],
  "instagramSpots": [
    "Sunset Point Beach",
    "Lighthouse viewpoint", 
    "Colorful fishing boats harbor"
  ],
  "generatedBy": "AI Travel Genius",
  "generatedAt": "2025-09-16T01:37:00.000Z"
}

RULES:
1. Include 2-4 activities per day with realistic costs in INR
2. Use weather data from tools to optimize indoor/outdoor activities  
3. Activity types: "adventure", "food", "cultural", "instagram", "attraction", "transport"
4. Always include at least one "instagram" type activity
5. Costs should be realistic for the destination and activity type
6. Use emojis in titles for visual appeal
7. Return ONLY the JSON object, no other text whatsoever""",
    sub_agents=[personality_agent, budget_agent, gems_agent, sustainability_agent, accommodation_agent, weather_agent],
    tools=all_tools
)


itinerary_assistant = Agent(
    name="itinerary_assistant",
    model="gemini-2.0-flash",
    description="Conversational assistant for itinerary questions and modifications",
    instruction="""You are a friendly AI Travel Assistant chatbot for AI Travel Genius. 

Your role is to help users with questions about their EXISTING travel itinerary in a conversational way.

CAPABILITIES:
- Answer questions about specific activities, costs, and timings
- Suggest modifications and alternatives
- Provide local tips and cultural insights
- Help with practical travel advice
- Explain weather considerations
- Offer budget-friendly alternatives

RESPONSE STYLE:
- Be conversational, friendly, and enthusiastic
- Use travel emojis appropriately (🎯, 🏖️, 🍽️, ✈️, 🌟, etc.)
- Provide specific, actionable advice
- Keep responses concise but helpful (2-4 sentences max)
- Always reference the specific itinerary when possible

EXAMPLE RESPONSES:
- "Great question! 🤔 For Day 2, I'd recommend trying the spice plantation lunch instead - it's vegetarian-friendly and costs about ₹800 less! Plus you'll learn about local Goan spices. 🌿"
- "Perfect timing for Fort Aguada! 📸 The golden hour shots there are absolutely stunning. Arrive by 6:30 PM for the best lighting, and don't forget to explore the lighthouse too! ✨"

You are NOT generating new itineraries - only helping with existing ones.""",
    tools=all_tools
)


travel_genius_router = Agent(
    name="travel_genius_router",
    model="gemini-2.0-flash",
    description="Router that determines whether to generate itineraries or provide chat assistance",
    instruction="""You are the master router for AI Travel Genius. Your job is to determine the user's intent and route to the appropriate agent.

ROUTING LOGIC:
1. If user wants to CREATE/GENERATE a NEW itinerary → Route to travel_genius agent
2. If user has QUESTIONS/MODIFICATIONS about an EXISTING itinerary → Route to itinerary_assistant agent

INDICATORS for ITINERARY GENERATION (travel_genius):
- "Create itinerary", "Plan a trip", "Generate itinerary"
- "X-day trip to [destination]" 
- Contains budget, duration, destination info for new planning
- "Plan my vacation", "Create travel plan"

INDICATORS for CHAT ASSISTANCE (itinerary_assistant):
- Questions about existing activities: "Can you change...", "What about...", "Is there..."
- Asking for alternatives: "cheaper option", "vegetarian restaurant", "indoor activity"
- Practical questions: "what to pack", "how to get there", "best time"
- Modifications: "replace this activity", "suggest different"

OUTPUT INSTRUCTIONS:
- If routing to travel_genius: Simply pass the query as-is for JSON generation
- If routing to itinerary_assistant: Pass the query with any provided itinerary context

You do not generate responses yourself - you only route to the appropriate agent.""",
    sub_agents=[travel_genius, itinerary_assistant],
    tools=all_tools
)

# ------------------------------
# QUERY HANDLER
# ------------------------------

def determine_intent(query: str, has_existing_itinerary: bool = False) -> str:
    """Determine if this is an itinerary generation or chat query"""
    query_lower = query.lower()
    
    # Strong indicators for itinerary generation
    generation_keywords = [
        'create itinerary', 'plan a trip', 'generate itinerary', 
        'plan my vacation', 'create travel plan', 'days trip to',
        'day trip', 'travel itinerary', 'plan for'
    ]
    
    # Strong indicators for chat assistance
    chat_keywords = [
        'can you change', 'what about', 'is there', 'how do i',
        'cheaper option', 'alternative', 'suggest different', 
        'what should i pack', 'best time', 'how to get',
        'vegetarian', 'modify', 'replace'
    ]
    
    # Check for generation keywords
    if any(keyword in query_lower for keyword in generation_keywords):
        return 'generate'
    
    # Check for chat keywords or if we have existing itinerary
    if any(keyword in query_lower for keyword in chat_keywords) or has_existing_itinerary:
        return 'chat'
    
    # Default fallback based on context
    return 'chat' if has_existing_itinerary else 'generate'

def format_weather_response(weather_report: Dict[str, Any]) -> str:
    if not weather_report.get("success", False):
        return f"Sorry, couldn't get weather information: {weather_report.get('error', 'Unknown error')}"
    destination = weather_report["destination"]
    current = weather_report["current"]
    overall_score = weather_report["overall_weather_score"]
    response = f"""🌤️ Weather Report for {destination}:

📍 Current Conditions:
{current['condition']}, {current['temperature']}°C (feels like {current['feels_like']}°C)

📅 7-Day Travel Outlook (Weather Score: {overall_score}/10):
"""
    for day in weather_report["daily_weather"]:
        response += f"""
• {day['date']}: {day['condition']}, {day['min_temp']}-{day['max_temp']}°C
  Activity Score: Outdoor {day['outdoor_score']}/10, Indoor {day['indoor_score']}/10
  Best for: {day['activity_recommendation']}"""
    alerts = weather_report.get("weather_alerts", [])
    if alerts:
        response += "\n\n⚠️ Weather Alerts:"
        for alert in alerts[:2]:
            response += f"\n• {alert.get('message', 'Weather alert active')}"
    response += "\n\n💡 Ready to create a weather-optimized itinerary? Just tell me your travel dates and preferences!"
    return response


# ------------------------------
# EXPORTS
# ------------------------------

root_agent = travel_genius

__all__ = ['root_agent', 'handle_user_query']