import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from auth.auth_service import Base, get_db, User
from auth.jwt_service import create_access_token

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
    response = client.post("/auth/register", json={"name": name, "email": email, "password": "pwd"})
    login = client.post("/auth/login", json={"email": email, "password": "pwd"})
    return login.json()["access_token"]

@patch("api.upload.DocumentParser")
@patch("api.upload.chunker.chunk_document")
@patch("api.upload.embedding_service.generate_embeddings")
@patch("api.upload.faiss_service.add_embeddings")
@patch("api.upload.faiss_service.save_index")
def test_upload_multiple_documents(mock_save, mock_faiss, mock_embed, mock_chunk, MockParser):
    token = _create_user_and_get_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # Mocking parser behavior
    mock_parser_instance = MagicMock()
    mock_parser_instance.parse_document.return_value = {"metadata": {}, "pages": []}
    MockParser.return_value.__enter__.return_value = mock_parser_instance
    mock_chunk.return_value = []
    mock_embed.return_value = []
    
    # Upload first doc
    file_content1 = b"PDF content 1"
    response1 = client.post("/upload", files={"file": ("doc1.pdf", file_content1, "application/pdf")}, headers=headers)
    assert response1.status_code == 200
    
    # Upload second doc
    file_content2 = b"PDF content 2"
    response2 = client.post("/upload", files={"file": ("doc2.pdf", file_content2, "application/pdf")}, headers=headers)
    assert response2.status_code == 200
    
    # Verify both are listed
    docs_resp = client.get("/documents", headers=headers)
    assert docs_resp.status_code == 200
    docs = docs_resp.json()
    assert len(docs) == 2
    assert {docs[0]["filename"], docs[1]["filename"]} == {"doc1.pdf", "doc2.pdf"}

def test_user_isolation_and_unauthorized_access():
    token_a = _create_user_and_get_token("a@example.com", "A")
    token_b = _create_user_and_get_token("b@example.com", "B")
    
    # Inject doc for user A directly into DB for testing
    db = TestingSessionLocal()
    user_a = db.query(User).filter(User.email == "a@example.com").first()
    from auth.auth_service import Document
    doc_a = Document(id="doc_a_123", user_id=user_a.id, filename="secret_a.pdf", status="uploaded")
    db.add(doc_a)
    db.commit()
    db.close()
    
    # User A can see their doc
    resp_a = client.get("/documents/doc_a_123", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.status_code == 200
    assert resp_a.json()["filename"] == "secret_a.pdf"
    
    # User B cannot see User A's doc
    resp_b = client.get("/documents/doc_a_123", headers={"Authorization": f"Bearer {token_b}"})
    assert resp_b.status_code == 403
    
    # User B list documents is empty
    resp_b_list = client.get("/documents", headers={"Authorization": f"Bearer {token_b}"})
    assert len(resp_b_list.json()) == 0

def test_delete_document():
    token = _create_user_and_get_token()
    db = TestingSessionLocal()
    user = db.query(User).first()
    from auth.auth_service import Document
    doc = Document(id="del_doc", user_id=user.id, filename="delete_me.pdf", status="uploaded")
    db.add(doc)
    db.commit()
    db.close()
    
    # Delete doc
    del_resp = client.delete("/documents/del_doc", headers={"Authorization": f"Bearer {token}"})
    assert del_resp.status_code == 204
    
    # Verify it's gone
    get_resp = client.get("/documents/del_doc", headers={"Authorization": f"Bearer {token}"})
    assert get_resp.status_code == 404

def test_search_across_documents():
    from services.vector_store.faiss_service import FAISSService
    faiss_service = FAISSService(dimension=4)
    faiss_service.create_index()
    
    # Chunks for User 1
    faiss_service.add_embeddings([
        {"user_id": 1, "document_id": "docA", "chunk_id": "c1", "page": 1, "content": "Company policy 1", "filename": "docA.pdf", "embedding": [1,0,0,0]},
        {"user_id": 1, "document_id": "docB", "chunk_id": "c2", "page": 1, "content": "Company policy 2", "filename": "docB.pdf", "embedding": [1,0,0,0]}
    ])
    
    # Chunks for User 2
    faiss_service.add_embeddings([
        {"user_id": 2, "document_id": "docC", "chunk_id": "c3", "page": 1, "content": "User B secret report", "filename": "docC.pdf", "embedding": [1,0,0,0]}
    ])
    
    # User 1 searches: should return docA and docB, never docC
    results = faiss_service.search([1,0,0,0], top_k=5, user_id=1)
    
    assert len(results) == 2
    doc_ids = {r["document_id"] for r in results}
    assert doc_ids == {"docA", "docB"}
    assert "docC" not in doc_ids
