import os
import json
import pytest
from evaluation.validate_benchmark import validate_benchmark, EXPECTED_CATEGORIES, TOTAL_EXPECTED


@pytest.fixture
def benchmark_data():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ds_path = os.path.join(base_dir, "evaluation", "benchmark_dataset.json")
    assert os.path.exists(ds_path), f"Benchmark file not found: {ds_path}"
    with open(ds_path, "r", encoding="utf-8") as f:
        return json.load(f)


# 1. Total Count Verification
def test_total_count(benchmark_data):
    assert len(benchmark_data) == TOTAL_EXPECTED


# 2. Category Distribution Verification
def test_category_distribution(benchmark_data):
    cat_counts = {}
    for item in benchmark_data:
        cat = item.get("category")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    for cat, expected in EXPECTED_CATEGORIES.items():
        assert cat_counts.get(cat, 0) == expected, f"Category {cat} count {cat_counts.get(cat, 0)} != {expected}"


# 3. Duplicate ID and Duplicate Question Detection
def test_no_duplicate_ids_or_questions(benchmark_data):
    seen_ids = set()
    seen_questions = set()
    for item in benchmark_data:
        item_id = item.get("id")
        q_text = item.get("question", "").strip().lower()

        assert item_id not in seen_ids, f"Duplicate ID: {item_id}"
        assert q_text not in seen_questions, f"Duplicate question: {q_text}"

        seen_ids.add(item_id)
        seen_questions.add(q_text)


# 4. Schema Integrity and Field Requirements
def test_schema_fields(benchmark_data):
    required_fields = [
        "schema_version", "benchmark_version", "id", "category",
        "source_dataset", "construction_type", "question",
        "answerable", "reference_answer", "gold_documents",
        "gold_evidence", "expected_final_action", "metadata"
    ]
    for item in benchmark_data:
        for f in required_fields:
            assert f in item, f"Item {item.get('id')} missing field {f}"


# 5. Answerable vs Unanswerable Evidence Integrity
def test_evidence_integrity(benchmark_data):
    for item in benchmark_data:
        item_id = item.get("id")
        if item.get("answerable") is True:
            assert item.get("reference_answer") is not None, f"Item {item_id} answerable but missing reference_answer"
            assert len(item.get("gold_documents", [])) > 0, f"Item {item_id} answerable but empty gold_documents"
            assert len(item.get("gold_evidence", [])) > 0, f"Item {item_id} answerable but empty gold_evidence"
        else:
            assert item.get("reference_answer") is None, f"Item {item_id} unanswerable but has reference_answer"
            assert len(item.get("gold_documents", [])) == 0, f"Item {item_id} unanswerable but has gold_documents"
            assert len(item.get("gold_evidence", [])) == 0, f"Item {item_id} unanswerable but has gold_evidence"


# 6. Contradiction Case Annotations
def test_contradiction_annotations(benchmark_data):
    contra_items = [i for i in benchmark_data if i.get("category") == "INTER_DOCUMENT_CONTRADICTION"]
    assert len(contra_items) == 15
    for item in contra_items:
        conflicts = item.get("conflicting_evidence", [])
        assert len(conflicts) >= 2, f"Contradiction item {item.get('id')} has < 2 conflicting evidence references"
        for conf in conflicts:
            assert "source_id" in conf and "claim" in conf


# 7. Ambiguity Annotations
def test_ambiguity_annotations(benchmark_data):
    ambig_items = [i for i in benchmark_data if i.get("category") == "AMBIGUOUS_ENTITY"]
    assert len(ambig_items) == 10
    for item in ambig_items:
        assert item.get("clarification_required") is True
        assert len(item.get("entity_candidates", [])) >= 2


# 8. Full Validation Script Execution
def test_validator_script():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ds_path = os.path.join(base_dir, "evaluation", "benchmark_dataset.json")
    rep_path = os.path.join(base_dir, "evaluation", "benchmark_quality_report.json")
    passed = validate_benchmark(ds_path, rep_path)
    assert passed is True
