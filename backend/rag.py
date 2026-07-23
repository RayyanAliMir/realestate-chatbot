"""
RAG pipeline: one Chroma collection per agent, so one agent's listings
can never leak into another agent's chatbot answers.
"""
import chromadb
from models import Listing

chroma_client = chromadb.PersistentClient(path="./chroma_data")


def _collection_name(agent_id: str) -> str:
    return f"agent_{agent_id.replace('-', '_')}"


def get_or_create_collection(agent_id: str):
    return chroma_client.get_or_create_collection(name=_collection_name(agent_id))


def index_listing(agent_id: str, listing: Listing):
    """Add or update a single listing's embedding in the agent's collection."""
    collection = get_or_create_collection(agent_id)
    collection.upsert(
        ids=[listing.id],
        documents=[listing.to_document()],
        metadatas=[{"listing_id": listing.id, "title": listing.title}],
    )


def remove_listing(agent_id: str, listing_id: str):
    collection = get_or_create_collection(agent_id)
    collection.delete(ids=[listing_id])


def retrieve_context(agent_id: str, query: str, n_results: int = 4) -> list[str]:
    """Return the top-N most relevant listing chunks for a buyer's question."""
    collection = get_or_create_collection(agent_id)
    if collection.count() == 0:
        return []
    results = collection.query(query_texts=[query], n_results=min(n_results, collection.count()))
    return results["documents"][0] if results["documents"] else []
