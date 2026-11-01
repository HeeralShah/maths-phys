from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AnchorSpec(ContractModel):
    kind: Literal["block", "quote", "formula", "figure_region", "gap"]
    block_key: str | None = None
    after_key: str | None = None
    before_key: str | None = None
    exact_quote: str | None = None
    prefix: str | None = None
    suffix: str | None = None
    formula_label: str | None = None
    segment_hint: str | None = None
    bbox: list[float] | None = None

    @model_validator(mode="after")
    def required_coordinates(self) -> Self:
        if self.kind == "gap":
            if not self.after_key or not self.before_key or self.block_key:
                raise ValueError("gap anchors require after_key and before_key only")
        elif not self.block_key or self.after_key or self.before_key:
            raise ValueError(f"{self.kind} anchors require block_key")
        if self.kind == "quote" and not self.exact_quote:
            raise ValueError("quote anchors require exact_quote")
        if self.kind == "figure_region" and (not self.bbox or len(self.bbox) != 4):
            raise ValueError("figure_region anchors require a four-number bbox")
        if self.bbox is not None and len(self.bbox) != 4:
            raise ValueError("bbox must contain four numbers")
        return self


class SourceBlockSpec(ContractModel):
    stable_key: str = Field(min_length=1, max_length=200)
    parent_key: str | None = Field(default=None, max_length=200)
    ordinal: int = Field(ge=0)
    kind: Literal["heading", "paragraph", "equation", "figure", "table", "list", "example", "exercise", "footnote"]
    source_content: str = Field(min_length=1)
    source_locator: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)


class DerivationSegment(ContractModel):
    id: str = Field(min_length=1, max_length=100)
    latex: str = Field(min_length=1)
    label: str = ""


class DerivationRow(ContractModel):
    id: str = Field(min_length=1, max_length=100)
    segments: list[DerivationSegment] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_segments(self) -> Self:
        keys = [segment.id for segment in self.segments]
        if len(keys) != len(set(keys)):
            raise ValueError("derivation segment IDs must be unique within a row")
        return self


class DerivationCorrespondence(ContractModel):
    from_row: str
    from_segment: str
    to_row: str
    to_segment: str
    role: Literal["preserved", "introduced", "substituted", "moved", "cancelled", "differentiated", "integrated", "simplified"]


class DerivationRule(ContractModel):
    after_row: str
    label: str = Field(min_length=1)
    explanation: str = Field(min_length=1)
    provenance: list[dict[str, Any]] = Field(default_factory=list)


class DerivationPayload(ContractModel):
    rows: list[DerivationRow] = Field(min_length=2)
    correspondences: list[DerivationCorrespondence] = Field(default_factory=list)
    rules: list[DerivationRule] = Field(min_length=1)

    @model_validator(mode="after")
    def references_resolve(self) -> Self:
        rows = {row.id: {segment.id for segment in row.segments} for row in self.rows}
        if len(rows) != len(self.rows):
            raise ValueError("derivation row IDs must be unique")
        order = {row.id: i for i, row in enumerate(self.rows)}
        for link in self.correspondences:
            if link.from_row not in rows or link.from_segment not in rows[link.from_row]:
                raise ValueError("derivation correspondence source does not resolve")
            if link.to_row not in rows or link.to_segment not in rows[link.to_row]:
                raise ValueError("derivation correspondence target does not resolve")
            if order[link.to_row] <= order[link.from_row]:
                raise ValueError("derivation correspondences must point to a later row")
        for rule in self.rules:
            if rule.after_row not in rows:
                raise ValueError("derivation rule row does not resolve")
        return self


class AnnotationSpec(ContractModel):
    stable_key: str = Field(min_length=1, max_length=200)
    origin: Literal["historical", "generated", "learner"]
    intent: Literal[
        "step_bridge", "derivation", "reason", "assumption", "notation", "intuition",
        "sanity_check", "prerequisite", "cross_reference", "correction", "exercise",
        "definition", "reference", "warning"
    ]
    visual_role: Literal["green_issue_reference", "yellow_explanation", "blue_historical", "purple_exercise", "neutral"]
    placement: Literal["inline_after", "interlinear", "near_margin", "overlay", "collapsed_detail"]
    body: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    anchors: list[AnchorSpec] = Field(min_length=1)
    importance: Literal["essential", "helpful", "optional"] = "helpful"
    confidence: float | None = Field(default=None, ge=0, le=1)
    provenance: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def annotation_content(self) -> Self:
        if self.visual_role == "blue_historical" and self.origin != "historical":
            raise ValueError("blue annotations are historical learner marks; generated understanding is forbidden")
        if self.intent == "exercise" and self.visual_role != "purple_exercise":
            raise ValueError("source exercises use the purple exercise visual role")
        if self.intent in ("step_bridge", "derivation"):
            if self.placement != "interlinear":
                raise ValueError("step-bridge annotations must be interlinear")
            DerivationPayload.model_validate(self.payload)
        elif not self.body:
            raise ValueError("non-step-bridge annotations require body text")
        return self


