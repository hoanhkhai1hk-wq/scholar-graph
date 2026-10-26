"""One entry point for local hooks, CI, acceptance and deployment regressions."""
import argparse
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('layer', choices=('fast', 'full'))
    parser.add_argument('--junit', type=Path)
    parser.add_argument('--corpus-dir', type=Path)
    parser.add_argument('--no-key', action='store_true')
    args = parser.parse_args()
    run = ROOT/'data/regression'/uuid4().hex
    run.mkdir(parents=True)
    junit = (args.junit or run/'junit.xml').resolve()
    junit.parent.mkdir(parents=True, exist_ok=True)
    command = [sys.executable, '-m', 'pytest', 'tests', '-q', '--layer', args.layer,
               '--basetemp', str(run/'temp'), '--junitxml', str(junit)]
    if args.layer == 'full':
        command += ['--run-ocr', '--run-real-model', '--run-vector', '--run-longbook']
        if args.corpus_dir:
            command += ['--corpus-dir', str(args.corpus_dir.resolve())]
    env = dict(os.environ)
    if args.no_key or args.layer == 'fast':
        for name in list(env):
            if any(part in name.upper() for part in ('API_KEY', 'TOKEN', 'SECRET', 'PASSWORD')):
                env.pop(name)
        env.pop('DEEPSEEK_MODEL', None)
    env.update(SCHOLAR_GRAPH_TRACKING_ENABLED='false', PYTHONIOENCODING='utf-8')
    if args.layer=='full':
        env.setdefault('SCHOLAR_GRAPH_OCR_CACHE_DIR',str(ROOT/'data/paddle-models'))
        # Public download/initialization has a separate bounded preparation stage;
        # actual inference still runs in every real OCR test with normal limits.
        prepared=subprocess.run([sys.executable,'backend/prepare_ocr_models.py'],cwd=ROOT,env=env)
        if prepared.returncode:
            return prepared.returncode
    return subprocess.run(command, cwd=ROOT, env=env).returncode


if __name__ == '__main__':
    raise SystemExit(main())
