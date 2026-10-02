from datetime import UTC, datetime, timedelta

from app.agent.context.contracts import (
    AmbiguousReference, ContextIdentityReader, ContextResolverInput, ObjectRef,
    CurrentTurnMaterialType, MaterialSatisfiedReference,
    ResolutionSource, ResolutionTrace, ResolvedContext, ResolvedObjectType,
    ResolvedReference, StructuredContext, TrustedContextRef, UnresolvedReference,
)
from app.agent.schemas.semantic import Intent, SemanticReference, SemanticReferenceType


TYPE_MAP = {
    SemanticReferenceType.RECENT_RESEARCH: ResolvedObjectType.RESEARCH,
    SemanticReferenceType.ACTIVE_RESEARCH: ResolvedObjectType.RESEARCH,
    SemanticReferenceType.ACTIVE_STRATEGY: ResolvedObjectType.CONTENT_STRATEGY,
    SemanticReferenceType.ACTIVE_DRAFT: ResolvedObjectType.DRAFT,
    SemanticReferenceType.RECENT_DRAFT: ResolvedObjectType.DRAFT,
    SemanticReferenceType.ACTIVE_PUBLISHED_NOTE: ResolvedObjectType.PUBLISHED_NOTE,
    SemanticReferenceType.RECENT_RUN: ResolvedObjectType.RUN,
    SemanticReferenceType.PROFILE: ResolvedObjectType.ACCOUNT,
    SemanticReferenceType.ACCOUNT: ResolvedObjectType.ACCOUNT,
}

EXPECTED_CONTEXT_TYPE = {
    Intent.CONTENT_STRATEGY: ResolvedObjectType.RESEARCH,
    Intent.CONTENT_CREATE: ResolvedObjectType.CONTENT_OPPORTUNITY,
    Intent.CONTENT_REFINE: ResolvedObjectType.DRAFT,
    Intent.POST_PUBLISH_REVIEW: ResolvedObjectType.PUBLISHED_NOTE,
}

DEICTIC_REFERENCES = frozenset({"这个", "这个选题", "刚才选的这个", "它"})


