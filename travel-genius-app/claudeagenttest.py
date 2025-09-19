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

print("🔧 DEBUG: Connection to MCP Toolbox successful!")

# Load your travel intelligence tools
travel_tools = toolbox.load_toolset('travel_genius_toolset')
print("🔧 DEBUG: Travel tools loaded successfully!")


async def handle_user_query(self, user_query: str) -> str:
    """
    Enhanced query routing that properly handles weather and trip planning requests
    """
    print(f"🔧 DEBUG: handle_user_query called with query: '{user_query}'")
    
    query_lower = user_query.lower()
    print(f"🔧 DEBUG: Query converted to lowercase: '{query_lower}'")
    
    # Enhanced weather query detection
    weather_keywords = ["weather", "forecast", "rain", "sunny", "temperature", "climate", "conditions"]
    trip_keywords = ["plan", "trip", "itinerary", "travel", "visit", "book"]
    
    weather_match = any(keyword in query_lower for keyword in weather_keywords)
    trip_match = any(keyword in query_lower for keyword in trip_keywords)
    
    print(f"🔧 DEBUG: Weather keywords match: {weather_match}")
    print(f"🔧 DEBUG: Trip keywords match: {trip_match}")
    
    if weather_match:
        print("🌤️ DEBUG: Weather query detected - calling weather handler")
        destination = extract_destination_from_query(user_query)
        print(f"🔧 DEBUG: Extracted destination: '{destination}'")
        
        if destination:
            print(f"🌤️ DEBUG: Calling handle_weather_query for destination: {destination}")
            return await self.handle_weather_query(destination)
        else:
            print("🔧 DEBUG: No destination found in weather query")
            return "I'd be happy to check the weather! Which destination are you asking about?"
    
    elif trip_match:
        print("🗓️ DEBUG: Trip planning query detected - calling trip handler")
        return await self.handle_trip_planning_query(user_query)
    
    else:
        print("🔧 DEBUG: Generic query - returning help message")
        return """I can help you with:
        
            🌤️ Weather information - "What's the weather in Mumbai?"
            🗓️ Trip planning - "Plan a 5-day trip to Kerala" 
            📋 Weather-optimized itineraries - "Plan outdoor activities in Goa for next week"

            What would you like to know?"""

# Add this helper function to extract destinations properly:
def extract_destination_from_query(query: str) -> str:
    """Extract destination from user query using improved pattern matching"""
    print(f"🔧 DEBUG: extract_destination_from_query called with: '{query}'")
    
    # Remove common noise words
    original_query = query
    query = re.sub(r'\b(the|in|at|for|weather|forecast|what|is|how|will|be)\b', '', query, flags=re.IGNORECASE)
    print(f"🔧 DEBUG: Query after noise removal: '{query}' (was: '{original_query}')")
    
    # Patterns to match destinations
    patterns = [
        r'(?:weather|forecast).*?(?:in|at|for)\s+([A-Z][a-zA-Z\s]+?)(?:\?|$|\.)',
        r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)',  # Capitalized words
    ]
    
    for i, pattern in enumerate(patterns):
        print(f"🔧 DEBUG: Trying pattern {i+1}: {pattern}")
        matches = re.findall(pattern, query)
        print(f"🔧 DEBUG: Pattern {i+1} matches: {matches}")
        
        if matches:
            destination = matches[0].strip()
            print(f"🔧 DEBUG: Found destination candidate: '{destination}'")
            
            # Filter out common false positives
            if len(destination) > 2 and destination.lower() not in ['tomorrow', 'today', 'next', 'this']:
                print(f"✅ DEBUG: Destination accepted: '{destination}'")
                return destination
            else:
                print(f"❌ DEBUG: Destination rejected (too short or false positive): '{destination}'")
    
    # Fallback: look for any capitalized word that might be a place
    print("🔧 DEBUG: Using fallback - looking for capitalized words")
    words = query.split()
    print(f"🔧 DEBUG: Words in query: {words}")
    
    for word in words:
        if word and word[0].isupper() and len(word) > 2:
            print(f"✅ DEBUG: Fallback destination found: '{word}'")
            return word
    
    print("❌ DEBUG: No destination found in query")
    return None

