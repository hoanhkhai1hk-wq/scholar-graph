"""V2 scheduled discovery uses operational metadata and never rewrites source records."""
from .workspace_repository import WorkspaceRepository
from .tracking import TrackingService


class WorkspaceTracking:
    def __init__(self, workspace, fetcher):
        self.workspace, self.fetcher = workspace, fetcher
        self.repository = WorkspaceRepository(workspace)

    def run(self, **parameters):
        # A new view per run avoids stale metadata after correction or ingestion.
        service = TrackingService(WorkspaceRepository(self.workspace), self.fetcher, read_only_sources=True)
        return service.run(**parameters)

    def status(self):
        return TrackingService(self.repository, self.fetcher, read_only_sources=True).status()