class CheckableItemSpec(ContractModel):
    stable_key: str = Field(min_length=1, max_length=200)
    ordinal: int = Field(ge=0)
    item_kind: Literal["claim", "equation_group", "proof_move", "definition", "paragraph_cluster"]
    label: str = Field(min_length=1)
    anchors: list[AnchorSpec] = Field(min_length=1)
    material_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class CoverageSpec(ContractModel):
    represented_blocks: list[str] = Field(min_length=1)
    typed_omissions: list[dict[str, Any]] = Field(default_factory=list)


class ChapterPackage(ContractModel):
    schema_version: Literal[2]
    complete: Literal[True]
    publication_key: str = Field(min_length=1, max_length=300)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generator: str = Field(min_length=1)
    model: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    skill_versions: dict[str, str] = Field(default_factory=dict)
    blocks: list[SourceBlockSpec] = Field(min_length=1)
    annotations: list[AnnotationSpec] = Field(default_factory=list)
    checkable_items: list[CheckableItemSpec] = Field(min_length=1)
    coverage: CoverageSpec

    @model_validator(mode="after")
    def package_invariants(self) -> Self:
        block_keys = [block.stable_key for block in self.blocks]
        block_set = set(block_keys)
        if len(block_keys) != len(block_set):
            raise ValueError("source block stable keys must be unique")
        ordinals = [block.ordinal for block in self.blocks]
        if len(ordinals) != len(set(ordinals)):
            raise ValueError("source block ordinals must be unique")
        by_key = {block.stable_key: block for block in self.blocks}
        for block in self.blocks:
            if block.parent_key and block.parent_key not in block_set:
                raise ValueError("source block parent does not resolve")
            if block.parent_key == block.stable_key:
                raise ValueError("source block cannot parent itself")
            seen = {block.stable_key}
            parent = block.parent_key
            while parent:
                if parent in seen:
                    raise ValueError("source block parent hierarchy cannot contain a cycle")
                seen.add(parent)
                parent = by_key[parent].parent_key
        if set(self.coverage.represented_blocks) != block_set or len(self.coverage.represented_blocks) != len(block_set):
            raise ValueError("coverage must list every source block exactly once")

        annotation_keys = [item.stable_key for item in self.annotations]
        if len(annotation_keys) != len(set(annotation_keys)):
            raise ValueError("annotation stable keys must be unique")
        item_keys = [item.stable_key for item in self.checkable_items]
        if len(item_keys) != len(set(item_keys)):
            raise ValueError("checkable item stable keys must be unique")
        item_ordinals = [item.ordinal for item in self.checkable_items]
        if len(item_ordinals) != len(set(item_ordinals)):
            raise ValueError("checkable item ordinals must be unique")

        for annotation in self.annotations:
            self._validate_anchors(annotation.anchors, by_key)
        for item in self.checkable_items:
            self._validate_anchors(item.anchors, by_key)
        return self

    @staticmethod
    def _validate_anchors(anchors: list[AnchorSpec], blocks: dict[str, SourceBlockSpec]) -> None:
        for anchor in anchors:
            if anchor.kind == "gap":
                if anchor.after_key not in blocks or anchor.before_key not in blocks:
                    raise ValueError("gap anchor block does not resolve")
                if blocks[anchor.after_key].ordinal >= blocks[anchor.before_key].ordinal:
                    raise ValueError("gap anchors must follow source order")
                continue
            if anchor.block_key not in blocks:
                raise ValueError("anchor block does not resolve")
            block = blocks[anchor.block_key]
            if anchor.kind == "quote" and anchor.exact_quote not in block.source_content:
                raise ValueError("exact_quote is not present in its source block")
            if anchor.kind == "formula" and block.kind != "equation":
                raise ValueError("formula anchors must target an equation block")
            if anchor.kind == "figure_region" and block.kind not in ("figure", "table"):
                raise ValueError("figure_region anchors must target a figure or table")


class CheckInV2(ContractModel):
    understood: bool
    reconfirmation_reason: str = ""
    carried_from_check_id: str | None = None

