"""
Real Estate AI Chatbot - MVP backend.

Endpoints:
  POST /agents                    - register a new agent, returns widget_key
  POST /agents/{agent_id}/listings - add a listing (auto-indexed for RAG)
  DELETE /listings/{listing_id}   - remove a listing
  POST /chat                      - main chat endpoint used by the widget
  GET  /agents/{agent_id}/leads   - dashboard: view captured leads
  GET  /agents/{agent_id}/conversations - dashboard: view chat logs
"""
import os
import uuid
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
import anthropic

from database import get_db
from models import Agent, Listing, Lead
from rag import index_listing, remove_listing, retrieve_context

load_dotenv()

app = FastAPI(title="Real Estate AI Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten to specific agent domains before real launch
    allow_methods=["*"],
    allow_headers=["*"],
)

claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# In-memory conversation history for the MVP phase.
# conversation_id -> list of {"role": ..., "content": ...}
conversations: dict[str, list[dict]] = {}

SYSTEM_PROMPT_TEMPLATE = """You are a helpful real estate assistant for {agent_name}.
Answer buyer questions ONLY using the listing information provided in context below.
Never invent a price, availability, or detail that isn't in the context - if you don't
know, say so and offer to connect them with the agent.

If the buyer asks something you can't answer from the listings, OR shows strong buying
interest (asks to view a property, asks about next steps, asks how to contact the agent),
respond normally AND append this exact tag on its own line at the end of your reply:
[CAPTURE_LEAD]

Listing context:
{context}
"""


# --- Pydantic schemas ---

class AgentCreate(BaseModel):
    name: str
    email: str


class ListingCreate(BaseModel):
    title: str
    location: str | None = None
    price: float | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    size_sqft: float | None = None
    amenities: str | None = None
    description: str | None = None


class ChatRequest(BaseModel):
    widget_key: str
    conversation_id: str | None = None
    message: str
    buyer_name: str | None = None
    buyer_contact: str | None = None


# --- Agent management ---

@app.post("/agents")
def create_agent(payload: AgentCreate, db: Session = Depends(get_db)):
    agent = Agent(
        id=str(uuid.uuid4()),
        name=payload.name,
        email=payload.email,
        widget_key=str(uuid.uuid4()),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return {"agent_id": agent.id, "widget_key": agent.widget_key}


# --- Listing management ---

@app.post("/agents/{agent_id}/listings")
def add_listing(agent_id: str, payload: ListingCreate, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")

    listing = Listing(id=str(uuid.uuid4()), agent_id=agent_id, **payload.model_dump())
    db.add(listing)
    db.commit()
    db.refresh(listing)

    index_listing(agent_id, listing)  # keep RAG index in sync
    return {"listing_id": listing.id}


@app.delete("/listings/{listing_id}")
def delete_listing(listing_id: str, db: Session = Depends(get_db)):
    listing = db.query(Listing).filter(Listing.id == listing_id).first()
    if not listing:
        raise HTTPException(404, "Listing not found")

    agent_id = listing.agent_id
    db.delete(listing)
    db.commit()
    remove_listing(agent_id, listing_id)
    return {"status": "deleted"}


# --- Chat (the core product) ---

@app.post("/chat")
def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    agent = db.query(Agent).filter(Agent.widget_key == payload.widget_key).first()
    if not agent:
        raise HTTPException(404, "Invalid widget key")

    conversation_id = payload.conversation_id or str(uuid.uuid4())
    history = conversations.setdefault(conversation_id, [])

    context_chunks = retrieve_context(agent.id, payload.message)
    context_text = "\n\n---\n\n".join(context_chunks) if context_chunks else "(no matching listings found)"

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(agent_name=agent.name, context=context_text)

    history.append({"role": "user", "content": payload.message})

    response = claude.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=500,
        system=system_prompt,
        messages=history,
    )
    reply_text = "".join(block.text for block in response.content if block.type == "text")

    lead_captured = False
    if "[CAPTURE_LEAD]" in reply_text:
        lead_captured = True
        reply_text = reply_text.replace("[CAPTURE_LEAD]", "").strip()
        db.add(Lead(
            id=str(uuid.uuid4()),
            agent_id=agent.id,
            name=payload.buyer_name,
            contact=payload.buyer_contact,
            question=payload.message,
            conversation_id=conversation_id,
        ))
        db.commit()

    history.append({"role": "assistant", "content": reply_text})

    return {
        "conversation_id": conversation_id,
        "reply": reply_text,
        "lead_captured": lead_captured,
    }


# --- Dashboard endpoints ---

@app.get("/agents/{agent_id}/leads")
def get_leads(agent_id: str, db: Session = Depends(get_db)):
    leads = db.query(Lead).filter(Lead.agent_id == agent_id).order_by(Lead.created_at.desc()).all()
    return [
        {
            "id": l.id,
            "name": l.name,
            "contact": l.contact,
            "question": l.question,
            "created_at": l.created_at.isoformat(),
        }
        for l in leads
    ]


@app.get("/agents/{agent_id}/conversations")
def get_conversations(agent_id: str):
    # MVP: in-memory only, no per-agent filtering yet (fine for a single-agent pilot)
    return conversations
