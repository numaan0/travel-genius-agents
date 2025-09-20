"""
Dynamic Travel Data Ingestion Service for AI Travel Genius
Uses New Google Places API and stores data in Cloud SQL
"""

from dotenv import load_dotenv
import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import requests
import psycopg2
from toolbox_core import ToolboxSyncClient

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class DatabaseIntegration:
    """Handles all database operations for storing discovered travel data"""
    
    def __init__(self):
        self.connection_params = {
            'host': os.getenv('CLOUDSQL_HOST'),
            'database': os.getenv('CLOUDSQL_DBNAME', 'postgres'),
            'user': os.getenv('CLOUDSQL_USER', 'postgres'),
            'password': os.getenv('CLOUDSQL_PASSWORD'),
            'port': int(os.getenv('CLOUDSQL_PORT', 5432))
        }
        
        # Validate required environment variables
        missing_vars = []
        for key, value in self.connection_params.items():
            if not value and key != 'port':
                missing_vars.append(f"CLOUDSQL_{key.upper()}")
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")
        
        self.logger = logging.getLogger("DatabaseIntegration")
        self.logger.info(f"✅ Database connection configured for host: {self.connection_params['host']}")

    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            conn = psycopg2.connect(**self.connection_params)
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            self.logger.info("✅ Database connection test successful!")
            return True
        except Exception as e:
            self.logger.error(f"❌ Database connection test failed: {e}")
            return False

    def insert_discovered_destination(self, data: Dict[str, Any]) -> Optional[int]:
        """Insert discovered destination data into Cloud SQL"""
        
        try:
            conn = psycopg2.connect(**self.connection_params)
            cursor = conn.cursor()
            
            dest_info = data.get("destination_info", {})
            
            # Insert destination with conflict handling
            insert_dest_query = """
                INSERT INTO destinations (name, country, category, description, best_season, avg_temperature, sustainability_rating, hidden_gem)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (name) DO UPDATE SET 
                    country = EXCLUDED.country,
                    category = EXCLUDED.category,
                    description = EXCLUDED.description,
                    sustainability_rating = EXCLUDED.sustainability_rating,
                    hidden_gem = EXCLUDED.hidden_gem,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING id;
                """
            
            cursor.execute(insert_dest_query, (
                dest_info.get("name"),
                dest_info.get("country", "Unknown"),  # <-- Add this line
                dest_info.get("category"),
                dest_info.get("description"),
                dest_info.get("best_season", "Year-round"),
                dest_info.get("avg_temperature", 25),
                dest_info.get("sustainability_rating", 7),
                dest_info.get("hidden_gem", False)
            ))
            
            destination_id = cursor.fetchone()[0]
            self.logger.info(f"✅ Inserted destination '{dest_info.get('name')}' with ID: {destination_id}")
            
            # Insert activities
            activities = data.get("activities", [])
            if activities:
                activity_query = """
                INSERT INTO activities (destination_id, name, type, price, duration_hours, sustainability_score, hidden_gem, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
                """
                
                for activity in activities:
                    cursor.execute(activity_query, (
                        destination_id,
                        activity.get("name"),
                        activity.get("type"),
                        activity.get("price", 0),
                        activity.get("duration_hours", 2),
                        activity.get("sustainability_score", 7),
                        activity.get("hidden_gem", False),
                        activity.get("description", "")
                    ))
                
                self.logger.info(f"✅ Inserted {len(activities)} activities")
            
            # Insert hotels
            hotels = data.get("hotels", [])
            if hotels:
                hotel_query = """
                INSERT INTO hotels (name, location, price_tier, rating, sustainability_score, amenities, checkin_date)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
                """
                
                for hotel in hotels:
                    cursor.execute(hotel_query, (
                        hotel.get("name"),
                        hotel.get("location"),
                        hotel.get("price_tier", "Upscale"),
                        hotel.get("rating", 4.0),
                        hotel.get("sustainability_score", 7),
                        hotel.get("amenities", ["WiFi", "Restaurant"]),
                        datetime.now().date()
                    ))
                
                self.logger.info(f"✅ Inserted {len(hotels)} hotels")
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return destination_id
            
        except Exception as e:
            self.logger.error(f"❌ Database insertion failed: {e}")
            if 'conn' in locals():
                try:
                    conn.rollback()
                    conn.close()
                except:
                    pass
            return None


