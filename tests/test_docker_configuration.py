"""Static guardrails; these do not stand in for an actual Docker build/run."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_default_services_do_not_require_private_corpus_or_host_credentials():
    value = yaml.safe_load((ROOT / 'docker-compose.yml').read_text(encoding='utf-8'))
    assert set(value['services']) == {'backend', 'frontend'}
    for service in value['services'].values():
        assert 'env_file' not in service and 'profiles' not in service
        assert not any('KEY' in name or 'TOKEN' in name for name in service.get('environment', {}))
        assert not any(isinstance(mount, dict) and mount.get('type') == 'bind' for mount in service.get('volumes', []))
        assert service['healthcheck']['test'][0] == 'CMD'
    assert value['services']['frontend']['environment']['NEXT_PUBLIC_API_BASE_URL'] == 'http://backend:8000'
    assert value['services']['backend']['environment']['SCHOLAR_GRAPH_QA_MODE'] == 'extractive'


def test_official_corpus_override_requires_existing_read_only_bind():
    value = yaml.safe_load((ROOT / 'services/docker-compose.acceptance.yml').read_text(encoding='utf-8'))
    mount = value['services']['backend']['volumes'][0]
    assert mount['target'] == '/corpus' and mount['read_only'] is True
    assert mount['type'] == 'bind' and mount['bind']['create_host_path'] is False
    assert ':?' in mount['source']


def test_build_inputs_exclude_host_packages_corpus_and_environment_files():
    patterns = (ROOT / '.dockerignore').read_text(encoding='utf-8').splitlines()
    assert {'pdf/', '**/*.pdf', '.env', '**/.env.*', '.git', '**/node_modules', '**/__pycache__',
            '**/.venv', '**/.next', 'data/', 'tests/reports/'}.issubset(patterns)
    dockerfile = (ROOT / 'Dockerfile').read_text(encoding='utf-8')
    assert "python -m pip install './backend[ocr,test]'" in dockerfile
    assert 'npm ci' in dockerfile and 'npm run build' in dockerfile
    assert not any(line.startswith(('COPY . ', 'ADD ', 'ARG DEEPSEEK', 'ENV DEEPSEEK')) for line in dockerfile.splitlines())
