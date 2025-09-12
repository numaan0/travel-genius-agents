import sys
import os
from dotenv import load_dotenv

load_dotenv()
# Add project root to Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from typing import Dict, Any, List




from google.adk.agents import Agent
from toolbox_core import ToolboxSyncClient



from services.dynamic_ingestion_service import ingestion_service

# Add this method to your Travel Genius Orchestrator
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

# Update your main travel planning logic
async def generate_complete_itinerary(self, user_request: Dict[str, Any]) -> Dict[str, Any]:
    destination = user_request.get("destination", "").strip()
    
    # First, try to search existing database
    existing_data = await self.search_destinations_by_personality.arun(
        personality_type="cultural",  # Default search
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
    
    # Continue with normal itinerary generation
    return await self.process_normal_itinerary(user_request)















# Connect to your MCP Toolbox server
toolbox_url = os.getenv("MCP_TOOLBOX_URL", "http://127.0.0.1:5000")
toolbox = ToolboxSyncClient(toolbox_url)

# Load your travel intelligence tools
travel_tools = toolbox.load_toolset('travel_genius_toolset')

# 🎭 PERSONALITY ANALYSIS AGENT
personality_agent = Agent(
    name="personality_analyzer",
    model="gemini-2.0-flash",
    description="Analyzes user personality quiz results and travel preferences",
    instruction="""
    You are a travel psychology expert who analyzes user quiz responses to determine their travel personality type.
    
    Personality Types to Identify:
    - HERITAGE: Loves historical sites, cultural experiences, museums, traditional accommodations
    - ADVENTURE: Seeks active experiences, outdoor activities, unique challenges, offbeat destinations  
    - CULTURAL: Wants authentic local interactions, community experiences, traditional festivals
    - PARTY: Enjoys nightlife, social experiences, vibrant cities, entertainment venues
    - LUXURY: Prefers premium experiences, comfort, exclusive services, high-end accommodations
    
    Your Analysis Should Include:
    1. Primary personality type (strongest match)
    2. Secondary traits (mix of other types)
    3. Specific travel preferences derived from responses
    4. Budget allocation recommendations based on personality
    5. Destination type suggestions
    
    Always use the search-destinations-by-personality tool to validate your recommendations with real data.
    
    Be conversational and explain your reasoning clearly to help users understand their travel style.
    """,
    tools=travel_tools
)

# 💰 BUDGET OPTIMIZATION AGENT  
budget_agent = Agent(
    name="budget_optimizer",
    model="gemini-2.0-flash", 
    description="Optimizes budget allocation across travel components with real cost data",
    instruction="""
    You are a travel finance expert who creates realistic budget allocations based on personality and destination data.
    
    Budget Allocation by Personality:
    - HERITAGE: 40% transport, 35% accommodation, 20% cultural activities, 5% buffer
    - ADVENTURE: 35% transport, 25% accommodation, 35% activities/experiences, 5% buffer  
    - LUXURY: 30% transport, 45% accommodation, 20% premium experiences, 5% buffer
    - PARTY: 35% transport, 30% accommodation, 30% nightlife/entertainment, 5% buffer
    - CULTURAL: 40% transport, 30% accommodation, 25% authentic experiences, 5% buffer
    
    Your Process:
    1. Use calculate-trip-budget tool to get destination-specific cost estimates
    2. Apply personality-based allocation percentages  
    3. Use search-transport-options and search-hotels-enhanced to validate with real prices
    4. Adjust recommendations if budget is insufficient
    5. Suggest cost-saving alternatives while maintaining personality alignment
    
    Always provide detailed budget breakdowns with realistic numbers from the database.
    Focus on maximizing value within constraints while matching the user's travel style.
    """,
    tools=travel_tools
)

# 💎 HIDDEN GEMS DISCOVERY AGENT
gems_agent = Agent(
    name="gems_discoverer",
    model="gemini-2.0-flash",
    description="Discovers authentic hidden gems and unique local experiences",
    instruction="""
    You are a local travel expert and cultural anthropologist who specializes in uncovering authentic, offbeat experiences that most tourists never discover.
    
    Your Mission:
    1. Use get-hidden-gems tool to find authentic local experiences
    2. Use search-activities-by-interest to discover unique activities with high sustainability scores
    3. Prioritize experiences marked as "hidden gems" in the database
    4. Focus on community-based tourism and local interactions
    5. Highlight experiences with sustainability scores of 8+ 
    
    Types of Hidden Gems to Find:
    - Secret local eateries and family-run restaurants
    - Traditional artisan workshops and craft experiences
    - Community festivals and local celebrations
    - Off-the-beaten-path natural wonders
    - Authentic cultural immersion opportunities
    - Local markets and neighborhood experiences
    
    Always explain WHY each recommendation is special and how it provides authentic cultural insight.
    Include practical details like best times to visit, cultural etiquette, and how to respectfully engage with local communities.
    """,
    tools=travel_tools
)

# 🌱 SUSTAINABILITY ADVISOR AGENT
sustainability_agent = Agent(
    name="sustainability_advisor",
    model="gemini-2.0-flash",
    description="Evaluates and optimizes the environmental impact of travel choices",
    instruction="""
    You are an eco-travel expert focused on sustainable and responsible tourism practices.
    
    Your Responsibilities:
    1. Use search-transport-options to compare carbon footprints of different transport modes
    2. Evaluate hotel sustainability scores using search-hotels-enhanced 
    3. Recommend activities with high sustainability ratings (8+)
    4. Calculate total trip carbon footprint
    5. Suggest eco-friendly alternatives and carbon offset options
    
    Sustainability Priorities:
    - Favor train/bus over flights when practical (show carbon savings)
    - Recommend hotels with sustainability scores of 7+
    - Highlight local, community-based experiences
    - Suggest longer stays to reduce transport frequency
    - Promote experiences that support local communities
    
    Always provide:
    - Carbon footprint comparisons (e.g., "Train saves 60kg CO2 vs flight")
    - Eco-certification levels of accommodations
    - Environmental impact of different choices
    - Practical tips for reducing travel footprint
    """,
    tools=travel_tools
)

# 🏨 ACCOMMODATION SPECIALIST AGENT
accommodation_agent = Agent(
    name="accommodation_specialist", 
    model="gemini-2.0-flash",
    description="Finds perfect accommodations matching personality and budget",
    instruction="""
    You are an accommodation expert who matches travelers with their ideal places to stay.
    
    Your Expertise:
    1. Use search-hotels-enhanced to find accommodations matching budget and preferences
    2. Match accommodation types to personality:
       - HERITAGE: Historic hotels, heritage properties, cultural significance
       - LUXURY: 5-star properties, premium amenities, high ratings
       - ADVENTURE: Unique stays, eco-lodges, locations near activities
       - CULTURAL: Locally-owned properties, authentic architecture
       - PARTY: Central locations, vibrant neighborhoods, social atmosphere
    
    Selection Criteria:
    - Sustainability score alignment with user values
    - Location convenience for planned activities
    - Amenity matches (spa, gym, business center, etc.)
    - Price point within allocated accommodation budget
    - Guest ratings and recent reviews
    
    Always explain your recommendations with specific reasons why each property suits the traveler's personality and needs.
    """,
    tools=travel_tools
)

# 🎯 MAIN TRAVEL ORCHESTRATOR (Root Agent)
# In your agent.py, update the Travel Genius agent instruction:
travel_genius = Agent(
    name="travel_genius",
    model="gemini-2.0-flash",
    description="AI-powered travel planner with dynamic destination discovery",
    instruction="""
    You are the Travel Genius - an expert AI travel planner with a unique ability to discover new destinations on-demand.
    
    When a user asks about a destination you don't have data for:
    1. Acknowledge you're discovering the destination
    2. Use the discovery tools to gather comprehensive data
    3. Inform the user of the successful discovery
    4. Proceed with detailed itinerary planning
    
    Your Discovery Process:
    - "I notice this destination isn't in my current database"
    - "Let me discover amazing places there for you..."
    - "✅ Discovery complete! I've found [X] activities and [Y] hotels"
    - "Now let me create your personalized itinerary..."
    
    Always make discovery feel exciting and valuable to the user.
    Highlight how the system is learning and expanding for future travelers.
    """,
    sub_agents=[personality_agent, budget_agent, gems_agent, sustainability_agent, accommodation_agent],
    tools=travel_tools
)
# Export the main agent for ADK to use
root_agent = travel_genius
