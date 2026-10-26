"""Itinerary generation: Claude (if ANTHROPIC_API_KEY is set) with an offline fallback."""
import json
import os
import random
import re
from datetime import date, timedelta

MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")

# ---------- AI generation ----------

PROMPT = """You are a travel planner. Create a {n}-day itinerary for {destination}.
Travelers: {travelers}. Total budget: {budget} (all travelers, whole trip, local currency units).
Interests: {interests}. Pace: {style}. Accommodation level: {stay_level}.
{extra}
Return ONLY valid JSON (no markdown) of this shape:
{{"days":[{{"theme":"short theme","items":[{{"time":"09:00","type":"attraction|food|stay|transport","title":"...","description":"one sentence","cost":0}}]}}]}}
Rules: include breakfast/lunch/dinner, attractions grouped by proximity to cut travel time,
a stay item on day 1, a transport item when moving across the city. "cost" is a number for ALL
travelers combined. Keep the total near or under budget. {pace_rule}"""

PACE = {
    "relaxed": "3-4 items per day, generous breaks.",
    "balanced": "5-6 items per day.",
    "packed": "7-8 items per day, efficient routing.",
}


def _extract_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    return json.loads(text)


def _ai_days(req: dict, n: int, extra: str = "") -> list[dict]:
    import anthropic

    client = anthropic.Anthropic()
    prompt = PROMPT.format(
        n=n,
        destination=req["destination"],
        travelers=req["travelers"],
        budget=req["budget"],
        interests=", ".join(req["interests"]) or "general sightseeing",
        style=req["style"],
        stay_level=req["stay_level"],
        extra=extra,
        pace_rule=PACE.get(req["style"], PACE["balanced"]),
    )
    msg = client.messages.create(
        model=MODEL, max_tokens=4000, messages=[{"role": "user", "content": prompt}]
    )
    return _extract_json(msg.content[0].text)["days"]


# ---------- Offline fallback (generic templates, NOT real local data) ----------

ACTIVITIES = {
    "food": ["Street-food walk", "Local market tasting", "Cooking class", "Famous local eatery"],
    "sightseeing": ["Old town walking tour", "City viewpoint", "Main landmark visit", "Historic district"],
    "culture": ["Museum visit", "Local temple/heritage site", "Art gallery", "Cultural performance"],
    "adventure": ["Guided hike", "Water/outdoor activity", "Cycling tour", "Zip-line or climbing"],
    "nature": ["Botanical garden / park", "Lakeside or riverside walk", "Sunset point", "Wildlife area"],
    "shopping": ["Local crafts bazaar", "Main shopping street", "Souvenir market"],
    "nightlife": ["Rooftop bar", "Live music venue", "Night market"],
    "relaxation": ["Spa session", "Scenic cafe time", "Slow beach/garden afternoon"],
}
STAY_SHARE = {"budget": 0.25, "mid": 0.35, "premium": 0.5}
ITEMS_PER_DAY = {"relaxed": 4, "balanced": 6, "packed": 8}


def _offline_days(req: dict, n: int, rng: random.Random) -> list[dict]:
    dest = req["destination"]
    interests = [i.lower() for i in req["interests"] if i.lower() in ACTIVITIES] or ["sightseeing", "food"]
    per_day_budget = req["budget"] / n
    stay_cost = per_day_budget * STAY_SHARE.get(req["stay_level"], 0.35)
    food_cost = per_day_budget * 0.3
    act_budget = max(per_day_budget - stay_cost - food_cost, 0)
    target = ITEMS_PER_DAY.get(req["style"], 6)
    days = []
    for d in range(n):
        items = [{"time": "08:30", "type": "food", "title": f"Breakfast near your stay in {dest}",
                  "description": "Start with a local breakfast.", "cost": round(food_cost * 0.2, 2)}]
        n_act = max(target - 3, 1)
        slots = ["10:00", "12:00", "14:30", "16:30", "18:00"][:n_act]
        picks = []
        for k in range(n_act):
            cat = interests[(d + k) % len(interests)]
            picks.append((cat, rng.choice(ACTIVITIES[cat])))
        for t, (cat, name) in zip(slots, picks):
            items.append({"time": t, "type": "attraction", "title": f"{name} - {dest}",
                          "description": f"Interest: {cat}. Activities are grouped to limit travel time.",
                          "cost": round(act_budget / n_act, 2)})
        items.append({"time": "13:00", "type": "food", "title": "Lunch at a well-rated local spot",
                      "description": "Midday meal close to the morning activity.",
                      "cost": round(food_cost * 0.35, 2)})
        items.append({"time": "20:00", "type": "food", "title": f"Dinner - regional specialties in {dest}",
                      "description": "Evening meal.", "cost": round(food_cost * 0.45, 2)})
        if d == 0:
            items.append({"time": "12:00", "type": "stay", "title": f"Check in: {req['stay_level']} stay",
                          "description": "Drop bags and check in.", "cost": round(stay_cost * n, 2)})
        items.sort(key=lambda x: x["time"])
        days.append({"theme": f"{picks[0][0].title()} day", "items": items})
    return days


# ---------- Public API ----------

def _finalize(req: dict, days: list[dict]) -> list[dict]:
    start = date.fromisoformat(str(req["start_date"]))
    for i, day in enumerate(days):
        day["day"] = i + 1
        day["date"] = (start + timedelta(days=i)).isoformat()
        for it in day["items"]:
            it["cost"] = float(it.get("cost") or 0)
        day["items"].sort(key=lambda x: x.get("time", ""))
        day["day_cost"] = round(sum(it["cost"] for it in day["items"]), 2)
    return days


def generate_plan(req: dict) -> tuple[list[dict], str]:
    n = req["days"]
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            return _finalize(req, _ai_days(req, n)), "ai"
        except Exception as e:  # fall back so the app always works
            print("AI generation failed, using offline planner:", e)
    return _finalize(req, _offline_days(req, n, random.Random())), "offline"


def regenerate_day(req: dict, plan: list[dict], day_no: int) -> tuple[dict, str]:
    idx = day_no - 1
    # Plan a single day against that day's share of the budget.
    one = dict(req, budget=req["budget"] / req["days"])
    keep_stay = day_no == 1
    day, mode = None, "offline"
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            other = "; ".join(f"Day {d['day']}: {d['theme']}" for d in plan if d["day"] != day_no)
            extra = (f"Generate ONE fresh, different day. Budget given is for this single day. "
                     f"Other days already cover: {other}. ")
            if not keep_stay:
                extra += "Do not include a stay/check-in item."
            day, mode = _ai_days(one, 1, extra)[0], "ai"
        except Exception as e:
            print("AI day regeneration failed, using offline planner:", e)
    if day is None:
        day = _offline_days(one, 1, random.Random())[0]
    if not keep_stay:
        day["items"] = [it for it in day["items"] if it.get("type") != "stay"]
    elif mode == "offline":  # offline stay item covers the whole trip, not one day
        for it in day["items"]:
            if it.get("type") == "stay":
                it["cost"] = round(it["cost"] * req["days"], 2)
    start = date.fromisoformat(str(req["start_date"]))
    day["day"] = day_no
    day["date"] = (start + timedelta(days=idx)).isoformat()
    for it in day["items"]:
        it["cost"] = float(it.get("cost") or 0)
    day["items"].sort(key=lambda x: x.get("time", ""))
    day["day_cost"] = round(sum(it["cost"] for it in day["items"]), 2)
    return day, mode
