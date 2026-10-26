"""Streamlit frontend for the Personalized Travel Itinerary Planner.
Run locally:  python -m streamlit run app.py
"""
import json
import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st

# Streamlit Cloud: put ANTHROPIC_API_KEY in the app's Secrets; expose it to planner.py
try:
    if "ANTHROPIC_API_KEY" in st.secrets:
        os.environ["ANTHROPIC_API_KEY"] = st.secrets["ANTHROPIC_API_KEY"]
except Exception:
    pass  # no secrets file locally -> offline planner

import planner  # noqa: E402

st.set_page_config(page_title="Wanderly - Travel Planner", page_icon="🧭", layout="wide")

TYPE_ICON = {"attraction": "🏛️", "food": "🍽️", "stay": "🏨", "transport": "🚆"}
INTERESTS = ["food", "sightseeing", "culture", "adventure", "nature", "shopping", "nightlife", "relaxation"]

st.markdown(
    """
<style>
  .block-container { padding-top: 1.5rem; max-width: 1150px; }
  .hero { background: linear-gradient(120deg,#2563eb 0%,#7c3aed 55%,#db2777 100%);
          color:#fff; padding:28px 32px; border-radius:18px; margin-bottom:18px; }
  .hero h1 { margin:0; font-size:2rem; color:#fff; }
  .hero p { margin:6px 0 0; opacity:.92; }
  .chip { display:inline-block; background:rgba(255,255,255,.18); padding:3px 12px;
          border-radius:999px; font-size:.82rem; margin:10px 6px 0 0; }
  .daycard { border:1px solid rgba(128,128,128,.25); border-radius:14px; padding:14px 18px;
             margin-bottom:10px; }
  .tl { display:flex; gap:14px; padding:9px 0; border-top:1px solid rgba(128,128,128,.18); }
  .tl:first-of-type { border-top:0; }
  .tl .t { width:52px; opacity:.6; font-variant-numeric:tabular-nums; }
  .tl .b { flex:1; } .tl .b small { opacity:.7; display:block; }
  .tl .c { font-weight:600; white-space:nowrap; }
  div[data-testid="stMetric"] { background:rgba(128,128,128,.08); padding:12px 16px; border-radius:12px; }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------- state ----------------
ss = st.session_state
ss.setdefault("trips", {})     # id -> trip dict
ss.setdefault("current", None)
ss.setdefault("next_id", 1)
ss.setdefault("ver", 0)        # bumps to reset data_editor widgets after regeneration


def total(plan):
    return round(sum(d["day_cost"] for d in plan), 2)


def add_trip(trip):
    tid = ss.next_id
    ss.next_id += 1
    ss.trips[tid] = trip
    ss.current = tid
    ss.ver += 1


# ---------------- sidebar ----------------
with st.sidebar:
    st.markdown("### 🧭 Plan a trip")
    with st.form("trip_form"):
        destination = st.text_input("Destination", placeholder="e.g. Jaipur")
        start = st.date_input("Start date", date.today() + timedelta(days=7))
        c1, c2 = st.columns(2)
        days = c1.number_input("Days", 1, 14, 3)
        travelers = c2.number_input("Travelers", 1, 20, 1)
        budget = st.number_input("Total budget", min_value=1, value=30000, step=1000)
        style = st.select_slider("Pace", ["relaxed", "balanced", "packed"], value="balanced")
        stay = st.radio("Stay level", ["budget", "mid", "premium"], index=1, horizontal=True)
        interests = st.multiselect("Interests", INTERESTS, default=["food", "sightseeing"])
        go = st.form_submit_button("✨ Generate itinerary", use_container_width=True, type="primary")

    if go:
        if len(destination.strip()) < 2:
            st.error("Please enter a destination.")
        else:
            req = {"destination": destination.strip(), "start_date": start.isoformat(), "days": int(days),
                   "budget": float(budget), "travelers": int(travelers), "interests": interests,
                   "style": style, "stay_level": stay}
            with st.spinner("Planning your trip..."):
                plan, source = planner.generate_plan(req)
            add_trip({"request": req, "plan": plan, "source": source})
            st.rerun()

    if ss.trips:
        st.markdown("### 📚 Saved trips")
        for tid, t in reversed(list(ss.trips.items())):
            r = t["request"]
            label = f"{r['destination']} · {r['days']}d"
            if st.button(label, key=f"open_{tid}", use_container_width=True,
                         type="primary" if tid == ss.current else "secondary"):
                ss.current = tid
                ss.ver += 1
                st.rerun()

    st.markdown("### 📥 Import trip")
    up = st.file_uploader("Load a saved .json", type="json", label_visibility="collapsed")
    if up is not None and ss.get("_last_upload") != up.file_id:
        try:
            add_trip(json.load(up))
            ss["_last_upload"] = up.file_id
            st.rerun()
        except Exception:
            st.error("That file isn't a valid trip.")

# ---------------- main ----------------
if ss.current is None:
    st.markdown(
        '<div class="hero"><h1>Wanderly</h1><p>Tell us where, when and how you like to travel - '
        "get a day-by-day plan with food, sights, stays and costs in seconds.</p></div>",
        unsafe_allow_html=True,
    )
    a, b, c = st.columns(3)
    a.info("**Solo weekend**\n\nShort on time? Get a tight, budget-friendly plan.")
    b.info("**Couples**\n\nRelaxed pace, scenic spots, premium stays. Edit or regenerate any day.")
    c.info("**Groups**\n\nSet group size and mixed interests; costs are for everyone combined.")
    st.caption("👈 Fill in the form in the sidebar to get started.")
    st.stop()

trip = ss.trips[ss.current]
req, plan = trip["request"], trip["plan"]

chips = "".join(f'<span class="chip">{x}</span>' for x in
                [f"{req['travelers']} traveler(s)", f"{req['style']} pace", f"{req['stay_level']} stay"]
                + req["interests"])
st.markdown(
    f'<div class="hero"><h1>{req["destination"]}</h1>'
    f'<p>{req["days"]} days from {req["start_date"]}</p>{chips}</div>',
    unsafe_allow_html=True,
)
metrics = st.container()

tabs = st.tabs([f"Day {d['day']}" for d in plan])
for idx, (tab, day) in enumerate(zip(tabs, plan)):
    with tab:
        head, btn = st.columns([4, 1])
        head.subheader(f"{day['date']} · {day.get('theme', '')}")
        if btn.button("🔄 Regenerate day", key=f"regen_{ss.current}_{idx}", use_container_width=True):
            with st.spinner("Rethinking this day..."):
                new_day, _ = planner.regenerate_day(req, plan, day["day"])
            plan[idx] = new_day
            ss.ver += 1
            st.rerun()

        timeline = "".join(
            f'<div class="tl"><div class="t">{it.get("time", "")}</div>'
            f'<div class="b">{TYPE_ICON.get(it.get("type"), "📍")} <b>{it.get("title", "")}</b>'
            f'<small>{it.get("description", "")}</small></div>'
            f'<div class="c">{it.get("cost", 0):,.0f}</div></div>'
            for it in day["items"]
        )
        st.markdown(f'<div class="daycard">{timeline}</div>', unsafe_allow_html=True)

        with st.expander("✏️ Edit this day (change, add or delete rows)"):
            df = pd.DataFrame(day["items"], columns=["time", "type", "title", "description", "cost"])
            edited = st.data_editor(
                df, num_rows="dynamic", use_container_width=True, hide_index=True,
                key=f"ed_{ss.current}_{idx}_{ss.ver}",
                column_config={
                    "type": st.column_config.SelectboxColumn("type", options=list(TYPE_ICON)),
                    "cost": st.column_config.NumberColumn("cost", min_value=0, format="%.0f"),
                },
            )
            items = []
            for row in edited.fillna("").to_dict("records"):
                if str(row["title"]).strip():
                    row["cost"] = float(row["cost"] or 0)
                    items.append(row)
            items.sort(key=lambda x: str(x.get("time", "")))
            if items != day["items"]:
                day["items"] = items
                day["day_cost"] = round(sum(i["cost"] for i in items), 2)
                st.rerun()

spent = total(plan)
with metrics:
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Estimated cost", f"{spent:,.0f}")
    m2.metric("Budget", f"{req['budget']:,.0f}")
    left = req["budget"] - spent
    m3.metric("Remaining" if left >= 0 else "Over budget", f"{abs(left):,.0f}")
    m4.metric("Per person / day", f"{spent / req['travelers'] / req['days']:,.0f}")
    st.progress(min(spent / req["budget"], 1.0))
    st.caption("✨ Written by Claude" if trip.get("source") == "ai"
               else "Generic offline plan - add an ANTHROPIC_API_KEY for real recommendations.")

st.divider()
d1, d2 = st.columns([1, 1])
d1.download_button("⬇️ Download trip (.json)", json.dumps(trip, indent=2),
                   file_name=f"{req['destination'].lower().replace(' ', '_')}_trip.json",
                   mime="application/json", use_container_width=True)
if d2.button("🗑️ Delete trip", use_container_width=True):
    del ss.trips[ss.current]
    ss.current = next(iter(reversed(ss.trips)), None)
    st.rerun()
