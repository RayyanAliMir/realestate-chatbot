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
from fastapi import FastAPI, Depends, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session
import anthropic

from database import get_db
from models import Agent, Conversation, Listing, Lead, Message
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

SYSTEM_PROMPT_TEMPLATE = """You are a helpful real estate assistant for {agent_name}.
Answer buyer questions ONLY using the listing information provided in context below.
Never invent a price, availability, or detail that isn't in the context - if you don't
know, say so and offer to connect them with the agent.

Write like {agent_name} texting a client: plain conversational sentences, no markdown.
Never use tables, headers, bold/italic asterisks, bullet lists, or emojis - if you're
listing a few details (like price and bedrooms), just say them in a normal sentence.

If the buyer asks something you can't answer from the listings, OR shows strong buying
interest (asks to view a property, asks about next steps, asks how to contact the agent),
respond normally AND append this exact tag on its own line at the end of your reply:
[CAPTURE_LEAD]

Listing context:
{context}
"""

EXTRACTION_SYSTEM_PROMPT = """Read this conversation between a real estate buyer and a chatbot.
Call the extract_contact tool with the buyer's name and contact info (phone number or email),
if they mentioned either anywhere in the conversation. Leave a field as an empty string if that
piece of info was never given."""

EXTRACT_CONTACT_TOOL = {
    "name": "extract_contact",
    "description": "Record the buyer's name and contact info as found in the conversation.",
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {"type": "string", "description": "Buyer's name, or empty string if not given"},
            "contact": {"type": "string", "description": "Buyer's phone or email, or empty string if not given"},
        },
        "required": ["name", "contact"],
    },
}


def extract_buyer_contact(messages: list[dict]) -> tuple[str | None, str | None]:
    try:
        response = claude.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=200,
            system=EXTRACTION_SYSTEM_PROMPT,
            tools=[EXTRACT_CONTACT_TOOL],
            tool_choice={"type": "tool", "name": "extract_contact"},
            messages=messages,
        )
    except anthropic.APIError as e:
        print(f"extract_buyer_contact failed: {e}")
        return None, None

    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_contact":
            return block.input.get("name") or None, block.input.get("contact") or None
    return None, None


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
        dashboard_key=str(uuid.uuid4()),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return {"agent_id": agent.id, "widget_key": agent.widget_key, "dashboard_key": agent.dashboard_key}


def require_dashboard_key(
    agent_id: str,
    x_dashboard_key: str = Header(default=None),
    db: Session = Depends(get_db),
) -> Agent:
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(404, "Agent not found")
    if not x_dashboard_key or x_dashboard_key != agent.dashboard_key:
        raise HTTPException(401, "Missing or invalid dashboard key")
    return agent


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
    conversation = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conversation:
        conversation = Conversation(id=conversation_id, agent_id=agent.id)
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    history = [{"role": m.role, "content": m.content} for m in conversation.messages]

    context_chunks = retrieve_context(agent.id, payload.message)
    context_text = "\n\n---\n\n".join(context_chunks) if context_chunks else "(no matching listings found)"

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(agent_name=agent.name, context=context_text)

    history.append({"role": "user", "content": payload.message})

    db.add(Message(id=str(uuid.uuid4()), conversation_id=conversation.id, role="user", content=payload.message))
    db.commit()

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

        # `history` already ends on the buyer's latest message - the extraction call
        # requires the conversation to end on a user turn (no assistant prefill).
        extracted_name, extracted_contact = extract_buyer_contact(history)
        name = extracted_name or payload.buyer_name
        contact = extracted_contact or payload.buyer_contact

        existing_lead = db.query(Lead).filter(Lead.conversation_id == conversation.id).first()
        if existing_lead:
            existing_lead.name = name or existing_lead.name
            existing_lead.contact = contact or existing_lead.contact
            existing_lead.question = payload.message
        else:
            db.add(Lead(
                id=str(uuid.uuid4()),
                agent_id=agent.id,
                name=name,
                contact=contact,
                question=payload.message,
                conversation_id=conversation.id,
            ))

    db.add(Message(id=str(uuid.uuid4()), conversation_id=conversation.id, role="assistant", content=reply_text))
    db.commit()

    return {
        "conversation_id": conversation.id,
        "reply": reply_text,
        "lead_captured": lead_captured,
    }


# --- Dashboard endpoints ---

@app.get("/agents/{agent_id}/leads")
def get_leads(agent_id: str, db: Session = Depends(get_db), agent: Agent = Depends(require_dashboard_key)):
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
def get_conversations(agent_id: str, db: Session = Depends(get_db), agent: Agent = Depends(require_dashboard_key)):
    conversations = db.query(Conversation).filter(Conversation.agent_id == agent_id).all()
    return {
        c.id: [{"role": m.role, "content": m.content} for m in c.messages]
        for c in conversations
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
