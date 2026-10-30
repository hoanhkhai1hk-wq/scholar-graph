"""Version-two workspace state, separate from immutable publication records."""
import copy
import hashlib
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from collections import OrderedDict

from .api_transport import paginate
from .errors import PipelineError
from .pdf_files import PdfFiles
from .heading_rules import heading_candidate
from .reference_identity import bibliography_sources


def now():
    return datetime.now(timezone.utc).isoformat()


def arxiv_submission_year(identity):
    # arXiv's new identifier scheme is YYMM.NNNN[N] (April 2007 onward).
    match = re.fullmatch(r'(\d{2})(0[1-9]|1[0-2])\.\d{4,5}(?:v[1-9]\d*)?', identity or '')
    if not match:
        return None
    year = 2000 + int(match[1])
    if 2007 <= year <= datetime.now(timezone.utc).year and (year > 2007 or int(match[2]) >= 4):
        return year
    return None


class Workspace:
    def __init__(self, repository):
        self.repository = repository
        self.root = repository.root
        self.path = self.root / 'workspace.sqlite3'
        self.lock = threading.RLock()
        self._bundle_cache = OrderedDict()
        self._reading_cache = OrderedDict()

    def bundle(self, paper_id):
        self.metadata(paper_id)
        directory = self.root / 'papers' / paper_id
        source = directory.glob('*.json') if directory.is_dir() else (self.root / 'partial' / paper_id).glob('batch-*/*.json')
        signature = tuple((str(p.relative_to(self.root)), p.stat().st_mtime_ns, p.stat().st_size) for p in sorted(source))
        with self.lock:
            cached = self._bundle_cache.get(paper_id)
            if cached is None or cached[0] != signature:
                loaded=self.repository.paper(paper_id)
                loaded=self._source_code_view(paper_id, loaded)
                size=len(json.dumps(loaded,ensure_ascii=False).encode())
                cached = (signature,loaded,size)
                self._bundle_cache.pop(paper_id,None)
                budget=64*1024*1024
                if size<=budget:
                    while self._bundle_cache and (len(self._bundle_cache)>=32 or sum(v[2] for v in self._bundle_cache.values())+size>budget):
                        self._bundle_cache.popitem(last=False)
                    self._bundle_cache[paper_id] = cached
            elif paper_id in self._bundle_cache:
                self._bundle_cache.move_to_end(paper_id)
            base = cached[1]
        enhanced = self.read('enrichment', paper_id, {})
        corrections = {record['chunk_id']: record for record in self.all('classification') if record['paper_id'] == paper_id}
        chunks = base['chunks']
        layout = {record['page_number']: record['regions'] for record in self.layout_pages(paper_id)}
        if layout:
            from .workspace_layout import REGION_TYPES, overlap_fraction
            updated = []
            for chunk in chunks:
                candidates = [region for region in layout.get(chunk['page_number'], [])
                              if chunk['type'] == 'text' and chunk['bbox'] and region['label'] in REGION_TYPES
                              and region['score'] >= .65 and overlap_fraction(chunk['bbox'], region['bbox']) >= .7]
                best = max(candidates, key=lambda r: r['score'], default=None)
                updated.append({**chunk, 'type': REGION_TYPES[best['label']]} if best else chunk)
            chunks = updated
        if corrections:
            chunks = []
            for original in (updated if layout else base['chunks']):
                correction = corrections.get(original['chunk_id'])
                if not correction:
                    chunks.append(original); continue
                path = correction['section_path']
                headings = path + [None] * (3 - len(path))
                chunks.append({**original, 'type': correction['type'], 'section_path': path,
                               'heading_1': headings[0], 'heading_2': headings[1], 'heading_3': headings[2]})
        return {**base, 'paper_meta': self.paper(paper_id)['paper'],
                'chunks': chunks,
                'reference_entries': enhanced.get('references', base['reference_entries']),
                'citation_links': enhanced.get('citation_links', base['citation_links'])}

    def _source_code_view(self, paper_id, bundle):
        """Repair an effective view with an audited sidecar, never frozen files."""
        from .code_layout import VERSION, repair_pdf_code
        if not any('```' in c['text'] or '~~~' in c['text'] for c in bundle['chunks']):
            return bundle
        digest = hashlib.sha256(json.dumps(bundle['chunks'], sort_keys=True).encode()).hexdigest()
        prior = self.read('code_layout', paper_id, {})
        if prior.get('version') == VERSION and prior.get('base_digest') == digest:
            return {**bundle, 'chunks': prior['chunks']}
        try:
            path = PdfFiles(self.root).locate(paper_id)
        except PipelineError:
            # Legacy libraries may not retain originals. Never guess source text.
            return bundle
        chunks, changes = repair_pdf_code(bundle['chunks'], path)
        self.put('code_layout', paper_id, {'version': VERSION, 'base_digest': digest,
                 'source_sha256': bundle['paper_meta']['file_hash'], 'chunks': chunks,
                 'changes': changes}, 'source_code_layout_verified')
        return {**bundle, 'chunks': chunks}

    @contextmanager
    def connect(self):
        self.root.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=20)
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('CREATE TABLE IF NOT EXISTS records(kind TEXT, id TEXT, value TEXT NOT NULL, PRIMARY KEY(kind,id))')
        connection.execute('CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at TEXT, action TEXT, subject TEXT, value TEXT)')
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def read(self, kind, identity, default=None):
        with self.lock, self.connect() as db:
            row = db.execute('SELECT value FROM records WHERE kind=? AND id=?', (kind, identity)).fetchone()
        return json.loads(row[0]) if row else copy.deepcopy(default)

    def put(self, kind, identity, value, action=None):
        with self.lock, self.connect() as db:
            db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?)', (kind, identity, json.dumps(value, ensure_ascii=False, allow_nan=False)))
            if action:
                db.execute('INSERT INTO audit(at,action,subject,value) VALUES(?,?,?,?)', (now(), action, identity, json.dumps(value, ensure_ascii=False)))
        return value

    def all(self, kind):
        with self.lock, self.connect() as db:
            return [json.loads(row[0]) for row in db.execute('SELECT value FROM records WHERE kind=? ORDER BY id', (kind,))]

    def layout_pages(self, paper_id):
        with self.lock, self.connect() as db:
            rows = db.execute('SELECT value FROM records WHERE kind=? AND id LIKE ? ORDER BY id', ('layout_page', paper_id + '-p%')).fetchall()
        return [value for row in rows if (value := json.loads(row[0])).get('paper_id') == paper_id]

    def metadata(self, paper_id):
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*', paper_id):
            raise PipelineError('PAPER_NOT_FOUND', '无该论文记录。')
        path = self.root / 'papers' / paper_id / 'paper-meta.json'
        if not path.is_file():
            return self.repository.paper(paper_id)['paper_meta']
        value = json.loads(path.read_text(encoding='utf-8'))
        self.repository.gate.record('PaperMeta', value)
        return value

    def paper(self, paper_id):
        original = self.metadata(paper_id)
        changes = self.read('paper', paper_id, {})
        effective = {**original, **changes.get('metadata', {})}
        year_source = 'metadata'
        if effective['year'] is None and 'year' not in changes.get('metadata', {}):
            effective['year'] = arxiv_submission_year(original['arxiv_id'])
            if effective['year']:
                year_source = 'arxiv_submission_identifier'
        return {'paper': effective, 'original': original, 'archived': changes.get('archived', False),
                'year_source': year_source,
                'hidden_version': changes.get('hidden_version', False), 'updated_at': changes.get('updated_at'),
                'missing_fields': [field for field in ('title', 'authors', 'abstract') if not effective.get(field)],
                'source': changes.get('metadata_source', 'user_correction' if changes.get('metadata') else 'parser'),
                'author_profiles': changes.get('author_profiles', []), 'filename': changes.get('filename')}

    def papers(self, *, page=1, page_size=20, title=None, archived=False, year=None, source=None):
        values = []
        for path in sorted((self.root / 'papers').glob('*/paper-meta.json')):
            view = self.paper(path.parent.name)
            if bool(view['archived']) != archived or (view['hidden_version'] and not archived):
                continue
            if title and title.casefold() not in ((view['paper']['title'] or '') + ' ' + (view['paper']['arxiv_id'] or '')).casefold():
                continue
            if year is not None and view['paper']['year'] != year:
                continue
            if source is not None and view['paper']['source'] != source:
                continue
            values.append(view)
        return paginate(values, page, page_size)

    def update(self, paper_id, patch):
        original = self.metadata(paper_id)
        candidate = {**original, **patch}
        self.repository.gate.record('PaperMeta', candidate)
        with self.lock:
            value = self.read('paper', paper_id, {})
            value.update(metadata={**value.get('metadata', {}), **patch}, updated_at=now())
            value['metadata_source'] = 'user_correction'
            if 'authors' in patch and patch['authors'] != self.paper(paper_id)['paper']['authors']:
                value['author_profiles'] = []
            self.put('paper', paper_id, value, 'metadata_corrected')
        return self.paper(paper_id)

    def archive(self, paper_id, archived):
        self.metadata(paper_id)
        with self.lock:
            value = self.read('paper', paper_id, {})
            value.update(archived=archived, updated_at=now())
            self.put('paper', paper_id, value, 'archived' if archived else 'restored')
        return self.paper(paper_id)

    def choose_version(self, paper_id, choice):
        decision = self.repository.comparison(paper_id, kind='decision')
        old, new = decision['old_paper_id'], decision['new_paper_id']
        self.metadata(old); self.metadata(new)
        if choice not in ('keep_old', 'keep_new', 'keep_both'):
            raise PipelineError('VALIDATION_ERROR', '请选择保留已有、使用新版或保留两份。')
        # Both visibility updates and the decision commit together; originals remain immutable.
        with self.lock, self.connect() as db:
            for identity, hidden in ((old, choice == 'keep_new'), (new, choice == 'keep_old')):
                row = db.execute('SELECT value FROM records WHERE kind=? AND id=?', ('paper', identity)).fetchone()
                value = json.loads(row[0]) if row else {}
                value.update(hidden_version=hidden, updated_at=now())
                db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?)', ('paper', identity, json.dumps(value, ensure_ascii=False)))
            result = {'old_paper_id': old, 'new_paper_id': new, 'choice': choice, 'at': now()}
            db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?)', ('version_choice', new, json.dumps(result)))
            db.execute('INSERT INTO audit(at,action,subject,value) VALUES(?,?,?,?)', (now(), 'version_selected', new, json.dumps(result)))
        return result

    def version_info(self, paper_id):
        self.metadata(paper_id)
        new_ids = set()
        for path in (self.root / 'comparisons').glob('comparison-*/diff-summary.json'):
            value = json.loads(path.read_text(encoding='utf-8'))
            if paper_id in (value['old_paper_id'], value['new_paper_id']):
                new_ids.add(value['new_paper_id'])
        groups = []
        for new_id in sorted(new_ids):
            decision = self.repository.comparison(new_id, kind='decision')
            diff = self.repository.comparison(new_id, kind='diff')
            with self.lock, self.connect() as db:
                history = [{'at': row[0], **json.loads(row[1])} for row in db.execute(
                    'SELECT at,value FROM audit WHERE action=? AND subject=? ORDER BY id', ('version_selected', new_id))]
            groups.append({'decision': decision, 'diff': diff,
                           'old': self.paper(decision['old_paper_id']), 'new': self.paper(new_id),
                           'selection': self.read('version_choice', new_id), 'history': history})
        return groups

    def _reading_signature(self, paper_id):
        # Frozen publications plus the effective, editable sidecars determine the
        # reader. Merely appending a chat/task must not invalidate a whole book.
        self.metadata(paper_id)
        directory = self.root / 'papers' / paper_id
        source = directory.glob('*.json') if directory.is_dir() else (self.root / 'partial' / paper_id).glob('batch-*/*.json')
        files = tuple((str(p.relative_to(self.root)), p.stat().st_mtime_ns, p.stat().st_size) for p in sorted(source))
        with self.lock, self.connect() as db:
            rows = db.execute("""SELECT kind,id,value FROM records WHERE
                (kind IN ('paper','enrichment','code_layout') AND id=?) OR
                (kind IN ('classification','layout_page') AND json_extract(value,'$.paper_id')=?)
                ORDER BY kind,id""", (paper_id, paper_id)).fetchall()
        return files, hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode()).hexdigest()

    def _reading_material(self, paper_id):
        signature = self._reading_signature(paper_id)
        with self.lock:
            hit = self._reading_cache.get(paper_id)
            if hit and hit['signature'] == signature:
                self._reading_cache.move_to_end(paper_id)
                return hit
            bundle = self.bundle(paper_id)
            pages = {}
            for chunk in bundle['chunks']:
                pages.setdefault(chunk['page_number'], []).append(chunk)
            item = {'signature': signature, 'bundle': bundle, 'pages': pages,
                    'navigation': None, 'bytes': len(json.dumps(bundle, ensure_ascii=False).encode())}
            # Bound retained material; oversized books still work without being
            # pinned in RAM. Never alter the published records to make a cache.
            self._reading_cache.pop(paper_id, None)
            budget = 32 * 1024 * 1024
            if item['bytes'] <= budget and self._reading_signature(paper_id) == signature:
                while self._reading_cache and (len(self._reading_cache) >= 8 or
                        sum(v['bytes'] for v in self._reading_cache.values()) + item['bytes'] > budget):
                    self._reading_cache.popitem(last=False)
                self._reading_cache[paper_id] = item
            return item

    def _reading_navigation(self, bundle):
        outline, seen = [], set()
        metadata = bundle['paper_meta']
        person_or_institution = {re.sub(r'\W+', '', value).casefold() for value in metadata['authors'] + metadata['institutions']}
        for chunk in bundle['chunks']:
            path = tuple(part for part in chunk['section_path'] if heading_candidate(part) and re.sub(r'\W+', '', part).casefold() not in person_or_institution)
            if path and path not in seen:
                seen.add(path)
                outline.append({'section_path': list(path), 'page_number': chunk['page_number'],
                                'chunk_id': chunk['chunk_id'], 'text': chunk['text'][:120]})
        bibliography = {str(entry['number']): {'page_number': entry['chunks'][0]['page_number'],
                         'chunk_id': entry['chunks'][0]['chunk_id'], 'text': entry['raw'][:400]} for entry in bibliography_sources(bundle['chunks'])}
        return {'outline': outline, 'bibliography_locations': bibliography,
                'references': bundle['reference_entries'], 'citation_links': bundle['citation_links']}

    def reading(self, paper_id, physical_page=1, include_navigation=True):
        material = self._reading_material(paper_id)
        bundle = material['bundle']
        if physical_page > bundle['paper_meta']['page_count']:
            raise PipelineError('VALIDATION_ERROR', '页码超过原文范围。')
        navigation = {'outline': [], 'bibliography_locations': {}, 'references': [], 'citation_links': []}
        if include_navigation:
            with self.lock:
                if material['navigation'] is None:
                    material['navigation'] = self._reading_navigation(bundle)
                navigation = material['navigation']
        return {'paper': bundle['paper_meta'], **navigation,
                'chunks': material['pages'].get(physical_page, []),
                'page_number': physical_page, 'total_chunks': len(bundle['chunks'])}

    def session(self, paper_ids):
        if len(set(paper_ids)) != len(paper_ids) or not 1 <= len(paper_ids) <= 10:
            raise PipelineError('VALIDATION_ERROR', '研究会话需要 1–10 篇不同论文。')
        for identity in paper_ids:
            self.metadata(identity)
        identity = uuid.uuid4().hex
        return self.put('session', identity, {'id': identity, 'paper_ids': paper_ids,
                        'created_at': now(), 'messages': []}, 'session_created')

    def get_session(self, identity):
        value = self.read('session', identity)
        if value is None:
            raise PipelineError('PAPER_NOT_FOUND', '研究会话不存在。')
        return value

    def append_message(self, identity, message):
        with self.lock:
            session = self.get_session(identity)
            session['messages'].append(message)
            session['updated_at'] = now()
            return self.put('session', identity, session)

    def system(self):
        configured = bool(os.environ.get('DEEPSEEK_API_KEY') and os.environ.get('DEEPSEEK_MODEL'))
        return {'api_version': '2.0', 'workspace_release': '20261027-workbench-r2',
                'data_class': os.environ.get('SG_DATA_CLASS', 'personal'), 'revision': os.environ.get('SCHOLAR_GRAPH_REVISION', 'workspace'),
                'model_configured': configured, 'qa_mode': os.environ.get('SCHOLAR_GRAPH_QA_MODE', 'extractive'),
                'research_retrieval': os.environ.get('SCHOLAR_GRAPH_WORKSPACE_RETRIEVAL', 'lexical'),
                'tracking_enabled': os.environ.get('SCHOLAR_GRAPH_TRACKING_ENABLED', 'false').lower() == 'true',
                'limits': {'upload_bytes': 50 * 1024 * 1024, 'pages': 2000, 'comparison_papers': 10},
                'capabilities': {'paper_management': True, 'version_choice': True, 'reading_pages': True,
                                 'sessions': True, 'translation': configured, 'generated_writing': configured,
                                 'author_mapping': True, 'layout_regions': True, 'tracking_read_only': True,
                                 'csv_provenance': True, 'translation_snapshots': True}}
