"""Parser-to-answer location provenance, including scans and legacy null boxes."""
import pytest

from scholar_graph.api_repository import ApiRepository
from scholar_graph.chunk_index import ChunkIndex
from scholar_graph.evidence_location import evidence_location
from scholar_graph.grounded_model import evidence_candidates
from scholar_graph.normalize import normalize
from scholar_graph.qa_evidence import retrieve
from scholar_graph.retrieval import SearchService
from scholar_graph.validation import ContractGate
from scholar_graph.workspace_research import checked_citation, validate_research
from test_validation_status import example_bundle
from test_workspace_research import material


@pytest.mark.parametrize("scanned", [False, True])
def test_parser_box_survives_freezing_indexing_retrieval_and_answer(tmp_path, scanned):
    paper = example_bundle()["paper_meta"]
    paper["has_text_layer"] = not scanned
    box = [.12, .26, .87, .31]
    page = {"page_idx": 0, "blocks": [{"type": "text", "content": "The study uses 12 samples.", "bbox": box}]}
    native = {"pages": [] if scanned else [page]}
    bundle = normalize(native, {"pages": [page]} if scanned else None, paper, [0] if scanned else [])
    expected = {"bbox": box, "coordinate_system": "page-normalized-top-left", "precision": "paragraph"}
    repo = ApiRepository(tmp_path, ContractGate())
    directory = repo.store.paper(bundle)
    bundle = repo.store.load(directory)
    index = ChunkIndex(tmp_path, paper["id"])
    index.append(bundle["chunks"])
    assert index.page(1, 10)["items"][0]["bbox"] == box
    candidates = evidence_candidates(bundle, "samples")
    strict = retrieve(bundle, "How many samples?")
    hits, _ = SearchService(repo).search("samples")
    assert candidates[0]["location"] == strict[0]["location"] == hits[0]["location"] == expected
    source = candidates[0]
    citation = checked_citation({"evidence_id": source["evidence_id"], "quote": source["quote"]},
                                {source["evidence_id"]: source}, [bundle], repo.gate)
    assert citation["location"] == expected
    # Old four-field anchors and frozen chunks remain exactly compatible.
    assert set(citation["anchor"]) == {"paper_id", "page_number", "section", "chunk_id"}
    assert repo.store.load(directory) == bundle


@pytest.mark.parametrize("box", [None, [], [0, 0, 0, .5], [.9, .2, .1, .3],
                                      [-.1, 0, .5, .5], [0, 0, 1.1, 1],
                                      [0, 0, float("nan"), 1], [True, 0, 1, 1]])
def test_missing_or_unusable_coordinates_never_invent_a_paragraph(box):
    assert evidence_location({"bbox": box}) == {
        "bbox": None, "coordinate_system": "page-normalized-top-left", "precision": "page"}


def test_location_is_a_snapshot_and_not_an_alias_to_frozen_coordinates():
    chunk = example_bundle()["chunks"][0]
    location = evidence_location(chunk)
    location["bbox"][0] = .99
    assert chunk["bbox"][0] == .1


def test_answer_coordinates_are_derived_from_authoritative_chunk_not_candidate_metadata():
    bundle = example_bundle()
    source = evidence_candidates(bundle, "samples")[0]
    source["location"] = {"bbox": [0, 0, 1, 1], "precision": "paragraph"}
    result = checked_citation({"evidence_id": source["evidence_id"], "quote": source["quote"]},
                             {source["evidence_id"]: source}, [bundle], ContractGate())
    assert result["location"] == evidence_location(bundle["chunks"][0])


def test_legacy_null_box_answer_and_calculation_operands_expose_page_fallback():
    bundle, evidence = material()
    bundle["chunks"][0]["bbox"] = None
    cited = {"evidence_id": "e1", "quote": evidence[0]["quote"]}
    value = {"refused": False, "paragraphs": [{"text": "当前28.4 BLEU，基线26.36 BLEU。",
             "kind": "answer", "citations": [cited]}],
             "calculations": [{"label": "提升", "operation": "subtract", "unit": "BLEU", "operands": [
                 {"label": "当前", "value": "28.4", **cited}, {"label": "基线", "value": "26.36", **cited}]}]}
    result = validate_research(value, evidence, [bundle], ContractGate(), "提升多少？")
    assert result["calculations"][0]["result"] == "2.04"
    for row in [*result["paragraphs"][0]["citations"], *result["calculations"][0]["operands"]]:
        assert row["location"]["bbox"] is None and row["location"]["precision"] == "page"