class DynamicIngestionService:
    """Main service for discovering and ingesting new travel destinations"""
    
    def __init__(self):
        self.api_key = os.getenv('GOOGLE_MAPS_API_KEY')
        if not self.api_key:
            raise ValueError("GOOGLE_MAPS_API_KEY not found in environment variables")
        
        self.weather_api_key = os.getenv('WEATHER_API_KEY')
        self.toolbox = ToolboxSyncClient(os.getenv('MCP_TOOLBOX_URL'))
        self.db_integration = DatabaseIntegration()
        
        self.logger = logging.getLogger("DynamicIngestion")
        self.logger.info(f"✅ Dynamic Ingestion Service initialized with NEW Places API")

    async def discover_missing_destination(self, destination_name: str) -> Dict[str, Any]:
        """Main function: Discovers and adds missing destination data using NEW API"""
        
        self.logger.info(f"🔍 Starting discovery for: {destination_name}")
        
        try:
            # Step 1: Search for the destination using NEW Places API
            destination_data = await self._search_destination_new_api(destination_name)
            
            if not destination_data:
                return {
                    "success": False, 
                    "message": f"Could not find comprehensive data for {destination_name}"
                }
            
            # Step 2: Get nearby places using NEW API
            activities = await self._discover_activities_new_api(destination_data['coordinates'])
            hotels = await self._discover_accommodations_new_api(destination_data['coordinates'])
            
            result_data = {
                "destination_info": destination_data,
                "activities": activities,
                "hotels": hotels
            }
            
            # Step 3: Store in database
            destination_id = self.db_integration.insert_discovered_destination(result_data)
            
            if destination_id:
                self.logger.info(f"✅ Successfully discovered and stored {destination_name}!")
                
                return {
                    "success": True,
                    "destination": destination_name,
                    "destination_id": destination_id,
                    "activities_found": len(activities),
                    "hotels_found": len(hotels),
                    "message": f"🎉 {destination_name} added to our knowledge base!"
                }
            else:
                return {
                    "success": False,
                    "message": f"Discovery completed but failed to store {destination_name}"
                }
            
        except Exception as e:
            self.logger.error(f"❌ Discovery failed for {destination_name}: {str(e)}")
            return {"success": False, "error": str(e)}

    async def _search_destination_new_api(self, destination: str) -> Optional[Dict[str, Any]]:
        """Search for destination using NEW Places API Text Search"""
        
        try:
            url = "https://places.googleapis.com/v1/places:searchText"
            
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount,places.types"
            }
            
            data = {
                "textQuery": destination,
                "includedType": "locality",
                "maxResultCount": 1
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=10)
            response.raise_for_status()
            
            result = response.json()
            
            if not result.get('places'):
                self.logger.warning(f"No places found for {destination}")
                return None
                
            place = result['places'][0]
            
            return {
                "name": destination,
                "country": self._extract_country(place.get('formattedAddress', '')) or "Unknown",
                "display_name": place.get('displayName', {}).get('text', destination),
                "coordinates": {
                    "lat": place['location']['latitude'],
                    "lng": place['location']['longitude']
                },
                "address": place.get('formattedAddress', ''),
                "rating": place.get('rating', 4.0),
                "user_rating_count": place.get('userRatingCount', 0),
                "types": place.get('types', []),
                "category": self._classify_destination(place.get('types', [])),
                "description": self._generate_description(destination, place.get('types', [])),
                "best_season": "Year-round",
                "avg_temperature": 25,
                "sustainability_rating": self._calculate_sustainability_score(place),
                "hidden_gem": place.get('userRatingCount', 0) < 5000
            }
            
        except Exception as e:
            self.logger.error(f"Failed to search destination with NEW API: {e}")
            return None
        
    def _extract_country(self, formatted_address: str) -> Optional[str]:
        """Extract country from formatted address (simple heuristic)"""
        if formatted_address:
            parts = formatted_address.split(',')
            if parts:
                return parts[-1].strip()
        return None

    async def _discover_activities_new_api(self, coordinates: Dict[str, float]) -> List[Dict[str, Any]]:
        """Discover activities using NEW Places API Nearby Search"""
        
        try:
            url = "https://places.googleapis.com/v1/places:searchNearby"
            
            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount,places.types,places.priceLevel"
            }
            
            data = {
                "includedTypes": ["tourist_attraction", "museum", "amusement_park", "zoo", "aquarium", "park"],
                "maxResultCount": 15,
                "locationRestriction": {
                    "circle": {
                        "center": {
                            "latitude": coordinates['lat'],
                            "longitude": coordinates['lng']
                        },
                        "radius": 25000.0  # 25km radius
                    }
                }
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=15)
            response.raise_for_status()
            
            result = response.json()
            activities = []
            
            for place in result.get('places', []):
                activity = {
                    "name": place.get('displayName', {}).get('text', 'Unknown Activity'),
                    "type": self._map_to_activity_type(place.get('types', [])),
                    "price": self._estimate_price_from_level(place.get('priceLevel')),
                    "duration_hours": self._estimate_duration(place.get('types', [])),
                    "sustainability_score": min(9, int(place.get('rating', 4) * 2)),
                    "description": f"Popular {place.get('types', ['attraction'])[0].replace('_', ' ')} near {place.get('formattedAddress', '')}",
                    "hidden_gem": place.get('userRatingCount', 0) < 1000 and place.get('rating', 0) >= 4.2,
                    "coordinates": {
                        "lat": place['location']['latitude'],
                        "lng": place['location']['longitude']
                    }
                }
                activities.append(activity)
            
            return activities[:10]  # Return top 10
            
        except Exception as e:
            self.logger.error(f"Failed to discover activities with NEW API: {e}")
            return []

    async def _discover_accommodations_new_api(self, coordinates: Dict[str, float]) -> List[Dict[str, Any]]:
        """Discover hotels using NEW Places API"""
        
        try:
            url = "https://places.googleapis.com/v1/places:searchNearby"
            
            headers = {
                "Content-Type": "application/json", 
                "X-Goog-Api-Key": self.api_key,
                "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount,places.priceLevel"
            }
            
            data = {
                "includedTypes": ["lodging"],
                "maxResultCount": 10,
                "locationRestriction": {
                    "circle": {
                        "center": {
                            "latitude": coordinates['lat'],
                            "longitude": coordinates['lng']
                        },
                        "radius": 20000.0  # 20km radius
                    }
                }
            }
            
            response = requests.post(url, headers=headers, json=data, timeout=15)
            response.raise_for_status()
            
            result = response.json()
            hotels = []
            
            for place in result.get('places', []):
                hotel = {
                    "name": place.get('displayName', {}).get('text', 'Unknown Hotel'),
                    "location": place.get('formattedAddress', ''),
                    "price_tier": self._determine_price_tier(place.get('priceLevel')),
                    "rating": place.get('rating', 4.0),
                    "sustainability_score": min(9, int(place.get('rating', 4) * 2)),
                    "amenities": ["WiFi", "Restaurant"],  # Basic amenities
                    "coordinates": {
                        "lat": place['location']['latitude'],
                        "lng": place['location']['longitude']
                    }
                }
                hotels.append(hotel)
            
            return hotels[:8]  # Return top 8
            
        except Exception as e:
            self.logger.error(f"Failed to discover hotels with NEW API: {e}")
            return []

    def _classify_destination(self, types: List[str]) -> str:
        """Classify destination based on Google Places types"""
        if any(t in types for t in ['church', 'hindu_temple', 'mosque', 'synagogue', 'tourist_attraction']):
            return 'heritage'
        elif any(t in types for t in ['natural_feature', 'park', 'campground']):
            return 'adventure'
        elif any(t in types for t in ['museum', 'art_gallery', 'cultural_center']):
            return 'cultural'
        elif any(t in types for t in ['night_club', 'bar', 'casino']):
            return 'party'
        elif any(t in types for t in ['spa', 'resort_hotel']):
            return 'luxury'
        else:
            return 'cultural'

    def _map_to_activity_type(self, types: List[str]) -> str:
        """Map Google Places types to our activity types"""
        if 'museum' in types or 'art_gallery' in types:
            return 'cultural'
        elif 'amusement_park' in types or 'zoo' in types:
            return 'adventure'
        elif 'aquarium' in types or 'tourist_attraction' in types:
            return 'cultural'
        else:
            return 'cultural'

    def _estimate_price_from_level(self, price_level: Optional[int]) -> int:
        """Convert Google's price level to INR estimate"""
        if price_level is None:
            return 1000
        
        price_map = {0: 200, 1: 500, 2: 1200, 3: 2500, 4: 5000}
        return price_map.get(price_level, 1000)

    def _estimate_duration(self, types: List[str]) -> int:
        """Estimate activity duration based on type"""
        if 'museum' in types:
            return 3
        elif 'amusement_park' in types or 'zoo' in types:
            return 6
        elif 'park' in types:
            return 2
        else:
            return 3

    def _determine_price_tier(self, price_level: Optional[int]) -> str:
        """Convert Google's price level to our tier system"""
        if price_level is None:
            return 'Upscale'
        
        tier_map = {0: 'Budget', 1: 'Upper Midscale', 2: 'Upscale', 3: 'Upper Upscale', 4: 'Luxury'}
        return tier_map.get(price_level, 'Upscale')

    def _calculate_sustainability_score(self, place: Dict) -> int:
        """Calculate sustainability score based on place data"""
        rating = place.get('rating', 4.0)
        user_count = place.get('userRatingCount', 100)
        
        base_score = int(rating * 2)
        if user_count < 1000:  # Less crowded = more sustainable
            base_score += 1
        
        return min(9, base_score)

    def _generate_description(self, destination: str, types: List[str]) -> str:
        """Generate a description based on destination and types"""
        if 'locality' in types:
            return f"{destination} is a vibrant destination offering rich cultural experiences and diverse attractions."
        elif 'natural_feature' in types:
            return f"{destination} is a stunning natural location perfect for adventure and exploration."
        else:
            return f"{destination} is an interesting place worth visiting for its unique character and local attractions."


