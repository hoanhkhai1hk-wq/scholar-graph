"""Local calibration on separate official PDFs, not the three acceptance pairs."""
import copy
import hashlib
import json
import os
import sys
from pathlib import Path
from itertools import combinations

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from scholar_graph.pipeline import Pipeline
from scholar_graph.semantic_vectors import BgePaperVectors, calibrate, cosine, REPRESENTATION
from scholar_graph.storage import write_json
from scholar_graph.vector_search import MODEL_REVISION


def main():
    root = ROOT / "data/semantic-dedup-calibration"
    samples = []
    sources = ["1607.06450v1.pdf", "1707.06347v2.pdf", "1910.02054v3.pdf", "2001.08361v1.pdf"]
    originals = []
    for n, name in enumerate(sources):
        pipeline = Pipeline(root / "records")
        bundle = pipeline.parse(ROOT / "pdf" / name)
        originals.append(bundle)
        samples.append(bundle)
        for label, modulus in (("calibration", 5), ("heldout", 7)):
            variant = copy.deepcopy(bundle)
            # Same actual paper, deterministic missing-block robustness challenge.
            variant["paper_meta"]["id"] += "-" + label
            variant["chunks"] = [c for i, c in enumerate(variant["chunks"]) if i % modulus != modulus - 1]
            samples.append(variant)
        print(json.dumps({"parsed": name, "chunks": len(bundle["chunks"])}), flush=True)
    encoder = BgePaperVectors(root, ROOT / "data/module-four-runtime/.venv/Scripts/python.exe", ROOT / "data/module-four-models/bge-m3", timeout=600)
    vectors = encoder.encode(samples)
    positives = []
    heldout = []
    for n, bundle in enumerate(originals):
        pid = bundle["paper_meta"]["id"]
        positives.append({"file": sources[n], "score": cosine(vectors[pid], vectors[pid + "-calibration"]), "label": "same_paper_missing_every_fifth_chunk"})
        heldout.append({"file": sources[n], "score": cosine(vectors[pid], vectors[pid + "-heldout"]), "label": "same_paper_missing_every_seventh_chunk"})
    negatives = [{"left": sources[i], "right": sources[j], "score": cosine(vectors[originals[i]["paper_meta"]["id"]], vectors[originals[j]["paper_meta"]["id"]])} for i, j in combinations(range(4), 2)]
    thresholds = calibrate([p["score"] for p in positives], [p["score"] for p in negatives])
    policy = {**thresholds, "model_revision": MODEL_REVISION, "representation": REPRESENTATION,
        "calibration_id": "official-separate-four-papers-drop5-v1", "calibration_files": sources}
    report = {"input_kind": "官方 pdf/ 真文件；四篇校准论文与三组验收输入分离；删块变体是明确的同论文人工扰动，不冒充不同版本PDF",
        "positive_pairs": positives, "negative_pairs": negatives, "heldout_positive_pairs": heldout,
        "policy": policy, "encoder": encoder.last_metadata,
        "source_sha256": {name: hashlib.sha256((ROOT / "pdf" / name).read_bytes()).hexdigest() for name in sources}}
    write_json(ROOT / "tests/reports/semantic-dedup-calibration.json", report)
    write_json(ROOT / "backend/scholar_graph/semantic_thresholds.json", policy)
    print(json.dumps({"thresholds": thresholds, "heldout_scores": [p["score"] for p in heldout]}))


if __name__ == "__main__":
    main()
