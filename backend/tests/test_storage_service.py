import pytest
from firebase.storage_service import (
    upload_document,
    download_document,
    delete_document,
    get_signed_url,
    health_check,
    list_documents,
)


def test_storage_upload_download_delete_and_logging(capsys):
    user_id = "user_storage_101"
    doc_id = "doc_st_001"
    sample_content = b"%PDF-1.4 sample pdf content for storage test"

    # 1. Upload Test (Write & Log)
    upload_res = upload_document(
        user_id=user_id,
        doc_id=doc_id,
        file_bytes=sample_content,
        filename="test_contract.pdf"
    )
    assert upload_res["doc_id"] == doc_id
    assert "users/user_storage_101/documents/" in upload_res["storage_path"]
    captured = capsys.readouterr().out
    assert "Storage upload" in captured

    # 2. Signed URL Generation Test
    signed_url = get_signed_url(user_id=user_id, doc_id=doc_id, storage_path=upload_res["storage_path"])
    assert signed_url is not None
    assert "storage.googleapis.com" in signed_url or "http" in signed_url

    # 3. Download Test (Read & Log)
    downloaded = download_document(user_id=user_id, doc_id=doc_id, filename="test_contract.pdf")
    assert downloaded == sample_content
    captured = capsys.readouterr().out
    assert "Storage download" in captured

    # 4. Delete Test (Delete & Log)
    deleted = delete_document(user_id=user_id, doc_id=doc_id, filename="test_contract.pdf")
    assert deleted is True
    captured = capsys.readouterr().out
    assert "Storage delete" in captured

    with pytest.raises(FileNotFoundError):
        download_document(user_id=user_id, doc_id=doc_id, filename="test_contract.pdf")


def test_storage_user_isolation():
    user_a = "user_alpha_99"
    user_b = "user_beta_88"
    content_a = b"Secret data for User A"
    content_b = b"Secret data for User B"

    upload_document(user_id=user_a, doc_id="doc_a", file_bytes=content_a)
    upload_document(user_id=user_b, doc_id="doc_b", file_bytes=content_b)

    # User A can download User A's file
    data_a = download_document(user_id=user_a, doc_id="doc_a")
    assert data_a == content_a

    # User A cannot download User B's file
    with pytest.raises(FileNotFoundError):
        download_document(user_id=user_a, doc_id="doc_b")


def test_storage_health_check(capsys):
    status = health_check()
    assert status["storage"] is True
    assert "files_count" in status
    captured = capsys.readouterr().out
    assert "Storage health check" in captured
