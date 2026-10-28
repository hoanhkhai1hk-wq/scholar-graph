"""Optional GROBID HTTP enrichment; local MinerU remains the text/page authority."""

import re
from urllib.parse import urlsplit

import httpx
from defusedxml import ElementTree as ET

from .errors import PipelineError
from .normalize import citation_links, doi
from .reference_identity import arxiv

NS = {"t": "http://www.tei-c.org/ns/1.0"}


def clean_abstract(value):
    if not value:
        return value
    # Explicit author-note markers are occasionally merged into TEI abstracts.
    # Keep the original scientific prose; never trim arbitrary mathematical stars.
    return re.split(r'\s*[*∗†‡]+\s*(?=Equal contribution|These authors contributed|Corresponding author|Work performed)', value, maxsplit=1, flags=re.I)[0].strip()


def text(node):
    if node is None:
        return None
    return " ".join("".join(node.itertext()).split()) or None


def person_name(node):
    # TEI serializes adjacent <forename>/<surname> tags without whitespace.
    # Insert boundaries between name components, preserving inline markup
    # inside each component (and any direct text/tails in mixed-content names).
    parts = [node.text or ""]
    for component in node:
        parts.extend((text(component) or "", component.tail or ""))
    return " ".join(" ".join(parts).split()) or None


def authors(node):
    return [name for item in node.findall(".//t:author/t:persName", NS) if (name := person_name(item))]


def year(node):
    item = node.find(".//t:date", NS)
    value = (item.get("when") or text(item) or "") if item is not None else ""
    match = re.search(r"\b((?:18|19|20)\d{2})\b", value)
    return int(match[1]) if match else None


def header_author_profiles(root):
    header = root.find('t:teiHeader', NS)
    if header is None:
        return []
    nodes = header.findall('.//t:sourceDesc/t:biblStruct/t:analytic/t:author', NS)
    if not nodes:
        nodes = header.findall('.//t:titleStmt/t:author', NS)
    result = []
    for node in nodes:
        person = node.find('t:persName', NS)
        name = person_name(person) if person is not None else None
        if not name:
            continue
        result.append({'order': len(result) + 1, 'name': name,
            'institutions': list(dict.fromkeys(value for org in node.findall('.//t:affiliation/t:orgName', NS) if (value := text(org)))),
            'emails': list(dict.fromkeys(value for email in node.findall('.//t:email', NS) if (value := text(email)))),
            'source': 'grobid_header', 'review_status': 'extracted_not_human_verified'})
    return result


class GrobidClient:
    def __init__(self, base_url: str, *, timeout: float = 60, transport=None):
        parsed = urlsplit(base_url)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise PipelineError("VALIDATION_ERROR", "GROBID_URL 必须是无凭据、无查询参数的 HTTP 服务地址。")
        self.url, self.timeout, self.transport = base_url.rstrip("/"), timeout, transport

    def enrich(self, bundle: dict, pdf_bytes: bytes) -> dict:
        try:
            with httpx.Client(timeout=self.timeout, transport=self.transport, trust_env=False) as client:
                response = client.post(self.url + "/api/processFulltextDocument",
                                       files={"input": ("source.pdf", pdf_bytes, "application/pdf")},
                                       data={"consolidateHeader": "0", "consolidateCitations": "0"})
                response.raise_for_status()
                if len(response.content) > 10 * 1024 * 1024:
                    raise ValueError("oversized TEI")
                root = ET.fromstring(response.content)
                self.last_author_profiles = header_author_profiles(root)
                return self._convert(bundle, root)
        except PipelineError:
            raise
        except httpx.TimeoutException:
            raise PipelineError('UPSTREAM_ERROR','GROBID 服务超时，未采用增强结果。',details={'failure_kind':'timeout'}) from None
        except httpx.ConnectError:
            raise PipelineError('UPSTREAM_ERROR','GROBID 服务不可达，未采用增强结果。',details={'failure_kind':'unavailable'}) from None
        except httpx.HTTPStatusError as error:
            raise PipelineError('UPSTREAM_ERROR',f'GROBID 服务返回 HTTP {error.response.status_code}，未采用增强结果。',
                details={'failure_kind':'http_status','http_status':error.response.status_code}) from None
        except Exception:
            raise PipelineError("UPSTREAM_ERROR", "GROBID 服务调用或 TEI 响应校验失败。") from None

    def _convert(self, bundle, root):
        if root.tag != "{http://www.tei-c.org/ns/1.0}TEI":
            raise ValueError("not TEI")
        paper = dict(bundle["paper_meta"])
        header = root.find("t:teiHeader", NS)
        if header is not None:
            header_title = text(header.find(".//t:titleStmt/t:title", NS))
            if header_title:
                paper["title"] = header_title
            header_authors = authors(header)
            if header_authors:
                paper["authors"] = list(dict.fromkeys(header_authors))
            institutions = [value for item in header.findall(".//t:affiliation/t:orgName", NS) if (value := text(item))]
            if institutions:
                paper["institutions"] = list(dict.fromkeys(institutions))
            abstract = clean_abstract(text(header.find(".//t:abstract", NS)))
            if abstract:
                paper["abstract"] = abstract
            if publication_year := year(header):
                paper["year"] = publication_year
            for item in header.findall(".//t:idno", NS):
                if item.get("type", "").lower() == "doi" and (identifier := doi(text(item) or "")):
                    paper["doi"] = identifier
        refs = []
        for index, item in enumerate(root.findall(".//t:listBibl/t:biblStruct", NS), 1):
            printed = (item.get("n") or "").strip("[] .")
            number = int(printed) if printed.isdigit() and int(printed) > 0 else index
            title = text(item.find("t:analytic/t:title", NS)) or text(item.find("t:monogr/t:title", NS))
            identifiers = [text(x) for x in item.findall(".//t:idno", NS) if x.get("type", "").lower() == "doi"]
            arxiv_ids = [arxiv('arXiv:' + (text(x) or '')) for x in item.findall('.//t:idno', NS)
                         if x.get('type', '').casefold() == 'arxiv']
            refs.append({"schema_version": "1.0.0", "ref_id": f"{paper['id']}-ref-{number}",
                         "paper_id": paper["id"], "number": number, "authors": authors(item),
                         "year": year(item), "title": title,
                         "venue": text(item.find("t:monogr/t:title", NS)),
                         "doi": next((value for x in identifiers if (value := doi(x or ""))), None),
                         "arxiv_id": next((value for value in arxiv_ids if value), None) or arxiv(text(item))})
        if not refs:
            refs = bundle["reference_entries"]
        return {**bundle, "paper_meta": paper, "reference_entries": refs,
                "citation_links": citation_links(bundle["chunks"], refs)}
