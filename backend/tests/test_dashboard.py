import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from datetime import datetime

from main import app
from auth.auth_service import Base, get_db, User, Document, Conversation, Message

# Test SQLite DB Setup
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    connect_args={"check_same_thread": False},
    poolclass=StaticPool
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

def _create_user_and_get_token(email="test@example.com", name="Test User"):
    client.post("/auth/register", json={"name": name, "email": email, "password": "pwd"})
    login = client.post("/auth/login", json={"email": email, "password": "pwd"})
    return login.json()["access_token"]

def test_dashboard_overview():
    token = _create_user_and_get_token()
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/dashboard/overview", headers=headers)
    assert response.status_code == 200

def test_dashboard_stats():
    token = _create_user_and_get_token("stats@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Inject data
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "stats@example.com").first()
    
    # 2 documents (1 OCR), 3MB total
    doc1 = Document(id="d1", user_id=user.id, filename="doc1.pdf", status="processed", file_size=1024*1024, ocr_used=0)
    doc2 = Document(id="d2", user_id=user.id, filename="doc2.pdf", status="processed", file_size=2048*1024, ocr_used=1)
    db.add_all([doc1, doc2])
    
    # 1 Conversation with 2 user messages
    conv = Conversation(id="c1", user_id=user.id, title="Test Conv")
    db.add(conv)
    m1 = Message(id="m1", conversation_id="c1", role="user", content="q1")
    m2 = Message(id="m2", conversation_id="c1", role="assistant", content="a1")
    m3 = Message(id="m3", conversation_id="c1", role="user", content="q2")
    db.add_all([m1, m2, m3])
    db.commit()
    db.close()
    
    resp = client.get("/dashboard/stats", headers=headers)
    assert resp.status_code == 200
    stats = resp.json()
    assert stats["total_documents"] == 2
    assert stats["total_ocr_documents"] == 1
    assert stats["total_storage_bytes"] == 3145728 # 3MB
    assert stats["total_conversations"] == 1
    assert stats["total_questions"] == 2 # 2 user messages

def test_dashboard_recent_documents_and_search():
    token = _create_user_and_get_token("search@example.com")
    headers = {"Authorization": f"Bearer {token}"}
    
    db = TestingSessionLocal()
    user = db.query(User).filter(User.email == "search@example.com").first()
    
    doc1 = Document(id="d1", user_id=user.id, filename="financial_report_2026.pdf", status="processed", ocr_used=0, uploaded_at=datetime(2026, 7, 19, 10, 0, 0))
    doc2 = Document(id="d2", user_id=user.id, filename="hr_policy.pdf", status="failed", ocr_used=1, uploaded_at=datetime(2026, 7, 18, 10, 0, 0))
    db.add_all([doc1, doc2])
    db.commit()
    db.close()
    
    # List all
    resp_all = client.get("/dashboard/recent-documents", headers=headers)
    assert resp_all.status_code == 200
    docs = resp_all.json()
    assert len(docs) == 2
    assert docs[0]["filename"] == "financial_report_2026.pdf" # sorted by uploaded_at desc
    assert docs[1]["ocr_used"] is True
    
    # Search by filename
    resp_search = client.get("/dashboard/recent-documents?search=report", headers=headers)
    assert len(resp_search.json()) == 1
    assert resp_search.json()[0]["filename"] == "financial_report_2026.pdf"
    
    # Filter by status
    resp_status = client.get("/dashboard/recent-documents?status=failed", headers=headers)
    assert len(resp_status.json()) == 1
    assert resp_status.json()[0]["filename"] == "hr_policy.pdf"

def test_dashboard_user_isolation():
    token_a = _create_user_and_get_token("a@example.com")
    token_b = _create_user_and_get_token("b@example.com")
    
    db = TestingSessionLocal()
    user_a = db.query(User).filter(User.email == "a@example.com").first()
    
    doc = Document(id="d1", user_id=user_a.id, filename="doc_a.pdf")
    db.add(doc)
    db.commit()
    db.close()
    
    # User B should see 0 stats
    resp_b = client.get("/dashboard/stats", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.json()["total_documents"] == 0
    assert resp_b.json()["total_storage_bytes"] == 0
    
    # User A should see 1 doc
    resp_a = client.get("/dashboard/stats", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.json()["total_documents"] == 1
