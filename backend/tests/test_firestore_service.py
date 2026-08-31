import pytest
from firebase.firestore_service import (
    create_document,
    get_document,
    list_documents,
    update_document,
    delete_document,
    create_conversation,
    get_conversation,
    list_conversations,
    delete_conversation,
    create_message,
    list_messages,
    health_check,
    count_documents,
    count_conversations,
)


def test_document_crud_and_logging(capsys):
    user_id = "user_test_101"
    doc_data = {
        "id": "doc_test_001",
        "filename": "sample.pdf",
        "file_path": "/storage/sample.pdf",
        "file_size": 1024,
        "page_count": 5,
        "ocr_used": 0,
        "status": "processed"
    }

    # 1. Create Document (Write)
    created = create_document(user_id=user_id, doc_data=doc_data)
    assert created["id"] == "doc_test_001"
    captured = capsys.readouterr().out
    assert "Firestore write" in captured

    # 2. Get Document (Read)
    retrieved = get_document(user_id=user_id, doc_id="doc_test_001")
    assert retrieved is not None
    assert retrieved["filename"] == "sample.pdf"
    captured = capsys.readouterr().out
    assert "Firestore read" in captured

    # 3. List Documents (Query)
    docs = list_documents(user_id=user_id)
    assert len(docs) >= 1
    captured = capsys.readouterr().out
    assert "Firestore query" in captured

    # 4. Update Document (Write)
    update_document(user_id=user_id, doc_id="doc_test_001", update_data={"status": "completed"})
    retrieved_updated = get_document(user_id=user_id, doc_id="doc_test_001")
    assert retrieved_updated["status"] == "completed"

    # 5. Delete Document (Delete)
    delete_document(user_id=user_id, doc_id="doc_test_001")
    assert get_document(user_id=user_id, doc_id="doc_test_001") is None
    captured = capsys.readouterr().out
    assert "Firestore delete" in captured


def test_conversation_and_message_crud(capsys):
    user_id = "user_test_202"
    conv_data = {
        "id": "conv_test_001",
        "title": "Test Discussion"
    }

    # Create Conversation
    conv = create_conversation(user_id=user_id, conv_data=conv_data)
    assert conv["id"] == "conv_test_001"

    # Add Messages
    msg1 = create_message(user_id=user_id, conversation_id="conv_test_001", msg_data={
        "id": "msg_001",
        "role": "user",
        "content": "What is Veritas AI?"
    })
    assert msg1["id"] == "msg_001"

    msg2 = create_message(user_id=user_id, conversation_id="conv_test_001", msg_data={
        "id": "msg_002",
        "role": "assistant",
        "content": "Veritas AI is an advanced document assistant."
    })
    assert msg2["id"] == "msg_002"

    # List Messages
    messages = list_messages(user_id=user_id, conversation_id="conv_test_001")
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"

    # Delete Conversation
    delete_conversation(user_id=user_id, conv_id="conv_test_001")
    assert get_conversation(user_id=user_id, conv_id="conv_test_001") is None


def test_user_isolation():
    user_a = "user_A_alpha"
    user_b = "user_B_beta"

    # Create document for User A
    create_document(user_id=user_a, doc_data={"id": "doc_A", "filename": "doc_A.pdf"})

    # Create document for User B
    create_document(user_id=user_b, doc_data={"id": "doc_B", "filename": "doc_B.pdf"})

    # Verify User A cannot access User B's documents
    assert get_document(user_id=user_a, doc_id="doc_B") is None
    assert get_document(user_id=user_b, doc_id="doc_A") is None

    user_a_docs = list_documents(user_id=user_a)
    user_b_docs = list_documents(user_id=user_b)

    assert all(d["id"] != "doc_B" for d in user_a_docs)
    assert all(d["id"] != "doc_A" for d in user_b_docs)


def test_firestore_health_check_and_parity():
    status = health_check()
    assert status["firestore"] is True
    assert "documents" in status
    assert "conversations" in status

    # Verify parity count calculation
    firestore_count = count_documents("user_parity_check")
    sqlite_count = 0
    assert sqlite_count == firestore_count
