"""Transactional page-batch anchor index; payloads remain the frozen Chunk records."""
import json
import sqlite3
from contextlib import closing
from pathlib import Path


class ChunkIndex:
    def __init__(self, root: Path, paper_id: str):
        self.path = root / 'chunk-index' / (paper_id + '.sqlite3')

    def append(self, chunks, *, reset=False):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self.path)) as connection, connection:
            connection.execute('CREATE TABLE IF NOT EXISTS chunks (ordinal INTEGER PRIMARY KEY, chunk_id TEXT UNIQUE NOT NULL, page_number INTEGER NOT NULL, payload TEXT NOT NULL)')
            connection.execute('CREATE INDEX IF NOT EXISTS physical_page ON chunks(page_number, ordinal)')
            if reset:
                connection.execute('DELETE FROM chunks')
            start = connection.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]
            connection.executemany('INSERT INTO chunks VALUES (?, ?, ?, ?)', [
                (start + n, c['chunk_id'], c['page_number'], json.dumps(c, ensure_ascii=False, allow_nan=False))
                for n, c in enumerate(chunks)])

    def page(self, page, page_size):
        # Read-only URI avoids creating a missing index on GET.
        with closing(sqlite3.connect(self.path.resolve().as_uri() + '?mode=ro', uri=True)) as connection:
            total = connection.execute('SELECT COUNT(*) FROM chunks').fetchone()[0]
            items = [json.loads(row[0]) for row in connection.execute(
                'SELECT payload FROM chunks ORDER BY ordinal LIMIT ? OFFSET ?', (page_size, (page - 1) * page_size))]
        pages = (total + page_size - 1) // page_size
        return {'items': items, 'page': page, 'page_size': page_size, 'total': total,
                'total_pages': pages, 'has_next': page < pages}
