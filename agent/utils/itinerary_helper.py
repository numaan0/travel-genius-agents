# utils/itinerary_helpers.py
from typing import Dict, Any, List

# ---------- DAILY ACTIVITY GENERATOR ----------
def create_daily_activities(day: int, destination: str,
                            cost_per_day: int,
                            outdoor_score: int,
                            indoor_score: int) -> List[dict]:
    activities = []
    # Morning block
    if outdoor_score >= 6:
        activities.append({
            "id": f"day{day}_outdoor",
            "title": f"🏖️ {destination} Adventure Experience",
            "description": f"Explore outdoor attractions in {destination}",
            "cost": int(cost_per_day * 0.30),
            "duration": "3-4h",
            "type": "adventure",
            "timing": "09:00-13:00",
            "rating": 4.8
        })
    else:
        activities.append({
            "id": f"day{day}_indoor",
            "title": "🏛️ Cultural Heritage Tour",
            "description": f"Discover {destination}'s history via museums & galleries",
            "cost": int(cost_per_day * 0.25),
            "duration": "3-4h",
            "type": "cultural",
            "timing": "09:00-13:00",
            "rating": 4.6
        })
    # Lunch
    activities.append({
        "id": f"day{day}_food",
        "title": "🍽️ Authentic Local Cuisine",
        "description": f"Savour traditional {destination} delicacies",
        "cost": int(cost_per_day * 0.35),
        "duration": "1-2h",
        "type": "food",
        "timing": "13:30-15:30",
        "rating": 4.7
    })
    # Evening
    if outdoor_score >= 5:
        activities.append({
            "id": f"day{day}_instagram",
            "title": "📸 Sunset Photography",
            "description": "Capture sunset views at Instagram-perfect spots",
            "cost": int(cost_per_day * 0.20),
            "duration": "2h",
            "type": "instagram",
            "timing": "18:00-20:00",
            "rating": 4.9
        })
    else:
        activities.append({
            "id": f"day{day}_cultural_evening",
            "title": "🎭 Evening Cultural Show",
            "description": "Enjoy traditional performances indoors",
            "cost": int(cost_per_day * 0.25),
            "duration": "2-3h",
            "type": "cultural",
            "timing": "18:00-21:00",
            "rating": 4.5
        })
    return activities

# ---------- MAIN ITINERARY BUILDER ----------
def create_weather_optimized_itinerary(weather_data: dict,
                                       user_input: dict,
                                       agent_text: str) -> dict:
    destination = user_input.get("destination", "Amazing Destination")
    days        = user_input.get("days",        5)
    budget      = user_input.get("budget",      50_000)
    group_size  = user_input.get("groupSize",   1)

    cost_per_day   = budget // days
    daily_forecast = weather_data.get("daily_forecast", []) if weather_data else []
    daily_plans    = []

    for d in range(1, days + 1):
        wf   = daily_forecast[d-1] if len(daily_forecast) >= d else {}
        o_sc = wf.get("suitability_scores", {}).get("outdoor", 7)
        i_sc = wf.get("suitability_scores", {}).get("indoor",  6)
        daily_plans.append({
            "day": d,
            "activities": create_daily_activities(d, destination, cost_per_day, o_sc, i_sc),
            "weather_summary": {
                "condition": wf.get("condition", "Good"),
                "outdoor_score": o_sc,
                "indoor_score":  i_sc,
                "recommendations": wf.get("recommendations", [])
            }
        })

    return {
        "tripTitle":          f"Weather-Optimized {days}-Day {destination} Adventure",
        "totalEstimatedCost": budget,
        "dailyPlans":         daily_plans,
        "weatherOptimized":   True,
        "overallWeatherScore": weather_data.get("weather_score", 7),
        "aiRecommendations": [
            f"Book outdoor activities early for {destination}",
            "Carry a reusable water bottle",
            "Reserve indoor options as backup"
        ],
        "generatedBy":  "AI Travel Genius",
        "generatedAt":  "2025-09-16T23:45:00+05:30"
    }
