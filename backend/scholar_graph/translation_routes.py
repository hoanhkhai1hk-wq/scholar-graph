"""Translation input/output envelopes; not new persisted business contracts."""
from typing import Annotated, Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from .translation import Translator

Identifier = Annotated[str, StringConstraints(pattern=r'^[A-Za-z0-9][A-Za-z0-9._:-]*$', strict=True)]
Section = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000, strict=True)]


class TranslationRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scope: Literal['abstract', 'section', 'selection', 'full']
    target: Literal['zh','en'] = 'zh'
    source_translation: 'ChineseSource | None' = None
    section_path: list[Section] | None = Field(default=None, min_length=1, max_length=20)
    chunk_ids: list[Identifier] | None = Field(default=None, min_length=1, max_length=5000)

    @model_validator(mode='after')
    def selection_shape(self):
        if ((self.scope == 'section') != (self.section_path is not None) or
                (self.scope == 'selection') != (self.chunk_ids is not None)):
            raise ValueError('section仅接受section_path，selection仅接受chunk_ids。')
        if self.chunk_ids is not None and len(set(self.chunk_ids)) != len(self.chunk_ids):
            raise ValueError('选区Chunk不可重复。')
        if self.target=='en' and self.scope not in ('abstract','full'):
            raise ValueError('中→英仅支持摘要与全文。')
        if self.target=='zh' and self.source_translation is not None:
            raise ValueError('英→中不接受中文源响应。')
        return self


class TranslatedSegment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source_chunk_id: str
    source_text: str
    translated_text: str
    paper_id: str
    page_number: int
    section_path: list[str]
    type: Literal['text', 'table', 'figure', 'formula']


class TranslationResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    paper_id: str
    scope: Literal['abstract', 'section', 'selection', 'full']
    target: Literal['zh','en']
    segments: list[TranslatedSegment]
    markdown: str | None
    metadata: dict


class ChineseSource(TranslationResponse):
    target: Literal['zh']


TranslationRequest.model_rebuild()


def translation_routes(repository):
    router = APIRouter(prefix='/api/v1')

    @router.post('/papers/{paper_id}/translate', response_model=TranslationResponse)
    def translate(paper_id: str, body: TranslationRequest):
        return Translator(repository).translate(paper_id, **body.model_dump())

    return router
