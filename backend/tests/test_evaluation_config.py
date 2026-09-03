import os
import json
import pytest


@pytest.fixture
def eval_config():
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    config_path = os.path.join(root_dir, "config", "evaluation_config.json")
    assert os.path.exists(config_path), f"Config file not found at: {config_path}"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_config_top_level_keys(eval_config):
    required_keys = [
        "protocol_version", "benchmark_file", "k_values", "primary_k",
        "metrics", "baselines", "ablations", "experimental_control"
    ]
    for key in required_keys:
        assert key in eval_config, f"Missing required top-level key: {key}"


def test_k_values_configuration(eval_config):
    k_vals = eval_config.get("k_values")
    primary_k = eval_config.get("primary_k")
    assert isinstance(k_vals, list) and len(k_vals) >= 4
    assert 5 in k_vals
    assert primary_k == 5


def test_metrics_families(eval_config):
    metrics = eval_config.get("metrics", {})
    expected_families = [
        "retrieval", "answer_quality", "faithfulness", "citation",
        "self_correction", "contradiction_handling", "efficiency"
    ]
    for fam in expected_families:
        assert fam in metrics, f"Missing metric family: {fam}"
        assert len(metrics[fam]) > 0, f"Metric family {fam} is empty"


def test_baselines_definitions(eval_config):
    baselines = eval_config.get("baselines", {})
    expected_baselines = ["Dense_RAG", "Hybrid_RAG", "CRAG_Baseline", "Veritas_AI"]
    for b in expected_baselines:
        assert b in baselines, f"Missing baseline: {b}"
        assert "components" in baselines[b], f"Baseline {b} missing 'components'"


def test_ablations_definitions(eval_config):
    ablations = eval_config.get("ablations", {})
    expected_ablations = [
        "Ablation_No_Hybrid", "Ablation_No_Reranker", "Ablation_No_NLI",
        "Ablation_No_Diagnostic_Reformulation", "Ablation_No_Self_Correction",
        "Ablation_Max_Retries_0", "Ablation_Max_Retries_1", "Ablation_Max_Retries_3"
    ]
    for abl in expected_ablations:
        assert abl in ablations, f"Missing ablation: {abl}"
        assert "research_question" in ablations[abl], f"Ablation {abl} missing 'research_question'"


def test_experimental_control_settings(eval_config):
    ctrl = eval_config.get("experimental_control", {})
    assert ctrl.get("random_seed") == 42
    assert ctrl.get("max_retries") == 2
    assert ctrl.get("min_score_delta") == 0.05
    assert "statistical_analysis" in ctrl
    stat = ctrl["statistical_analysis"]
    assert stat.get("confidence_level") == 0.95
    assert stat.get("bootstrap_resamples") == 1000
