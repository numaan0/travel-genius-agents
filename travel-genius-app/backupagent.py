import sys
import os
from dotenv import load_dotenv

load_dotenv()
# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)
import re
from datetime import datetime, timedelta
from typing import Dict, Any, List
from datetime import datetime, timedelta

from google.adk.agents import Agent
from toolbox_core import ToolboxSyncClient

from services.weather_service import weather_service
from services.dynamic_ingestion_service import ingestion_service

# Connect to your MCP Toolbox server
toolbox_url = os.getenv("MCP_TOOLBOX_URL", "http://127.0.0.1:5000")
toolbox = ToolboxSyncClient(toolbox_url)

print("Connection successful!")

# Load your travel intelligence tools
travel_tools = toolbox.load_toolset('travel_genius_toolset')


async def handle_user_query(self, user_query: str) -> str:
    """
    Enhanced query routing that properly handles weather and trip planning requests
    """
    query_lower = user_query.lower()
    
    # Enhanced weather query detection
    weather_keywords = ["weather", "forecast", "rain", "sunny", "temperature", "climate", "conditions"]
    trip_keywords = ["plan", "trip", "itinerary", "travel", "visit", "book"]
    
    if any(keyword in query_lower for keyword in weather_keywords):
        destination = extract_destination_from_query(user_query)
        if destination:
            return await self.handle_weather_query(destination)
        else:
            return "I'd be happy to check the weather! Which destination are you asking about?"
    
    elif any(keyword in query_lower for keyword in trip_keywords):
        return await self.handle_trip_planning_query(user_query)
    
    else:
        return """I can help you with:
        
            🌤️ Weather information - "What's the weather in Mumbai?"
            🗓️ Trip planning - "Plan a 5-day trip to Kerala" 
            📋 Weather-optimized itineraries - "Plan outdoor activities in Goa for next week"

            What would you like to know?"""

# Add this helper function to extract destinations properly:
def extract_destination_from_query(query: str) -> str:
    """Extract destination from user query using improved pattern matching"""
    
    # Remove common noise words
    query = re.sub(r'\b(the|in|at|for|weather|forecast|what|is|how|will|be)\b', '', query, flags=re.IGNORECASE)
    
    # Patterns to match destinations
    patterns = [
        r'(?:weather|forecast).*?(?:in|at|for)\s+([A-Z][a-zA-Z\s]+?)(?:\?|$|\.)',
        r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',  # Capitalized words
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, query)
        if matches:
            destination = matches[0].strip()
            # Filter out common false positives
            if len(destination) > 2 and destination.lower() not in ['tomorrow', 'today', 'next', 'this']:
                return destination
    
    # Fallback: look for any capitalized word that might be a place
    words = query.split()
    for word in words:
        if word and word[0].isupper() and len(word) > 2:
            return word
    
    return None

# Enhance your existing handle_trip_planning_query:
async def handle_trip_planning_query(self, query: str) -> str:
    """Handle trip planning with automatic weather integration"""
    
    destination = extract_destination_from_query(query)
    
    if not destination:
        return """I'd love to plan a weather-optimized trip for you!
        
            Please tell me:
            📍 Destination
            📅 Travel dates (or duration)  
            🎭 Your interests (adventure, culture, luxury, etc.)
            💰 Budget range

            Example: "Plan a 5-day cultural trip to Kerala from Dec 15-20 with ₹40,000 budget" """
    
    # Extract duration if mentioned
    duration_match = re.search(r'(\d+)[-\s]?days?', query.lower())
    duration = int(duration_match.group(1)) if duration_match else 5
    
    # Check weather for the destination
    weather_summary = weather_service.get_weather_summary_for_dates(
        destination, 
        datetime.now().strftime("%Y-%m-%d"), 
        duration
    )
    
    if weather_summary.get("overall_weather_score", 0) >= 7:
        weather_note = f"Great news! {destination} has excellent weather (Score: {weather_summary['overall_weather_score']}/10) for your travel dates."
    elif weather_summary.get("overall_weather_score", 0) >= 5:
        weather_note = f"{destination} has mixed weather conditions (Score: {weather_summary['overall_weather_score']}/10). I'll optimize your itinerary accordingly."
    else:
        weather_note = f"{destination} has challenging weather (Score: {weather_summary['overall_weather_score']}/10). I'll focus on indoor activities and weather-resistant experiences."
    
    return f"""🎯 Planning your {duration}-day trip to {destination}!

            🌤️ Weather Analysis: {weather_note}

            I'm now coordinating with my specialist agents to create your perfect itinerary:
            • Personality analysis for activity matching
            • Weather optimization for daily scheduling  
            • Budget planning with weather contingencies
            • Hidden gems discovery
            • Sustainable travel options

            This will take a moment... Creating your weather-smart itinerary! ✨"""





