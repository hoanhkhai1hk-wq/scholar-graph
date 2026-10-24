import pytest
from scholar_graph.api_repository import ApiRepository
from scholar_graph.validation import ContractGate
from scholar_graph.retrieval import SearchService, lexical_ranking, fuse_ranks, VectorUnavailable
from scholar_graph.errors import PipelineError
from graph_samples import graph_bundles


@pytest.fixture
def repository(tmp_path):
    repo = ApiRepository(tmp_path, ContractGate())
    for bundle in graph_bundles():
        repo.store.paper(bundle)
    return repo


def test_lexical_ranking_returns_real_anchored_chunks(repository):
    items, status = SearchService(repository).search("document-level extraction")
    assert items and status["method"] == "lexical"
    assert items[0]["relevance"] >= items[-1]["relevance"] > 0
    for item in items:
        assert set(item["anchor"]) == {"paper_id", "page_number", "section", "chunk_id"}
        assert item["anchor"]["chunk_id"] == item["chunk"]["chunk_id"]


def test_no_results_and_empty_corpus_are_explicit(repository, tmp_path):
    assert SearchService(repository).search("zzzznonexistent")[1]["reason"] == "NO_MATCHING_CHUNKS"
    empty = ApiRepository(tmp_path / "empty", ContractGate())
    assert SearchService(empty).search("retrieval")[1]["reason"] == "EMPTY_CORPUS"


def test_dense_and_sparse_rank_fusion_has_known_order():
    ranked = fuse_ranks({"a": .9, "b": .8, "c": .1}, {"a": 0, "b": 5, "c": 2})
    assert [cid for cid, score in ranked] == ["b", "c", "a"]
    assert dict(ranked)["b"] == pytest.approx(.5 * 61 / 62 + .5)


def test_vector_failure_is_labelled_lexical_fallback(repository):
    class Missing:
        def search(self, *args):
            raise VectorUnavailable
    items, status = SearchService(repository, Missing()).search("cross-lingual transfer")
    assert items and status == {"method": "lexical", "vector_status": "UNAVAILABLE", "reason": "OK"}


@pytest.mark.parametrize("result", [[("fake", .5)], [("chunk-graph-a", float("nan"))], [("chunk-graph-a", 2)]])
def test_fake_vector_hits_cannot_escape_anchor_gate(repository, result):
    class Fake:
        def search(self, *args):
            return result
    with pytest.raises(PipelineError):
        SearchService(repository, Fake()).search("question")


def test_filter_and_minimum_do_not_fabricate_records(repository):
    items, status = SearchService(repository).search("cross-lingual", ["paper-graph-d"])
    assert items == []
    assert SearchService(repository).search("cross-lingual", minimum=1)[0] == []
