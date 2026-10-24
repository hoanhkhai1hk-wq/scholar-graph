"""Structured extractive drafts; unverifiable requests never become invented prose."""

from copy import deepcopy

from .errors import PipelineError
from .frameworks import validate_outline
from .future_work import anchored_quote
from .retrieval import lexical_ranking

MISSING_POINT = "未在本章摘录材料中检出所需要点；不可验证，未补写结论。"


def assemble_review(bundles, framework, requirements, gate):
    validate_outline(framework, bundles, gate)
    by_id = {bundle["paper_meta"]["id"]: bundle for bundle in bundles}
    chapters = []
    for chapter in framework["chapters"]:
        def supported(point, requirement=None):
            anchor = point["anchor"]
            bundle = by_id[anchor["paper_id"]]
            chunk = next(chunk for chunk in bundle["chunks"] if chunk["chunk_id"] == anchor["chunk_id"])
            quote = anchored_quote(bundle, chunk, point["text"], gate)
            return {"text": point["text"], "status": "verified", "anchors": quote["anchors"],
                    "numeric_fact_check": quote["numeric_fact_check"], "requirement": requirement}
        points = [supported(point) for point in chapter["writing_points"]]
        # Rank only the already justified outline quotations: an excluded future direction
        # elsewhere in a shared Chunk cannot leak back into the future-work chapter.
        excerpts = [{"chunk_id": f"point-{index}", "text": point["text"]}
                    for index, point in enumerate(chapter["writing_points"])]
        for requirement in requirements:
            hits = lexical_ranking(excerpts, requirement)
            if hits:
                index = int(hits[0][0].removeprefix("point-"))
                points.append(supported(chapter["writing_points"][index], requirement))
            else:
                points.append({"text": MISSING_POINT, "status": "unverifiable", "anchors": [],
                               "numeric_fact_check": {"status": "unverifiable", "checks": []},
                               "requirement": requirement})
        chapters.append({"chapter_id": chapter["chapter_id"], "title": chapter["title"], "points": points})
    return {"framework": deepcopy(framework), "chapters": chapters, "mode": "extractive",
            "unverifiable_count": sum(point["status"] == "unverifiable" for chapter in chapters for point in chapter["points"])}


def validate_review(value, bundles, framework, requirements, gate):
    if value != assemble_review(bundles, framework, requirements, gate):
        raise PipelineError("VALIDATION_ERROR", "综述草稿含无来源论断、错误锚点或伪造核验状态。")


def generate_review(bundles, framework, requirements, gate):
    value = assemble_review(bundles, framework, requirements, gate)
    validate_review(value, bundles, framework, requirements, gate)
    return value
