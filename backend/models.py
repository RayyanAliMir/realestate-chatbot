"""
SQLAlchemy models for the real estate chatbot MVP.

Three core tables:
- Agent: the paying customer (an individual agent, later an agency)
- Listing: a property listing belonging to an agent
- Lead: a captured buyer contact + question, generated when the bot
  can't answer confidently or detects strong buyer interest
"""
from datetime import datetime, timezone
from sqlalchemy import create_engine, Column, String, Integer, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True)  # UUID
    name = Column(String, nullable=False)
    email = Column(String, nullable=False, unique=True)
    widget_key = Column(String, nullable=False, unique=True)  # public key embedded in widget script
    dashboard_key = Column(String, nullable=False, unique=True)  # private key for dashboard access, returned once at creation
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    listings = relationship("Listing", back_populates="agent")
    leads = relationship("Lead", back_populates="agent")
    conversations = relationship("Conversation", back_populates="agent")


class Listing(Base):
    __tablename__ = "listings"

    id = Column(String, primary_key=True)  # UUID
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    title = Column(String, nullable=False)
    location = Column(String)
    price = Column(Float)
    bedrooms = Column(Integer)
    bathrooms = Column(Integer)
    size_sqft = Column(Float)
    amenities = Column(Text)  # comma-separated for MVP simplicity
    description = Column(Text)
    available = Column(String, default="yes")  # yes/no/pending
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    agent = relationship("Agent", back_populates="listings")

    def to_document(self) -> str:
        """Flatten a listing into a text chunk for embedding/retrieval."""
        return (
            f"Listing: {self.title}\n"
            f"Location: {self.location}\n"
            f"Price: {self.price}\n"
            f"Bedrooms: {self.bedrooms}, Bathrooms: {self.bathrooms}\n"
            f"Size: {self.size_sqft} sqft\n"
            f"Amenities: {self.amenities}\n"
            f"Availability: {self.available}\n"
            f"Description: {self.description}"
        )


class Lead(Base):
    __tablename__ = "leads"

    id = Column(String, primary_key=True)  # UUID
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    name = Column(String)
    contact = Column(String)  # phone or email, whatever the buyer gave
    question = Column(Text)  # what they were asking about when captured
    conversation_id = Column(String, ForeignKey("conversations.id"))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    agent = relationship("Agent", back_populates="leads")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True)  # UUID
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    agent = relationship("Agent", back_populates="conversations")
    messages = relationship("Message", back_populates="conversation", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True)  # UUID
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String, nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    conversation = relationship("Conversation", back_populates="messages")


# --- DB setup helpers ---

def get_engine(db_url: str = "sqlite:///./realestate_chatbot.db"):
    return create_engine(db_url, connect_args={"check_same_thread": False} if "sqlite" in db_url else {})


def init_db(engine):
    Base.metadata.create_all(bind=engine)


def get_session_factory(engine):
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)
