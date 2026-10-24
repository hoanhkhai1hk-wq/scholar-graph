"""Local module-one commands. Stdout contains existing contract records only."""

import argparse
import json
import os
from pathlib import Path

from .adapters import LocalEngines
from .dedup import compare, human_decision
from .errors import PipelineError
from .grobid import GrobidClient
from .pipeline import Pipeline
from .storage import RecordStore
from .validation import ContractGate


def main(argv=None):
    parser = argparse.ArgumentParser(prog="scholar-graph")
    sub = parser.add_subparsers(dest="command", required=True)
    parse = sub.add_parser("parse", help="Parse a local PDF and publish four v1 record files.")
    parse.add_argument("pdf", type=Path)
    parse.add_argument("--data-dir", type=Path, default=Path("data/module-one"))
    parse.add_argument("--timeout", type=float, default=300)
    parse.add_argument("--ocr-language", default="en")
    parse.add_argument("--grobid-url", default=os.environ.get("GROBID_URL"))
    comparison = sub.add_parser("compare", help="Compare two validated paper directories.")
    comparison.add_argument("old", type=Path)
    comparison.add_argument("new", type=Path)
    comparison.add_argument("--data-dir", type=Path, default=Path("data/module-one"))
    comparison.add_argument("--human-choice", choices=("keep_new", "keep_old", "keep_both", "manual_review"))
    comparison.add_argument("--human-reason", default="")
    args = parser.parse_args(argv)
    gate = ContractGate()
    try:
        if args.command == "parse":
            if not 1 <= args.timeout <= 3600:
                raise PipelineError("VALIDATION_ERROR", "解析时限必须在 1 到 3600 秒之间。")
            grobid = GrobidClient(args.grobid_url) if args.grobid_url else None
            engines = LocalEngines(timeout=args.timeout, language=args.ocr_language,
                                   cache_dir=args.data_dir / "models")
            result = Pipeline(args.data_dir, gate=gate, engines=engines, grobid=grobid).parse(args.pdf)["paper_meta"]
        else:
            store = RecordStore(args.data_dir, gate)
            old, new = store.load(args.old), store.load(args.new)
            system, diff = compare(old, new, gate)
            human = human_decision(system, args.human_choice, args.human_reason, diff, [old, new], gate) if args.human_choice else None
            store.comparison(system, diff, [old, new], human=human)
            result = human if human is not None else system
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return 0
    except PipelineError as error:
        envelope = error.envelope()
        gate.error(envelope)
        print(json.dumps(envelope, ensure_ascii=False))
        return 1
    except Exception:
        envelope = PipelineError("INTERNAL_ERROR", "本地命令未完成。依赖异常内容未输出。").envelope()
        gate.error(envelope)
        print(json.dumps(envelope, ensure_ascii=False))
        return 1
