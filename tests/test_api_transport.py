import pytest

from scholar_graph.api_transport import paginate
from scholar_graph.errors import PipelineError


@pytest.mark.parametrize("page,size,count,expected", [
    (1, 20, 0, (0, 0, False, 20)),
    (1, 1, 2, (1, 2, True, 1)),
    (2, 1, 2, (1, 2, False, 1)),
    (999, 20, 2, (0, 1, False, 20)),
    (1, 101, 101, (100, 2, True, 100)),
])
def test_pagination_boundaries(page, size, count, expected):
    result = paginate(list(range(count)), page, size)
    assert set(result) == {"items", "page", "page_size", "total", "total_pages", "has_next"}
    assert result["total"] == count and result["page"] == page
    assert (len(result["items"]), result["total_pages"], result["has_next"], result["page_size"]) == expected


@pytest.mark.parametrize("page,size", [(0, 20), (1, 0), (-1, 20), (1, -1), (True, 20)])
def test_invalid_pagination(page, size):
    with pytest.raises(PipelineError):
        paginate([], page, size)
