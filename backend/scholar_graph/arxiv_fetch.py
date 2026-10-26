"""Public arXiv metadata/PDF retrieval and reuse of the existing module-one pipeline."""

import os
import re
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from defusedxml import ElementTree as ET

from .atomic_io import windows_retry
from .errors import PipelineError
from .pipeline import Pipeline
from .pdf_files import PdfFiles
from .storage import write_json
from .tracking_state import TrackingState, operation_lock

ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV = "{http://arxiv.org/schemas/atom}"
IDENTITY = re.compile(r"(?:\d{4}\.\d{4,5}|[A-Za-z-]+(?:\.[A-Za-z]{2})?/\d{7})(?:v[1-9]\d*)?")
MAX_PDF = 50 * 1024 * 1024


def text(element, tag):
    return " ".join((element.findtext(tag) or "").split())


def normalized_title(value):
    return "".join(character for character in value.casefold() if character.isalnum())


def arxiv_identity(value):
    if not isinstance(value, str) or not IDENTITY.fullmatch(value):
        raise PipelineError("VALIDATION_ERROR", "arXiv 标识格式不合法。")
    return value


def base_identity(value):
    return re.sub(r"v\d+$", "", arxiv_identity(value))


def entry_metadata(entry, gate):
    raw_id = text(entry, ATOM + "id")
    parsed = urlparse(raw_id)
    if parsed.hostname not in {"arxiv.org", "export.arxiv.org"} or not parsed.path.startswith("/abs/"):
        raise PipelineError("UPSTREAM_ERROR", "arXiv 返回无法核验的论文标识。")
    identity = arxiv_identity(parsed.path.removeprefix("/abs/"))
    title, abstract = text(entry, ATOM + "title"), text(entry, ATOM + "summary")
    if not title:
        raise PipelineError("UPSTREAM_ERROR", "arXiv 未返回论文标题。")
    published = text(entry, ATOM + "published")
    try:
        year = datetime.fromisoformat(published.replace("Z", "+00:00")).year if published else None
    except ValueError:
        raise PipelineError("UPSTREAM_ERROR", "arXiv 发表时间无法核验。") from None
    doi = text(entry, ARXIV + "doi") or None
    if doi:
        doi = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", "", doi, flags=re.I)
        if not re.fullmatch(r"10\.\d{4,9}/\S+", doi):
            raise PipelineError("UPSTREAM_ERROR", "arXiv DOI 无法核验。")
    affiliations = []
    for author in entry.findall(ATOM + "author"):
        for affiliation in author.findall(ARXIV + "affiliation"):
            value = " ".join((affiliation.text or "").split())
            if value and value not in affiliations:
                affiliations.append(value)
    version = re.search(r"v[1-9]\d*$", identity)
    paper = {"schema_version": "1.0.0", "id": "arxiv-" + identity.replace("/", "-"),
        "title": title, "authors": [text(author, ATOM + "name") for author in entry.findall(ATOM + "author") if text(author, ATOM + "name")],
        "institutions": affiliations, "abstract": abstract or None, "year": year,
        "source": "https://arxiv.org/abs/" + identity, "arxiv_id": identity, "doi": doi,
        "version": version[0] if version else None, "file_hash": None, "page_count": None, "has_text_layer": None}
    gate.record("PaperMeta", paper)
    return paper


