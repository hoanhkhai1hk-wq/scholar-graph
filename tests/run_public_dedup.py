"""公开等价物、非官方 pdf/ 文件: v7 then v1, raw uploads and public-fetch control."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.arxiv_fetch import ArxivClient
from scholar_graph.errors import PipelineError
from scholar_graph.validation import ContractGate
from public_pdf_support import prepare, header, save, file_info, upload, read, parsed_details, Measure


def comparison(client, pid):
    return {"decision": read(client, f"/api/v1/papers/{pid}/dedup-decision"),
            "diff": read(client, f"/api/v1/papers/{pid}/diff-summary")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = prepare(args.output_root)
    result = header("dedup-v7-then-v1")
    result.update(sources=[], raw_uploads=[], fetch_controls=[])
    public = ArxivClient(ContractGate())
    inputs = root / "inputs"
    inputs.mkdir()
    for version in ("v7", "v1"):
        identity = "1706.03762" + version
        source = {"scope": result["scope"], "arxiv_id": identity, "url": "https://arxiv.org/pdf/" + identity}
        try:
            try:
                source["metadata"] = public.metadata(reference={"arxiv_id": identity})
            except PipelineError as error:
                source["metadata_error"] = error.envelope()
            raw = public.pdf({"arxiv_id": identity})
            path = inputs / ("attention-" + version + ".pdf")
            path.write_bytes(raw)
            source.update(file_info(path))
        except PipelineError as error:
            source["download_error"] = error.envelope()
        result["sources"].append(source)
        save(args.report, result)
    app = create_app(data_dir=root / "raw-records")
    client = TestClient(app)
    for source in result["sources"]:
        if "file" not in source:
            continue
        value = upload(client, Path(source["file"]))
        value["source_arxiv_version"] = source["arxiv_id"]
        value["parsed"] = parsed_details(client, app.state.repository.root, value)
        if value["http_status"] == 201:
            value["comparison"] = comparison(client, value["response"]["id"])
        result["raw_uploads"].append(value)
        save(args.report, result)
    # Separate fresh store: real public endpoint, no injected identities or mock engines.
    control = TestClient(create_app(data_dir=root / "fetch-records"))
    example = json.loads((ROOT / "contracts/reference-entry.v1.example.json").read_text(encoding="utf-8"))
    for version in ("v7", "v1"):
        reference = {**example, "arxiv_id": "1706.03762" + version, "doi": None}
        with Measure() as meter:
            response = control.post("/api/v1/retrieval/fetch", json={"reference": reference})
        value = {"arxiv_id": reference["arxiv_id"], "http_status": response.status_code,
                 "response": response.json(), "measurement": meter.result}
        if response.status_code == 200 and response.json()["succeeded"]:
            value["comparison"] = comparison(control, response.json()["paper"]["id"])
        result["fetch_controls"].append(value)
        save(args.report, result)
    result["conclusion"] = {
        "upload_warning_field_exists": False,
        "semantic_dedup_or_version_quality_ranking_implemented": False,
        "note": "原始上传只返回PaperMeta；是否生成裁决以实际GET响应为准。精确身份匹配与词频Dice不等于向量语义去重。new_paper_id指后入库版本，本例是v1；keep_new会保留v1，不能误称保留v7。"}
    save(args.report, result)
    print(json.dumps({"scope": result["scope"], "raw_upload_http": [v["http_status"] for v in result["raw_uploads"]],
        "raw_decision_http": [v.get("comparison", {}).get("decision", {}).get("http_status") for v in result["raw_uploads"]],
        "fetch_succeeded": [v["response"].get("succeeded") for v in result["fetch_controls"]], "report": str(args.report)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
