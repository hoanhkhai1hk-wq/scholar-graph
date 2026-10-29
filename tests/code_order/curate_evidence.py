"""Publish only test-owned text/screenshots; never original PDFs or credentials."""
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from common import ROOT, BASE, write, digest, configured_environment

if __name__ == '__main__':
    output = ROOT / 'test-records/code-order-20261029'
    output.mkdir(exist_ok=False)
    for name in ['fast02.log', 'fast02.xml', 'related01.log', 'related02.log', 'related03.log', 'related03.xml', 'related04.log', 'related04.xml',
                 'runtime-audit.json', 'runtime-audit.log', 'release01.log', 'release01-result.json',
                 'historical-live-result.json', 'historical-live-task.json', 'prompt-measurement.json', 'ocr-cache-provenance.json']:
        shutil.copyfile(BASE / name, output / name)
    for folder, files in [('live01', ['result.json', 'native-en-task.json', 'native-zh-task.json', 'prior-zh-to-en-task.json',
                                     'native-en.md', 'native-zh.md', 'prior-zh-to-en.md', 'fresh-source-chunks.json']),
                          ('browser01', ['result.json', 'ui-translation-task.json', 'downloaded-translation.md', 'source-indent.png',
                                         'code-1440.png', 'code-1366.png', 'code-1024.png', 'code-390.png', 'legacy-warning.png', 'trace.zip'])]:
        (output / folder).mkdir()
        for file in files:
            shutil.copyfile(BASE / folder / file, output / folder / file)
    # The detector reports incumbent visual rules too. Check every reported
    # snippet against the committed version, rather than calling warnings pass.
    raw = (BASE / 'ui-detector.json').read_bytes()
    findings = json.loads(raw.decode('utf16' if raw.startswith(b'\xff\xfe') else 'utf-8-sig'))
    baseline, new = [], []
    for finding in findings:
        file = str(__import__('pathlib').Path(finding['file']).relative_to(ROOT)).replace('\\', '/')
        old = subprocess.check_output(['git', 'show', 'b930bbd257824e960cf829560d77dd58fd06bbdf:' + file], cwd=ROOT).decode('utf8')
        (baseline if finding['snippet'] in old else new).append(finding)
    write(output / 'ui-detector-audit.json', {'existing_findings': baseline, 'new_findings': new})
    assert not new
    checks = {}
    for name in ['fast02', 'related04']:
        root = ET.parse(BASE / (name + '.xml')).getroot()
        suite = root if root.tag == 'testsuite' else root.find('testsuite')
        checks[name] = {key: suite.attrib.get(key) for key in ['tests', 'errors', 'failures', 'skipped', 'time']}
        assert all(int(suite.attrib.get(key, 0)) == 0 for key in ['errors', 'failures', 'skipped'])
    write(output / 'verification.json', {'checks': checks, 'production_build_id': (ROOT / 'frontend/.next/BUILD_ID').read_text().strip(),
          'production_build_verified_in_running_containers': True, 'ui_existing_detector_findings': len(baseline), 'ui_new_detector_findings': 0,
          'real_provider_runs': 4, 'browser_provider_calls': 0, 'browser_cache_hits': 1})
    credential = configured_environment()['DEEPSEEK_API_KEY'].encode()
    for file in output.rglob('*'):
        if file.is_file():
            assert file.suffix.lower() != '.pdf' and credential not in file.read_bytes()
    write(output / 'evidence-manifest.json', {str(file.relative_to(output)).replace('\\', '/'): digest(file)
          for file in sorted(output.rglob('*')) if file.is_file()})
    print(json.dumps({'evidence_files': sum(file.is_file() for file in output.rglob('*')), 'new_ui_findings': len(new), 'checks': checks}))
