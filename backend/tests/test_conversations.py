import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from auth.auth_service import Base, get_db, User, Conversation, Message

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

def test_create_conversation():
    token = _create_user_and_get_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    response = client.post("/conversations", json={"title": "Enterprise Documents"}, headers=headers)
    assert response.status_code == 201
    assert response.json()["title"] == "Enterprise Documents"
    assert "id" in response.json()
    
    # List conversations
    resp_list = client.get("/conversations", headers=headers)
    assert len(resp_list.json()) == 1

@patch("api.conversations.rag_service.embed_query")
@patch("api.conversations.rag_service.retrieve_chunks")
@patch("api.conversations.verification_service.verify_response")
@patch("api.conversations.rag_service.answer_question")
def test_add_message_and_retrieve_history(mock_answer, mock_verify, mock_retrieve, mock_embed):
    token = _create_user_and_get_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    conv_resp = client.post("/conversations", json={"title": "Test Conv"}, headers=headers)
    conv_id = conv_resp.json()["id"]
    
    # Mock RAG pipeline
    mock_embed.return_value = [0.1]
    mock_retrieve.return_value = [{"chunk_id": "c1", "page": 1, "content": "mocked"}]
    mock_verify.return_value = {"can_answer": True, "verified": True, "issues": []}
    mock_answer.return_value = {"answer": "Veritas AI is...", "citations": []}
    
    # Send message 1
    msg_resp1 = client.post(f"/conversations/{conv_id}/message", json={"content": "What is Veritas AI?"}, headers=headers)
    assert msg_resp1.status_code == 200
    assert msg_resp1.json()["answer"] == "Veritas AI is..."
    
    # Check history
    hist_resp = client.get(f"/conversations/{conv_id}", headers=headers)
    assert hist_resp.status_code == 200
    hist = hist_resp.json()
    assert len(hist["messages"]) == 2 # 1 user msg, 1 assistant msg
    assert hist["messages"][0]["role"] == "user"
    assert hist["messages"][1]["role"] == "assistant"
    
    # Empty message handling
    err_resp = client.post(f"/conversations/{conv_id}/message", json={"content": " "}, headers=headers)
    assert err_resp.status_code == 400
    assert err_resp.json()["detail"] == "Empty message"

def test_user_isolation_and_delete():
    token_a = _create_user_and_get_token("a@example.com", "A")
    token_b = _create_user_and_get_token("b@example.com", "B")
    
    # Create conversation for User A
    conv_a = client.post("/conversations", json={"title": "A's Docs"}, headers={"Authorization": f"Bearer {token_a}"}).json()
    conv_id = conv_a["id"]
    
    # User B tries to get User A's history
    resp_b = client.get(f"/conversations/{conv_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 403
    
    # User B tries to message User A's conversation
    msg_b = client.post(f"/conversations/{conv_id}/message", json={"content": "test"}, headers={"Authorization": f"Bearer {token_b}"})
    assert msg_b.status_code == 403
    
    # User B tries to delete User A's conversation
    del_b = client.delete(f"/conversations/{conv_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert del_b.status_code == 403
    
    # User A deletes their own conversation
    del_a = client.delete(f"/conversations/{conv_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert del_a.status_code == 204
    
    # Try fetching it again
    fetch_a = client.get(f"/conversations/{conv_id}", headers={"Authorization": f"Bearer {token_a}"})
    assert fetch_a.status_code == 404