# Enhance your existing handle_trip_planning_query:
async def handle_trip_planning_query(self, query: str) -> str:
    """Handle trip planning with automatic weather integration"""
    print(f"🗓️ DEBUG: handle_trip_planning_query called with: '{query}'")
    
    destination = extract_destination_from_query(query)
    print(f"🔧 DEBUG: Trip planning destination extracted: '{destination}'")
    
    if not destination:
        print("❌ DEBUG: No destination in trip planning query - returning input request")
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
    print(f"🔧 DEBUG: Trip duration extracted: {duration} days")
    
    # Check weather for the destination
    print(f"🌤️ DEBUG: About to call weather_service.get_weather_summary_for_dates")
    print(f"🌤️ DEBUG: Parameters - destination: '{destination}', start_date: '{datetime.now().strftime('%Y-%m-%d')}', duration: {duration}")
    
    try:
        weather_summary = weather_service.get_weather_summary_for_dates(
            destination, 
            datetime.now().strftime("%Y-%m-%d"), 
            duration
        )
        print(f"✅ DEBUG: Weather service call successful!")
        print(f"🌤️ DEBUG: Weather summary received: {weather_summary}")
        
        overall_score = weather_summary.get("overall_weather_score", 0)
        print(f"🌤️ DEBUG: Overall weather score: {overall_score}")
        
    except Exception as e:
        print(f"❌ DEBUG: Weather service call failed with error: {e}")
        # Set default values for error case
        weather_summary = {"overall_weather_score": 6}
        overall_score = 6
    
    if overall_score >= 7:
        weather_note = f"Great news! {destination} has excellent weather (Score: {overall_score}/10) for your travel dates."
        print(f"✅ DEBUG: Excellent weather detected")
    elif overall_score >= 5:
        weather_note = f"{destination} has mixed weather conditions (Score: {overall_score}/10). I'll optimize your itinerary accordingly."
        print(f"⚠️ DEBUG: Mixed weather conditions detected")
    else:
        weather_note = f"{destination} has challenging weather (Score: {overall_score}/10). I'll focus on indoor activities and weather-resistant experiences."
        print(f"❌ DEBUG: Challenging weather conditions detected")
    
    response = f"""🎯 Planning your {duration}-day trip to {destination}!

            🌤️ Weather Analysis: {weather_note}

            I'm now coordinating with my specialist agents to create your perfect itinerary:
            • Personality analysis for activity matching
            • Weather optimization for daily scheduling  
            • Budget planning with weather contingencies
            • Hidden gems discovery
            • Sustainable travel options

            This will take a moment... Creating your weather-smart itinerary! ✨"""
    
    print(f"🗓️ DEBUG: Trip planning response prepared, length: {len(response)} characters")
    return response


