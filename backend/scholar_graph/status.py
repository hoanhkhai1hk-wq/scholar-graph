"""Single-job ParseStatus state machine; state snapshots use the published v1.1 schema."""

from copy import deepcopy

from .errors import PipelineError
from .validation import ContractGate


class ParseJob:
    NEXT = {"queued": {"parsing", "failed"}, "parsing": {"ocr", "indexing", "failed"},
            "ocr": {"indexing", "failed"}, "indexing": {"completed", "failed"},
            "completed": set(), "failed": set()}

    def __init__(self, paper_id: str, gate: ContractGate, publish=None):
        self.gate, self.publish = gate, publish
        self.history = []
        self._append({"schema_version": "1.1.0", "paper_id": paper_id,
                      "status": "queued", "progress": 0, "current_stage": "等待解析",
                      "error_code": None, "error_message": None})

    @property
    def current(self):
        return deepcopy(self.history[-1])

    def _append(self, record):
        self.gate.record("ParseStatus", record)
        updated = self.history + [deepcopy(record)]
        if self.publish:
            self.publish(updated)
        self.history = updated

    def move(self, target: str, stage: str, *, progress: int | None = None,
             error: PipelineError | None = None):
        old = self.current
        same_active = target == old["status"] and target in {"parsing", "ocr", "indexing"}
        if not same_active and target not in self.NEXT[old["status"]]:
            raise PipelineError("VALIDATION_ERROR", "非法解析状态迁移。")
        value = old["progress"] if progress is None else progress
        if target == "completed":
            if progress not in (None, 100):
                raise PipelineError("VALIDATION_ERROR", "完成状态必须为 100。")
            value = 100
        elif target == "failed":
            if error is None or (progress is not None and progress != old["progress"]):
                raise PipelineError("VALIDATION_ERROR", "失败必须带错误且保留原进度。")
        elif value < old["progress"]:
            raise PipelineError("VALIDATION_ERROR", "解析进度不能倒退。")
        if target != "failed" and error is not None:
            raise PipelineError("VALIDATION_ERROR", "成功或进行中状态不能携带错误。")
        self._append({**old, "status": target, "progress": value, "current_stage": stage,
                      "error_code": error.code if error else None,
                      "error_message": error.message if error else None})
        return self.current
