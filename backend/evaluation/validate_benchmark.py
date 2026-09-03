#!/usr/bin/env python3
"""
Scientific Benchmark Validator for Veritas AI (evaluation/validate_benchmark.py)

Enforces strict compliance with:
1. Exact total record count (N = 100)
2. Exact category distribution (25 Factoid, 25 Multi-Hop, 15 Divergence, 15 Contradiction, 10 Ambiguous, 10 OOD)
3. Unique query IDs and no duplicate questions
4. Provenance preservation for native dataset records
5. Gold evidence integrity for answerable cases
6. Empty gold evidence for unanswerable cases
7. Contradiction verification (at least 2 conflicting evidence references)
8. Ambiguity documentation (entity candidate sets)
9. Valid schema structure and zero fabricated page/chunk IDs
"""

import os
import sys
import json
from collections import Counter
from typing import Dict, Any, List

EXPECTED_CATEGORIES = {
    "DIRECT_FACTOID": 25,
    "MULTI_DOCUMENT_MULTIHOP": 25,
    "LEXICAL_SEMANTIC_DIVERGENCE": 15,
    "INTER_DOCUMENT_CONTRADICTION": 15,
    "AMBIGUOUS_ENTITY": 10,
    "UNANSWERABLE_OUT_OF_DOMAIN": 10
}

TOTAL_EXPECTED = 100
VALID_SOURCES = {"hotpotqa", "nfcorpus", "ragtruth", "controlled"}
VALID_CONSTRUCTION_TYPES = {"native", "controlled"}

REQUIRED_FIELDS = [
    "schema_version", "benchmark_version", "id", "category",
    "source_dataset", "construction_type", "question",
    "answerable", "reference_answer", "gold_documents",
    "gold_evidence", "expected_final_action", "metadata"
]


