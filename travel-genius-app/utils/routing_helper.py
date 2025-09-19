# utils/routing_helpers.py
def determine_intent(query: str, has_existing_itinerary: bool = False) -> str:
    q = query.lower()
    gen = ['create itinerary', 'plan a trip', 'generate itinerary', 'plan my vacation']
    chat = ['can you change', 'what about', 'suggest', 'alternative', 'cheaper']
    if any(k in q for k in gen):   return "generate"
    if any(k in q for k in chat):  return "chat"
    return "chat" if has_existing_itinerary else "generate"

def validate_user_input(data: dict) -> bool:
    return all(data.get(k) for k in ["destination", "days", "budget"])
