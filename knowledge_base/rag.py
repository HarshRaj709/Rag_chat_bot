# knowledge_base/rag.py
import uuid
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from qdrant_client import QdrantClient
from qdrant_client.models import VectorParams, Distance, PointStruct, Filter, FieldCondition, MatchValue
from django.conf import settings


class KBRagService:
    def __init__(self):
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small",
            openai_api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.BASE_URL,
        )
        self.qdrant = QdrantClient(
            url=settings.QDRANT_URL,
            api_key=settings.QDRANT_API_KEY,
        )

    def ensure_collection(self, collection_name: str):
        existing = {c.name for c in self.qdrant.get_collections().collections}
        if collection_name not in existing:
            self.qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )

    def ingest(self, kb, document, text: str) -> int:
        """
        Chunk, embed, and upsert into Qdrant.
        Each chunk stores document_id in payload so we can delete per-document later.
        Returns chunk count.
        """
        self.ensure_collection(kb.qdrant_collection)

        splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=40)
        chunks = splitter.split_text(text)

        if not chunks:
            raise ValueError("No text content could be extracted from this file.")

        vectors = self.embeddings.embed_documents(chunks)

        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vec,
                payload={
                    "content": chunk,
                    "document_id": str(document.id),   # key for per-document deletion
                    "filename": document.original_filename,
                }
            )
            for chunk, vec in zip(chunks, vectors)
        ]

        self.qdrant.upsert(collection_name=kb.qdrant_collection, points=points)
        return len(points)

    def delete_document_vectors(self, kb, document_id: str):
        """Delete all vectors belonging to a specific document."""
        self.qdrant.delete(
            collection_name=kb.qdrant_collection,
            points_selector=Filter(
                must=[
                    FieldCondition(
                        key="document_id",
                        match=MatchValue(value=document_id)
                    )
                ]
            )
        )

    def delete_collection(self, collection_name: str):
        """Hard delete the entire Qdrant collection when a KB is deleted."""
        existing = {c.name for c in self.qdrant.get_collections().collections}
        if collection_name in existing:
            self.qdrant.delete_collection(collection_name=collection_name)


rag_service = KBRagService()  # singleton — one instance reused across requests