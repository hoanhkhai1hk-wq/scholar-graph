"""Transient topology transport; no new persisted business schema."""
from typing import Annotated,Literal
from fastapi import APIRouter
from pydantic import BaseModel,ConfigDict,Field,StringConstraints,model_validator
from .topology import generate_topology

Text = Annotated[str,StringConstraints(strip_whitespace=True,min_length=1,max_length=200,pattern=r'^[^\x00-\x1f]+$',strict=True)]
Identity = Annotated[str,StringConstraints(pattern=r'^[A-Za-z][A-Za-z0-9_-]{0,63}$',strict=True)]


class Node(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: Identity
    label: Text
    source_chunk_ids: list[str] = Field(min_length=1,max_length=20)
    column: int = Field(default=0,ge=0,le=10)
    row: int | None = Field(default=None,ge=0,le=100)


class Edge(BaseModel):
    model_config = ConfigDict(extra='forbid')
    from_id: Identity
    to_id: Identity
    label: Text
    source_chunk_ids: list[str] = Field(min_length=1,max_length=20)


class Logic(BaseModel):
    model_config = ConfigDict(extra='forbid')
    nodes: list[Node] = Field(min_length=1,max_length=100)
    edges: list[Edge] = Field(max_length=200)


class TopologyRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    paper_ids: list[str] = Field(min_length=1,max_length=20)
    logic: Logic | None = None
    framework: dict | None = None
    formats: list[Literal['tikz','dot','mermaid','matplotlib']] = Field(default_factory=lambda:['tikz','dot','mermaid'],min_length=1,max_length=4)

    @model_validator(mode='after')
    def one_source(self):
        if (self.logic is None) == (self.framework is None) or len(set(self.formats)) != len(self.formats):
            raise ValueError('提供logic或framework二选一，格式不可重复。')
        return self


def topology_routes(repository):
    router=APIRouter(prefix='/api/v1')
    @router.post('/topologies')
    def generate(body:TopologyRequest):
        return generate_topology(repository,body)
    return router
