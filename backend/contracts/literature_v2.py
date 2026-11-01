from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class WorkSpec(ContractModel):
    local_key: str = Field(min_length=1, max_length=200)
    work_type: Literal["paper", "book", "thesis", "notes", "proceedings", "other"]
    title: str = Field(min_length=1)
    authors: list[str] = Field(default_factory=list)
    year: int | None = Field(default=None, ge=1400, le=2200)
    venue: str = ""
    doi: str | None = None
    arxiv_id: str | None = None
    isbn: str | None = None
    external_ids: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    abstract: str = ""
    metadata_provenance: dict[str, Any] = Field(default_factory=dict)


class MapWorkSpec(ContractModel):
    work_key: str
    roles: list[Literal["focal", "foundation", "predecessor", "contemporary", "downstream", "explanatory"]] = Field(min_length=1)
    importance_reason: str = Field(min_length=1)
    lane: Literal["focal", "foundation", "predecessor", "contemporary", "downstream", "explanatory"]


class EvidenceSpec(ContractModel):
    local_key: str = Field(min_length=1, max_length=200)
    work_key: str | None = None
    source_id: str | None = None
    evidence_kind: Literal["direct_text", "bibliographic_metadata", "provider_metadata"]
    locator: str = ""
    quote: str = ""
    url: str | None = None
    provider_identifier: str | None = None
    retrieved_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def sufficient_evidence(self) -> Self:
        if not any((self.work_key, self.source_id, self.url, self.provider_identifier)):
            raise ValueError("evidence must identify a work, source, URL, or provider record")
        if self.evidence_kind == "direct_text" and (not self.quote or not self.locator):
            raise ValueError("direct_text evidence requires quote and locator")
        if self.evidence_kind != "direct_text" and not any((self.quote, self.provider_identifier, self.url)):
            raise ValueError("metadata evidence requires a quote, provider identifier, or URL")
        return self


class PaperRecordSpec(ContractModel):
    stable_key: str = Field(min_length=1, max_length=200)
    record_type: Literal["section_summary", "contribution", "result", "method", "assumption", "limitation", "notation"]
    label: str = Field(min_length=1)
    claim: str = Field(min_length=1)
    section_label: str = ""
    locator: dict[str, Any]
    evidence_keys: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RelationshipContextSpec(ContractModel):
    section_label: str = ""
    paper_record_key: str | None = None
    source_anchor: dict[str, Any] = Field(default_factory=dict)


class RelationshipSpec(ContractModel):
    stable_key: str = Field(min_length=1, max_length=200)
    from_work_key: str
    to_work_key: str
    relationship_class: Literal["citation", "intellectual"]
    relation_type: Literal[
        "cites", "cited_by", "uses_result_from", "uses_method_from", "extends",
        "applies", "generalises", "contrasts", "replicates", "corrects"
    ]
    claim: str = Field(min_length=1)
    epistemic_status: Literal["bibliographic_fact", "stated", "inferred"]
    citation_status: Literal["cites", "does_not_cite", "unknown"]
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence_keys: list[str] = Field(min_length=1)
    contexts: list[RelationshipContextSpec] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LiteratureMapPackage(ContractModel):
    schema_version: Literal[2]
    complete: Literal[True]
    publication_key: str = Field(min_length=1, max_length=300)
    focal_work_key: str
    generator: str = Field(min_length=1)
    model: str = Field(min_length=1)
    works: list[WorkSpec] = Field(min_length=1)
    map_works: list[MapWorkSpec] = Field(min_length=1)
    evidence: list[EvidenceSpec] = Field(min_length=1)
    paper_records: list[PaperRecordSpec] = Field(default_factory=list)
    relationships: list[RelationshipSpec] = Field(default_factory=list)
    research_scope: dict[str, Any]
    cutoff_reason: str = Field(min_length=1)
    provider_provenance: dict[str, Any]
    edition_id: str | None = None

    @model_validator(mode="after")
    def map_invariants(self) -> Self:
        work_keys = [work.local_key for work in self.works]
        works = {work.local_key: work for work in self.works}
        if len(work_keys) != len(works):
            raise ValueError("work local keys must be unique")
        if self.focal_work_key not in works:
            raise ValueError("focal work does not resolve")
        explicit_identities = []
        for work in self.works:
            if work.doi:
                explicit_identities.append("doi:" + work.doi.casefold().strip())
            elif work.arxiv_id:
                explicit_identities.append("arxiv:" + work.arxiv_id.casefold().strip())
            elif work.isbn:
                explicit_identities.append("isbn:" + work.isbn.casefold().strip())
        if len(explicit_identities) != len(set(explicit_identities)):
            raise ValueError("works must have distinct bibliographic identities")
        map_keys = [node.work_key for node in self.map_works]
        if len(map_keys) != len(set(map_keys)) or set(map_keys) != set(works):
            raise ValueError("map_works must contain every work exactly once")
        focal = [node for node in self.map_works if "focal" in node.roles]
        if len(focal) != 1 or focal[0].work_key != self.focal_work_key or focal[0].lane != "focal":
            raise ValueError("the map requires exactly one matching focal work")
        if not self.research_scope or not self.provider_provenance:
            raise ValueError("research_scope and provider_provenance cannot be empty")

        evidence_keys = [item.local_key for item in self.evidence]
        evidence = {item.local_key: item for item in self.evidence}
        if len(evidence_keys) != len(evidence):
            raise ValueError("evidence local keys must be unique")
        for item in self.evidence:
            if item.work_key and item.work_key not in works:
                raise ValueError("evidence work does not resolve")

        record_keys = [record.stable_key for record in self.paper_records]
        records = set(record_keys)
        if len(record_keys) != len(records):
            raise ValueError("paper record stable keys must be unique")
        for record in self.paper_records:
            if any(key not in evidence for key in record.evidence_keys):
                raise ValueError("paper record evidence does not resolve")

        relationship_keys = [item.stable_key for item in self.relationships]
        if len(relationship_keys) != len(set(relationship_keys)):
            raise ValueError("relationship stable keys must be unique")
        citation_types = {"cites", "cited_by"}
        intellectual_types = {"uses_result_from", "uses_method_from", "extends", "applies", "generalises", "contrasts", "replicates", "corrects"}
        for relation in self.relationships:
            if relation.from_work_key not in works or relation.to_work_key not in works:
                raise ValueError("literature relationship endpoint is not a work")
            if relation.from_work_key == relation.to_work_key:
                raise ValueError("literature relationships cannot be self-links")
            if any(key not in evidence for key in relation.evidence_keys):
                raise ValueError("relationship evidence does not resolve")
            if any(context.paper_record_key and context.paper_record_key not in records for context in relation.contexts):
                raise ValueError("relationship context paper record does not resolve")
            linked_evidence = [evidence[key] for key in relation.evidence_keys]
            if relation.relationship_class == "citation":
                if relation.relation_type not in citation_types or relation.epistemic_status != "bibliographic_fact" or relation.citation_status != "cites":
                    raise ValueError("citation relationships must remain bibliographic facts")
            else:
                if relation.relation_type not in intellectual_types or relation.epistemic_status == "bibliographic_fact":
                    raise ValueError("intellectual relationships must be stated or inferred, not bare citations")
                if not any(item.evidence_kind == "direct_text" for item in linked_evidence):
                    raise ValueError("intellectual relationships require direct-text evidence beyond citation metadata")
        return self