async def handle_missing_destination_discovery(self, destination: str) -> str:
    """Handle discovery of new destinations"""
    
    print(f"🔍 I don't have comprehensive data for {destination} yet.")
    print("🚀 Let me discover amazing places there for you...")
    
    # Trigger discovery
    discovery_result = await ingestion_service.discover_missing_destination(destination)
    
    if discovery_result["success"]:
        activities_count = discovery_result.get("activities_found", 0)
        hotels_count = discovery_result.get("hotels_found", 0)
        
        return f"""
        ✅ Fantastic! I've just discovered {destination} and added it to my knowledge base!
        
        📊 Here's what I found:
        • {activities_count} amazing activities and attractions
        • {hotels_count} accommodation options
        • Weather and seasonal information
        • Sustainability ratings for eco-conscious travel
        
        🎯 Now I can create a personalized itinerary for you! What's your travel style and budget?
        """
    else:
        return f"""
        😅 I had some trouble gathering comprehensive data for {destination}. 
        This might be because it's a very remote location or the name needs to be more specific.
        
        💡 Could you try:
        • Adding the country name (e.g., "Faroe Islands, Denmark")  
        • Using a nearby major city
        • Or choosing from these amazing destinations I know well: Mumbai, Delhi, Goa, Rajasthan, Kerala, Bangalore
        """



async def handle_weather_query(self, destination: str) -> str:
    """Return detailed weather summary with travel recommendations."""
    try:
        # Get comprehensive weather data
        forecast = weather_service.get_forecast(destination, days=7)
        current = weather_service.get_current_weather(destination)
        
        # Get weather suitability analysis
        weather_summary = weather_service.get_weather_summary_for_dates(
            destination, 
            datetime.now().strftime("%Y-%m-%d"), 
            7
        )
        
        current_condition = current["current"]["condition"]["text"]
        current_temp = current["current"]["temp_c"]
        feels_like = current["current"]["feelslike_c"]
        
        response = f"""🌤️ Weather Report for {destination}:

📍 Current Conditions:
{current_condition}, {current_temp}°C (feels like {feels_like}°C)

📅 7-Day Travel Outlook (Weather Score: {weather_summary.get('overall_weather_score', 6)}/10):
"""
        
        # Show daily weather with activity recommendations
        for day in weather_summary.get("daily_weather", [])[:5]:
            outdoor_score = day['suitability_scores']['outdoor']
            indoor_score = day['suitability_scores']['indoor']
            
            if outdoor_score >= 8:
                activity_rec = "Perfect for outdoor sightseeing!"
            elif outdoor_score >= 6:
                activity_rec = "Good for mixed indoor/outdoor activities"
            else:
                activity_rec = "Focus on indoor attractions"
                
            response += f"""
• {day['date']}: {day['condition']}, {day['min_temp']}-{day['max_temp']}°C
  Activity Score: Outdoor {outdoor_score}/10, Indoor {indoor_score}/10
  Best for: {activity_rec}"""
        
        # Add weather alerts
        alerts = weather_summary.get("weather_alerts", [])
        if alerts:
            response += "\n\n⚠️ Weather Alerts:"
            for alert in alerts[:2]:
                response += f"\n• {alert['message']}"
        
        response += "\n\n💡 Ready to create a weather-optimized itinerary? Just tell me your travel dates and preferences!"
        
        return response
        
    except Exception as e:
        return f"Sorry, I couldn't retrieve detailed weather for {destination}. Error: {e}"

