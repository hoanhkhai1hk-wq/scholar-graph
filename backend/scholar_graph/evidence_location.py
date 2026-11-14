"""Location sidecars for transport; frozen v1 Chunk/Anchor records stay compatible."""

import math


def evidence_location(chunk):
    """Copy the parser's top-left, page-normalized region; never infer a missing box."""
    box = chunk.get("bbox")
    valid = (isinstance(box, list) and len(box) == 4
             and all(type(v) in (int, float) and math.isfinite(v) and 0 <= v <= 1 for v in box)
             and box[0] < box[2] and box[1] < box[3])
    return {"bbox": list(box) if valid else None,
            "coordinate_system": "page-normalized-top-left",
            "precision": "paragraph" if valid else "page"}
