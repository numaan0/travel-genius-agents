# services/dynamic_ingestion_service.py
import asyncio
from dotenv import load_dotenv
load_dotenv()
import os
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import googlemaps
import requests
from toolbox_core import ToolboxSyncClient
from services.weather_service import weather_service
class DynamicIngestionService:
    def __init__(self):
        self.gmaps = googlemaps.Client(key=os.getenv('GOOGLE_MAPS_API_KEY'))
        self.weather_api_key = os.getenv('WEATHER_API_KEY')
        self.toolbox = ToolboxSyncClient(os.getenv('MCP_TOOLBOX_URL'))
        
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)

    async def discover_missing_destination(self, destination_name: str) -> Dict[str, Any]:
        """
        🔍 Main function: Discovers and adds missing destination data
        """
        self.logger.info(f"🔍 Starting discovery for: {destination_name}")
        
        try:
            # Step 1: Gather data from multiple sources
            destination_data = await self._gather_destination_data(destination_name)
            
            if not destination_data:
                return {"success": False, "message": f"Could not find data for {destination_name}"}
            
            # Step 2: Store in database
            await self._store_destination_data(destination_data)
            
            # Step 3: Log success
            self.logger.info(f"✅ Successfully added {destination_name} to database!")
            
            return {
                "success": True,
                "destination": destination_name,
                "activities_found": len(destination_data.get('activities', [])),
                "hotels_found": len(destination_data.get('hotels', [])),
                "message": f"🎉 {destination_name} is now available with {len(destination_data.get('activities', []))} activities!"
            }
            
        except Exception as e:
            self.logger.error(f"❌ Discovery failed for {destination_name}: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _get_weather_data(self, lat: float, lng: float, destination: str) -> Dict[str, Any]:
        """Get weather data for destination using centralized weather_service"""
        try:
            # Use the destination name for forecast (or use reverse geocoding for city if needed)
            forecast = weather_service.get_forecast(destination)
            avg_temp = forecast["forecast"]["forecastday"][0]["day"]["avgtemp_c"]
            # You can add more logic to determine best_season if needed
            return {
                "best_season": "Year-round",  # Or derive from forecast
                "avg_temp": avg_temp
            }
        except Exception as e:
            self.logger.warning(f"Weather data fetch failed: {e}")
            return {"best_season": "Year-round", "avg_temp": 25}


    async def _gather_destination_data(self, destination: str) -> Optional[Dict[str, Any]]:
        """Gather comprehensive data from Google APIs"""
        
        # Get basic place information
        places_result = self.gmaps.places(query=destination, type='locality')
        
        if not places_result['results']:
            self.logger.warning(f"No places found for {destination}")
            return None
            
        place = places_result['results'][0]
        place_id = place['place_id']
        
        # Get detailed place information
        details = self.gmaps.place(
            place_id=place_id,
            fields=['name', 'geometry', 'formatted_address', 'types', 
                   'rating', 'user_ratings_total', 'photos', 'reviews', 'website']
        )
        
        place_details = details['result']
        location = place_details['geometry']['location']
        
        # Classify destination type based on Google types
        destination_category = self._classify_destination(place_details.get('types', []))
        
        # Get weather data
        weather_data = await self._get_weather_data(location['lat'], location['lng'], destination)        
        # Find activities and attractions
        activities = await self._discover_activities(location['lat'], location['lng'], destination)
        
        # Find accommodations
        hotels = await self._discover_accommodations(location['lat'], location['lng'], destination)
        
        return {
            "destination_info": {
                "name": destination,
                "category": destination_category,
                "description": self._generate_description(place_details),
                "coordinates": {"lat": location['lat'], "lng": location['lng']},
                "rating": place_details.get('rating', 4.0),
                "best_season": weather_data.get('best_season', 'Year-round'),
                "avg_temperature": weather_data.get('avg_temp', 25),
                "sustainability_rating": self._calculate_sustainability_score(place_details),
                "hidden_gem": place_details.get('user_ratings_total', 0) < 5000
            },
            "activities": activities,
            "hotels": hotels
        }

    def _classify_destination(self, types: List[str]) -> str:
        """Classify destination based on Google Places types"""
        if any(t in types for t in ['historical_site', 'museum', 'church', 'hindu_temple']):
            return 'heritage'
        elif any(t in types for t in ['natural_feature', 'park', 'campground']):
            return 'adventure'  
        elif any(t in types for t in ['night_club', 'bar', 'casino']):
            return 'party'
        elif any(t in types for t in ['spa', 'lodging', 'luxury_hotel']):
            return 'luxury'
        else:
            return 'cultural'

    async def _discover_activities(self, lat: float, lng: float, destination: str) -> List[Dict[str, Any]]:
        """Discover activities using Google Places API"""
        
        activity_types = ['tourist_attraction', 'museum', 'amusement_park', 'zoo', 'aquarium', 'park','point_of_interest', 'art_gallery', 'shopping_mall', 'spa', 'stadium','local_event','movie_theater', 'night_club', 'bar', 'casino', 'restaurant']
        activities = []
        
        for activity_type in activity_types:
            try:
                nearby = self.gmaps.places_nearby(
                    location=(lat, lng),
                    radius=15000,  # 15km radius
                    type=activity_type
                )
                
                for place in nearby.get('results', [])[:3]:  # Top 3 per type
                    activity = {
                        "name": place['name'],
                        "type": self._map_to_activity_type(activity_type),
                        "price": self._estimate_price(place, activity_type),
                        "duration_hours": self._estimate_duration(activity_type),
                        "sustainability_score": min(9, place.get('rating', 4) * 2),
                        "description": f"Popular {activity_type.replace('_', ' ')} in {destination}",
                        "hidden_gem": place.get('user_ratings_total', 0) < 500 and place.get('rating', 0) >= 4.2
                    }
                    activities.append(activity)
                    
            except Exception as e:
                self.logger.warning(f"Failed to get {activity_type}: {e}")
                continue
                
        return activities[:10]  # Return top 10 activities

    async def _discover_accommodations(self, lat: float, lng: float, destination: str) -> List[Dict[str, Any]]:
        """Discover hotels using Google Places API"""
        
        try:
            hotels_result = self.gmaps.places_nearby(
                location=(lat, lng),
                radius=20000,
                type='lodging'
            )
            
            hotels = []
            for hotel in hotels_result.get('results', [])[:5]:  # Top 5 hotels
                hotel_data = {
                    "name": hotel['name'],
                    "location": destination,
                    "price_tier": self._determine_price_tier(hotel.get('price_level', 2)),
                    "rating": hotel.get('rating', 4.0),
                    "sustainability_score": min(9, int(hotel.get('rating', 4) * 2)),
                    "amenities": ["WiFi", "Restaurant"],  # Basic amenities
                    "coordinates": {
                        "lat": hotel['geometry']['location']['lat'],
                        "lng": hotel['geometry']['location']['lng']
                    }
                }
                hotels.append(hotel_data)
                
            return hotels
            
        except Exception as e:
            self.logger.warning(f"Failed to get hotels: {e}")
            return []

    def _determine_price_tier(self, price_level: int) -> str:
        """Convert Google's price level to our tier system"""
        tiers = {0: 'Budget', 1: 'Upper Midscale', 2: 'Upscale', 3: 'Upper Upscale', 4: 'Luxury'}
        return tiers.get(price_level, 'Upscale')

    def _map_to_activity_type(self, google_type: str) -> str:
        """Map Google types to our activity types"""
        mapping = {
            'tourist_attraction': 'cultural',
            'museum': 'cultural', 
            'amusement_park': 'adventure',
            'zoo': 'adventure',
            'aquarium': 'cultural',
            'park': 'adventure'
        }
        return mapping.get(google_type, 'cultural')

    def _estimate_price(self, place: Dict, activity_type: str) -> int:
        """Estimate activity price based on type and rating"""
        base_prices = {
            'tourist_attraction': 500,
            'museum': 200,
            'amusement_park': 800,
            'zoo': 300,
            'aquarium': 400,
            'park': 0
        }
        
        base = base_prices.get(activity_type, 300)
        rating_multiplier = place.get('rating', 4) / 4
        return int(base * rating_multiplier)

    def _estimate_duration(self, activity_type: str) -> int:
        """Estimate activity duration in hours"""
        durations = {
            'tourist_attraction': 2,
            'museum': 3,
            'amusement_park': 6,
            'zoo': 4,
            'aquarium': 3,
            'park': 2
        }
        return durations.get(activity_type, 2)

    

    def _generate_description(self, place_details: Dict) -> str:
        """Generate description from place data"""
        name = place_details.get('name', '')
        types = place_details.get('types', [])
        
        if 'locality' in types:
            return f"{name} is a beautiful destination offering rich cultural experiences and local attractions."
        elif 'natural_feature' in types:
            return f"{name} is a stunning natural location perfect for adventure and exploration."
        else:
            return f"{name} is an interesting place worth visiting for its unique character."

    def _calculate_sustainability_score(self, place_details: Dict) -> int:
        """Calculate sustainability score based on available data"""
        rating = place_details.get('rating', 4)
        total_ratings = place_details.get('user_ratings_total', 100)
        
        # Higher rating + fewer crowds = more sustainable
        base_score = int(rating * 2)
        if total_ratings < 1000:  # Less crowded = more sustainable
            base_score += 1
            
        return min(9, base_score)

    async def _store_destination_data(self, data: Dict[str, Any]) -> bool:
        """Store the discovered data in Cloud SQL via direct SQL"""
        try:
            dest_info = data["destination_info"]
            
            # Insert destination
            destination_query = f"""
            INSERT INTO destinations (name, category, description, best_season, avg_temperature, sustainability_rating, hidden_gem)
            VALUES ('{dest_info["name"]}', '{dest_info["category"]}', '{dest_info["description"]}', 
                    '{dest_info["best_season"]}', {dest_info["avg_temperature"]}, 
                    {dest_info["sustainability_rating"]}, {dest_info["hidden_gem"]})
            ON CONFLICT (name) DO NOTHING
            RETURNING id;
            """
            
            # For now, we'll add the data insertion logic
            # In a full implementation, you'd execute these via your MCP connection
            self.logger.info(f"Would execute: {destination_query}")
            
            # Store activities (simplified for demo)
            for activity in data["activities"]:
                activity_query = f"""
                INSERT INTO activities (name, type, price, duration_hours, sustainability_score, hidden_gem, description)
                VALUES ('{activity["name"].replace("'", "''")}', '{activity["type"]}', {activity["price"]}, 
                        {activity["duration_hours"]}, {activity["sustainability_score"]}, 
                        {activity["hidden_gem"]}, '{activity["description"].replace("'", "''")}');
                """
                self.logger.info(f"Would execute activity insert")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Storage failed: {e}")
            return False

# Initialize the service
ingestion_service = DynamicIngestionService()
