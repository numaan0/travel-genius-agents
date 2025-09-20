import os
import aiohttp
import asyncio
from dotenv import load_dotenv
from typing import Dict, Any, List
from datetime import datetime, timedelta
from collections import defaultdict

load_dotenv()

class WeatherService:
    def __init__(self):
        print("[Init] Initializing WeatherService...")
        self.api_key = os.getenv("WEATHER_API_KEY")
        if not self.api_key:
            raise ValueError("WEATHER_API_KEY not found in environment variables")
        self.base_url_current = "https://api.openweathermap.org/data/2.5/weather"
        self.base_url_forecast = "https://api.openweathermap.org/data/2.5/forecast"
        print("[Init] WeatherService initialized successfully.")

    async def _fetch_json(self, url: str, retries: int = 3, timeout: int = 10) -> Dict:
        """Internal method to fetch JSON with retries, timeout, and debug prints"""
        for attempt in range(1, retries + 1):
            try:
                print(f"[Attempt {attempt}] Fetching {url} ...")
                async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
                    async with session.get(url) as response:
                        response.raise_for_status()
                        data = await response.json()
                        print(f"[Success] Fetched data from {url}")
                        return data
            except asyncio.TimeoutError:
                print(f"[Attempt {attempt}] Timeout fetching {url}")
            except aiohttp.ClientResponseError as e:
                print(f"[Attempt {attempt}] HTTP error fetching {url}: {e.status}, message='{e.message}'")
            except aiohttp.ClientError as e:
                print(f"[Attempt {attempt}] Client error fetching {url}: {str(e)}")
            except Exception as e:
                print(f"[Attempt {attempt}] Unexpected error fetching {url}: {str(e)}")
            if attempt < retries:
                await asyncio.sleep(2 * attempt)  # exponential backoff
        raise Exception(f"Failed to fetch {url} after {retries} attempts")

    async def get_current_weather(self, destination: str) -> dict:
        """Get current weather for a destination with debug prints"""
        print(f"[Start] get_current_weather for {destination}")
        try:
            url = f"{self.base_url_current}?q={destination}&appid={self.api_key}&units=metric"
            data = await self._fetch_json(url)
            result = {
                "current": {
                    "condition": data["weather"][0]["description"],
                    "temp_c": data["main"]["temp"],
                    "feelslike_c": data["main"]["feels_like"]
                }
            }
            print(f"[Success] Current weather for {destination}: {result}")
            return result
        except Exception as e:
            print(f"[Error] Failed to fetch current weather for {destination}: {str(e)}")
            return {"current": {}, "error": str(e)}

    async def get_forecast(self, destination: str, duration_days: int = 5) -> dict:
        """Get daily forecast summary from OpenWeatherMap 3-hour interval data"""
        print(f"[Start] get_forecast for {destination}, duration_days={duration_days}")
        try:
            url = f"{self.base_url_forecast}?q={destination}&appid={self.api_key}&units=metric"
            data = await self._fetch_json(url)

            daily_data = defaultdict(list)
            for item in data.get("list", []):
                date_str = item["dt_txt"].split(" ")[0]
                daily_data[date_str].append(item)

            forecast_days = []
            for i, (date, items) in enumerate(daily_data.items()):
                if i >= duration_days:
                    break
                min_temp = min(item["main"]["temp_min"] for item in items)
                max_temp = max(item["main"]["temp_max"] for item in items)
                avg_temp = sum(item["main"]["temp"] for item in items) / len(items)
                precipitation = sum(item.get("rain", {}).get("3h", 0) for item in items)
                wind_speed = max(item["wind"]["speed"] for item in items)
                humidity = sum(item["main"]["humidity"] for item in items) / len(items)
                condition = items[len(items)//2]["weather"][0]["description"]
                uv_index = 5  # Default since free API does not provide UV

                forecast_days.append({
                    "date": date,
                    "condition": condition,
                    "min_temp": min_temp,
                    "max_temp": max_temp,
                    "avg_temp": avg_temp,
                    "precipitation": precipitation,
                    "wind_speed": wind_speed,
                    "humidity": humidity,
                    "uv_index": uv_index
                })
            print(f"[Success] Processed forecast for {destination}, days={len(forecast_days)}")
            return {"forecastday": forecast_days}
        except Exception as e:
            print(f"[Error] Failed to fetch forecast for {destination}: {str(e)}")
            return {"forecastday": [], "error": str(e)}

    def get_weather_suitability_score(self, weather_data: Dict, activity_type: str) -> int:
        """Score weather suitability for activities (1-10)"""
        try:
            print(f"[Start] get_weather_suitability_score for {activity_type}, data={weather_data}")
            day_data = weather_data
            condition = day_data.get("condition", "").lower()
            max_temp = day_data.get("max_temp", 25)
            min_temp = day_data.get("min_temp", 20)
            avg_temp = day_data.get("avg_temp", 22)
            precipitation = day_data.get("precipitation", 0)
            wind_speed = day_data.get("wind_speed", 0)

            score = 5
            if activity_type.lower() in ['outdoor', 'adventure', 'sightseeing', 'walking']:
                if "clear" in condition or "sun" in condition:
                    score += 3
                elif "cloud" in condition:
                    score += 1
                elif "rain" in condition:
                    score -= 3
                elif "storm" in condition:
                    score -= 5
                if 20 <= avg_temp <= 28:
                    score += 2
                elif 15 <= avg_temp < 20 or 28 < avg_temp <= 35:
                    score += 1
                elif avg_temp < 10 or avg_temp > 40:
                    score -= 3
                if precipitation > 10:
                    score -= 3
                elif precipitation > 5:
                    score -= 1
                if wind_speed > 30:
                    score -= 2
                elif wind_speed > 20:
                    score -= 1

            elif activity_type.lower() in ['indoor', 'cultural', 'museum', 'shopping']:
                score += 2
                if "rain" in condition or "drizzle" in condition:
                    score += 1
                elif "storm" in condition:
                    score += 2

            elif activity_type.lower() in ['beach', 'water', 'swimming']:
                if "clear" in condition or "sun" in condition:
                    score += 4
                elif "cloud" in condition:
                    score += 2
                if 25 <= avg_temp <= 32:
                    score += 3
                elif 22 <= avg_temp < 25:
                    score += 1
                elif avg_temp < 20 or avg_temp > 35:
                    score -= 2
                if precipitation > 2:
                    score -= 4
                if 10 <= wind_speed <= 25:
                    score += 1
                elif wind_speed > 35:
                    score -= 2

            final_score = max(1, min(10, score))
            print(f"[Success] Suitability score for {activity_type}: {final_score}")
            return final_score
        except Exception as e:
            print(f"[Error] get_weather_suitability_score failed: {str(e)}")
            return 5

    async def get_weather_summary_for_dates(self, destination: str, start_date: str, duration_days: int) -> Dict[str, Any]:
        """Generate daily summary with scores and recommendations"""
        print(f"[Start] get_weather_summary_for_dates for {destination}, start_date={start_date}, duration_days={duration_days}")
        try:
            forecast_data = await self.get_forecast(destination, duration_days)
            daily_weather = []
            overall_score = 0

            for day in forecast_data.get("forecastday", []):
                outdoor_score = self.get_weather_suitability_score(day, "outdoor")
                indoor_score = self.get_weather_suitability_score(day, "indoor")
                beach_score = self.get_weather_suitability_score(day, "beach")

                day["suitability_scores"] = {
                    "outdoor": outdoor_score,
                    "indoor": indoor_score,
                    "beach": beach_score
                }
                day["recommendations"] = self._get_day_recommendations(day, outdoor_score)
                daily_weather.append(day)
                overall_score += (outdoor_score + indoor_score) / 2

            result = {
                "destination": destination,
                "duration_days": duration_days,
                "overall_weather_score": round(overall_score / max(1, duration_days), 1),
                "daily_weather": daily_weather,
                "best_days_for_outdoor": sorted(daily_weather, key=lambda x: x["suitability_scores"]["outdoor"], reverse=True)[:3],
                "weather_alerts": self._generate_weather_alerts(daily_weather)
            }
            print(f"[Success] Weather summary generated for {destination}")
            return result

        except Exception as e:
            print(f"[Error] Failed to generate weather summary for {destination}: {str(e)}")
            return {
                "error": f"Weather data unavailable: {str(e)}",
                "destination": destination,
                "overall_weather_score": 6,
                "daily_weather": [],
                "weather_alerts": []
            }

    def _get_day_recommendations(self, day_data: Dict, outdoor_score: int) -> List[str]:
        print(f"[Info] Generating recommendations for {day_data.get('date', 'unknown')}...")
        recommendations = []
        condition = day_data.get("condition", "").lower()
        avg_temp = day_data.get("avg_temp", 22)
        precipitation = day_data.get("precipitation", 0)

        try:
            if outdoor_score >= 8:
                recommendations.append("Perfect day for outdoor sightseeing and adventure activities")
            elif outdoor_score >= 6:
                recommendations.append("Good day for outdoor activities with some precautions")
            elif outdoor_score >= 4:
                recommendations.append("Mixed conditions - plan indoor alternatives")
            else:
                recommendations.append("Focus on indoor cultural activities and museums")

            if precipitation > 10:
                recommendations.append("Heavy rain expected - bring waterproof gear or stay indoors")
            elif precipitation > 5:
                recommendations.append("Light rain possible - carry an umbrella")

            if avg_temp > 35:
                recommendations.append("Very hot - plan early morning or late evening activities")
            elif avg_temp < 10:
                recommendations.append("Cold weather - dress warmly and consider heated venues")

            print(f"[Success] Recommendations generated: {recommendations}")
        except Exception as e:
            print(f"[Error] Failed generating recommendations: {str(e)}")

        return recommendations

    def _generate_weather_alerts(self, daily_weather: List[Dict]) -> List[Dict]:
        print("[Info] Generating weather alerts...")
        alerts = []
        try:
            for day in daily_weather:
                if day.get("precipitation", 0) > 15:
                    alerts.append({
                        "date": day["date"],
                        "type": "heavy_rain",
                        "message": f"Heavy rain expected ({day['precipitation']}mm) - plan indoor activities"
                    })
                if day.get("avg_temp", 0) > 38:
                    alerts.append({
                        "date": day["date"],
                        "type": "extreme_heat",
                        "message": f"Extreme heat warning ({day['avg_temp']}°C) - stay hydrated and avoid midday sun"
                    })
                if day.get("wind_speed", 0) > 40:
                    alerts.append({
                        "date": day["date"],
                        "type": "high_wind",
                        "message": f"High winds expected ({day['wind_speed']} km/h) - outdoor activities may be affected"
                    })
            print(f"[Success] Generated {len(alerts)} weather alerts")
        except Exception as e:
            print(f"[Error] Failed to generate alerts: {str(e)}")

        return alerts

# Singleton instance for use in other modules
weather_service = WeatherService()
