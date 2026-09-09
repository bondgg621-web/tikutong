"""Stdlib-only deterministic validation for frozen Question Bank contracts.

This module validates already-structured artifacts.  It deliberately does not
scan directories, parse source files, associate cross-file content, or migrate
identities; those are later Milestone responsibilities.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any


UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$")
QUESTION_TYPES = {"single_choice", "multiple_choice", "true_false", "unsupported", "ambiguous"}
CANDIDATE_STATES = {"candidate", "validated", "unsupported", "ambiguous", "archived"}
DECISION_STATES = {"valid", "needs_revalidation", "archived"}
ISSUE_CODES = {
    "QB-SOURCE-UNSUPPORTED", "QB-SOURCE-READ-FAILED", "QB-ROLE-AMBIGUOUS",
    "QB-TYPE-UNSUPPORTED", "QB-STRUCTURE-AMBIGUOUS", "QB-ANSWER-MISSING",
    "QB-ANSWER-CONFLICT", "QB-ASSOCIATION-LOW-CONFIDENCE", "QB-DUPLICATE-CANDIDATE",
    "QB-IDENTITY-AMBIGUOUS", "QB-OPTION-IDENTITY-AMBIGUOUS", "QB-DECISION-STALE",
    "QB-FORMAT-LOSS", "QB-SECURITY-INSTRUCTION-DATA", "QB-REMOTE-CAPABILITY-NOT-AUTHORIZED",
}


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str


def schema_path(name: str) -> Path:
    """Locate a distributed runtime schema relative to the copied Skill."""
    path = Path(__file__).resolve().parents[2] / "schemas" / name
    if path.parent.name != "schemas":
        raise ValueError("schema lookup escaped the Skill package")
    return path


def _issue(errors: list[ValidationIssue], code: str, path: str, message: str) -> None:
    errors.append(ValidationIssue(code, path, message))


def _required(errors: list[ValidationIssue], value: Any, fields: set[str], path: str) -> bool:
    if not isinstance(value, dict):
        _issue(errors, "QB-CONTRACT-TYPE", path, "must be a JSON object")
        return False
    for field in sorted(fields - value.keys()):
        _issue(errors, "QB-CONTRACT-REQUIRED", path, f"missing required field {field}")
    return True


def _is_uuid(value: Any) -> bool:
    return isinstance(value, str) and bool(UUID_PATTERN.fullmatch(value))


def _is_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(HASH_PATTERN.fullmatch(value))


def _check_uuid(errors: list[ValidationIssue], value: Any, path: str) -> None:
    if not _is_uuid(value):
        _issue(errors, "QB-CONTRACT-PATTERN", path, "must be a UUID")


def _check_hash(errors: list[ValidationIssue], value: Any, path: str) -> None:
    if not _is_hash(value):
        _issue(errors, "QB-CONTRACT-PATTERN", path, "must be a lowercase SHA-256 hex digest")


def _check_int(errors: list[ValidationIssue], value: Any, path: str, minimum: int = 0) -> None:
    if type(value) is not int:
        _issue(errors, "QB-CONTRACT-TYPE", path, "must be an integer")
    elif value < minimum:
        _issue(errors, "QB-CONTRACT-CARDINALITY", path, f"must be at least {minimum}")


def _check_string(errors: list[ValidationIssue], value: Any, path: str, nonempty: bool = True) -> None:
    if not isinstance(value, str):
        _issue(errors, "QB-CONTRACT-TYPE", path, "must be a string")
    elif nonempty and not value:
        _issue(errors, "QB-CONTRACT-CARDINALITY", path, "must not be empty")


def _validate_fingerprints(errors: list[ValidationIssue], value: Any, path: str) -> None:
    fields = {"stem_fingerprint", "option_set_fingerprint", "content_revision_fingerprint"}
    if not _required(errors, value, fields, path):
        return
    for field in fields:
        _check_hash(errors, value.get(field), f"{path}.{field}")


def _validate_option(errors: list[ValidationIssue], option: Any, path: str) -> None:
    fields = {
        "option_id", "candidate_id", "option_revision", "normalized_text_fingerprint",
        "current_position", "source_label", "source_ref", "previous_labels",
    }
    if not _required(errors, option, fields, path):
        return
    _check_uuid(errors, option.get("option_id"), f"{path}.option_id")
    _check_uuid(errors, option.get("candidate_id"), f"{path}.candidate_id")
    _check_int(errors, option.get("option_revision"), f"{path}.option_revision", 1)
    _check_hash(errors, option.get("normalized_text_fingerprint"), f"{path}.normalized_text_fingerprint")
    _check_int(errors, option.get("current_position"), f"{path}.current_position", 1)
    _check_string(errors, option.get("source_label"), f"{path}.source_label")
    source_ref = option.get("source_ref")
    if _required(errors, source_ref, {"source_id", "locator"}, f"{path}.source_ref"):
        _check_uuid(errors, source_ref.get("source_id"), f"{path}.source_ref.source_id")
        _check_string(errors, source_ref.get("locator"), f"{path}.source_ref.locator")
    labels = option.get("previous_labels")
    if not isinstance(labels, list):
        _issue(errors, "QB-CONTRACT-TYPE", f"{path}.previous_labels", "must be an array")
    elif not all(isinstance(label, str) for label in labels):
        _issue(errors, "QB-CONTRACT-TYPE", f"{path}.previous_labels", "must contain strings")


def _validate_candidate_document(value: Any) -> list[ValidationIssue]:
    errors: list[ValidationIssue] = []
    if not _required(errors, value, {"schema_version", "candidates"}, "candidate"):
        return errors
    _check_string(errors, value.get("schema_version"), "candidate.schema_version")
    candidates = value.get("candidates")
    if not isinstance(candidates, list):
        _issue(errors, "QB-CONTRACT-TYPE", "candidate.candidates", "must be an array")
        return errors
    if not candidates:
        _issue(errors, "QB-CONTRACT-CARDINALITY", "candidate.candidates", "must contain at least one candidate")
    for index, candidate in enumerate(candidates):
        path = f"candidate.candidates[{index}]"
        fields = {
            "candidate_id", "candidate_revision", "source_id", "locator", "question_type", "status",
            "stem", "fingerprints", "options", "duplicate_group",
        }
        if not _required(errors, candidate, fields, path):
            continue
        _check_uuid(errors, candidate.get("candidate_id"), f"{path}.candidate_id")
        _check_int(errors, candidate.get("candidate_revision"), f"{path}.candidate_revision", 1)
        _check_uuid(errors, candidate.get("source_id"), f"{path}.source_id")
        _check_string(errors, candidate.get("locator"), f"{path}.locator")
        _check_string(errors, candidate.get("stem"), f"{path}.stem")
        if candidate.get("question_type") not in QUESTION_TYPES:
            _issue(errors, "QB-CONTRACT-ENUM", f"{path}.question_type", "is not a frozen question type")
        if candidate.get("status") not in CANDIDATE_STATES:
            _issue(errors, "QB-CONTRACT-ENUM", f"{path}.status", "is not a candidate state")
        _validate_fingerprints(errors, candidate.get("fingerprints"), f"{path}.fingerprints")
        if candidate.get("duplicate_group") is not None:
            _check_string(errors, candidate.get("duplicate_group"), f"{path}.duplicate_group")
        options = candidate.get("options")
        if not isinstance(options, list):
            _issue(errors, "QB-CONTRACT-TYPE", f"{path}.options", "must be an array")
        else:
            for option_index, option in enumerate(options):
                _validate_option(errors, option, f"{path}.options[{option_index}]")
    return errors


def _validate_manifest_document(value: Any) -> list[ValidationIssue]:
    errors: list[ValidationIssue] = []
    if not _required(errors, value, {"schema_version", "dataset_id", "sources"}, "manifest"):
        return errors
    _check_string(errors, value.get("schema_version"), "manifest.schema_version")
    _check_uuid(errors, value.get("dataset_id"), "manifest.dataset_id")
    sources = value.get("sources")
    if not isinstance(sources, list):
        _issue(errors, "QB-CONTRACT-TYPE", "manifest.sources", "must be an array")
        return errors
    if not sources:
        _issue(errors, "QB-CONTRACT-CARDINALITY", "manifest.sources", "must contain at least one source")
    for index, source in enumerate(sources):
        path = f"manifest.sources[{index}]"
        fields = {"source_id", "kind", "current_relative_path", "path_history", "current_content_hash", "revision"}
        if not _required(errors, source, fields, path):
            continue
        _check_uuid(errors, source.get("source_id"), f"{path}.source_id")
        if source.get("kind") not in {"question_document", "answer_document", "unrelated", "duplicate_version"}:
            _issue(errors, "QB-CONTRACT-ENUM", f"{path}.kind", "is not a source kind")
        _check_string(errors, source.get("current_relative_path"), f"{path}.current_relative_path")
        _check_hash(errors, source.get("current_content_hash"), f"{path}.current_content_hash")
        _check_int(errors, source.get("revision"), f"{path}.revision", 1)
        history = source.get("path_history")
        if not isinstance(history, list):
            _issue(errors, "QB-CONTRACT-TYPE", f"{path}.path_history", "must be an array")
        elif not history or not all(isinstance(item, str) and item for item in history):
            _issue(errors, "QB-CONTRACT-CARDINALITY", f"{path}.path_history", "must contain nonempty paths")
    return errors


def _validate_review_document(value: Any) -> list[ValidationIssue]:
    errors: list[ValidationIssue] = []
    if not _required(errors, value, {"schema_version", "review_items"}, "review-item"):
        return errors
    items = value.get("review_items")
    if not isinstance(items, list):
        _issue(errors, "QB-CONTRACT-TYPE", "review-item.review_items", "must be an array")
        return errors
    for index, item in enumerate(items):
        path = f"review-item.review_items[{index}]"
        fields = {"review_id", "issue_code", "blocking_level", "status", "allowed_user_actions"}
        if not _required(errors, item, fields, path):
            continue
        _check_uuid(errors, item.get("review_id"), f"{path}.review_id")
        if item.get("issue_code") not in ISSUE_CODES:
            _issue(errors, "QB-CONTRACT-ENUM", f"{path}.issue_code", "is not a fixed issue code")
        if item.get("blocking_level") not in {"blocking", "review_required", "informational"}:
            _issue(errors, "QB-CONTRACT-ENUM", f"{path}.blocking_level", "is not a blocking level")
        if item.get("status") not in {"open", "resolved", "archived"}:
            _issue(errors, "QB-CONTRACT-ENUM", f"{path}.status", "is not a review status")
        actions = item.get("allowed_user_actions")
        if not isinstance(actions, list) or not actions or not all(isinstance(action, str) for action in actions):
            _issue(errors, "QB-CONTRACT-CARDINALITY", f"{path}.allowed_user_actions", "must contain actions")
        if "candidate_id" in item:
            _check_uuid(errors, item.get("candidate_id"), f"{path}.candidate_id")
    return errors


def _validate_decision_document(value: Any) -> list[ValidationIssue]:
    errors: list[ValidationIssue] = []
    if not _required(errors, value, {"schema_version", "decisions"}, "decision"):
        return errors
    decisions = value.get("decisions")
    if not isinstance(decisions, list):
        _issue(errors, "QB-CONTRACT-TYPE", "decision.decisions", "must be an array")
        return errors
    for index, decision in enumerate(decisions):
        path = f"decision.decisions[{index}]"
        fields = {"decision_id", "candidate_id", "candidate_revision", "decision_type", "value", "evidence", "status"}
        if not _required(errors, decision, fields, path):
            continue
        _check_uuid(errors, decision.get("decision_id"), f"{path}.decision_id")
        _check_uuid(errors, decision.get("candidate_id"), f"{path}.candidate_id")
        _check_int(errors, decision.get("candidate_revision"), f"{path}.candidate_revision", 1)
        if decision.get("decision_type") not in {"answer_resolution", "duplicate_relation", "association"}:
            _issue(errors, "QB-CONTRACT-ENUM", f"{path}.decision_type", "is not a decision type")
        if not isinstance(decision.get("value"), dict):
            _issue(errors, "QB-CONTRACT-TYPE", f"{path}.value", "must be an object")
        evidence = decision.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            _issue(errors, "QB-CONTRACT-CARDINALITY", f"{path}.evidence", "must contain evidence bindings")
        elif isinstance(evidence, list):
            for evidence_index, binding in enumerate(evidence):
                evidence_path = f"{path}.evidence[{evidence_index}]"
                if not _required(errors, binding, {"source_id", "source_revision", "locator", "evidence_fingerprint"}, evidence_path):
                    continue
                _check_uuid(errors, binding.get("source_id"), f"{evidence_path}.source_id")
                _check_int(errors, binding.get("source_revision"), f"{evidence_path}.source_revision", 1)
                _check_string(errors, binding.get("locator"), f"{evidence_path}.locator")
                _check_hash(errors, binding.get("evidence_fingerprint"), f"{evidence_path}.evidence_fingerprint")
        if decision.get("status") not in DECISION_STATES:
            _issue(errors, "QB-CONTRACT-ENUM", f"{path}.status", "is not a decision state")
    return errors


def validate_document(kind: str, value: Any) -> list[ValidationIssue]:
    """Validate the schema-overlap portion of one structured artifact."""
    validators = {
        "manifest": _validate_manifest_document,
        "candidate": _validate_candidate_document,
        "review-item": _validate_review_document,
        "decision": _validate_decision_document,
    }
    try:
        return validators[kind](value)
    except KeyError as exc:
        raise ValueError(f"unsupported contract document kind: {kind}") from exc


def validate_bundle(bundle: Any) -> list[ValidationIssue]:
    """Validate runtime-only references, revisions, answer semantics, and gate."""
    if not isinstance(bundle, dict):
        return [ValidationIssue("QB-CONTRACT-TYPE", "bundle", "must be an object")]
    errors: list[ValidationIssue] = []
    manifest = bundle.get("manifest")
    candidate_document = {"schema_version": "1.0", "candidates": bundle.get("candidates")}
    review_document = {"schema_version": "1.0", "review_items": bundle.get("review_items")}
    decision_document = {"schema_version": "1.0", "decisions": bundle.get("decisions")}
    errors.extend(validate_document("manifest", manifest))
    errors.extend(validate_document("candidate", candidate_document))
    errors.extend(validate_document("review-item", review_document))
    errors.extend(validate_document("decision", decision_document))
    if errors:
        return errors

    sources = {source["source_id"]: source for source in manifest["sources"]}
    candidates = {candidate["candidate_id"]: candidate for candidate in bundle["candidates"]}
    if len(candidates) != len(bundle["candidates"]):
        _issue(errors, "QB-CANDIDATE-ID-DUPLICATE", "bundle.candidates", "candidate IDs must be unique")
    option_owner: dict[str, str] = {}
    for candidate in bundle["candidates"]:
        candidate_path = f"bundle.candidates[{candidate['candidate_id']}]"
        if candidate["source_id"] not in sources:
            _issue(errors, "QB-SOURCE-REFERENCE-MISSING", candidate_path, "candidate source does not exist")
        for option in candidate["options"]:
            option_path = f"{candidate_path}.options[{option['option_id']}]"
            if option["candidate_id"] != candidate["candidate_id"]:
                _issue(errors, "QB-OPTION-OWNERSHIP-INVALID", option_path, "option candidate_id differs from container")
            if option["source_ref"]["source_id"] not in sources:
                _issue(errors, "QB-SOURCE-REFERENCE-MISSING", option_path, "option source does not exist")
            if option["option_id"] in option_owner:
                _issue(errors, "QB-OPTION-ID-DUPLICATE", option_path, "option IDs must be unique across candidates")
            option_owner[option["option_id"]] = candidate["candidate_id"]

    for review in bundle["review_items"]:
        candidate_id = review.get("candidate_id")
        if candidate_id is not None and candidate_id not in candidates:
            _issue(errors, "QB-CANDIDATE-REFERENCE-MISSING", "bundle.review_items", "review candidate does not exist")

    valid_answer_decisions: set[tuple[str, int]] = set()
    for decision in bundle["decisions"]:
        path = f"bundle.decisions[{decision['decision_id']}]"
        candidate = candidates.get(decision["candidate_id"])
        if candidate is None:
            _issue(errors, "QB-CANDIDATE-REFERENCE-MISSING", path, "decision candidate does not exist")
            continue
        if decision["candidate_revision"] != candidate["candidate_revision"]:
            _issue(errors, "QB-DECISION-REVISION-STALE", path, "decision revision is not candidate current revision")
        for binding in decision["evidence"]:
            source = sources.get(binding["source_id"])
            if source is None:
                _issue(errors, "QB-EVIDENCE-REFERENCE-MISSING", path, "evidence source does not exist")
            elif binding["source_revision"] > source["revision"]:
                _issue(errors, "QB-EVIDENCE-REVISION-INVALID", path, "evidence revision exceeds source revision")
        if decision["decision_type"] != "answer_resolution":
            continue
        value = decision["value"]
        question_type = candidate["question_type"]
        if question_type == "true_false":
            if type(value.get("boolean_value")) is not bool or not isinstance(value.get("source_lexeme"), str):
                _issue(errors, "QB-TRUE-FALSE-VALUE-INVALID", path, "true_false requires boolean_value and source_lexeme")
        else:
            resolved = value.get("resolved_option_ids")
            if not isinstance(resolved, list) or not all(isinstance(option_id, str) for option_id in resolved):
                _issue(errors, "QB-ANSWER-SHAPE-INVALID", path, "answer resolution requires resolved_option_ids")
            else:
                if question_type == "single_choice" and len(resolved) != 1:
                    _issue(errors, "QB-ANSWER-CARDINALITY-INVALID", path, "single_choice needs exactly one option")
                if question_type == "multiple_choice" and (len(resolved) < 2 or len(set(resolved)) != len(resolved)):
                    _issue(errors, "QB-ANSWER-CARDINALITY-INVALID", path, "multiple_choice needs two or more distinct options")
                for option_id in resolved:
                    owner = option_owner.get(option_id)
                    if owner is None:
                        _issue(errors, "QB-OPTION-REFERENCE-MISSING", path, "resolved option does not exist")
                    elif owner != candidate["candidate_id"]:
                        _issue(errors, "QB-OPTION-OWNERSHIP-INVALID", path, "resolved option belongs to another candidate")
        if decision["status"] == "valid" and decision["candidate_revision"] == candidate["candidate_revision"]:
            valid_answer_decisions.add((candidate["candidate_id"], candidate["candidate_revision"]))

    for candidate in bundle["candidates"]:
        if candidate["status"] == "validated" and (candidate["candidate_id"], candidate["candidate_revision"]) not in valid_answer_decisions:
            _issue(errors, "QB-VALIDATED-GATE-FAILED", f"bundle.candidates[{candidate['candidate_id']}]", "validated candidate lacks a current valid answer decision")
    return errors
