"""Deterministic contribution-weighted RRF with a replayable per-hit accounting."""

import math


def contribution_fusion(routes, *, k=60):
    """Share each hit's rank credit across routes that recalled it, then normalize.

    Credit is (k+1)/(k+rank)/support_count. With two active routes, clamp each
    normalized weight to [0.35, 0.65] to retain both recall channels. This measures
    recall contribution, not relevance probability or measured answer accuracy.
    Empty routes get zero weight. Identical lists naturally receive equal weights.
    """
    if type(k) is not int or k < 1 or len(routes) != 2:
        raise ValueError("RRF requires two routes and a positive integer k")
    ranks = {}
    for name, ids in routes.items():
        if len(ids) != len(set(ids)):
            raise ValueError("A recall route must not contain duplicate IDs")
        ranks[name] = {cid: rank for rank, cid in enumerate(ids, 1)}
    ids = set().union(*ranks.values())
    support = {cid: sum(cid in row for row in ranks.values()) for cid in ids}
    masses = {name: math.fsum((k + 1) / (k + rank) / support[cid]
                             for cid, rank in row.items()) for name, row in ranks.items()}
    total = math.fsum(masses.values())
    weights = {name: mass / total if total else 0.0 for name, mass in masses.items()}
    if all(masses.values()):
        first, second = routes
        weights[first] = max(.35, min(.65, weights[first]))
        weights[second] = 1 - weights[first]
    hits = {}
    for cid in sorted(ids):
        contributions = {name: weights[name] * (k + 1) / (k + row[cid]) if cid in row else 0.0
                         for name, row in ranks.items()}
        hits[cid] = {"ranks": {name: row.get(cid) for name, row in ranks.items()},
                     "contributions": contributions, "score": math.fsum(contributions.values())}
    ordered = sorted(ids, key=lambda cid: (-hits[cid]["score"], cid))
    trace = {"method": "contribution_weighted_rrf", "k": k,
             "weight_rule": "shared_discounted_rank_mass",
             "active_weight_bounds": [.35, .65],
             "routes": {name: {"recalled": len(row),
                               "unique": sum(support[cid] == 1 for cid in row),
                               "shared": sum(support[cid] > 1 for cid in row),
                               "credit_mass": masses[name], "weight": weights[name]}
                        for name, row in ranks.items()},
             "hits": hits}
    return [(cid, hits[cid]["score"]) for cid in ordered], trace
