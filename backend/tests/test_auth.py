import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import jwt

from main import app
from auth.auth_service import Base, get_db
from auth.jwt_service import SECRET_KEY, ALGORITHM

from sqlalchemy.pool import StaticPool

# Use in-memory SQLite for testing
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
    # Clear the database before each test
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield

def test_successful_registration():
    response = client.post("/auth/register", json={
        "name": "Test User",
        "email": "test@example.com",
        "password": "strongpassword123"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert data["name"] == "Test User"
    assert "id" in data

def test_duplicate_registration():
    client.post("/auth/register", json={
        "name": "Test User",
        "email": "duplicate@example.com",
        "password": "password"
    })
    
    response = client.post("/auth/register", json={
        "name": "Test User 2",
        "email": "duplicate@example.com",
        "password": "password"
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "Duplicate email"

def test_successful_login():
    client.post("/auth/register", json={
        "name": "Login User",
        "email": "login@example.com",
        "password": "strongpassword"
    })
    
    response = client.post("/auth/login", json={
        "email": "login@example.com",
        "password": "strongpassword"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_invalid_login():
    client.post("/auth/register", json={
        "name": "Bad Login",
        "email": "bad@example.com",
        "password": "correct_password"
    })
    
    response = client.post("/auth/login", json={
        "email": "bad@example.com",
        "password": "wrong_password"
    })
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid password"

def test_jwt_validation():
    # Register and login to get token
    client.post("/auth/register", json={
        "name": "JWT User",
        "email": "jwt@example.com",
        "password": "password"
    })
    login_response = client.post("/auth/login", json={
        "email": "jwt@example.com",
        "password": "password"
    })
    token = login_response.json()["access_token"]
    
    # Decode token directly to verify contents
    payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    assert payload["sub"] == "jwt@example.com"
    assert "exp" in payload

def test_protected_route_access():
    # Attempt without token
    response = client.get("/auth/me")
    assert response.status_code in [401, 403] # Missing token gives 403 or 401 depending on FastAPI version
    
    # Register and login
    client.post("/auth/register", json={
        "name": "Protected User",
        "email": "protected@example.com",
        "password": "password"
    })
    login_response = client.post("/auth/login", json={
        "email": "protected@example.com",
        "password": "password"
    })
    token = login_response.json()["access_token"]
    
    # Attempt with token
    headers = {"Authorization": f"Bearer {token}"}
    response = client.get("/auth/me", headers=headers)
    assert response.status_code == 200
    assert response.json()["email"] == "protected@example.com"
    
    # Attempt protected /ask stub
    ask_resp = client.post("/ask", headers=headers)
    assert ask_resp.status_code == 200
