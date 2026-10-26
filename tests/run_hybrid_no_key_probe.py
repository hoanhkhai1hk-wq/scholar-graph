"""Actual local-vector QA and missing-vector fallback without any model key."""
import json
import os
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from fastapi.testclient import TestClient
from scholar_graph.api import create_app
from scholar_graph.storage import write_json


def main():
    if os.environ.get("DEEPSEEK_API_KEY"):
        raise RuntimeError("probe requires a credential-free child environment")
    os.environ["SCHOLAR_GRAPH_QA_MODE"] = "extractive"
    os.environ["SCHOLAR_GRAPH_QA_RETRIEVAL_MODE"] = "hybrid"
    ids = json.loads((ROOT / "data/real-model/sources.json").read_text(encoding="utf-8"))
    client = TestClient(create_app(data_dir=ROOT / "data/hybrid-retrieval-acceptance/records"))
    question = "基础网络借助什么加速卡完成学习？"
    response = client.post(f'/api/v1/papers/{ids["attention_id"]}/qa', json={"question": question})
    result = {"environment": "未设置模型Key", "scope": "官方pdf/真文件，无Key实际本地向量与摘录QA",
        "question": question, "http_status": response.status_code, "result": response.json(),
        "metadata": json.loads(unquote(response.headers.get("X-ScholarGraph-QA-Meta", "%7B%7D")))}
    os.environ["SCHOLAR_GRAPH_VECTOR_PYTHON"] = str(ROOT / "data/not-configured-python.exe")
    missing = client.post(f'/api/v1/papers/{ids["attention_id"]}/qa', json={"question": "How many samples?"})
    result["missing_vector"] = {"http_status": missing.status_code, "result": missing.json(),
        "metadata": json.loads(unquote(missing.headers.get("X-ScholarGraph-QA-Meta", "%7B%7D")))}
    write_json(ROOT / "tests/reports/hybrid-retrieval-no-key.json", result)
    print(json.dumps({"no_key_method": result["metadata"].get("method"), "refused": result["result"].get("refused"),
        "missing_vector_method": result["missing_vector"]["metadata"].get("method")}))


if __name__ == "__main__":
    main()
