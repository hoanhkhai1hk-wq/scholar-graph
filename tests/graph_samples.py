"""Self-made on-disk contract data, not official pdf/ cases or parsed real papers."""

import copy
import hashlib
from test_validation_status import example_bundle


def graph_bundles():
    bundles = []
    for letter, year, text in [
        ("a", 2024, "We build on the calibration study [1]."),
        ("b", 2020, "Resolved future direction: cross-lingual transfer.\nWe did not resolve document-level extraction.\nWe cite the original directions [1]."),
        ("c", 2018, "Future work: cross-lingual transfer.\nFuture work: document-level extraction.\nFuture work: robust noisy labels."),
        ("d", 2025, "An isolated synthetic paper with no references."),
    ]:
        bundle = example_bundle()
        pid = "paper-graph-" + letter
        bundle["paper_meta"].update(id=pid, title="Synthetic Graph Study " + letter.upper(), year=year,
            authors=["Demo Author"], doi="10.5555/graph-" + letter, arxiv_id=None,
            page_count=1, file_hash=hashlib.sha256(pid.encode()).hexdigest(), source="synthetic-graph-fixture")
        bundle["chunks"][0].update(chunk_id="chunk-graph-" + letter, paper_id=pid, page_number=1,
            text=text, section_path=["Future Work" if letter == "c" else "Main"],
            heading_1="Future Work" if letter == "c" else "Main", heading_2=None, heading_3=None)
        bundle["reference_entries"], bundle["citation_links"] = [], []
        bundles.append(bundle)
    for source, target in [(bundles[0], bundles[1]), (bundles[1], bundles[2])]:
        ref = copy.deepcopy(example_bundle()["reference_entries"][0])
        ref.update(ref_id="ref-" + source["paper_meta"]["id"], paper_id=source["paper_meta"]["id"], number=1,
            authors=target["paper_meta"]["authors"], year=target["paper_meta"]["year"],
            title=target["paper_meta"]["title"], doi=target["paper_meta"]["doi"], arxiv_id=None)
        source["reference_entries"] = [ref]
        source["citation_links"] = [{"schema_version": "1.0.0", "paper_id": source["paper_meta"]["id"],
            "citation_number": 1, "page_number": 1, "chunk_id": source["chunks"][0]["chunk_id"], "ref_id": ref["ref_id"]}]
    return bundles