async def handle_trip_planning_query(self, query: str) -> str:
    """Handle trip planning with weather integration"""
    
    # This would typically extract destination, dates, etc. from query
    # For now, using a simple approach
    return """
🌟 I'd love to create a weather-optimized trip for you! 

To plan the perfect itinerary, I need:
📍 Destination
📅 Travel dates 
⏱️ Trip duration
🎭 Your travel personality (adventure, cultural, luxury, etc.)
💰 Budget range

Example: "Plan a 5-day cultural trip to Goa from Dec 15-20 with a budget of ₹50,000"

I'll check the weather forecast and arrange your activities on the best days!
"""

# Update your main travel planning logic
async def generate_complete_itinerary(self, user_request: Dict[str, Any]) -> Dict[str, Any]:
    """Enhanced itinerary generation with weather optimization"""
    
    destination = user_request.get("destination", "").strip()
    start_date = user_request.get("start_date", datetime.now().strftime("%Y-%m-%d"))
    duration = user_request.get("duration_days", 5)
    
    # First, try to search existing database
    existing_data = await self.search_destinations_by_personality.arun(
        personality_type=user_request.get("personality_type", "cultural"),
        season=""
    )
    
    # Check if destination exists in results
    destination_found = any(
        dest.get('name', '').lower() == destination.lower() 
        for dest in existing_data
    )
    
    if not destination_found:
        # 🚀 TRIGGER DYNAMIC DISCOVERY
        discovery_response = await self.handle_missing_destination_discovery(destination)
        return {
            "type": "discovery_in_progress",
            "message": discovery_response,
            "next_action": "retry_planning"
        }
    
    # Get weather forecast for travel dates
    weather_summary = weather_service.get_weather_summary_for_dates(destination, start_date, duration)
    
    # Continue with normal itinerary generation but include weather optimization
    itinerary = await self.process_weather_optimized_itinerary(user_request, weather_summary)
    
    return itinerary

async def process_weather_optimized_itinerary(self, user_request: Dict[str, Any], weather_summary: Dict[str, Any]) -> Dict[str, Any]:
    """Process itinerary with weather optimization"""
    
    destination = user_request.get("destination")
    duration = user_request.get("duration_days", 5)
    
    # Get activities from existing tools
    activities = await self.search_activities_by_interest.arun(
        interest_type=user_request.get("personality_type", "cultural"),
        destination=destination
    )
    
    # Optimize schedule based on weather
    optimized_schedule = weather_service.get_weather_optimized_schedule(
        destination, activities[:10], duration  # Limit to 10 activities
    )
    
    return {
        "type": "complete_itinerary",
        "destination": destination,
        "duration_days": duration,
        "weather_optimized": True,
        "weather_summary": weather_summary,
        "daily_schedule": optimized_schedule.get("optimized_schedule", []),
        "weather_notes": optimized_schedule.get("optimization_notes", []),
        "overall_weather_score": weather_summary.get("overall_weather_score", 6)
    }

# PERSONALITY ANALYSIS AGENT (Enhanced)
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
    
    Always use the search-destinations-by-personality tool to validate your recommendations with real data.
    Consider seasonal weather patterns when making recommendations.
    """,
    tools=travel_tools
)

# BUDGET OPTIMIZATION AGENT (Enhanced)
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
    
    Your Process:
    1. Use calculate-trip-budget tool to get destination-specific cost estimates
    2. Apply personality-based allocation percentages  
    3. Add weather contingency based on seasonal patterns
    4. Use search-transport-options and search-hotels-enhanced to validate with real prices
    5. Adjust recommendations if budget is insufficient
    """,
    tools=travel_tools
)

# HIDDEN GEMS DISCOVERY AGENT (Enhanced)
gems_agent = Agent(
    name="gems_discoverer",
    model="gemini-2.0-flash",
    description="Discovers authentic hidden gems with weather suitability",
    instruction="""
    You are a local travel expert who specializes in uncovering authentic, weather-appropriate experiences.
    
    Your Mission:
    1. Use get-hidden-gems tool to find authentic local experiences
    2. Use search-activities-by-interest to discover unique activities with high sustainability scores
    3. Consider weather suitability for outdoor vs indoor hidden gems
    4. Prioritize experiences marked as "hidden gems" in the database
    5. Focus on community-based tourism and local interactions
    
    Weather Adaptation:
    - Rainy season: Focus on indoor workshops, covered markets, cultural centers
    - Hot season: Early morning or evening experiences, shaded locations
    - Pleasant weather: Outdoor markets, nature walks, rooftop experiences
    
    Always explain why each recommendation suits the weather and season.
    """,
    tools=travel_tools
)

