# Real Estate AI Chatbot — MVP

## Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # add your ANTHROPIC_API_KEY
uvicorn main:app --reload
```

API runs at `http://localhost:8000`. Interactive docs at `http://localhost:8000/docs`.

## Try it end to end

1. **Register an agent**
   `POST /agents` with `{"name": "Jane Doe", "email": "jane@example.com"}`
   → save the returned `agent_id` and `widget_key`

2. **Add a few listings**
   `POST /agents/{agent_id}/listings` with a listing body (see `ListingCreate` in `main.py`)

3. **Embed the widget**
   Open `widget/demo.html`, set `data-widget-key` to your agent's key, open in a browser, chat with it.

4. **Check leads**
   `GET /agents/{agent_id}/leads` — populated whenever the bot can't answer or the buyer shows strong interest.

## What's here (v1 scope)

- Agent + listing management (SQLite via SQLAlchemy)
- Per-agent Chroma collection for RAG — one agent's data can never leak into another's answers
- Chat endpoint grounded only in that agent's listings, via Claude
- Automatic lead capture (`[CAPTURE_LEAD]` tag pattern) when the bot can't answer or detects buying intent
- Embeddable vanilla JS widget, no framework dependency
- In-memory conversation history (fine for MVP pilot, swap for Redis/DB before scaling past a handful of agents)

## Explicitly cut from v1 (agency-tier upsell later)

- Multi-language support
- CRM integrations
- Analytics dashboards
- Team/multi-agent permissions

## Next steps

- Swap in-memory `conversations` dict for persistent storage before running more than a couple of pilot agents at once
- Build a minimal dashboard UI (leads + conversation log) — currently just raw JSON endpoints
- Lock down CORS to real agent domains before going live
- Get this into a proper git repo / local dev environment (Claude Code) — this sandbox is disposable between chat sessions
