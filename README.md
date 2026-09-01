# Veritas AI — Autonomous Multi-Document Intelligence

A pure, lightweight AI document intelligence platform built with **FastAPI**, **HTML5 / CSS3 / Vanilla JavaScript**, **FAISS Vector Search**, and a **Self-Healing Corrective RAG (CRAG)** pipeline.

---

## 🛠️ Technology Stack (100% Pure & Simple)

- **Frontend**: Pure **HTML5**, **CSS3**, and **Vanilla JavaScript** (Zero Node.js, Zero npm packages, Zero build steps).
- **Backend**: **FastAPI** (Python 3.12) with CORS & REST endpoints.
- **Embeddings**: Sentence-Transformers `all-MiniLM-L6-v2` (384-dimensional dense vectors).
- **Vector Index**: **FAISS** (`IndexFlatIP` normalized cosine similarity) with user isolation.
- **RAG & Synthesis**: Self-Healing RAG with query rewriting, verification threshold, and citations.
- **Database**: SQLite with automatic schema migration + Firebase sync support.

---

## 🚀 Quick Start (Single Command)

### 1. Set Up Virtual Environment & Dependencies
```bash
cd backend
python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### 2. Run the Application
```bash
./venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

Open your browser at:
👉 **[http://localhost:8000](http://localhost:8000)**

---

## ✨ Features

- **Dashboard**: Real-time statistics on documents, chat sessions, queries, and storage.
- **PDF Upload**: Drag-and-drop PDF ingestion with text extraction & OCR fallback.
- **Document Grounded Chat**: Ask questions across your documents and get answers with verified page citations.
- **Self-Healing Retrieval**: Context verification, contradiction detection, and query rewriting loops.
- **Document Repository**: Search and manage uploaded files.
