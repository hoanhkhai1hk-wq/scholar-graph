"""Operational views for new research features; v1 remains an immutable baseline."""
class WorkspaceRepository:
    def __init__(self, workspace):
        self.workspace = workspace
        self.root = workspace.root
        self.gate = workspace.repository.gate
        self._papers = {}

    def paper(self, identity):
        if identity not in self._papers:
            self._papers[identity] = self.workspace.bundle(identity)
        return self._papers[identity]

    def papers(self, **filters):
        page = 1
        values = []
        while True:
            result = self.workspace.papers(page=page, page_size=100, **filters)
            values.extend(view['paper'] for view in result['items'])
            if not result['has_next']:
                return values
            page += 1

    def year_bases(self):
        return {paper['id']: self.workspace.paper(paper['id'])['year_source'] for paper in self.papers()}
