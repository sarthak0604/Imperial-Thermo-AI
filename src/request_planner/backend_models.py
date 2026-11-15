"""Version 2 internal contracts; the version 1 file/response adapters remain available."""

from typing import Literal

from pydantic import Field

from .models import Contract, FileRecord, FrontendResponse


class Requirement(Contract):
    id: str
    kind: Literal[
        "calculation",
        "chart",
        "inspection",
        "document",
        "video",
        "image",
        "explanation",
        "discovery",
    ]
    source_text: str
    model_id: str | None = None


class RequestSpec(Contract):
    schema_version: Literal["2.0"] = "2.0"
    original_prompt: str = Field(min_length=1, max_length=12000)
    requirements: list[Requirement]
    investigations: list[str] = Field(default_factory=list)
    excluded_investigations: list[str] = Field(default_factory=list)
    clarifications: list[str] = Field(default_factory=list)
    context: dict = Field(default_factory=dict)
    semantic_plan: dict | None = None
    explicit_conditions: list[str] = Field(default_factory=list)


class EvidenceItem(Contract):
    id: str
    file_id: str
    investigation_id: str
    title: str
    text: str
    locator: str
    source_url: str
    sha256: str
    review_status: str


class RetrievalBundle(Contract):
    schema_version: Literal["2.0"] = "2.0"
    query_id: str
    graph_id: str
    files: list[FileRecord]
    evidence: list[EvidenceItem] = Field(default_factory=list)
    coverage: dict = Field(default_factory=dict)
    diagnostics: list[dict] = Field(default_factory=list)
    trusted_source_hashes: dict[str, str] = Field(default_factory=dict)


class AnswerResult(Contract):
    schema_version: Literal["2.0"] = "2.0"
    trace_id: str
    status: Literal[
        "completed", "partial", "needs_input", "no_evidence", "unsupported", "error"
    ]
    message: str
    request: RequestSpec
    retrieval: RetrievalBundle
    result: FrontendResponse
    fulfilment: list[dict]
    claims: list[dict] = Field(default_factory=list)
    timings: dict = Field(default_factory=dict)

    def frontend(self):
        """Omri answer contract, including actual result blocks and precise source locators."""
        evidence = [
            {
                "file_id": e.file_id,
                "psi_id": e.investigation_id,
                "note": e.title + " — " + e.locator,
                "url": e.source_url,
                "evidence_id": e.id,
                "review_status": e.review_status,
            }
            for e in self.retrieval.evidence
            if any(e.id in c["evidence_ids"] for c in self.claims)
        ]
        evidence += [
            {
                "file_id": s.get("file_id"),
                "psi_id": s.get("investigation_id"),
                "note": s.get("title"),
                "url": s.get("source_page_url")
                or next(
                    (
                        str(f.source_page_url or f.retrieval_url or "")
                        for f in self.retrieval.files
                        if f.file_id == s.get("file_id")
                    ),
                    "",
                ),
            }
            for s in self.result.sources
        ]
        return {
            "summary": self.message,
            "answer": self.message,
            "blocks": self.result.blocks,
            "evidence": evidence,
            "points": [
                {"text": c["text"], "psi_ids": c.get("psi_ids", []), "charts": []}
                for c in self.claims
            ],
            "widgets": [],
            "limitations": "\n\n".join(
                self.result.warnings + self.request.clarifications
            ),
            "fulfilment": self.fulfilment,
            "meta": {
                "source": "live",
                "provider": "thermo",
                "status": self.status,
                "trace_id": self.trace_id,
                "seconds": self.timings.get("total"),
                "schema_version": "2.0",
            },
        }
