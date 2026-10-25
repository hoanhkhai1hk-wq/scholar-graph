"""官方 pdf/ 真文件修复后执行全量回归；回归本身仍使用既有自制样例。"""
import subprocess
import sys
import xml.etree.ElementTree as ET
from official_pdf_support import ROOT, SCOPE, prepare


def main():
    # Refuse reuse: pytest may clear basetemp, so keep it inside a new verified data root.
    root = prepare(ROOT / 'data/official-repair/regression')
    report = ROOT / 'tests/reports/official-pdf-repair-pytest.xml'
    command = [sys.executable, '-m', 'pytest', 'tests', '-q', '--run-ocr',
               '--basetemp', str(root / 'temp'), '--junitxml', str(report)]
    result = subprocess.run(command, cwd=ROOT, capture_output=True)
    (root / 'console.txt').write_bytes(result.stdout + result.stderr)
    print(result.stdout.decode('utf-8', errors='replace'))
    print(result.stderr.decode('utf-8', errors='replace'))
    if report.is_file():
        tree = ET.parse(report)
        for suite in tree.getroot().findall('testsuite'):
            properties = suite.find('properties')
            if properties is None:
                properties = ET.SubElement(suite, 'properties')
            ET.SubElement(properties, 'property', name='validation_scope', value=SCOPE)
            ET.SubElement(properties, 'property', name='regression_input', value='既有回归自制样例；不把回归通过当作官方三项业务通过。')
        # Add provenance properties only; do not change test totals, durations or results.
        tree.write(report, encoding='utf-8', xml_declaration=True)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