class ArxivClient:
    def __init__(self, gate, *, transport=None, interval=3):
        self.gate, self.transport, self.interval = gate, transport, interval
        self._lock, self._last_request = threading.Lock(), 0.0

    def _bytes(self, url, *, params=None, maximum):
        # Fixed public hosts; no arbitrary URLs, API keys, credentials, or implicit redirects.
        for _ in range(5):
            parsed = urlparse(url)
            if parsed.scheme != "https" or parsed.hostname not in {"arxiv.org", "export.arxiv.org"} or parsed.username or parsed.password:
                raise PipelineError("UPSTREAM_ERROR", "拒绝非 arXiv 公共地址。")
            with self._lock:
                time.sleep(max(0, self.interval - (time.monotonic() - self._last_request)))
                self._last_request = time.monotonic()
                try:
                    with httpx.Client(transport=self.transport, timeout=30, follow_redirects=False) as client:
                        with client.stream("GET", url, params=params, headers={"User-Agent": "ScholarGraph/0.1 public research API client"}) as response:
                            if response.is_redirect:
                                url = str(response.url.join(response.headers["location"]))
                                params = None
                                continue
                            if response.status_code != 200:
                                raise PipelineError("UPSTREAM_ERROR", f"arXiv 公共接口返回 HTTP {response.status_code}，未取得所需记录或文件。")
                            blocks, size = [], 0
                            for block in response.iter_bytes():
                                size += len(block)
                                if size > maximum:
                                    raise PipelineError("FILE_TOO_LARGE", "arXiv 响应超过本单允许大小。")
                                blocks.append(block)
                            return b"".join(blocks)
                except PipelineError:
                    raise
                except Exception:
                    raise PipelineError("UPSTREAM_ERROR", "arXiv 公共接口连接失败，未编造记录。") from None
        raise PipelineError("UPSTREAM_ERROR", "arXiv 重定向次数超限。")

    def metadata(self, title=None, reference=None):
        reference = reference or {}
        if reference.get("arxiv_id"):
            requested = arxiv_identity(reference["arxiv_id"])
            params = {"id_list": requested, "max_results": 5}
            selector = lambda paper: (paper["arxiv_id"] == requested if re.search(r"v\d+$", requested)
                else re.sub(r"v\d+$", "", paper["arxiv_id"]) == requested)
        elif reference.get("doi"):
            requested = reference["doi"]
            if not re.fullmatch(r"10\.\d{4,9}/\S+", requested):
                raise PipelineError("VALIDATION_ERROR", "参考文献 DOI 必须为裸 DOI。")
            params = {"search_query": 'doi:"' + requested.replace('"', '\\"') + '"', "max_results": 5}
            selector = lambda paper: bool(paper["doi"] and paper["doi"].casefold() == requested.casefold())
        else:
            requested = title or reference.get("title")
            if not requested:
                raise PipelineError("VALIDATION_ERROR", "缺少可查询的论文名、arXiv 标识或 DOI。")
            escaped = re.sub(r'([+\-!(){}\[\]^"~*?:\\/|&])', r'\\\1', requested)
            params = {"search_query": 'ti:"' + escaped + '"', "max_results": 5}
            selector = lambda paper: normalized_title(paper["title"]) == normalized_title(requested)
        raw = self._bytes("https://export.arxiv.org/api/query", params=params, maximum=1024 * 1024)
        try:
            root = ET.fromstring(raw)
            papers = [entry_metadata(entry, self.gate) for entry in root.findall(ATOM + "entry")]
        except PipelineError:
            raise
        except Exception:
            raise PipelineError("UPSTREAM_ERROR", "arXiv 元数据不是合法安全的 Atom。") from None
        matches = [paper for paper in papers if selector(paper)]
        if len(matches) != 1:
            raise PipelineError("PAPER_NOT_FOUND", "arXiv 未找到唯一匹配论文；未选取相似标题冒充结果。")
        return matches[0]

    def pdf(self, paper):
        identity = arxiv_identity(paper["arxiv_id"])
        return self._bytes("https://arxiv.org/pdf/" + identity, maximum=MAX_PDF)

    def search(self, query, limit=5):
        if not isinstance(query, str) or not 1 <= len(query) <= 1500 or not 1 <= limit <= 20:
            raise PipelineError("VALIDATION_ERROR", "arXiv 追踪查询或候选上限不合法。")
        raw = self._bytes("https://export.arxiv.org/api/query", params={"search_query": query,
            "start": 0, "max_results": limit, "sortBy": "submittedDate", "sortOrder": "descending"}, maximum=2 * 1024 * 1024)
        try:
            root = ET.fromstring(raw)
            if root.tag != ATOM + "feed":
                raise ValueError("not an Atom feed")
            entries = root.findall(ATOM + "entry")
            return [entry_metadata(entry, self.gate) for entry in entries[:limit]]
        except PipelineError:
            raise
        except Exception:
            raise PipelineError("UPSTREAM_ERROR", "arXiv 追踪结果不是合法安全的 Atom，未编造候选。") from None


