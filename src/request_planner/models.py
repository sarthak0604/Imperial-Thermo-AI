"""Input and output contracts. SI-assisted code; reviewed through automated tests."""

from typing import Literal
from typing_extensions import NotRequired, TypedDict

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


class ColumnBinding(Contract):
    column: str
    field: str
    unit: str


class DatasetBinding(Contract):
    """Copy measured CSV values into an existing JSON input slot, without conversion."""

    target: str = Field(pattern=r"^/")
    mode: Literal["scalar", "series", "records"]
    columns: list[ColumnBinding] = Field(min_length=1)
    row: int | None = Field(ge=0)


class ThermoParameters(Contract):
    model_id: Literal[
        "THM-01", "THM-02", "THM-03", "THM-04", "THM-05", "THM-06", "THM-07",
        "THM-08", "THM-09", "THM-10", "THM-11", "THM-12", "THM-13", "THM-14",
        "THM-15", "THM-16", "THM-17", "THM-18", "THM-19", "THM-20",
    ]
    # JSON strings keep the provider schema strict despite differing THM inputs.
    request_json: str | None
    template_file_id: str | None
    bindings: list[DatasetBinding]


class ThermoOperation(Contract):
    name: Literal["run_thermo_model"]
    file_id: str
    parameters: ThermoParameters


class Plan(Contract):
    """All fields required so this is also an API Structured Outputs schema."""

    action: Literal["inspect_files", "calculate", "retrieve_assets", "no_match"]
    selected_file_ids: list[str]
    requested_asset_ids: list[str]
    operation: PlotOperation | ThermoOperation | None
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


class ChartAxis(TypedDict):
    label: str
    unit: str | None
    values: list[float]


class CalculationBlock(TypedDict):
    type: Literal["calculation"]
    model_id: str
    evidence_type: Literal["data_reduction", "model_estimate"]
    illustrative: bool | None
    source_file_ids: list[str]
    data: dict
    task_id: NotRequired[str]
    input_json: NotRequired[dict]
    input_provenance: NotRequired[list[dict]]
    depends_on: NotRequired[list[str]]
    method: NotRequired[dict]


class ChartBlock(TypedDict):
    type: Literal["chart"]
    chart_type: Literal["line", "scatter", "bar"]
    categories: NotRequired[list[str]]
    title: str
    x: ChartAxis
    series: list[ChartAxis]
    evidence_type: Literal["measured", "data_reduction", "model_estimate"]
    illustrative: NotRequired[bool | None]
    source_file_ids: list[str]


class MediaBlock(TypedDict):
    type: Literal["video", "document", "image"]
    file_id: str
    title: str
    media_type: str
    url: str
    source_page_url: str | None


class InspectionBlock(TypedDict):
    type: Literal["inspection"]
    file_id: str
    kind: Literal["table", "json", "unsupported"]
    columns: NotRequired[list[dict]]
    row_count: NotRequired[int]
    preview: NotRequired[dict | list]
    message: NotRequired[str]
    media_type: NotRequired[str]
    note: NotRequired[str]


class FrontendResponse(Contract):
    schema_version: Literal["1.0"] = "1.0"
    query_id: str
    status: Literal["completed", "needs_input", "no_match", "error"]
    message: str
    requests: list[ServiceRequest] = Field(default_factory=list)
    blocks: list[CalculationBlock | ChartBlock | MediaBlock | InspectionBlock] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)
    generated_by: str = "SI-assisted planner; deterministic Python execution"

