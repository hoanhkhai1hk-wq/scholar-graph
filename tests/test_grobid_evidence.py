"""Self-made TEI tests for evidence counting; these are NOT live service passes."""
import copy
import sys
import httpx
import pytest
from defusedxml import ElementTree as ET

from run_grobid_acceptance import tei_summary, command
from scholar_graph.grobid import GrobidClient
from scholar_graph.validation import ContractGate
from scholar_graph.errors import PipelineError
from scholar_graph.pipeline import Pipeline
from sample_pdfs import make_pdf
from test_validation_status import example_bundle


TEI = b'''<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><fileDesc>
<titleStmt><title>Self-made study</title></titleStmt><sourceDesc><biblStruct><analytic>
<author><persName><forename>Ada</forename><surname>Example</surname></persName>
<affiliation><orgName>Test Lab</orgName></affiliation></author>
<author><persName><forename>Bo</forename><surname>Example</surname></persName>
<affiliation><orgName>Test Lab</orgName></affiliation></author>
</analytic></biblStruct></sourceDesc></fileDesc><profileDesc><abstract><p>Self-made abstract.</p></abstract></profileDesc>
</teiHeader><text><body><div><head>Introduction</head><p>Evidence <ref type="bibr">[1]</ref>.</p>
<figure type="table"><head>Table caption is not a section</head><table><row><cell>1</cell></row></table></figure>
<formula>x = 1</formula></div></body><back><listBibl><biblStruct xml:id="b0">
<analytic><title>Prior study</title><author><persName>A. Writer</persName></author></analytic>
<monogr><title>Test Venue</title><imprint><date when="2024"/></imprint></monogr>
<note type="raw_reference">[1] Prior study. 2024.</note></biblStruct></listBibl></back></text></TEI>'''


def test_tei_counts_distinguish_header_authors_and_caption():
    result = tei_summary(TEI)
    assert result["counts"] == {"titles": 1, "authors": 2, "unique_institution_names": 1,
        "affiliation_elements": 2, "abstracts": 1, "section_heads": 1, "table_figures": 1,
        "table_elements": 1, "formulas": 1, "references": 1, "bibliography_markers": 1}
    assert result["samples"]["authors"] == ["Ada Example", "Bo Example"]
    assert result["reference_coverage"] == {"title": 1, "authors": 1, "year": 1, "venue": 1, "raw": 1}
    assert result["tables"] == [{"label": "", "head": "Table caption is not a section", "rows": 1, "cells": 1}]


def test_missing_tables_formula_refs_are_zero_not_filled():
    root = ET.fromstring(TEI)
    namespace = {"t": "http://www.tei-c.org/ns/1.0"}
    div = root.find("t:text/t:body/t:div", namespace)
    div.remove(div.find("t:figure", namespace))
    div.remove(div.find("t:formula", namespace))
    root.find("t:text/t:back", namespace).clear()
    result = tei_summary(ET.tostring(root))
    assert result["counts"]["references"] == result["counts"]["formulas"] == result["counts"]["table_figures"] == 0
    assert result["samples"]["formula"] is None and result["samples"]["table"] is None


@pytest.mark.parametrize("payload", [b"not XML", b"<root/>", b'<TEI xmlns="http://www.tei-c.org/ns/1.0"/>'])
def test_malformed_or_incomplete_response_cannot_count_as_success(payload):
    with pytest.raises((ValueError, ET.ParseError)):
        tei_summary(payload)


def test_external_entities_not_expanded():
    from defusedxml.common import DefusedXmlException
    with pytest.raises(DefusedXmlException):
        tei_summary(b'<!DOCTYPE TEI [<!ENTITY x SYSTEM "file:///no-file">]><TEI>&x;</TEI>')


def test_optional_mapper_preserves_chunks_and_file_identity():
    bundle = example_bundle()
    original = copy.deepcopy(bundle)
    result = GrobidClient("http://127.0.0.1:8070")._convert(bundle, ET.fromstring(TEI))
    assert bundle == original
    assert result["chunks"] == original["chunks"]
    for key in ("id", "file_hash", "page_count", "has_text_layer", "arxiv_id", "version"):
        assert result["paper_meta"][key] == original["paper_meta"][key]
    assert result["paper_meta"]["title"] == "Self-made study"
    assert result["reference_entries"][0]["title"] == "Prior study"
    ContractGate().bundle(result)


def test_docker_metadata_probe_decodes_utf8_on_windows():
    # Docker Compose's command abbreviation contains an ellipsis. Windows GBK
    # decoding previously lost the entire successful live evidence at final ps.
    result = command(sys.executable, "-c", "import sys; sys.stdout.buffer.write(chr(0x2026).encode('utf-8'))")
    assert result == {"exit_code": 0, "stdout": "…", "stderr": ""}


def test_empty_grobid_reference_fields_fail_before_publication(tmp_path):
    # Reproduce the real CRF response shape with a self-made TEI. This protects
    # the schema gate; it does not claim the existing converter has been fixed.
    root = ET.fromstring(TEI)
    namespace = {"t": "http://www.tei-c.org/ns/1.0"}
    ref = root.find(".//t:listBibl/t:biblStruct", namespace)
    ref.find("t:analytic/t:title", namespace).text = ""
    ref.find("t:monogr/t:title", namespace).text = ""
    client = GrobidClient("http://127.0.0.1:8070", transport=httpx.MockTransport(
        lambda request: httpx.Response(200, content=ET.tostring(root))))
    pipeline = Pipeline(tmp_path / "records", grobid=client)
    with pytest.raises(PipelineError, match="ReferenceEntry"):
        pipeline.parse(make_pdf(tmp_path / "self-made.pdf"))
    assert pipeline.last_job.current["status"] == "failed"
    assert pipeline.last_job.current["error_code"] == "VALIDATION_ERROR"
    assert not (pipeline.store.root / "papers").exists()