async def handle_missing_destination_discovery(self, destination: str) -> str:
    """Handle discovery of new destinations"""
    print(f"🔍 DEBUG: handle_missing_destination_discovery called for: '{destination}'")
    
    print(f"🔍 I don't have comprehensive data for {destination} yet.")
    print("🚀 Let me discover amazing places there for you...")
    
    # Trigger discovery
    print(f"🔍 DEBUG: Calling ingestion_service.discover_missing_destination")
    try:
        discovery_result = await ingestion_service.discover_missing_destination(destination)
        print(f"✅ DEBUG: Discovery service call successful: {discovery_result}")
    except Exception as e:
        print(f"❌ DEBUG: Discovery service call failed: {e}")
        discovery_result = {"success": False, "error": str(e)}
    
    if discovery_result["success"]:
        activities_count = discovery_result.get("activities_found", 0)
        hotels_count = discovery_result.get("hotels_found", 0)
        print(f"✅ DEBUG: Discovery successful - {activities_count} activities, {hotels_count} hotels")
        
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
        print(f"❌ DEBUG: Discovery failed for {destination}")
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
    print(f"🌤️ DEBUG: handle_weather_query called for destination: '{destination}'")
    
    try:
        print(f"🌤️ DEBUG: Calling weather_service.get_forecast for {destination}")
        forecast = weather_service.get_forecast(destination, days=7)
        print(f"✅ DEBUG: Forecast retrieved successfully")
        
        print(f"🌤️ DEBUG: Calling weather_service.get_current_weather for {destination}")
        current = weather_service.get_current_weather(destination)
        print(f"✅ DEBUG: Current weather retrieved successfully")
        
        # Get weather suitability analysis
        print(f"🌤️ DEBUG: Calling weather_service.get_weather_summary_for_dates")
        weather_summary = weather_service.get_weather_summary_for_dates(
            destination, 
            datetime.now().strftime("%Y-%m-%d"), 
            7
        )
        print(f"✅ DEBUG: Weather summary retrieved successfully")
        print(f"🌤️ DEBUG: Weather summary data: {weather_summary}")
        
        current_condition = current["current"]["condition"]["text"]
        current_temp = current["current"]["temp_c"]
        feels_like = current["current"]["feelslike_c"]
        
        print(f"🌤️ DEBUG: Current conditions parsed - {current_condition}, {current_temp}°C")
        
        response = f"""🌤️ Weather Report for {destination}:

📍 Current Conditions:
{current_condition}, {current_temp}°C (feels like {feels_like}°C)

📅 7-Day Travel Outlook (Weather Score: {weather_summary.get('overall_weather_score', 6)}/10):
"""
        
        # Show daily weather with activity recommendations
        daily_weather = weather_summary.get("daily_weather", [])
        print(f"🌤️ DEBUG: Processing {len(daily_weather)} daily weather entries")
        
        for i, day in enumerate(daily_weather[:5]):
            print(f"🌤️ DEBUG: Processing day {i+1}: {day}")
            
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
        print(f"🌤️ DEBUG: Found {len(alerts)} weather alerts")
        
        if alerts:
            response += "\n\n⚠️ Weather Alerts:"
            for alert in alerts[:2]:
                response += f"\n• {alert['message']}"
                print(f"🌤️ DEBUG: Alert: {alert['message']}")
        
        response += "\n\n💡 Ready to create a weather-optimized itinerary? Just tell me your travel dates and preferences!"
        
        print(f"✅ DEBUG: Weather query response prepared, length: {len(response)} characters")
        return response
        
    except Exception as e:
        error_msg = f"Sorry, I couldn't retrieve detailed weather for {destination}. Error: {e}"
        print(f"❌ DEBUG: Weather query failed with error: {e}")
        return error_msg

async def handle_trip_planning_query(self, query: str) -> str:
    """Handle trip planning with weather integration"""
    print(f"🗓️ DEBUG: handle_trip_planning_query (standalone) called with: '{query}'")
    
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
    print(f"🗓️ DEBUG: generate_complete_itinerary called with request: {user_request}")
    
    destination = user_request.get("destination", "").strip()
    start_date = user_request.get("start_date", datetime.now().strftime("%Y-%m-%d"))
    duration = user_request.get("duration_days", 5)
    
    print(f"🔧 DEBUG: Extracted params - destination: '{destination}', start_date: '{start_date}', duration: {duration}")
    
    # First, try to search existing database
    print(f"🔍 DEBUG: Searching existing destinations for personality type: {user_request.get('personality_type', 'cultural')}")
    
    try:
        existing_data = await self.search_destinations_by_personality.arun(
            personality_type=user_request.get("personality_type", "cultural"),
            season=""
        )
        print(f"✅ DEBUG: Existing data search successful, found {len(existing_data)} destinations")
    except Exception as e:
        print(f"❌ DEBUG: Existing data search failed: {e}")
        existing_data = []
    
    # Check if destination exists in results
    destination_found = any(
        dest.get('name', '').lower() == destination.lower() 
        for dest in existing_data
    )
    print(f"🔧 DEBUG: Destination '{destination}' found in existing data: {destination_found}")
    
    if not destination_found:
        # 🚀 TRIGGER DYNAMIC DISCOVERY
        print(f"🔍 DEBUG: Destination not found, triggering discovery for: '{destination}'")
        discovery_response = await self.handle_missing_destination_discovery(destination)
        return {
            "type": "discovery_in_progress",
            "message": discovery_response,
            "next_action": "retry_planning"
        }
    
    # Get weather forecast for travel dates
    print(f"🌤️ DEBUG: Getting weather forecast for {destination} from {start_date} for {duration} days")
    try:
        weather_summary = weather_service.get_weather_summary_for_dates(destination, start_date, duration)
        print(f"✅ DEBUG: Weather summary obtained: {weather_summary}")
    except Exception as e:
        print(f"❌ DEBUG: Weather summary failed: {e}")
        weather_summary = {"overall_weather_score": 6, "daily_weather": []}
    
    # Continue with normal itinerary generation but include weather optimization
    print(f"🗓️ DEBUG: Proceeding to process weather-optimized itinerary")
    itinerary = await self.process_weather_optimized_itinerary(user_request, weather_summary)
    
    return itinerary