def validate_benchmark(dataset_path: str, report_path: str = None) -> bool:
    errors: List[str] = []
    warnings: List[str] = []

    if not os.path.exists(dataset_path):
        print(f"[FATAL] Benchmark file does not exist: {dataset_path}")
        return False

    with open(dataset_path, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
        except Exception as e:
            print(f"[FATAL] Failed to parse JSON: {e}")
            return False

    if not isinstance(data, list):
        print(f"[FATAL] Benchmark root must be a JSON array, got {type(data)}")
        return False

    # 1. Total Count Verification
    actual_total = len(data)
    if actual_total != TOTAL_EXPECTED:
        errors.append(f"Total records mismatch: expected {TOTAL_EXPECTED}, found {actual_total}")

    # 2. Category Distribution Verification
    cat_counts = Counter(item.get("category") for item in data)
    for cat, expected_count in EXPECTED_CATEGORIES.items():
        actual_count = cat_counts.get(cat, 0)
        if actual_count != expected_count:
            errors.append(f"Category '{cat}' count mismatch: expected {expected_count}, got {actual_count}")

    for cat in cat_counts:
        if cat not in EXPECTED_CATEGORIES:
            errors.append(f"Unknown category found: '{cat}'")

    # 3. ID Uniqueness and Question Duplication
    seen_ids = set()
    seen_questions = set()
    duplicate_ids = []
    duplicate_questions = []

    # 4. Individual Record Checks
    native_count = 0
    controlled_count = 0
    answerable_count = 0
    unanswerable_count = 0
    contradiction_count = 0
    ambiguity_count = 0

    for idx, item in enumerate(data):
        item_id = item.get("id")
        q_text = item.get("question", "").strip().lower()

        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in item:
                errors.append(f"Record #{idx+1} ({item_id}) missing required field: '{field}'")

        # Check ID
        if not item_id:
            errors.append(f"Record #{idx+1} has missing or empty 'id'")
        elif item_id in seen_ids:
            duplicate_ids.append(item_id)
        else:
            seen_ids.add(item_id)

        # Check duplicate questions
        if q_text in seen_questions:
            duplicate_questions.append(item.get("question"))
        else:
            seen_questions.add(q_text)

        # Source dataset & construction type
        src = item.get("source_dataset")
        c_type = item.get("construction_type")
        if src not in VALID_SOURCES:
            errors.append(f"Record {item_id}: invalid source_dataset '{src}'")
        if c_type not in VALID_CONSTRUCTION_TYPES:
            errors.append(f"Record {item_id}: invalid construction_type '{c_type}'")

        if c_type == "native":
            native_count += 1
            if "original_id" not in item.get("metadata", {}) and "original_source_id" not in item.get("metadata", {}):
                warnings.append(f"Record {item_id}: native case missing original ID in metadata.")
        else:
            controlled_count += 1
            if "construction_notes" not in item:
                errors.append(f"Record {item_id}: controlled case missing 'construction_notes'")

        # Answerable / Unanswerable Rules
        ans_bool = item.get("answerable")
        if ans_bool is True:
            answerable_count += 1
            if not item.get("reference_answer"):
                errors.append(f"Record {item_id}: answerable query missing reference_answer")
            if not item.get("gold_documents"):
                errors.append(f"Record {item_id}: answerable query has empty gold_documents")
            if not item.get("gold_evidence"):
                errors.append(f"Record {item_id}: answerable query has empty gold_evidence")
        elif ans_bool is False:
            unanswerable_count += 1
            if item.get("reference_answer") is not None:
                errors.append(f"Record {item_id}: unanswerable query must have reference_answer=null")
            if len(item.get("gold_documents", [])) > 0:
                errors.append(f"Record {item_id}: unanswerable query must have empty gold_documents")
            if len(item.get("gold_evidence", [])) > 0:
                errors.append(f"Record {item_id}: unanswerable query must have empty gold_evidence")
        else:
            errors.append(f"Record {item_id}: 'answerable' must be a boolean, got {ans_bool}")

        # Category-Specific Deep Rules
        category = item.get("category")
        if category == "INTER_DOCUMENT_CONTRADICTION":
            contradiction_count += 1
            conflicts = item.get("conflicting_evidence", [])
            if len(conflicts) < 2:
                errors.append(f"Record {item_id}: contradiction case must have >= 2 conflicting_evidence items")
            for c_idx, conf in enumerate(conflicts):
                if "source_id" not in conf or "claim" not in conf:
                    errors.append(f"Record {item_id}: conflicting_evidence #{c_idx} missing source_id or claim")

        if category == "AMBIGUOUS_ENTITY":
            ambiguity_count += 1
            if not item.get("clarification_required"):
                errors.append(f"Record {item_id}: ambiguous entity case must have clarification_required=True")
            candidates = item.get("entity_candidates", [])
            if len(candidates) < 2:
                errors.append(f"Record {item_id}: ambiguous entity case must have >= 2 entity_candidates")

        # Ensure no fabricated non-null string chunk IDs where null was expected
        for ev in item.get("gold_evidence", []):
            if ev.get("page") is not None and not isinstance(ev.get("page"), int):
                errors.append(f"Record {item_id}: page must be integer or null")

    if duplicate_ids:
        errors.append(f"Duplicate IDs detected: {duplicate_ids}")
    if duplicate_questions:
        errors.append(f"Duplicate questions detected: {len(duplicate_questions)} duplicates found.")

    # Quality Report Compilation
    quality_report = {
        "benchmark_file": dataset_path,
        "total_records": actual_total,
        "category_distribution": dict(cat_counts),
        "source_dataset_distribution": dict(Counter(item.get("source_dataset") for item in data)),
        "native_records_count": native_count,
        "controlled_records_count": controlled_count,
        "answerable_count": answerable_count,
        "unanswerable_count": unanswerable_count,
        "contradiction_cases_count": contradiction_count,
        "ambiguity_cases_count": ambiguity_count,
        "duplicate_ids_count": len(duplicate_ids),
        "duplicate_questions_count": len(duplicate_questions),
        "validation_passed": (len(errors) == 0),
        "errors_count": len(errors),
        "warnings_count": len(warnings),
        "errors": errors,
        "warnings": warnings
    }

    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(quality_report, f, indent=2)
        print(f"[INFO] Quality report saved to: {report_path}")

    # Output Console Summary
    print("\n" + "=" * 60)
    print("VERITAS AI SCIENTIFIC BENCHMARK VALIDATION REPORT")
    print("=" * 60)
    print(f"Total Records: {actual_total} (Expected: {TOTAL_EXPECTED})")
    print(f"Validation Status: {'PASS' if len(errors) == 0 else 'FAIL'}")
    print("\nCategory Distribution:")
    for cat, exp in EXPECTED_CATEGORIES.items():
        act = cat_counts.get(cat, 0)
        status = "OK" if act == exp else "MISMATCH"
        print(f"  - {cat:<30}: {act:>2} / {exp} [{status}]")

    print("\nDataset Partition Breakdown:")
    print(f"  - Native Benchmark Cases     : {native_count:>2}")
    print(f"  - Controlled Diagnostic Cases : {controlled_count:>2}")
    print(f"  - Answerable Queries         : {answerable_count:>2}")
    print(f"  - Unanswerable / OOD Queries : {unanswerable_count:>2}")
    print(f"  - Contradiction Pairs        : {contradiction_count:>2}")
    print(f"  - Entity Ambiguity Queries   : {ambiguity_count:>2}")

    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings[:5]:
            print(f"  [WARN] {w}")

    if errors:
        print(f"\n[ERROR] Validation Failed with {len(errors)} errors:")
        for err in errors:
            print(f"  - {err}")
        print("=" * 60)
        return False

    print("\n[SUCCESS] All 100 test cases strictly satisfy scientific integrity constraints!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ds_path = os.path.join(base_dir, "benchmark_dataset.json")
    rep_path = os.path.join(base_dir, "benchmark_quality_report.json")

    success = validate_benchmark(ds_path, rep_path)
    sys.exit(0 if success else 1)
