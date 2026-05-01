# 📌 Project Plan: RAG SaaS Chat Bot (API-Based Integration)

---

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

### Implemented / In Progress:

* Upload document
* Extract text
* Split into chunks
* Store chunks

👉 No embeddings yet (planned)

---

## 🔄 Planned Ingestion Pipeline

* Async processing (Celery)
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
POST /api/bots/{bot_id}/chat/
```

Headers:

```http id="gxvtwx"
Authorization: Bearer <bot_api_key>
```

Body:

```json id="6dtp9s"
{
  "message": "What services do you offer?"
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
* **Vector DB (planned):** Qdrant
* **AI (planned):** OpenAI API

---

## 🧪 What to Build Next

1. Document upload + chunking completion
2. Chunk storage & retrieval logic
3. Bot chat API (basic retrieval)
4. API key generation & validation
5. Permission enforcement
6. Usage tracking per bot key

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
* ⏳ Document chunking in progress
* ⏳ Bot + chat APIs pending
* ⏳ Retrieval + LLM pending

---
