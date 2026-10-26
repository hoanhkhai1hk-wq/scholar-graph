"""Explicit fast allowlist: deterministic records/transports, no inference or OCR."""
FAST_FILES = frozenset({
    'test_validation_status.py', 'test_graph_contracts.py', 'test_framework_contract.py',
    'test_citation_graph.py', 'test_reference_identity.py', 'test_graph_identity_evidence.py',
    'test_future_work.py', 'test_frameworks.py', 'test_api_transport.py', 'test_api_read.py',
    'test_docker_configuration.py', 'test_tracking_scheduler.py', 'test_citation_cleanup.py',
    'test_recommendations.py', 'test_recommendation_feedback.py', 'test_regression_layers.py',
    'test_grobid_default_path.py',
})


def fast_case(item):
    return item.path.name in FAST_FILES and not {'ocr', 'real_model', 'real_vector', 'longbook'} & set(item.keywords)
