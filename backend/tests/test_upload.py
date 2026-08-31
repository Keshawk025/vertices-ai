import os
import io
import pytest
from fastapi.testclient import TestClient
from main import app
from api.upload import STORAGE_DIR

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Setup: ensure storage dir exists
    os.makedirs(STORAGE_DIR, exist_ok=True)
    
    # Store initial files to clean up only new ones
    initial_files = set(os.listdir(STORAGE_DIR))
    
    yield
    
    # Teardown: remove files created during tests
    current_files = set(os.listdir(STORAGE_DIR))
    new_files = current_files - initial_files
    for file in new_files:
        os.remove(os.path.join(STORAGE_DIR, file))

def test_successful_upload():
    # Create a dummy PDF file
    file_content = b"%PDF-1.4\nTest PDF content"
    files = {"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")}
    
    response = client.post("/upload", files=files)
    
    assert response.status_code == 200
    data = response.json()
    assert "file_id" in data
    assert data["filename"] == "test.pdf"
    assert data["size"] == len(file_content)
    assert data["status"] == "uploaded"
    
    # Verify file was actually saved
    expected_filename = f"{data['file_id']}_test.pdf"
    assert expected_filename in os.listdir(STORAGE_DIR)
    
    with open(os.path.join(STORAGE_DIR, expected_filename), "rb") as f:
        saved_content = f.read()
    assert saved_content == file_content

def test_invalid_file_type():
    file_content = b"Not a PDF"
    files = {"file": ("test.txt", io.BytesIO(file_content), "text/plain")}
    
    response = client.post("/upload", files=files)
    
    assert response.status_code == 400
    assert response.json()["detail"] == "Only PDF files are accepted."

def test_file_size_exceeded():
    # Simulate a file larger than 20MB
    # Since generating 20MB in memory might be slow, we can mock or just create a 20.1 MB bytes object
    # It takes very little time in Python to do b"a" * (20 * 1024 * 1024 + 1)
    file_content = b"a" * (20 * 1024 * 1024 + 1)
    files = {"file": ("large.pdf", io.BytesIO(file_content), "application/pdf")}
    
    response = client.post("/upload", files=files)
    
    assert response.status_code == 413
    assert response.json()["detail"] == "File size exceeds the 20 MB limit."
