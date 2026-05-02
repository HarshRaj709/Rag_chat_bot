# 🚀 Introduction

This project started from a simple problem I faced while building my first RAG-based chatbot — a **portfolio assistant** that could answer questions about my experience, education, and projects. That bot is already integrated into my portfolio website and can interact with users in real time.

While building it, I realized something important:

> Every individual or organization has data — but not everyone has an easy way to turn that data into an intelligent, conversational system.

That idea led to the creation of this platform.

---

## 💡 What This Project Does

This is a **RAG (Retrieval-Augmented Generation) SaaS platform** that allows anyone to:

* Upload their documents
* Automatically process and structure their knowledge
* Generate a chatbot powered by their own data
* Integrate that chatbot directly into their website using APIs

No need to build RAG pipelines from scratch.

---

## 🏗️ Core Concept

Users can:

* Sign up and create an **organization**
* Invite team members with **role-based access control**

  * **Owner / Admin / Member**
* Manage knowledge and bots in a **multi-tenant environment**

Only **owners and admins** can perform critical/destructive actions like deletion.

---

## 📚 Knowledge Management

* Create multiple **Knowledge Bases**
* Each knowledge base can contain multiple documents
* Supported formats:

  * PDF
  * DOCX
  * Markdown
  * TXT

Each document goes through:

* Text extraction
* Chunking using **Recursive Text Splitter**
* Storage for retrieval

---

## 🤖 Bot System

Users can create bots connected to their knowledge:

* Each bot gets a **unique slug** → used to generate a public API endpoint
* Bots can be connected to **multiple knowledge bases**
* Bots respond strictly based on provided documents

---

## 🔐 Security (Important Design Decision)

When a bot is created:

* A **secret API key** is generated
* The **raw key is shown only once**
* Only a **hashed version is stored in the database**

If the key is lost:

* Users must generate a new one (cannot retrieve old key)

---

## 🔗 Integration

Bots are **API-first**:

* Can be integrated into any website or application
* Communication happens via secure API requests
* No UI/widget dependency — full flexibility for frontend

---

## 🧠 Smart Responses

* Responses are generated using document context (RAG)
* Bot maintains **short-term memory (last 10 messages)** for context-aware conversations

---

## 🎯 Vision

The goal of this project is to:

> Make it effortless for anyone to convert their documents into an intelligent, production-ready chatbot — without worrying about infrastructure, vector databases, or LLM pipelines.

---

# 📌 Project Plan: RAG SaaS Chat Bot (API-Based Integration)




## 🚀 Overview

This project is a **Django-based RAG (Retrieval-Augmented Generation) SaaS platform** for building **organization-specific chatbots**.

Organizations can:

* Upload and manage documents
* Process and chunk content
* Create bots connected to their knowledge bases
* Integrate chat functionality into their applications using **secure APIs**

⚠️ This system is **API-first** — no embedded scripts or UI widgets are provided.
Frontend integration is handled by the client using exposed APIs.

---

## 🎯 Core Goals

* Provide multi-tenant organization-based architecture
* Enable document-based knowledge systems
* Support bot creation linked to knowledge bases
* Expose **secure, token-based chatbot APIs**
* Focus on **document chunking (current stage)**
* Ensure strict organization-level data isolation

---

## 🧠 Core System Flow

```text id="zbsmhy"
Client Application (Website / App)
        ↓
Bot Chat API (token-based)
        ↓
Retrieve relevant chunks (from KB)
        ↓
LLM response generation (planned)
        ↓
Response returned via API
```

---

## 🏢 Multi-Tenant Design

* Users can belong to multiple organizations
* Each organization has:

  * Members (owner, admin, member)
  * Knowledge Bases
  * Documents
  * Bots

👉 Complete **data isolation per organization**

---

## 📦 Key Components

---

### 🔐 Authentication & User Management (`authentication`, `user`)

* Custom user model
* JWT authentication using `rest_framework_simplejwt`
* Signup:

  * Creates user + organization
  * Assigns owner role
* Login returns access & refresh tokens

---

### 🏢 Organization & Membership (`organization`)

* Organization CRUD
* Role-based access:

  * owner
  * admin
  * member
* Invite system:

  * Email invites
  * Token-based acceptance
  * Expiry handling

---

### 📚 Knowledge Base (`knowledge_base`)

* Multiple KBs per organization
* Unique name per org
* Logical grouping of documents

---

### 📄 Documents (`knowledge_base`)

* Upload documents (text / PDF)
* Metadata:

  * filename
  * storage/file
  * ingestion status
  * chunk count

---

## ⚙️ Current Focus: Document Chunking

### Implemented:

* Upload document
* Extract text
* Split into chunks
* Store chunks


---

## 🔄 Ingestion Pipeline

* Async processing (Celery) - Future plan
* Steps:

  1. Text extraction
  2. Chunking
  3. Embedding generation
  4. Store in vector DB (Qdrant)

---

### 🤖 Chat Bots (`chat_bot`)

* Bots belong to organizations
* Each bot can connect to multiple KBs
* Configurable parameters (planned):

  * temperature
  * max tokens

---

## 🔑 Bot API Access

Bots are accessed via **secure API keys**

### Example Request

```http id="c07hgp"
POST /api/chat/bot/{unique-slug}/chat/
```

Headers:

```http id="gxvtwx"
Authorization: Bearer <bot_api_key>
```

Body:

```json id="6dtp9s"
{
  "query": "What services do you offer?",
  "session_id": "bd98146c-ae25-4e43-a861-6f2a930ceaa1"
}
```

---

## 📡 API Structure

```id="a6pbr6"
/api/
 ├── auth/
 ├── orgs/
 │     └── {org_id}/
 │           ├── kbs/
 │           ├── bots/
 │           └── members/
 ├── bots/   (public bot APIs - API key based)
```

---

## 🔄 Example API Flows

* `POST /api/auth/signup/` → register + create org
* `POST /api/auth/login/` → get tokens
* `GET /api/orgs/` → list orgs
* `POST /api/orgs/{org_id}/kbs/` → create KB
* `POST /api/orgs/{org_id}/kbs/{kb_id}/documents/` → upload doc
* `POST /api/orgs/{org_id}/bots/` → create bot
* `POST /api/bots/{bot_id}/chat/` → query bot (API key)

---

## ⚙️ Tech Stack

* **Backend:** Django, DRF
* **Auth:** JWT
* **Async (planned):** Celery + Redis
* **DB:** SQLite (dev), PostgreSQL (planned)
* **Vector DB:** Qdrant
* **Embedding Model:** OpenAI text-embedding-3-small
* **LLM Model:** deepseek/deepseek-chat-v3-0324

---

## 🧪 Completed

1. Document upload + chunking completion
2. Chunk storage & retrieval logic
3. Bot chat API (basic retrieval)
4. API key generation & validation
5. Permission enforcement

## Left 
1. Usage tracking per bot key

---

## 🧱 Local Setup

```bash id="r94xne"
python manage.py migrate
python manage.py runserver
```

---

## 🧭 Current Status

* ✅ Organization system complete
* ✅ Invite flow implemented
* ✅ Knowledge base APIs done
* ✅ Document chunking in progress
* ✅ Bot + chat APIs pending
* ✅ Retrieval + LLM pending

---
