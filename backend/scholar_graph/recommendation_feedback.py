"""Persisted explicit local profiles; transparent signed topic similarity."""

import copy

from .tracking import topic_terms
from .tracking_state import TrackingState, operation_lock, utc_now
from .errors import PipelineError

FEEDBACK_FORMULA = "score = clamp(base_score + 50 * mean(vote * Jaccard(title_topics(candidate), title_topics(voted_paper))), 0, 100); empty profile adds 0"


def rerank(repository, items, votes):
    if not votes:
        return items
    result = copy.deepcopy(items)
    profiles = [(vote, repository.paper(vote["paper_id"])["paper_meta"]) for vote in votes]
    for item in result:
        topics = topic_terms(item["paper"])
        evidence = []
        for vote, paper in profiles:
            other = topic_terms(paper)
            overlap, union = topics & other, topics | other
            similarity = len(overlap) / len(union) if union else 0.0
            evidence.append({**vote, "matched_terms": sorted(overlap), "candidate_terms": sorted(topics),
                             "voted_terms": sorted(other), "jaccard": similarity})
        adjustment = 50 * sum(e["vote"] * e["jaccard"] for e in evidence) / len(evidence)
        item["base_score"] = item["score"]
        item["feedback_adjustment"] = adjustment
        item["score"] = min(100.0, max(0.0, item["score"] + adjustment))
        item["scoring_version"] = "module-four-feedback-v1"
        item["reasons"].append({"signal": "explicit_feedback", "text": "落盘点赞/踩的标题主题词 Jaccard 相似度；不是向量或引用数。",
                                "evidence": {"formula": FEEDBACK_FORMULA, "votes": evidence}})
    return sorted(result, key=lambda item: (-item["score"], item["paper"]["id"]))


def feedback(repository, profile, seed_id, paper_id, vote, year):
    from .recommendations import recommendations
    if paper_id == seed_id:
        raise PipelineError("VALIDATION_ERROR", "推荐反馈对象必须是种子论文以外的候选论文。")
    repository.paper(paper_id)
    with operation_lock(repository.root, "feedback", timeout=30):
        state = TrackingState(repository.root)
        before = recommendations(repository, seed_id, year, profile_id=profile)
        votes = [row for row in state.votes(profile) if row["paper_id"] != paper_id]
        votes.append({"paper_id": paper_id, "vote": vote, "updated_at": utc_now()})
        base = recommendations(repository, seed_id, year, profile_id=None)
        after = rerank(repository, base, votes)
        def ranking(values):
            return [{"paper_id": item["paper"]["id"], "rank": n, "score": item["score"],
                     "base_score": item.get("base_score", item["score"]),
                     "feedback_adjustment": item.get("feedback_adjustment", 0)} for n, item in enumerate(values, 1)]
        event = {"profile_id": profile, "paper_id": paper_id, "seed_paper_id": seed_id, "vote": vote,
                 "at": utc_now(), "as_of_year": year, "before": ranking(before), "after": ranking(after),
                 "formula": FEEDBACK_FORMULA, "evidence": [item for item in after if item["paper"]["id"] == paper_id]}
        event_id = state.feedback(profile, paper_id, vote, event)
        return {"event_id": event_id, **event}
