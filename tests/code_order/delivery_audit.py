"""Verify exact staged scope, real-secret absence and untouched prior work."""
import json
import subprocess
from common import ROOT, BASE, write, digest, configured_environment

CODE = ['.gitattributes', 'backend/scholar_graph/code_layout.py', 'backend/scholar_graph/pipeline.py',
        'backend/scholar_graph/translation.py', 'backend/scholar_graph/workspace.py', 'backend/scholar_graph/workspace_translation.py',
        'frontend/app/globals.css', 'frontend/components/BilingualPane.tsx', 'frontend/components/ReaderPane.tsx',
        'frontend/components/TranslatePanel.tsx', 'frontend/lib/types.ts', 'tests/regression_layers.py', 'tests/test_code_layout.py']

if __name__ == '__main__':
    allowed = set(CODE + ['test-records/代码阅读顺序修复报告.md'])
    allowed.update(str(p.relative_to(ROOT)).replace('\\', '/') for p in (ROOT / 'tests/code_order').iterdir() if p.is_file())
    allowed.update(str(p.relative_to(ROOT)).replace('\\', '/') for p in (ROOT / 'test-records/code-order-20261029').rglob('*') if p.is_file())
    before = json.loads((BASE / 'workspace-before.json').read_text(encoding='utf8'))
    for group in ['files', 'originals', 'frozen', 'old_evidence']:
        assert all((ROOT / name).is_file() and digest(ROOT / name) == sha for name, sha in before[group].items() if name not in CODE), group + ' changed'
    staged = subprocess.check_output(['git', 'diff', '--cached', '--name-only', '-z'], cwd=ROOT).decode().strip('\0').split('\0')
    assert set(staged) == allowed, {'missing': sorted(allowed - set(staged)), 'unexpected': sorted(set(staged) - allowed)}
    key = configured_environment()['DEEPSEEK_API_KEY'].encode()
    hashes = {}
    import hashlib
    for name in staged:
        assert not name.lower().endswith('.pdf') and not name.startswith('pdf/')
        value = subprocess.check_output(['git', 'show', ':' + name], cwd=ROOT)
        assert key not in value
        hashes[name] = hashlib.sha256(value).hexdigest()
    manifest = json.loads((ROOT / 'test-records/code-order-20261029/evidence-manifest.json').read_text(encoding='utf8'))
    assert all(hashes['test-records/code-order-20261029/' + name] == sha for name, sha in manifest.items())
    report = {'staged_files': len(staged), 'staged_pdf_files': 0, 'configured_key_found': False,
              'preexisting_files_unchanged': len(before['files']), 'original_pdfs_unchanged': len(before['originals']),
              'frozen_json_unchanged': len(before['frozen']), 'old_evidence_files_unchanged': len(before['old_evidence']),
              'manifest_verified': True, 'staged_sha256': hashes}
    write(BASE / 'delivery-audit.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'staged_sha256'}))
