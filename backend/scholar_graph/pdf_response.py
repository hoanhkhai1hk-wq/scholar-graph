"""Keep framework Range errors in ScholarGraph's existing three-field envelope."""
from starlette.responses import FileResponse, JSONResponse


class PdfResponse(FileResponse):
    async def __call__(self, scope, receive, send):
        failure = None
        headers = {}
        async def forward(message):
            nonlocal failure
            if message["type"] == "http.response.start" and message["status"] in {400, 416}:
                failure = message["status"]
                headers.update((key.decode("latin-1"), value.decode("latin-1"))
                               for key, value in message["headers"] if key.lower() == b"content-range")
            elif failure is not None:
                if message["type"] == "http.response.body" and not message.get("more_body", False):
                    await JSONResponse({"error_code": "VALIDATION_ERROR", "message": "PDF 字节范围请求不合法。", "details": None},
                                       status_code=failure, headers=headers)(scope, receive, send)
            else:
                await send(message)
        await super().__call__(scope, receive, forward)
