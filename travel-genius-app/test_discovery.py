# test_discovery.py
import asyncio
from services.dynamic_ingestion_service import ingestion_service

async def test_discovery():
    print("🧪 Testing dynamic discovery system...")
    
    # Test with a destination not in your database
    test_destinations = ["Punjab"]
    
    for destination in test_destinations:
        print(f"\n{'='*50}")
        print(f"Testing discovery for: {destination}")
        print(f"{'='*50}")
        
        result = await ingestion_service.discover_missing_destination(destination)
        print(f"Result: {result}")
        
        if result["success"]:
            print(f"✅ Successfully discovered {destination}!")
            print(f"   - Activities found: {result.get('activities_found', 0)}")
            print(f"   - Hotels found: {result.get('hotels_found', 0)}")
        else:
            print(f"❌ Discovery failed: {result.get('message', 'Unknown error')}")

if __name__ == "__main__":
    asyncio.run(test_discovery())
