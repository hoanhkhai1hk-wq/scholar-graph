import json
import subprocess

import pytest

from sample_pdfs import make_pdf
from scholar_graph.adapters import LocalEngines
from scholar_graph.cli import main
from scholar_graph.errors import PipelineError
from scholar_graph.validation import ContractGate


def test_cli_real_parse_and_comparison(tmp_path, capsys):
    output = tmp_path / "output"
    for version, samples in [("v1", 12), ("v7", 18)]:
        pdf = make_pdf(tmp_path / f"{version}.pdf", version=version, samples=samples)
        assert main(["parse", str(pdf), "--data-dir", str(output)]) == 0
        record = json.loads(capsys.readouterr().out)
        ContractGate().record("PaperMeta", record)
    paths = sorted((output / "papers").iterdir())
    assert main(["compare", str(paths[0]), str(paths[1]), "--data-dir", str(output)]) == 0
    record = json.loads(capsys.readouterr().out)
    ContractGate().record("DedupDecision", record)


def test_cli_failure_is_valid_error_envelope(tmp_path, capsys):
    assert main(["parse", str(tmp_path / "absent.pdf"), "--data-dir", str(tmp_path / "out")]) == 1
    error = json.loads(capsys.readouterr().out)
    ContractGate().error(error)
    assert error["error_code"] == "VALIDATION_ERROR"


def test_subprocess_credentials_and_exception_details_are_not_exposed(tmp_path, monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "synthetic-sentinel-never-a-real-key")
    def execute(command, **kwargs):
        assert "DEEPSEEK_API_KEY" not in kwargs["env"]
        assert kwargs["cwd"] == tmp_path
        raise subprocess.TimeoutExpired(command, 1, stderr=b"synthetic-sentinel-never-a-real-key")
    monkeypatch.setattr(subprocess, "run", execute)
    with pytest.raises(PipelineError) as caught:
        LocalEngines(cache_dir=tmp_path / "cache").text(tmp_path / "source.pdf")
    assert caught.value.code == "PARSE_FAILED"
    assert "synthetic-sentinel" not in json.dumps(caught.value.envelope())
