"""Input and output contracts. SI-assisted code; reviewed through automated tests."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Variable(Contract):
    name: str = Field(min_length=1)
    unit: str | None = None
    numeric: bool | None = None


class FileRecord(Contract):
    file_id: str = Field(min_length=1)
    investigation_id: str = Field(min_length=1)
    run_ids: list[str] = Field(default_factory=list)
    title: str
    role: Literal["measurement", "documentation", "video", "image", "other"]
    media_type: str
    size_bytes: int | None = Field(default=None, ge=0)
    retrieval_url: HttpUrl | None = None
    source_page_url: HttpUrl | None = None
    variables: list[Variable] | None = None
    encoding: str | None = None
    data_notes: list[str] = Field(default_factory=list)
    conditions: dict[str, str | float | None] = Field(default_factory=dict)
    related_file_ids: list[str] = Field(default_factory=list)
    match_reason: str | None = None

    @model_validator(mode="after")
    def unique_variables(self):
        names = [variable.name for variable in self.variables or []]
        if len(names) != len(set(names)):
            raise ValueError("Variable names must be unique within a file")
        return self


class SearchResults(Contract):
    query_id: str = Field(min_length=1)
    files: list[FileRecord]

    @model_validator(mode="after")
    def unique_files(self):
        ids = [file.file_id for file in self.files]
        if len(ids) != len(set(ids)):
            raise ValueError("Search results contain duplicate file IDs")
        return self


class PlotParameters(Contract):
    x: str
    y: str


class PlotOperation(Contract):
    name: Literal["plot_relationship"]
    file_id: str
    parameters: PlotParameters


class Plan(Contract):
    """All fields required so this is also an API Structured Outputs schema."""

    action: Literal["inspect_files", "calculate", "retrieve_assets", "no_match"]
    selected_file_ids: list[str]
    requested_asset_ids: list[str]
    operation: PlotOperation | None
    explanation: str
    warnings: list[str]


class ExecutionLimits(Contract):
    max_download_bytes: int = Field(default=100_000_000, gt=0)
    max_runtime_seconds: int = Field(default=60, gt=0)


class ServiceRequest(Contract):
    schema_version: Literal["1.0"] = "1.0"
    query_id: str
    plan: Plan
    limits: ExecutionLimits = Field(default_factory=ExecutionLimits)
    generated_by: Literal["SI-assisted request planner"] = "SI-assisted request planner"

