"""Safe failures: dependency exception text, credentials and PDF content are not logged."""


class PipelineError(Exception):
    def __init__(self, code: str, message: str, *, details=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details

    def envelope(self) -> dict:
        return {"error_code": self.code, "message": self.message, "details": self.details}
