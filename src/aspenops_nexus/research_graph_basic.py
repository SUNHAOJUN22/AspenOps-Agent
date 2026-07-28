from __future__ import annotations

from .research_common import ObjectRef
from .research_graph_support import GraphContext


def validate_basic(ctx: GraphContext) -> None:
    document = ctx.document
    all_nonstudy = {key for key in ctx.objects if key[0] != "study"}
    declared = {(item.object_type, item.object_id) for item in document.study.object_refs}
    study_ref = ObjectRef("study", document.study.study_id)

    for object_type, object_id in sorted(all_nonstudy - declared):
        ctx.add(
            "error",
            "study_missing_object_ref",
            f"Study does not reference {object_type}:{object_id}",
            study_ref,
            "study.object_refs",
        )
    for object_type, object_id in sorted(declared - all_nonstudy):
        ctx.add(
            "error",
            "study_unresolved_object_ref",
            f"Study references missing {object_type}:{object_id}",
            study_ref,
            "study.object_refs",
        )

    datasets = {item.dataset_id: item for item in document.datasets}
    for target in document.targets:
        owner = ObjectRef("target", target.target_id)
        binding = target.dataset_binding
        if binding is not None:
            dataset = datasets.get(binding.dataset_id)
            if dataset is None:
                ctx.add(
                    "error",
                    "target_dataset_missing",
                    f"Target dataset does not exist: {binding.dataset_id}",
                    owner,
                    "target.dataset_binding",
                )
            elif binding.variable not in {item.name for item in dataset.variables}:
                ctx.add(
                    "error",
                    "target_variable_missing",
                    f"Dataset variable does not exist: {binding.variable}",
                    owner,
                    "target.dataset_binding.variable",
                )
        for index, dependency in enumerate(target.dependencies):
            ctx.resolve(
                dependency,
                owner=owner,
                path=f"target.dependencies[{index}]",
            )

    for assumption in document.assumptions:
        owner = ObjectRef("assumption", assumption.assumption_id)
        for index, affected in enumerate(assumption.affected_objects):
            ctx.resolve(
                affected,
                owner=owner,
                path=f"assumption.affected_objects[{index}]",
            )
        if assumption.category == "source_contradiction" and not assumption.contradiction_group:
            ctx.add(
                "error",
                "contradiction_group_required",
                "Source contradiction assumptions require contradiction_group",
                owner,
                "assumption.contradiction_group",
            )
        if assumption.status in {"rejected", "superseded"} and assumption.resolution is None:
            ctx.add(
                "warning",
                "assumption_resolution_missing",
                "Rejected or superseded assumption should record its resolution",
                owner,
                "assumption.resolution",
            )