async def process_weather_optimized_itinerary(self, user_request: Dict[str, Any], weather_summary: Dict[str, Any]) -> Dict[str, Any]:
    """Process itinerary with weather optimization"""
    print(f"🗓️ DEBUG: process_weather_optimized_itinerary called")
    print(f"🗓️ DEBUG: User request: {user_request}")
    print(f"🌤️ DEBUG: Weather summary: {weather_summary}")
    
    destination = user_request.get("destination")
    duration = user_request.get("duration_days", 5)
    
    # Get activities from existing tools
    print(f"🔍 DEBUG: Searching activities by interest for {destination}")
    try:
        activities = await self.search_activities_by_interest.arun(
            interest_type=user_request.get("personality_type", "cultural"),
            destination=destination
        )
        print(f"✅ DEBUG: Found {len(activities)} activities")
        print(f"🔧 DEBUG: Activities preview: {activities[:2] if activities else 'None'}")
    except Exception as e:
        print(f"❌ DEBUG: Activities search failed: {e}")
        activities = []
    
    # Optimize schedule based on weather
    print(f"🌤️ DEBUG: Calling weather_service.get_weather_optimized_schedule")
    try:
        optimized_schedule = weather_service.get_weather_optimized_schedule(
            destination, activities[:10], duration  # Limit to 10 activities
        )
        print(f"✅ DEBUG: Weather optimization successful")
        print(f"🌤️ DEBUG: Optimized schedule preview: {optimized_schedule}")
    except Exception as e:
        print(f"❌ DEBUG: Weather optimization failed: {e}")
        optimized_schedule = {"optimized_schedule": [], "optimization_notes": []}
    
    result = {
        "type": "complete_itinerary",
        "destination": destination,
        "duration_days": duration,
        "weather_optimized": True,
        "weather_summary": weather_summary,
        "daily_schedule": optimized_schedule.get("optimized_schedule", []),
        "weather_notes": optimized_schedule.get("optimization_notes", []),
        "overall_weather_score": weather_summary.get("overall_weather_score", 6)
    }
    
    print(f"✅ DEBUG: process_weather_optimized_itinerary completed successfully")
    return result