class ArxivFetcher:
    def __init__(self, repository, *, client=None, pipeline_factory=None, lock=None):
        self.repository = repository
        self.client = client or ArxivClient(repository.gate)
        self.factory = pipeline_factory or self._pipeline
        self.lock = lock or threading.Lock()
        self.state = TrackingState(repository.root)

    def _pipeline(self, metadata):
        def enrich(paper):
            for field in ("title", "authors", "institutions", "abstract", "year", "source", "arxiv_id", "doi", "version"):
                paper[field] = metadata[field]
            return paper
        return Pipeline(self.repository.root, gate=self.repository.gate, metadata_enricher=enrich)

    def _catalog(self, paper):
        self.repository.gate.record("PaperMeta", paper)
        parent = self.repository.root / "catalog" / paper["id"]
        parent.mkdir(parents=True, exist_ok=True)
        temporary = parent / (".metadata-" + uuid4().hex + ".tmp")
        try:
            write_json(temporary, paper)
            windows_retry(lambda: os.replace(temporary, parent / "paper-meta.json"))
        finally:
            windows_retry(lambda: temporary.unlink(missing_ok=True))

    def fetch(self, title=None, reference=None):
        try:
            if reference is not None:
                self.repository.gate.record("ReferenceEntry", reference)
            metadata = self.client.metadata(title, reference)
        except Exception as error:
            return self._failure(error)
        return self.fetch_metadata(metadata)

    def _failure(self, error, metadata=None, pipeline=None):
        if not isinstance(error, PipelineError):
            error = PipelineError("INTERNAL_ERROR", "抓取或入库失败，未返回伪造解析结果。")
        self.repository.gate.error(error.envelope())
        job = pipeline.last_job if pipeline is not None else None
        return {"succeeded": False, "metadata": metadata, "paper": None,
                "initial_parse_status": job.history[0] if job else None,
                "parse_status": job.current if job else None, "error": error.envelope()}

    def fetch_metadata(self, metadata):
        """Import verified public metadata; versions of an existing arXiv identity are not reimported."""
        pipeline = None
        try:
            self.repository.gate.record("PaperMeta", metadata)
            identity = base_identity(metadata["arxiv_id"])
            self._catalog(metadata)  # Actual API metadata is published before PDF/parse work.
            with self.lock, operation_lock(self.repository.root, "ingestion", timeout=30):
                for paper in self.repository.papers():
                    same_arxiv = paper["arxiv_id"] and base_identity(paper["arxiv_id"]) == identity
                    same_doi = metadata["doi"] and paper["doi"] and metadata["doi"].casefold() == paper["doi"].casefold()
                    if not (same_arxiv or same_doi):
                        continue
                    dedup = self.state.duplicate(identity, paper["id"], "ARXIV_ID" if same_arxiv else "DOI_EXACT")
                    try:
                        status = self.repository.status(paper["id"])
                    except PipelineError as error:
                        if error.code != "PAPER_NOT_FOUND":
                            raise
                        status = None  # Older imported bundles may have no parse job history.
                    return {"succeeded": True, "metadata": metadata, "paper": paper,
                        "initial_parse_status": None, "parse_status": status, "error": None,
                        "already_present": True, "dedup": dedup}
                raw = self.client.pdf(metadata)
                scratch = self.repository.root / ".fetch"
                scratch.mkdir(parents=True, exist_ok=True)
                with tempfile.TemporaryDirectory(prefix="arxiv-", dir=scratch) as directory:
                    source = Path(directory) / "source.pdf"
                    source.write_bytes(raw)
                    pipeline = self.factory(metadata)
                    bundle = pipeline.parse(source)
                    PdfFiles(self.repository.root).retain(source, bundle["paper_meta"])
                dedup = None
                if getattr(pipeline, "last_comparison", None):
                    decision = self.repository.comparison(bundle["paper_meta"]["id"], kind="decision")
                    dedup = self.state.duplicate(identity, decision["old_paper_id"], "DOI_OR_TOKEN_DICE",
                                                 score=decision["similarity"])
            return {"succeeded": True, "metadata": metadata, "paper": bundle["paper_meta"],
                "initial_parse_status": pipeline.last_job.history[0], "parse_status": pipeline.last_job.current, "error": None,
                "already_present": False, "dedup": dedup}
        except Exception as error:
            return self._failure(error, metadata, pipeline)
