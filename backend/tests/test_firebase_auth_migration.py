import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from main import app
from auth.auth_service import Base, get_db, engine
from firebase.firebase_admin import verify_firebase_token

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


def test_firebase_register_and_logging(capsys):
    """
    Test POST /auth/register endpoint returns deprecation shim message and logs 'Firebase signup'.
    """
    response = client.post("/auth/register", json={
        "name": "Firebase User",
        "email": "firebase_signup@example.com",
        "password": "password123"
    })
    assert response.status_code == 201
    data = response.json()
    assert "Deprecated" in data["message"]

    captured = capsys.readouterr().out
    assert "Firebase signup" in captured


def test_firebase_login_and_logging(capsys):
    """
    Test POST /auth/login endpoint returns deprecation shim message and logs 'Firebase login'.
    """
    response = client.post("/auth/login", json={
        "email": "firebase_login@example.com",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "Deprecated" in data["message"]

    captured = capsys.readouterr().out
    assert "Firebase login" in captured



def test_firebase_me_endpoint_and_token_verification(capsys):
    """
    Test GET /auth/me returns uid, email, and provider: firebase when authorized with Firebase ID token.
    """
    mock_token_payload = {
        "uid": "fb_uid_999",
        "email": "fb_me@example.com"
    }

    with patch("firebase.firebase_admin.auth.verify_id_token", return_value=mock_token_payload):
        headers = {"Authorization": "Bearer fake_firebase_id_token_999"}
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "fb_me@example.com"
        assert data["provider"] == "firebase"
        assert "uid" in data

        captured = capsys.readouterr().out
        assert "Firebase token verified" in captured


def test_protected_routes_access_with_firebase_token():
    """
    Test protected routes (/ask, /dashboard/overview, /documents, /conversations) using Firebase token.
    """
    mock_token_payload = {
        "uid": "fb_uid_888",
        "email": "protected_fb@example.com"
    }

    with patch("firebase.firebase_admin.auth.verify_id_token", return_value=mock_token_payload):
        headers = {"Authorization": "Bearer fake_firebase_token_888"}

        # Protected /ask
        ask_resp = client.post("/ask", headers=headers)
        assert ask_resp.status_code == 200

        # Protected /documents
        docs_resp = client.get("/documents", headers=headers)
        assert docs_resp.status_code == 200

        # Protected /conversations
        conv_resp = client.get("/conversations", headers=headers)
        assert conv_resp.status_code == 200

        # Protected /dashboard/overview
        dash_resp = client.get("/dashboard/overview", headers=headers)
        assert dash_resp.status_code == 200


def test_invalid_and_expired_token_handling():
    """
    Test error handling for invalid and expired tokens.
    """
    with patch("firebase.firebase_admin.auth.verify_id_token", side_effect=ValueError("Invalid token")):
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 401

    with patch("firebase.firebase_admin.auth.verify_id_token", side_effect=ValueError("Expired token")):
        headers = {"Authorization": "Bearer expired_token"}
        response = client.get("/auth/me", headers=headers)
        assert response.status_code == 401


def test_firebase_auth_status_endpoint():
    """
    Test GET /auth/status endpoint returns authenticated status, uid, email, provider.
    """
    mock_token_payload = {
        "uid": "status_user_777",
        "email": "status@example.com"
    }
    with patch("firebase.firebase_admin.auth.verify_id_token", return_value=mock_token_payload):
        headers = {"Authorization": "Bearer valid_status_token"}
        response = client.get("/auth/status", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["authenticated"] is True
        assert data["email"] == "status@example.com"
        assert data["provider"] == "firebase"
        assert "uid" in data