# PERSONALITY ANALYSIS AGENT (Enhanced)
personality_agent = Agent(
    name="personality_analyzer",
    model="gemini-2.0-flash",
    description="Analyzes user personality quiz results and travel preferences with weather awareness",
    instruction="""
    You are a travel psychology expert who analyzes user quiz responses to determine their travel personality type.
    
    DEBUG: Always print when you are called and what personality type you determine.
    
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
    
    DEBUG: Always print when you are called and what budget calculations you make.
    
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
    
    DEBUG: Always print when you are called and what gems you discover.
    
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
    
    DEBUG: Always print when you are called and what sustainability scores you calculate.
    
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
    
    DEBUG: Always print when you are called and what accommodations you recommend.
    
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
    
    DEBUG: Always print when you are called and what weather optimizations you make.
    
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
    
    DEBUG: Always print when you are called and what actions you take.
    
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
    print(f"🌤️ DEBUG: check_weather_for_destination called")
    print(f"🌤️ DEBUG: Parameters - destination: '{destination}', start_date: '{start_date}', duration: {duration}")
    
    try:
        print(f"🌤️ DEBUG: Calling weather_service.get_weather_summary_for_dates...")
        weather_summary = weather_service.get_weather_summary_for_dates(destination, start_date, duration)
        print(f"✅ DEBUG: Weather service call successful!")
        print(f"🌤️ DEBUG: Raw weather summary: {weather_summary}")
        
        recommendations = []
        overall_score = weather_summary.get("overall_weather_score", 0)
        print(f"🌤️ DEBUG: Overall weather score: {overall_score}")
        
        if overall_score >= 8:
            recommendations.append("Excellent weather expected - perfect for all outdoor activities!")
            print(f"✅ DEBUG: Excellent weather recommendation added")
        elif overall_score >= 6:
            recommendations.append("Good weather overall with some mixed conditions - plan flexible itinerary")
            print(f"⚠️ DEBUG: Mixed weather recommendation added")
        else:
            recommendations.append("Challenging weather expected - focus on indoor attractions and cultural sites")
            print(f"❌ DEBUG: Challenging weather recommendation added")
        
        # Check for specific weather alerts
        alerts = weather_summary.get("weather_alerts", [])
        print(f"🌤️ DEBUG: Found {len(alerts)} weather alerts")
        
        if alerts:
            recommendations.append(f"Weather alerts: {len(alerts)} warnings for your travel dates")
            print(f"⚠️ DEBUG: Added alert recommendation for {len(alerts)} alerts")
        
        daily_forecast = weather_summary.get("daily_weather", [])[:5]  # First 5 days
        print(f"🌤️ DEBUG: Daily forecast entries: {len(daily_forecast)}")
        
        result = {
            "weather_suitable": overall_score >= 6,
            "weather_score": overall_score,
            "recommendations": recommendations,
            "daily_forecast": daily_forecast,
            "alerts": alerts
        }
        
        print(f"✅ DEBUG: check_weather_for_destination completed successfully")
        print(f"🌤️ DEBUG: Result summary - suitable: {result['weather_suitable']}, score: {result['weather_score']}")
        return result
        
    except Exception as e:
        print(f"❌ DEBUG: check_weather_for_destination failed with error: {e}")
        print(f"❌ DEBUG: Error type: {type(e)}")
        
        default_result = {
            "weather_suitable": True,  # Default to suitable if check fails
            "weather_score": 6,
            "recommendations": ["Weather check unavailable - plan for variable conditions"],
            "daily_forecast": [],
            "alerts": [],
            "error": str(e)
        }
        
        print(f"⚠️ DEBUG: Returning default weather result due to error")
        return default_result


async def generate_weather_adjusted_itinerary(user_request: Dict[str, Any]) -> Dict[str, Any]:
    """Main function that integrates all weather-aware planning"""
    print(f"🗓️ DEBUG: generate_weather_adjusted_itinerary called")
    print(f"🗓️ DEBUG: User request received: {user_request}")
    
    destination = user_request.get("destination", "")
    start_date = user_request.get("start_date", datetime.now().strftime("%Y-%m-%d"))
    duration = user_request.get("duration_days", 5)
    personality = user_request.get("personality_type", "cultural")
    budget = user_request.get("budget", 50000)
    
    print(f"🔧 DEBUG: Parsed parameters:")
    print(f"  - Destination: '{destination}'")
    print(f"  - Start date: '{start_date}'")
    print(f"  - Duration: {duration} days")
    print(f"  - Personality: '{personality}'")
    print(f"  - Budget: ₹{budget}")
    
    # Step 1: Check if destination exists, discover if needed
    print(f"🔍 DEBUG: Step 1 - Checking if destination exists...")
    try:
        print(f"🔍 DEBUG: Searching destinations by personality: {personality}")
        existing_data = await travel_genius.search_destinations_by_personality.arun(
            personality_type=personality,
            season=""
        )
        print(f"✅ DEBUG: Destination search successful, found {len(existing_data)} results")
        
        destination_found = any(
            dest.get('name', '').lower() == destination.lower() 
            for dest in existing_data
        )
        print(f"🔧 DEBUG: Destination '{destination}' found in existing data: {destination_found}")
        
        if not destination_found:
            print(f"🔍 DEBUG: Destination not found, triggering discovery...")
            discovery_result = await ingestion_service.discover_missing_destination(destination)
            print(f"🔍 DEBUG: Discovery result: {discovery_result}")
            
            if not discovery_result["success"]:
                print(f"❌ DEBUG: Discovery failed for '{destination}'")
                return {
                    "success": False,
                    "message": f"Could not find or discover data for {destination}",
                    "suggestions": ["Try a nearby major city", "Check destination spelling", "Choose from popular destinations"]
                }
            else:
                print(f"✅ DEBUG: Discovery successful for '{destination}'")
    
    except Exception as e:
        print(f"❌ DEBUG: Error in destination checking step: {e}")
        print(f"❌ DEBUG: Error type: {type(e)}")
    
    # Step 2: Get weather analysis
    print(f"🌤️ DEBUG: Step 2 - Getting weather analysis...")
    weather_check = await check_weather_for_destination(destination, start_date, duration)
    print(f"🌤️ DEBUG: Weather check completed: {weather_check}")
    
    # Step 3: Get base activities and optimize for weather
    print(f"🗓️ DEBUG: Step 3 - Getting base activities and optimizing for weather...")
    try:
        print(f"🔍 DEBUG: This would call MCP tools to get activities...")
        # This would call your existing MCP tools
        base_activities = []  # Would be populated by search_activities_by_interest
        print(f"🔍 DEBUG: Base activities retrieved: {len(base_activities)} activities")
        
        print(f"🌤️ DEBUG: Calling weather_service.get_weather_optimized_schedule...")
        optimized_schedule = weather_service.get_weather_optimized_schedule(
            destination, base_activities, duration
        )
        print(f"✅ DEBUG: Weather optimization completed")
        print(f"🌤️ DEBUG: Optimized schedule preview: {optimized_schedule}")
        
        result = {
            "success": True,
            "destination": destination,
            "travel_dates": f"{start_date} ({duration} days)",
            "weather_analysis": weather_check,
            "optimized_itinerary": optimized_schedule.get("optimized_schedule", []),
            "weather_notes": optimized_schedule.get("optimization_notes", []),
            "budget_estimate": budget,  # Would be calculated by budget_agent
            "personality_match": personality
        }
        
        print(f"✅ DEBUG: generate_weather_adjusted_itinerary completed successfully")
        print(f"🗓️ DEBUG: Final result keys: {list(result.keys())}")
        return result
        
    except Exception as e:
        print(f"❌ DEBUG: Error in itinerary generation step: {e}")
        print(f"❌ DEBUG: Error type: {type(e)}")
        
        error_result = {
            "success": False,
            "error": f"Itinerary generation failed: {str(e)}",
            "weather_analysis": weather_check
        }
        
        print(f"❌ DEBUG: Returning error result")
        return error_result

# Debug wrapper functions to track weather service calls
def debug_weather_service_wrapper():
    """Wrapper to add debug prints to weather service calls"""
    print(f"🔧 DEBUG: Setting up weather service debug wrapper...")
    
    original_get_forecast = weather_service.get_forecast
    original_get_current = weather_service.get_current_weather
    original_get_summary = weather_service.get_weather_summary_for_dates
    original_get_optimized = weather_service.get_weather_optimized_schedule
    
    def debug_get_forecast(destination, days=7):
        print(f"🌤️ DEBUG: weather_service.get_forecast called - destination: '{destination}', days: {days}")
        try:
            result = original_get_forecast(destination, days)
            print(f"✅ DEBUG: weather_service.get_forecast successful")
            return result
        except Exception as e:
            print(f"❌ DEBUG: weather_service.get_forecast failed: {e}")
            raise
    
    def debug_get_current(destination):
        print(f"🌤️ DEBUG: weather_service.get_current_weather called - destination: '{destination}'")
        try:
            result = original_get_current(destination)
            print(f"✅ DEBUG: weather_service.get_current_weather successful")
            return result
        except Exception as e:
            print(f"❌ DEBUG: weather_service.get_current_weather failed: {e}")
            raise
    
    def debug_get_summary(destination, start_date, duration):
        print(f"🌤️ DEBUG: weather_service.get_weather_summary_for_dates called")
        print(f"🌤️ DEBUG: Parameters - destination: '{destination}', start_date: '{start_date}', duration: {duration}")
        try:
            result = original_get_summary(destination, start_date, duration)
            print(f"✅ DEBUG: weather_service.get_weather_summary_for_dates successful")
            print(f"🌤️ DEBUG: Summary result preview: {str(result)[:200]}...")
            return result
        except Exception as e:
            print(f"❌ DEBUG: weather_service.get_weather_summary_for_dates failed: {e}")
            raise
    
    def debug_get_optimized(destination, activities, duration):
        print(f"🌤️ DEBUG: weather_service.get_weather_optimized_schedule called")
        print(f"🌤️ DEBUG: Parameters - destination: '{destination}', activities: {len(activities)}, duration: {duration}")
        try:
            result = original_get_optimized(destination, activities, duration)
            print(f"✅ DEBUG: weather_service.get_weather_optimized_schedule successful")
            print(f"🌤️ DEBUG: Optimized result preview: {str(result)[:200]}...")
            return result
        except Exception as e:
            print(f"❌ DEBUG: weather_service.get_weather_optimized_schedule failed: {e}")
            raise
    
    # Replace methods with debug versions
    weather_service.get_forecast = debug_get_forecast
    weather_service.get_current_weather = debug_get_current
    weather_service.get_weather_summary_for_dates = debug_get_summary
    weather_service.get_weather_optimized_schedule = debug_get_optimized
    
    print(f"✅ DEBUG: Weather service debug wrapper installed!")

# Initialize debug wrapper
try:
    debug_weather_service_wrapper()
    print(f"🔧 DEBUG: Debug wrapper initialization successful!")
except Exception as e:
    print(f"⚠️ DEBUG: Debug wrapper initialization failed: {e}")

# MAIN TRAVEL ORCHESTRATOR (Enhanced with Weather Integration and Direct Debugging)
travel_genius = Agent(
    name="travel_genius",
    model="gemini-2.0-flash",
    description="AI-powered travel planner with dynamic destination discovery and weather optimization",
    instruction=f"""
    🚀 CRITICAL DEBUG INSTRUCTION: You MUST start EVERY response with "🚀 DEBUG: TRAVEL GENIUS AGENT ACTIVATED!" followed by analysis of the user's request.
    
    You are the Travel Genius - an expert AI travel planner with unique abilities:
    1. Dynamic destination discovery for new places
    2. Real-time weather integration and itinerary optimization  
    3. Multi-agent coordination for comprehensive trip planning
    
    MANDATORY DEBUG WORKFLOW:
    1. ALWAYS print "🚀 DEBUG: TRAVEL GENIUS AGENT ACTIVATED!"
    2. ALWAYS analyze: "User asked about: [weather/trip planning/general]"
    3. ALWAYS identify destinations mentioned in the query
    4. For weather queries: IMMEDIATELY use weather tools
    5. For trip planning: IMMEDIATELY check weather for destinations
    
    Core Workflow:
    1. Analyze user request for destination, dates, personality, budget
    2. Check if destination exists in database, discover if missing  
    3. **CRITICAL**: Get weather forecast for travel dates using weather-forecast tool
    4. Coordinate with specialized agents based on user needs
    
    Weather Integration Priority (TOP PRIORITY):
    - For ANY mention of weather words (weather, forecast, rain, sunny, temperature, climate, conditions), immediately use the weather-forecast tool
    - Always check weather forecast when planning activities
    - Reorganize schedule to match weather conditions  
    - Provide alternatives for poor weather days
    - Include weather alerts and recommendations
    
    Available Tools (USE THESE AGGRESSIVELY):
    - weather-forecast: Get detailed weather forecasts - USE FOR ALL WEATHER QUERIES
    - search-activities-by-interest: Find activities suitable for weather
    - search-destinations-by-personality: Weather-aware destination matching
    - calculate-trip-budget: Include weather contingencies
    - get-hidden-gems: Find weather-appropriate hidden experiences
    
    Response Format:
    - Start with "🚀 DEBUG: TRAVEL GENIUS AGENT ACTIVATED!"
    - Identify query type and destinations
    - Use tools immediately for weather/trip queries
    - Always include weather summary when relevant
    - Provide practical weather-related advice
    
    Remember: Weather integration and tool usage is your ABSOLUTE TOP PRIORITY!
    
    Current time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
    """,
    sub_agents=[personality_agent, budget_agent, gems_agent, sustainability_agent, accommodation_agent, weather_agent],
    tools=travel_tools
)

# Export the main agent directly (no wrapper)
root_agent = travel_genius

# Remove the DebugTravelGenius class since it's causing issues
# The debugging will happen inside the agent instruction instead

# Export helper functions for direct use
__all__ = [
    'root_agent',
    'travel_genius', 
    'weather_agent',
    'handle_weather_query',
    'generate_weather_adjusted_itinerary',
    'check_weather_for_destination',
    'debug_user_input_handler'
]

# Add a debug handler that gets called for every user message
async def debug_user_input_handler(user_message: str) -> str:
    """Debug function to track all user inputs"""
    print(f"\n" + "="*80)
    print(f"🚀 DEBUG: USER INPUT RECEIVED!")
    print(f"📝 DEBUG: Message: '{user_message}'")
    print(f"⏰ DEBUG: Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔍 DEBUG: Message length: {len(user_message)} characters")
    print(f"=" * 80)
    
    # Immediately check if this should trigger weather
    query_lower = user_message.lower()
    weather_keywords = ["weather", "forecast", "rain", "sunny", "temperature", "climate", "conditions"]
    trip_keywords = ["plan", "trip", "itinerary", "travel", "visit", "book"]
    
    has_weather = any(keyword in query_lower for keyword in weather_keywords)
    has_trip = any(keyword in query_lower for keyword in trip_keywords)
    
    print(f"🌤️ DEBUG: Contains weather keywords: {has_weather}")
    print(f"🗓️ DEBUG: Contains trip keywords: {has_trip}")
    
    if has_weather:
        print(f"⚡ DEBUG: WEATHER QUERY DETECTED - Should call weather functions!")
        destination = extract_destination_from_query(user_message)
        print(f"📍 DEBUG: Extracted destination: '{destination}'")
    
    print(f"📋 DEBUG: Now routing to travel_genius agent...")
    print(f"=" * 80 + "\n")
    
    return user_message  # Return unchanged

# Additional debug print at module level
print(f"🎯 DEBUG: Travel agent module loaded successfully!")
print(f"🎯 DEBUG: Available functions: {__all__}")
print(f"🎯 DEBUG: Weather service integration: {'✅ ENABLED' if hasattr(weather_service, 'get_forecast') else '❌ MISSING'}")
print(f"🎯 DEBUG: Dynamic ingestion service: {'✅ ENABLED' if hasattr(ingestion_service, 'discover_missing_destination') else '❌ MISSING'}")
print(f"🎯 DEBUG: Root agent configured: {root_agent.name if hasattr(root_agent, 'name') else 'UNKNOWN'}")
print(f"🎯 DEBUG: Module initialization complete! 🚀")