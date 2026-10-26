from types import SimpleNamespace
from pathlib import Path
from regression_layers import fast_case, FAST_FILES


def test_fast_layer_is_explicit_and_excludes_all_expensive_inference():
    assert 'test_full_layer_live.py' not in FAST_FILES
    assert 'test_parsing.py' not in FAST_FILES
    assert 'test_deepseek_live.py' not in FAST_FILES
    for marker in ('ocr', 'real_model', 'real_vector', 'longbook'):
        assert not fast_case(SimpleNamespace(path=Path('test_validation_status.py'), keywords={marker: True}))
    assert fast_case(SimpleNamespace(path=Path('test_reference_identity.py'), keywords={}))