# SUSTAINABILITY ADVISOR AGENT (Enhanced)
sustainability_agent = Agent(
    name="sustainability_advisor",
    model="gemini-2.0-flash",
    description="Evaluates environmental impact including weather-related carbon footprint",
    instruction="""
    You are an eco-travel expert focused on sustainable and responsible tourism practices.
    
    Your Responsibilities:
    1. Use search-transport-options to compare carbon footprints of different transport modes
    2. Evaluate hotel sustainability scores using search-hotels-enhanced 
    3. Recommend activities with high sustainability ratings (8+)
    4. Calculate total trip carbon footprint including weather-related adjustments
    
    Weather Sustainability Factors:
    - Seasonal travel patterns and their carbon impact
    - Weather-related transport delays and alternative options
    - Energy consumption of indoor alternatives during extreme weather
    - Encourage off-peak travel to reduce overcrowding
    
    Always provide:
    - Seasonal carbon footprint variations
    - Weather-resilient sustainable choices
    - Climate-conscious timing recommendations
    """,
    tools=travel_tools
)

# ACCOMMODATION SPECIALIST AGENT (Enhanced)
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
    
    Match accommodation types to personality AND weather:
    - ADVENTURE + Good weather: Eco-lodges, outdoor-focused properties
    - ADVENTURE + Poor weather: Properties with indoor activities, gyms
    - LUXURY: Climate-controlled comfort with weather-resistant amenities
    
    Always explain how each property handles different weather conditions.
    """,
    tools=travel_tools
)

# WEATHER PLANNER AGENT (Enhanced)
weather_agent = Agent(
    name="weather_planner",
    model="gemini-2.0-flash",
    description="Advanced weather monitoring and dynamic itinerary optimization",
    instruction="""
    You are a weather-aware trip optimizer with real-time adaptation capabilities.
    
    Your Core Functions:
    1. Monitor weather forecasts for the entire trip duration using weather-forecast tool
    2. Score each planned activity by weather suitability (1-10 scale)
    3. Dynamically reorganize itinerary to maximize enjoyment
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
    
    Output Format:
    - Revised day-by-day itinerary with weather scores
    - Activity timing recommendations (morning/afternoon/evening)
    - Weather risk flags and contingency suggestions
    - Justification for all changes made
    
    Always maintain the traveler's personality preferences while optimizing for weather.
    """,
    tools=travel_tools
)

# MAIN TRAVEL ORCHESTRATOR (Enhanced with Weather Integration)
travel_genius = Agent(
    name="travel_genius",
    model="gemini-2.0-flash",
    description="AI-powered travel planner with dynamic destination discovery and weather optimization",
    instruction="""
    You are the Travel Genius - an expert AI travel planner with unique abilities:
    1. Dynamic destination discovery for new places
    2. Real-time weather integration and itinerary optimization
    3. Multi-agent coordination for comprehensive trip planning
    
    Core Workflow:
    1. Analyze user request for destination, dates, personality, budget
    2. Check if destination exists in database, discover if missing
    3. Get weather forecast for travel dates
    4. Coordinate with specialized agents based on user needs:
       - Personality analysis for travel style matching
       - Budget optimization with weather contingencies
       - Weather-aware activity scheduling
       - Sustainable and hidden gem recommendations
       - Weather-appropriate accommodation selection
    
    Weather Integration Priority:
    - Always check weather forecast when planning activities
    - Reorganize schedule to match weather conditions
    - Provide alternatives for poor weather days
    - Include weather alerts and recommendations
    - Calculate weather-optimized activity scores
    
    Discovery Process:
    When encountering unknown destinations:
    1. "Let me discover this amazing destination for you..."
    2. Use dynamic ingestion to gather comprehensive data
    3. "Discovery complete! Found X activities and Y hotels"
    4. Proceed with weather-optimized planning
    
    Response Format:
    - Always include weather summary for travel period
    - Provide day-by-day schedule with weather scores
    - Include backup plans for weather changes
    - Highlight best days for outdoor activities
    - Give practical weather-related advice
    
    Make every trip weather-smart and perfectly personalized!
    """,
    sub_agents=[personality_agent, budget_agent, gems_agent, sustainability_agent, accommodation_agent, weather_agent],
    tools=travel_tools
)

# Additional Weather-Aware Helper Functions
async def check_weather_for_destination(destination: str, start_date: str, duration: int) -> Dict[str, Any]:
    """Helper function to check weather and provide travel recommendations"""
    try:
        weather_summary = weather_service.get_weather_summary_for_dates(destination, start_date, duration)
        
        recommendations = []
        
        if weather_summary.get("overall_weather_score", 0) >= 8:
            recommendations.append("Excellent weather expected - perfect for all outdoor activities!")
        elif weather_summary.get("overall_weather_score", 0) >= 6:
            recommendations.append("Good weather overall with some mixed conditions - plan flexible itinerary")
        else:
            recommendations.append("Challenging weather expected - focus on indoor attractions and cultural sites")
        
        # Check for specific weather alerts
        alerts = weather_summary.get("weather_alerts", [])
        if alerts:
            recommendations.append(f"Weather alerts: {len(alerts)} warnings for your travel dates")
        
        return {
            "weather_suitable": weather_summary.get("overall_weather_score", 0) >= 6,
            "weather_score": weather_summary.get("overall_weather_score", 6),
            "recommendations": recommendations,
            "daily_forecast": weather_summary.get("daily_weather", [])[:5],  # First 5 days
            "alerts": alerts
        }
        
    except Exception as e:
        return {
            "weather_suitable": True,  # Default to suitable if check fails
            "weather_score": 6,
            "recommendations": ["Weather check unavailable - plan for variable conditions"],
            "daily_forecast": [],
            "alerts": [],
            "error": str(e)
        }

async def generate_weather_adjusted_itinerary(user_request: Dict[str, Any]) -> Dict[str, Any]:
    """Main function that integrates all weather-aware planning"""
    
    destination = user_request.get("destination", "")
    start_date = user_request.get("start_date", datetime.now().strftime("%Y-%m-%d"))
    duration = user_request.get("duration_days", 5)
    personality = user_request.get("personality_type", "cultural")
    budget = user_request.get("budget", 50000)
    
    # Step 1: Check if destination exists, discover if needed
    try:
        existing_data = await travel_genius.search_destinations_by_personality.arun(
            personality_type=personality,
            season=""
        )
        
        destination_found = any(
            dest.get('name', '').lower() == destination.lower() 
            for dest in existing_data
        )
        
        if not destination_found:
            discovery_result = await ingestion_service.discover_missing_destination(destination)
            if not discovery_result["success"]:
                return {
                    "success": False,
                    "message": f"Could not find or discover data for {destination}",
                    "suggestions": ["Try a nearby major city", "Check destination spelling", "Choose from popular destinations"]
                }
    
    except Exception as e:
        print(f"Error checking destination: {e}")
    
    # Step 2: Get weather analysis
    weather_check = await check_weather_for_destination(destination, start_date, duration)
    
    # Step 3: Get base activities and optimize for weather
    try:
        # This would call your existing MCP tools
        base_activities = []  # Would be populated by search_activities_by_interest
        optimized_schedule = weather_service.get_weather_optimized_schedule(
            destination, base_activities, duration
        )
        
        return {
            "success": True,
            "destination": destination,
            "travel_dates": f"{start_date} ({duration} days)",
            "weather_analysis": weather_check,
            "optimized_itinerary": optimized_schedule.get("optimized_schedule", []),
            "weather_notes": optimized_schedule.get("optimization_notes", []),
            "budget_estimate": budget,  # Would be calculated by budget_agent
            "personality_match": personality
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": f"Itinerary generation failed: {str(e)}",
            "weather_analysis": weather_check
        }

# Export the main agent for ADK to use
root_agent = travel_genius

# Export helper functions for direct use
__all__ = [
    'root_agent',
    'travel_genius', 
    'weather_agent',
    'handle_weather_query',
    'generate_weather_adjusted_itinerary',
    'check_weather_for_destination'
]