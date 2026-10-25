"""One bounded task for Windows Task Scheduler/cron; --due enforces the interval."""

import argparse
import json
import os
from pathlib import Path

from .api_repository import ApiRepository
from .arxiv_fetch import ArxivFetcher
from .errors import PipelineError
from .tracking import TrackingService
from .validation import ContractGate


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=Path(os.environ.get("SCHOLAR_GRAPH_DATA_DIR", "data/module-one")))
    parser.add_argument("--paper-id", action="append")
    parser.add_argument("--due", action="store_true")
    parser.add_argument("--interval-seconds", type=int, default=86400)
    parser.add_argument("--max-candidates", type=int, default=5)
    parser.add_argument("--max-imports", type=int, default=2)
    args = parser.parse_args(argv)
    try:
        if not 60 <= args.interval_seconds <= 2592000 or not 1 <= args.max_candidates <= 20 or not 0 <= args.max_imports <= 5:
            raise PipelineError("VALIDATION_ERROR", "追踪间隔或批量上限不合法。")
        repo = ApiRepository(args.data_dir.resolve(), ContractGate())
        result = TrackingService(repo, ArxivFetcher(repo)).run(paper_ids=args.paper_id, force=not args.due,
            interval_seconds=args.interval_seconds, max_candidates=args.max_candidates, max_imports=args.max_imports)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False))
        return int(result.get("status") in {"failed", "partial"})
    except PipelineError as error:
        print(json.dumps(error.envelope(), ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
