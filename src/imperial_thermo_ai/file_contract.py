"""Planner wire contract, transcribed from supplied contract. SI: OpenAI Codex."""
from typing import Literal
from urllib.parse import urlsplit
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, allow_inf_nan=False)


class Variable(Strict):
    name: str = Field(min_length=1)
    unit: str | None = None
    numeric: bool | None = None


class FileRecord(Strict):
    file_id: str = Field(min_length=1)
    investigation_id: str = Field(min_length=1)
    title: str
    role: Literal['measurement', 'documentation', 'video', 'image', 'other']
    media_type: str
    retrieval_url: str | None = None
    source_page_url: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    run_ids: list[str] = Field(default_factory=list)
    variables: list[Variable] | None = None
    encoding: str | None = None
    data_notes: list[str] = Field(default_factory=list)
    conditions: dict[str, str | int | float | None] = Field(default_factory=dict)
    related_file_ids: list[str] = Field(default_factory=list)
    match_reason: str | None = None

    @field_validator('retrieval_url', 'source_page_url')
    @classmethod
    def url(cls, value):
        if value is not None and (urlsplit(value).scheme not in {'http', 'https'} or not urlsplit(value).netloc):
            raise ValueError('Expected an HTTP(S) URL.')
        return value

    @model_validator(mode='after')
    def unique_columns(self):
        names = [v.name for v in self.variables or []]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate column headers.')
        return self


class SearchResults(Strict):
    query_id: str = Field(min_length=1)
    files: list[FileRecord]

    @model_validator(mode='after')
    def unique_files(self):
        ids = [f.file_id for f in self.files]
        if len(ids) != len(set(ids)):
            raise ValueError('Duplicate file IDs.')
        return self
