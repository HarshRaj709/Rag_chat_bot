# rag/service.py
import uuid
from datetime import datetime
from asgiref.sync import sync_to_async
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct,
    Filter, FieldCondition, MatchValue, PayloadSchemaType
)
from django.conf import settings
import redis.asyncio as aioredis
import json


class RAGService:

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
        self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)


#  Collection management
    

    def ensure_collection(self, collection_name: str):
        existing = {c.name for c in self.qdrant.get_collections().collections}
        if collection_name not in existing:
            self.qdrant.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )
            self.qdrant.create_payload_index(
                collection_name=collection_name,
                field_name="document_id",
                field_schema=PayloadSchemaType.KEYWORD,
            )

    def delete_collection(self, collection_name: str):
        existing = {c.name for c in self.qdrant.get_collections().collections}
        if collection_name in existing:
            self.qdrant.delete_collection(collection_name=collection_name)

# Ingestion

    def ingest(self, kb, document, text: str) -> int:
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
                    "document_id": str(document.id),
                    "filename": document.filename,
                }
            )
            for chunk, vec in zip(chunks, vectors)
        ]

        self.qdrant.upsert(collection_name=kb.qdrant_collection, points=points)
        return len(points)

    def delete_document_vectors(self, kb, document_id: str):
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

# Memory

    async def get_history(self, session_key: str) -> list:
        data = await self.redis.get(session_key)
        return json.loads(data) if data else []

    async def append_history(self, session_key: str, role: str, content: str):
        history = await self.get_history(session_key)
        history.append({"role": role, "content": content})
        history = history[-10:]
        await self.redis.setex(session_key, 3600, json.dumps(history))

    def format_history(self, history: list) -> str:
        if not history:
            return "No previous conversation."
        return "\n".join(
            f"{'User' if h['role'] == 'user' else 'Assistant'}: {h['content']}"
            for h in history
        )

# retrieval

    async def retrieve_context(self, bot, question: str) -> str:
        # print('this is question', question)
        q_vec = await sync_to_async(self.embeddings.embed_query)(question)
        kbs = await sync_to_async(list)(bot.kbs.all())
        # print("get all the kbs", kbs)

        all_hits = []
        for kb in kbs:
            try:
                results = await sync_to_async(self.qdrant.query_points)(
                    collection_name=kb.qdrant_collection,
                    query=q_vec,
                    limit=4,
                )
                # print("got this in result", results)
                all_hits.extend(results.points)
            except Exception as e:
                print(f"[RAG] Qdrant search error for {kb.qdrant_collection}: {e}")
                pass

        if not all_hits:
            return "No relevant information found."

        all_hits.sort(key=lambda h: h.score, reverse=True)
        return "\n\n".join(h.payload["content"] for h in all_hits[:6])


# streaming

    async def stream(self, bot, session_id: str, question: str):
        session_key = f"bot:{bot.slug}:{session_id}"

        history = await self.get_history(session_key)
        # print("this is retrievd history", history)
        formatted_history = self.format_history(history)
        # print("this is formatted history")
        context = await self.retrieve_context(bot, question)
        # print("we got this context", context)

        llm = ChatOpenAI(
            model="deepseek/deepseek-chat-v3-0324",
            openai_api_key=settings.OPENROUTER_API_KEY,
            base_url=settings.BASE_URL,
            streaming=True,
            temperature=bot.temperature,
            max_tokens=bot.max_tokens,
        )

        system = bot.system_prompt or "You are a helpful assistant. Answer only using the provided context."

        prompt = ChatPromptTemplate.from_template(f"""
            {system}

            Today is {datetime.now().strftime('%B %d, %Y')}.

            Conversation so far:
            {formatted_history}

            Context:
            {context}

            Question:
            {{question}}

            Answer (friendly, concise):
            """)

        chain = prompt | llm | StrOutputParser()

        await self.append_history(session_key, "user", question)
        assistant_response = ""

        async for chunk in chain.astream({"question": question}):
            assistant_response += chunk
            yield chunk

        await self.append_history(session_key, "assistant", assistant_response)


rag_service = RAGService()