# Create service instance for use in other modules
ingestion_service = DynamicIngestionService()


# Test functions
async def test_discovery():
    """Test the dynamic discovery system"""
    print("🧪 Testing Dynamic Discovery System...")
    print("="*60)
    
    # Test database connection first
    print("1. Testing database connection...")
    if ingestion_service.db_integration.test_connection():
        print("✅ Database connection successful!")
    else:
        print("❌ Database connection failed!")
        return
    
    # Test destination discovery
    test_destinations = ["Seychelles", "Madagascar", "Faroe Islands"]
    
    for destination in test_destinations:
        print(f"\n2. Testing discovery for: {destination}")
        print("-" * 40)
        
        try:
            result = await ingestion_service.discover_missing_destination(destination)
            
            if result["success"]:
                print(f"✅ Successfully discovered {destination}!")
                print(f"   - Destination ID: {result.get('destination_id')}")
                print(f"   - Activities found: {result.get('activities_found', 0)}")
                print(f"   - Hotels found: {result.get('hotels_found', 0)}")
                print(f"   - Message: {result.get('message')}")
            else:
                print(f"❌ Discovery failed: {result.get('message', 'Unknown error')}")
                
        except Exception as e:
            print(f"❌ Error during discovery: {str(e)}")
        
        # Small delay between requests
        await asyncio.sleep(2)

def test_environment_variables():
    """Test that all required environment variables are loaded"""
    print("🧪 Testing Environment Variables...")
    print("="*40)
    
    required_vars = [
        'GOOGLE_MAPS_API_KEY',
        'CLOUDSQL_HOST',
        'CLOUDSQL_PASSWORD'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            masked_value = value[:10] + "..." if len(value) > 10 else value
            print(f"✅ {var}: {masked_value}")
        else:
            missing_vars.append(var)
            print(f"❌ {var}: NOT SET")
    
    if missing_vars:
        print(f"\n❌ Missing environment variables: {missing_vars}")
        print("Please check your .env file!")
        return False
    else:
        print("\n✅ All required environment variables are set!")
        return True


if __name__ == "__main__":
    print("🚀 AI Travel Genius - Dynamic Data Ingestion Service")
    print("="*60)
    
    # Test environment variables first
    if test_environment_variables():
        # Run discovery tests
        asyncio.run(test_discovery())
    else:
        print("❌ Cannot proceed without proper environment variables!")