class ContextResolver:
    """只解析可信结构化引用，不规划、不执行、不读取 Evidence。"""

    def __init__(self, reader: ContextIdentityReader, *, now=None):
        self.reader = reader
        self.now = now or (lambda: datetime.now(UTC))

    def resolve(self, data: ContextResolverInput) -> ResolvedContext:
        out = ResolvedContext(account_ref=data.account_ref)
        for semantic in data.semantic_frame.references:
            self._resolve_one(data, semantic, out)
        self._resolve_required_context(data, out)
        out.blocking_missing_info.extend(
            [f"{item.raw_text}: {item.reason}" for item in (*out.unresolved_references, *out.ambiguous_references)]
        )
        self._facts(out)
        return out

    def _resolve_required_context(self, data, out):
        """Use one trusted explicit/workspace candidate when semantic output omits the required reference."""
        object_type = EXPECTED_CONTEXT_TYPE.get(data.semantic_frame.primary_intent)
        if object_type is None:
            return
        if any(item.resolved_object_type == object_type for item in out.resolved_references):
            return
        if out.unresolved_references or out.ambiguous_references:
            return

        semantic = SemanticReference(
            type=SemanticReferenceType.UNKNOWN,
            raw_text=f"{data.semantic_frame.primary_intent.value}:required_context",
        )
        levels = (
            (data.explicit_references, ResolutionSource.EXPLICIT_SELECTION, 1),
            (data.workspace_selection.references, ResolutionSource.WORKSPACE_SELECTION, 2),
        )
        for refs, source, priority in levels:
            candidates = [item for item in refs if item.ref.type == object_type]
            if candidates:
                return self._trusted(semantic, candidates, source, priority, data, out)

    def _resolve_one(self, data, semantic, out):
        if semantic.type in {SemanticReferenceType.PROFILE, SemanticReferenceType.ACCOUNT}:
            return self._account_material(data, semantic, out)
        if semantic.type == SemanticReferenceType.UNKNOWN and semantic.raw_text.strip() in DEICTIC_REFERENCES:
            if data.semantic_frame.primary_intent == Intent.RESEARCH and data.current_turn_materials:
                return self._material_candidates(data, semantic, out)
            return self._deictic(data, semantic, out)
        if semantic.type == SemanticReferenceType.ORDINAL_OPPORTUNITY:
            return self._ordinal(data, semantic, out)
        if semantic.type == SemanticReferenceType.TEMPORAL_PUBLISHED_NOTE:
            return self._temporal(data, semantic, out)
        if semantic.type == SemanticReferenceType.LATEST_PUBLISHED_NOTE:
            record = self.reader.latest_published(data.account_ref)
            return self._records(semantic, [record] if record else [], ResolutionSource.TEMPORAL_SELECTION, 8, data, out, "PUBLISHED_NOTE_NOT_FOUND")
        object_type = TYPE_MAP.get(semantic.type)
        if object_type is None:
            return self._unresolved(semantic, "REFERENCE_CONTEXT_MISSING", out)
        levels = [
            (data.explicit_references, ResolutionSource.EXPLICIT_SELECTION, 1),
            (data.workspace_selection.references, ResolutionSource.WORKSPACE_SELECTION, 2),
            ((data.pending_context.references if data.pending_context else []), ResolutionSource.PENDING_CONTEXT, 3),
            (data.active_context.references, ResolutionSource.ACTIVE_CONTEXT, 4),
            (data.conversation_context.references, ResolutionSource.RECENT_CONVERSATION, 5),
            (data.history_context.references, ResolutionSource.HISTORY, 6),
        ]
        for refs, source, priority in levels:
            candidates = [item for item in refs if item.ref.type == object_type]
            if candidates:
                return self._trusted(semantic, candidates, source, priority, data, out)
        return self._unresolved(semantic, "REFERENCE_CONTEXT_MISSING", out)

    def _account_material(self, data, semantic, out):
        """Resolve current-turn canonical Account refs first, then authorized Profile material."""
        explicit = [item for item in data.explicit_references if item.ref.type == ResolvedObjectType.ACCOUNT]
        materials = [item for item in data.current_turn_materials if item.type == CurrentTurnMaterialType.PROFILE]
        if explicit:
            records = [self.reader.get_identity(item.ref) for item in explicit if item.account_ref == data.account_ref]
            known = [record for record in records if record and record.account_ref == data.account_ref]
            if len(known) == 1 and len(materials) == 1 and known[0].external_identity and known[0].external_identity != materials[0].external_identity:
                out.ambiguous_references.append(AmbiguousReference(
                    reference_type=semantic.type, raw_text=semantic.raw_text,
                    candidate_refs=[known[0].ref], candidate_materials=[materials[0].external_identity],
                    reason="EXPLICIT_MATERIAL_CONFLICT",
                ))
                return
            return self._trusted(semantic, explicit, ResolutionSource.EXPLICIT_SELECTION, 1, data, out)
        if materials:
            return self._material_candidates(data, semantic, out)
        levels = [
            (data.workspace_selection.references, ResolutionSource.WORKSPACE_SELECTION, 2),
            ((data.pending_context.references if data.pending_context else []), ResolutionSource.PENDING_CONTEXT, 3),
            (data.active_context.references, ResolutionSource.ACTIVE_CONTEXT, 4),
            (data.conversation_context.references, ResolutionSource.RECENT_CONVERSATION, 5),
            (data.history_context.references, ResolutionSource.HISTORY, 6),
        ]
        for refs, source, priority in levels:
            candidates = [item for item in refs if item.ref.type == ResolvedObjectType.ACCOUNT]
            if candidates:
                return self._trusted(semantic, candidates, source, priority, data, out)
        return self._unresolved(semantic, "REFERENCE_CONTEXT_MISSING", out)

    def _material_candidates(self, data, semantic, out):
        candidates = [item for item in data.current_turn_materials if item.type == CurrentTurnMaterialType.PROFILE]
        if any(item.account_ref != data.account_ref for item in candidates):
            return self._unresolved(semantic, "CONTEXT_ACCOUNT_MISMATCH", out)
        unique = {item.external_identity: item for item in candidates}
        out.resolution_trace.append(ResolutionTrace(
            raw_text=semantic.raw_text, source=ResolutionSource.CURRENT_TURN_MATERIAL,
            priority=1, candidate_count=len(unique),
        ))
        if len(unique) > 1:
            out.ambiguous_references.append(AmbiguousReference(
                reference_type=semantic.type, raw_text=semantic.raw_text,
                candidate_refs=[], candidate_materials=list(unique)[:10],
                reason="MULTIPLE_VALID_CANDIDATES",
            ))
            return
        if not unique:
            return self._unresolved(semantic, "REFERENCE_CONTEXT_MISSING", out)
        item = next(iter(unique.values()))
        out.material_satisfied_references.append(MaterialSatisfiedReference(
            reference_type=semantic.type, raw_text=semantic.raw_text,
            material_type=item.type, external_identity=item.external_identity,
        ))

    def _deictic(self, data, semantic, out):
        """Resolve a bounded contextual reference using the intent's required object type."""
        object_type = EXPECTED_CONTEXT_TYPE.get(data.semantic_frame.primary_intent)
        if object_type is None:
            return self._unresolved(semantic, "REFERENCE_CONTEXT_MISSING", out)
        levels = [
            (data.explicit_references, ResolutionSource.EXPLICIT_SELECTION, 1),
            (data.workspace_selection.references, ResolutionSource.WORKSPACE_SELECTION, 2),
            ((data.pending_context.references if data.pending_context else []), ResolutionSource.PENDING_CONTEXT, 3),
            (data.active_context.references, ResolutionSource.ACTIVE_CONTEXT, 4),
            (data.conversation_context.references, ResolutionSource.RECENT_CONVERSATION, 5),
            (data.history_context.references, ResolutionSource.HISTORY, 6),
        ]
        for refs, source, priority in levels:
            candidates = [item for item in refs if item.ref.type == object_type]
            if not candidates:
                continue
            before = len(out.resolved_references)
            self._trusted(semantic, candidates, source, priority, data, out)
            if object_type == ResolvedObjectType.CONTENT_OPPORTUNITY and len(out.resolved_references) > before:
                self._set_strategy_for_opportunity(data, out.resolved_references[-1].resolved_ref, out)
            return
        return self._unresolved(semantic, "REFERENCE_CONTEXT_MISSING", out)

    @staticmethod
    def _set_strategy_for_opportunity(data, opportunity_ref, out):
        contexts = [
            data.workspace_selection,
            data.pending_context,
            data.active_context,
            data.conversation_context,
            data.history_context,
        ]
        matches = []
        for context in contexts:
            if context is None:
                continue
            matches = [
                collection.strategy_ref
                for collection in context.opportunity_collections
                if opportunity_ref in [item.ref for item in collection.opportunity_refs]
            ]
            if matches:
                break
        if len(matches) == 1 and matches[0].account_ref == data.account_ref:
            out.context_facts["active_strategy_ref"] = matches[0].ref

    def _trusted(self, semantic, candidates, source, priority, data, out):
        mismatch = any(item.account_ref != data.account_ref for item in candidates)
        valid = []
        for item in candidates:
            record = self.reader.get_identity(item.ref)
            if item.account_ref == data.account_ref and record and record.account_ref == data.account_ref:
                valid.append(record)
            elif record and record.account_ref != data.account_ref:
                mismatch = True
        if not valid:
            return self._unresolved(semantic, "CONTEXT_ACCOUNT_MISMATCH" if mismatch else "REFERENCE_NOT_FOUND", out)
        return self._records(semantic, valid, source, priority, data, out, "REFERENCE_NOT_FOUND")

    def _records(self, semantic, records, source, priority, data, out, empty_reason, strategy_ref=None):
        unique = {f"{r.ref.type}:{r.ref.id}": r for r in records if r is not None}
        records = list(unique.values())
        out.resolution_trace.append(ResolutionTrace(raw_text=semantic.raw_text, source=source, priority=priority, candidate_count=len(records), context_strategy_ref=strategy_ref))
        if not records:
            return self._unresolved(semantic, empty_reason, out)
        if len(records) > 1:
            out.ambiguous_references.append(AmbiguousReference(reference_type=semantic.type, raw_text=semantic.raw_text, candidate_refs=[r.ref for r in records[:10]], reason="MULTIPLE_VALID_CANDIDATES"))
            return
        record = records[0]
        if record.account_ref != data.account_ref:
            return self._unresolved(semantic, "CONTEXT_ACCOUNT_MISMATCH", out)
        out.resolved_references.append(ResolvedReference(reference_type=semantic.type, raw_text=semantic.raw_text, resolved_ref=record.ref, resolved_object_type=record.ref.type, resolution_source=source, confidence=1))

    def _ordinal(self, data, semantic, out):
        ordinal = semantic.ordinal
        if ordinal is None:
            return self._unresolved(semantic, "ORDINAL_MISSING", out)
        contexts = [data.workspace_selection, data.pending_context, data.active_context, data.conversation_context, data.history_context]
        collections = []
        for context in contexts:
            if context and context.opportunity_collections:
                collections = context.opportunity_collections
                break
        if not collections:
            return self._unresolved(semantic, "REFERENCE_CONTEXT_MISSING", out)
        if len(collections) > 1:
            refs = [c.opportunity_refs[ordinal - 1].ref for c in collections if len(c.opportunity_refs) >= ordinal]
            out.ambiguous_references.append(AmbiguousReference(reference_type=semantic.type, raw_text=semantic.raw_text, candidate_refs=refs[:10], reason="MULTIPLE_OPPORTUNITY_COLLECTIONS"))
            return
        collection = collections[0]
        if ordinal > len(collection.opportunity_refs):
            return self._unresolved(semantic, "ORDINAL_OUT_OF_RANGE", out)
        if collection.strategy_ref.account_ref != data.account_ref:
            return self._unresolved(semantic, "CONTEXT_ACCOUNT_MISMATCH", out)
        out.context_facts["active_strategy_ref"] = collection.strategy_ref.ref
        return self._trusted(semantic, [collection.opportunity_refs[ordinal - 1]], ResolutionSource.ORDINAL_SELECTION, 7, data, out)

    def _temporal(self, data, semantic, out):
        if semantic.temporal_hint != "YESTERDAY":
            return self._unresolved(semantic, "TEMPORAL_WINDOW_UNSUPPORTED", out)
        current = self.now().astimezone(UTC)
        start = (current - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        records = self.reader.list_published_between(data.account_ref, start, end)
        return self._records(semantic, records, ResolutionSource.TEMPORAL_SELECTION, 8, data, out, "PUBLISHED_NOTE_NOT_FOUND")

    @staticmethod
    def _unresolved(semantic, reason, out):
        out.unresolved_references.append(UnresolvedReference(reference_type=semantic.type, raw_text=semantic.raw_text, reason=reason))

    @staticmethod
    def _facts(out):
        keys = {ResolvedObjectType.DRAFT: "active_draft_ref", ResolvedObjectType.RESEARCH: "active_research_ref", ResolvedObjectType.CONTENT_STRATEGY: "active_strategy_ref", ResolvedObjectType.PUBLISHED_NOTE: "active_published_note_ref"}
        for item in out.resolved_references:
            if item.resolved_object_type in keys:
                out.context_facts[keys[item.resolved_object_type]] = item.resolved_ref
