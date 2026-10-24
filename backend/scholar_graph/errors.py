"""Safe failures: dependency exception text, credentials and PDF content are not logged."""


class PipelineError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message

    def envelope(self) -> dict:
        return {"error_code": self.code, "message": self.message, "details": None}
