# services/database_integration.py
from dotenv import load_dotenv
import os
import psycopg2
from typing import Dict, Any

# Load environment variables from .env file
load_dotenv()

class DatabaseIntegration:
    def __init__(self):
        # Get database credentials from environment variables
        self.connection_params = {
            'host': os.getenv('CLOUDSQL_HOST'),
            'database': os.getenv('CLOUDSQL_DBNAME', 'postgres'),
            'user': os.getenv('CLOUDSQL_USER', 'postgres'),
            'password': os.getenv('CLOUDSQL_PASSWORD'),
            'port': os.getenv('CLOUDSQL_PORT', '5432')
        }
        
        # Verify all required environment variables are loaded
        missing_vars = [key for key, value in self.connection_params.items() if not value]
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {missing_vars}")
        
        print(f"✅ Database connection configured for host: {self.connection_params['host']}")

    async def insert_discovered_destination(self, data: Dict[str, Any]) -> int:
        """Actually insert the discovered data into Cloud SQL"""
        
        try:
            conn = psycopg2.connect(**self.connection_params)
            cursor = conn.cursor()
            
            dest_info = data["destination_info"]
            
            # Insert destination and get ID
            insert_dest_query = """
            INSERT INTO destinations (name, category, description, best_season, avg_temperature, sustainability_rating, hidden_gem)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (name) DO UPDATE SET 
                category = EXCLUDED.category,
                description = EXCLUDED.description,
                sustainability_rating = EXCLUDED.sustainability_rating,
                hidden_gem = EXCLUDED.hidden_gem
            RETURNING id;
            """
            
            cursor.execute(insert_dest_query, (
                dest_info["name"],
                dest_info["category"], 
                dest_info["description"],
                dest_info.get("best_season", "Year-round"),
                dest_info.get("avg_temperature", 25),
                dest_info["sustainability_rating"],
                dest_info["hidden_gem"]
            ))
            
            destination_id = cursor.fetchone()[0]
            print(f"✅ Inserted destination '{dest_info['name']}' with ID: {destination_id}")
            
            # Insert activities
            for activity in data.get("activities", []):
                activity_query = """
                INSERT INTO activities (destination_id, name, type, price, duration_hours, sustainability_score, hidden_gem, description)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
                """
                
                cursor.execute(activity_query, (
                    destination_id,
                    activity["name"],
                    activity["type"],
                    activity["price"],
                    activity["duration_hours"],
                    activity["sustainability_score"],
                    activity["hidden_gem"],
                    activity["description"]
                ))
            
            print(f"✅ Inserted {len(data.get('activities', []))} activities")
            
            # Insert hotels
            for hotel in data.get("hotels", []):
                hotel_query = """
                INSERT INTO hotels (name, location, price_tier, rating, sustainability_score, amenities)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT DO NOTHING;
                """
                
                cursor.execute(hotel_query, (
                    hotel["name"],
                    hotel["location"],
                    hotel["price_tier"],
                    hotel["rating"],
                    hotel["sustainability_score"],
                    hotel.get("amenities", ["WiFi"])
                ))
            
            print(f"✅ Inserted {len(data.get('hotels', []))} hotels")
            
            conn.commit()
            cursor.close()
            conn.close()
            
            return destination_id
            
        except Exception as e:
            print(f"❌ Database insertion failed: {e}")
            if 'conn' in locals():
                conn.rollback()
                conn.close()
            return None

    def test_connection(self) -> bool:
        """Test database connection"""
        try:
            conn = psycopg2.connect(**self.connection_params)
            cursor = conn.cursor()
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()
            cursor.close()
            conn.close()
            print("✅ Database connection test successful!")
            return True
        except Exception as e:
            print(f"❌ Database connection test failed: {e}")
            return False

# Create instance for use in other modules
db_integration = DatabaseIntegration()
