# Personalized Travel Itinerary Planner (basic version)

FastAPI backend + simple web UI. Generates day-by-day itineraries from destination, dates,
budget, travelers, interests, pace and stay level. Trips can be saved, edited, and any day
can be regenerated.

## Run
```bash
pip install -r requirements.txt
# optional: real AI itineraries (otherwise a generic offline planner is used)
export ANTHROPIC_API_KEY=your_key        # Windows: set ANTHROPIC_API_KEY=your_key
uvicorn main:app --reload
```
Open http://127.0.0.1:8000  (API docs: http://127.0.0.1:8000/docs)

## Structure
- `main.py`     – FastAPI routes + SQLite storage (`trips.db`, created automatically)
- `planner.py`  – itinerary generation: Claude prompt (JSON output) with offline fallback
- `static/index.html` – trip builder form, saved trips, itinerary view (edit / remove / regenerate day)

## API
| Method | Path | Purpose |
|---|---|---|
| POST | `/api/trips` | generate + save a trip |
| GET | `/api/trips` | list saved trips |
| GET | `/api/trips/{id}` | get one trip |
| PUT | `/api/trips/{id}` | save edited plan |
| POST | `/api/trips/{id}/days/{n}/regenerate` | regenerate day n |
| DELETE | `/api/trips/{id}` | delete trip |

## Notes / next steps
- Without `ANTHROPIC_API_KEY` the offline planner uses generic templates (not real local places).
- Storage is SQLite; replace `db()/load()/save()` in `main.py` with Supabase for auth and shared trips.
- The UI is plain HTML/JS; it can be replaced by a React app calling the same `/api/trips` endpoints.
