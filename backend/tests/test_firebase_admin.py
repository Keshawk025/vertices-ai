import os
import pytest
from unittest.mock import patch, MagicMock

from firebase.firebase_admin import (
    initialize_firebase_admin,
    get_firestore_client,
    get_storage_bucket,
    verify_firebase_token,
    health_check,
    verify_connections,
)

def test_firebase_admin_initialization(capsys):
    """
    Test that initialize_firebase_admin initializes the app cleanly and logs output.
    """
    app = initialize_firebase_admin()
    assert app is not None
    
    verify_connections()
    captured = capsys.readouterr().out
    assert "Firebase initialized" in captured
    assert "Firestore connected" in captured
    assert "Storage connected" in captured
    assert "Authentication connected" in captured


def test_health_check():
    """
    Test health_check returns the expected status structure.
    """
    with patch("firebase.firebase_admin.get_firestore_client", return_value=MagicMock()), \
         patch("firebase.firebase_admin.get_storage_bucket", return_value=MagicMock()):
        health = health_check()
        assert health["firebase"] is True
        assert health["firestore"] is True
        assert health["storage"] is True
        assert health["auth"] is True


def test_token_verification():
    """
    Test token verification with valid and invalid token mocks.
    """
    mock_decoded_token = {
        "uid": "test_user_123",
        "email": "test@veritas-ai.com"
    }

    with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded_token):
        result = verify_firebase_token("valid_token_123")
        assert result["uid"] == "test_user_123"
        assert result["email"] == "test@veritas-ai.com"

    with patch("firebase_admin.auth.verify_id_token", side_effect=ValueError("Invalid token")):
        with pytest.raises(ValueError, match="Invalid token"):
            verify_firebase_token("invalid_token")


def test_firestore_and_storage_access():
    """
    Test Firestore client and Storage bucket access getters.
    """
    with patch("firebase_admin.firestore.client", return_value=MagicMock()) as mock_fs, \
         patch("firebase_admin.storage.bucket", return_value=MagicMock()) as mock_sb:
        db = get_firestore_client()
        assert db is not None
        mock_fs.assert_called_once()

        bucket = get_storage_bucket()
        assert bucket is not None
        mock_sb.assert_called_once()
