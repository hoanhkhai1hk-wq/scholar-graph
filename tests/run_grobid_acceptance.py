"""Live GROBID/MinerU comparison on official pdf/ input; never uses an LLM.

Full TEI and complete bundles stay under ignored data/. Only bounded field samples
and measurements go into the committed report. A failed service is not a pass.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from uuid import uuid4

import httpx
from defusedxml import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from scholar_graph.adapters import LocalEngines
from scholar_graph.grobid import GrobidClient, NS
from scholar_graph.normalize import block_text
from scholar_graph.pipeline import Pipeline
from scholar_graph.validation import ContractGate


def words(node):
    """Display XML token boundaries; not a replacement for the production mapper."""
    return " ".join(" ".join(node.itertext()).split()) if node is not None else ""


def reference_fields(item):
    analytic = item.find("t:analytic/t:title", NS)
    monograph = item.find("t:monogr/t:title", NS)
    date = item.find(".//t:date", NS)
    return {
        "xml_id": item.get("{http://www.w3.org/XML/1998/namespace}id"),
        "title": words(analytic) or words(monograph),
        "authors": [words(x) for x in item.findall(".//t:author/t:persName", NS)],
        "venue": words(monograph),
        "year": (date.get("when") or words(date)) if date is not None else None,
        "raw": words(item.find("t:note[@type='raw_reference']", NS)),
    }


def tei_summary(payload):
    root = ET.fromstring(payload)
    if root.tag != "{http://www.tei-c.org/ns/1.0}TEI":
        raise ValueError("response is not TEI")
    header = root.find("t:teiHeader", NS)
    body = root.find("t:text/t:body", NS)
    if header is None or body is None:
        raise ValueError("TEI missing header or body")
    titles = header.findall(".//t:titleStmt/t:title", NS)
    people = header.findall(".//t:sourceDesc//t:analytic/t:author/t:persName", NS)
    institutions = sorted(set(filter(None, (words(x) for x in header.findall(".//t:affiliation/t:orgName", NS)))))
    affiliations = header.findall(".//t:affiliation", NS)
    abstracts = header.findall(".//t:abstract", NS)
    # Figure/table captions are also <head>; count section headings only under <div>.
    sections = body.findall(".//t:div/t:head", NS)
    tables = body.findall(".//t:figure[@type='table']", NS)
    formulas = body.findall(".//t:formula", NS)
    refs = root.findall(".//t:listBibl/t:biblStruct", NS)
    return {
        "counts": {"titles": len(titles), "authors": len(people),
                   "unique_institution_names": len(institutions), "affiliation_elements": len(affiliations),
                   "abstracts": len(abstracts), "section_heads": len(sections),
                   "table_figures": len(tables), "table_elements": len(body.findall(".//t:table", NS)),
                   "formulas": len(formulas), "references": len(refs),
                   "bibliography_markers": len(body.findall(".//t:ref[@type='bibr']", NS))},
        "samples": {"titles": [words(x) for x in titles], "authors": [words(x) for x in people],
                    "institutions": institutions,
                    "affiliation": words(affiliations[0]) if affiliations else None,
                    "abstract": words(abstracts[0]) if abstracts else None,
                    "section_heads": [words(x) for x in sections],
                    "table": words(tables[0])[:1600] if tables else None,
                    "table_xml": ET.tostring(tables[0], encoding="unicode")[:2600] if tables else None,
                    "formula": words(formulas[0]) if formulas else None,
                    "formula_xml": ET.tostring(formulas[0], encoding="unicode") if formulas else None,
                    "references": [reference_fields(x) for x in refs[:2]]},
        "reference_coverage": {key: sum(bool(reference_fields(x)[key]) for x in refs)
                               for key in ("title", "authors", "year", "venue", "raw")},
        "tables": [{"label": words(x.find("t:label", NS)), "head": words(x.find("t:head", NS)),
                    "rows": len(x.findall(".//t:row", NS)), "cells": len(x.findall(".//t:cell", NS))}
                   for x in tables],
        "tei_sha256": hashlib.sha256(payload).hexdigest(), "tei_bytes": len(payload),
    }


def bundle_summary(bundle):
    paper, chunks, refs = bundle["paper_meta"], bundle["chunks"], bundle["reference_entries"]
    def sample(kind):
        found = next((x for x in chunks if x["type"] == kind), None)
        return ({key: found[key] for key in ("chunk_id", "page_number", "section_path", "type", "bbox")} |
                {"text": found["text"][:2000]}) if found else None
    return {"paper_meta": paper, "counts": {"titles": int(bool(paper["title"])), "authors": len(paper["authors"]),
                "institutions": len(paper["institutions"]), "abstracts": int(bool(paper["abstract"])),
                "chunks": len(chunks), "types": dict(Counter(x["type"] for x in chunks)),
                "chunks_with_bbox": sum(x["bbox"] is not None for x in chunks),
                "distinct_section_paths": len(set(tuple(x["section_path"]) for x in chunks if x["section_path"])),
                "references": len(refs), "citation_links": len(bundle["citation_links"])},
            "reference_coverage": {key: sum(bool(x[key]) for x in refs) for key in ("title", "authors", "year", "venue", "doi")},
            "samples": {"table": sample("table"), "formula": sample("formula"),
                        "first_page_chunks": [{"chunk_id": x["chunk_id"], "text": x["text"][:1800]}
                                              for x in chunks if x["page_number"] == 1][:9],
                        "abstract_chunks": [{"chunk_id": x["chunk_id"], "page_number": x["page_number"], "text": x["text"][:1800]}
                                            for x in chunks if x["section_path"] == ["Abstract"]][:2],
                        "references": refs[:2]}}


class MeasuredEngines(LocalEngines):
    def text(self, pdf, *, timeout=None):
        started = time.perf_counter()
        result = super().text(pdf, timeout=timeout)
        self.elapsed = time.perf_counter() - started
        blocks = [x for p in result["pages"] for x in p.get("blocks", [])]
        self.native_summary = {"schema": result["schema"], "page_count": len(result["pages"]),
            "block_types": dict(Counter(x.get("type", "text") for x in blocks)),
            "formula_samples": [json.dumps(x, ensure_ascii=False)[:2400] for x in blocks
                                if x.get("type") in {"equation", "formula"}][:2],
            "formulas_with_text": sum(bool(block_text(x.get("content")).strip()) for x in blocks
                                      if x.get("type") in {"equation", "formula"}),
            "heading_samples": [block_text(x.get("content")) for x in blocks
                                if x.get("type") in {"doc_title", "title", "paragraph_title", "section_title"}][:45]}
        return result


class MeasuredGrobid(GrobidClient):
    """Runs the actual production HTTP client. Only measures wall time."""
    def enrich(self, bundle, pdf_bytes):
        started = time.perf_counter()
        value = super().enrich(bundle, pdf_bytes)
        self.elapsed = time.perf_counter() - started
        gate = ContractGate()
        self.reference_validation_errors = [
            {"reference_number": ref["number"], "path": list(error.path),
             "validator": error.validator, "message": error.message}
            for ref in value["reference_entries"]
            for error in gate.validators["ReferenceEntry"].iter_errors(ref)]
        return value


def command(*args):
    # Whitelisted callers use only version/digest/state, never inspect environment.
    value = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", timeout=30, cwd=ROOT)
    return {"exit_code": value.returncode, "stdout": value.stdout.strip(), "stderr": value.stderr.strip()}


def save(path, data):
    raw = json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key and key in raw:
        raise ValueError("credential detected in evidence; not written")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(raw, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=ROOT / "pdf/1706.03762v7.pdf")
    parser.add_argument("--url", default="http://127.0.0.1:8070")
    parser.add_argument("--timeout", type=float, default=300)
    args = parser.parse_args()
    # Disables unrelated model/vector features; never reads a credential file.
    os.environ["SCHOLAR_GRAPH_DEDUP_MODE"] = "off"
    os.environ["SCHOLAR_GRAPH_QA_MODE"] = "extractive"
    folder = ROOT / "data/grobid-integration" / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8])
    folder.mkdir(parents=True)
    output = ROOT / "tests/reports/grobid-integration-live.json"
    source = args.pdf.resolve(strict=True)
    raw = source.read_bytes()
    report = {"scope": "官方 pdf/ 真文件；本地 MinerU 与真实 GROBID 容器；不调用模型 API",
        "started_utc": datetime.now(timezone.utc).isoformat(), "revision": command("git", "rev-parse", "HEAD")["stdout"],
        "input": {"filename": source.name, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()},
        "versions": {name: importlib.metadata.version(name) for name in ("mineru", "httpx", "pypdf")},
        "local_artifacts": str(folder.relative_to(ROOT)), "passed": False,
        "service_evidence_passed": False, "production_pipeline_passed": False}
    engines = MeasuredEngines(cache_dir=folder / "models")
    pipeline = Pipeline(folder / "mineru-only", engines=engines)
    started = time.perf_counter()
    bundle = pipeline.parse(source)
    ContractGate().bundle(bundle)
    report["mineru"] = {"elapsed_seconds": round(time.perf_counter() - started, 6),
        "engine_seconds": round(engines.elapsed, 6), "native": engines.native_summary,
        "status": pipeline.last_job.current, "schema_and_anchor_gate": "passed", **bundle_summary(bundle)}
    save(output, report)
    stage = "service"
    try:
        with httpx.Client(timeout=args.timeout, trust_env=False) as client:
            checks = {}
            for name in ("isalive", "version"):
                response = client.get(args.url.rstrip("/") + "/api/" + name)
                checks[name] = {"status": response.status_code, "body": response.text[:200]}
                response.raise_for_status()
            form = {"consolidateHeader": "0", "consolidateCitations": "0", "consolidateFunders": "0",
                    "includeRawCitations": "1", "includeRawAffiliations": "1", "generateIDs": "1",
                    "teiCoordinates": ["persName", "figure", "ref", "biblStruct", "formula", "head", "p"]}
            started = time.perf_counter()
            response = client.post(args.url.rstrip("/") + "/api/processFulltextDocument", data=form,
                files={"input": (source.name, raw, "application/pdf")}, headers={"Accept": "application/xml"})
            elapsed = time.perf_counter() - started
            response.raise_for_status()
            if len(response.content) > 10 * 1024 * 1024:
                raise ValueError("oversized TEI")
            summary = tei_summary(response.content)
            (folder / "attention.tei.xml").write_bytes(response.content)
            report["grobid"] = {"status": response.status_code, "elapsed_seconds": round(elapsed, 6),
                                "health_checks": checks, "request_parameters": form, **summary}
            report["service_evidence_passed"] = all(summary["counts"][key] > 0 for key in
                ("titles", "authors", "unique_institution_names", "abstracts", "section_heads", "table_figures", "formulas", "references"))
            save(output, report)
        # A SECOND fresh record store forces a real HTTP call in the opt-in
        # production Pipeline. No cached MinerU records or mocked TEI are used.
        grobid = MeasuredGrobid(args.url, timeout=args.timeout)
        opted_in = Pipeline(folder / "mineru-with-grobid", grobid=grobid)
        stage = "optional_pipeline"
        started = time.perf_counter()
        enriched = opted_in.parse(source)
        ContractGate().bundle(enriched)
        report["optional_pipeline"] = {"elapsed_seconds": round(time.perf_counter() - started, 6),
            "grobid_http_seconds": round(grobid.elapsed, 6), "schema_and_anchor_gate": "passed",
            "chunks_unchanged": enriched["chunks"] == bundle["chunks"],
            "status": opted_in.last_job.current, **bundle_summary(enriched)}
        report["production_pipeline_passed"] = report["optional_pipeline"]["chunks_unchanged"]
        report["passed"] = report["service_evidence_passed"] and report["production_pipeline_passed"]
        save(output, report)
    except Exception as error:
        # GROBID is a keyless local service. Retain the actual transport/service
        # failure, without dumping a response/PDF body or process environment.
        report["grobid_error"] = {"stage": stage, "type": type(error).__name__, "message": str(error)[:1500]}
        if stage == "optional_pipeline":
            paper_root = opted_in.store.root / "papers"
            report["optional_pipeline"] = {"elapsed_seconds": round(time.perf_counter() - started, 6),
                "grobid_http_seconds": round(grobid.elapsed, 6) if hasattr(grobid, "elapsed") else None,
                "schema_and_anchor_gate": "failed", "chunks_unchanged": None,
                "status": opted_in.last_job.current, "status_history": opted_in.last_job.history,
                "published_paper_groups": len(list(paper_root.iterdir())) if paper_root.exists() else 0,
                "reference_validation_errors": getattr(grobid, "reference_validation_errors", [])}
    report["docker"] = {"version": command("docker", "version", "--format", "{{.Server.Version}}"),
        "service": command("docker", "compose", "-f", "services/docker-compose.grobid.yml", "-p", "scholar-graph-grobid", "ps", "--format", "json"),
        "image": command("docker", "image", "inspect", "grobid/grobid:0.9.1-crf", "--format", '{{json .RepoDigests}} {{.Id}} {{.Size}}')}
    report["finished_utc"] = datetime.now(timezone.utc).isoformat()
    save(output, report)
    print(json.dumps({"passed": report["passed"], "service_evidence_passed": report["service_evidence_passed"],
                      "production_pipeline_passed": report["production_pipeline_passed"], "report": str(output.relative_to(ROOT)),
                      "mineru_chunks": len(bundle["chunks"]),
                      "grobid": report.get("grobid", {}).get("counts", report.get("grobid_error"))}, ensure_ascii=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
