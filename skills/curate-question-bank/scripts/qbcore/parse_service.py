"""Source resolution and bounded publication for the single-choice parser."""

from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path, PureWindowsPath
import re
import stat
from typing import Literal
import unicodedata
from uuid import UUID, uuid4

from qbcore.capabilities import _utc_z
from qbcore.candidate_materializer import materialize_candidates
from qbcore.paths import PathPolicyError, is_reparse_directory, validate_roots
from qbcore.parse_contracts import validate_parse_contracts
from qbcore.single_choice_parser import ParseResult, parse_single_choice
from qbcore.validation import validate_document
from qbcore.workspace import Workspace, WorkspaceWriteError, workspace_json_payload
from qbcore.workspace_contracts import UUID_PATTERN, validate_workspace_document


SourceIssueCode = Literal["QB-SOURCE-READ-FAILED", "QB-SOURCE-UNSUPPORTED"]

_READ_FAILED = "QB-SOURCE-READ-FAILED"
_UNSUPPORTED = "QB-SOURCE-UNSUPPORTED"
_ALLOWED_ISSUE_CODES = frozenset({_READ_FAILED, _UNSUPPORTED})
_SUPPORTED_SUFFIXES = frozenset({".md", ".markdown", ".txt"})
_DRIVE_PATH = re.compile(r"^[A-Za-z]:")
_INVALID_WINDOWS_SEGMENT_CHARACTERS = frozenset('<>"|?*')
_WINDOWS_REPARSE_ATTRIBUTE = 0x400
_CHUNK_SIZE = 1024 * 1024


class SourceResolutionError(RuntimeError):
    """A deterministic error that does not disclose source data or host paths."""

    def __init__(
        self,
        message: str,
        *,
        issue_code: SourceIssueCode | None = None,
    ) -> None:
        if issue_code is not None and issue_code not in _ALLOWED_ISSUE_CODES:
            raise ValueError("source resolution issue code is not frozen")
        super().__init__(message)
        self.issue_code = issue_code


class ParsePublicationError(RuntimeError):
    """A deterministic publication failure without source text or host paths."""


class ParseServiceError(RuntimeError):
    """A failed-closed service precondition with an optional frozen issue code."""

    def __init__(self, message: str, *, issue_code: str | None = None) -> None:
        super().__init__(message)
        self.issue_code = issue_code


@dataclass(frozen=True)
class ResolvedSource:
    source_id: str
    source_revision: int
    relative_path: str
    content_hash: str
    text: str
    parse_result: ParseResult


@dataclass(frozen=True)
class ResolvedSourceSnapshot:
    source_id: str
    source_revision: int
    relative_path: str
    content_hash: str
    text: str


@dataclass(frozen=True)
class ParseServiceResult:
    run_id: str
    status: str
    workspace_root: Path


def system_now() -> datetime:
    return datetime.now(timezone.utc)


def system_uuid() -> UUID:
    return uuid4()


def _content_hash(document: dict) -> str:
    return sha256(workspace_json_payload(document)).hexdigest()


def _validate_publication_contracts(
    report: dict,
    parse_issues: dict,
    parse_run: dict,
    *,
    artifact_content_hashes: dict[str, str] | None = None,
):
    try:
        return validate_parse_contracts(
            report,
            parse_issues,
            parse_run,
            artifact_content_hashes=artifact_content_hashes,
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        raise ParsePublicationError(
            "parse publication contract validation failed"
        ) from None


def _require_candidate_matches_report(report: dict, candidate_document: dict) -> None:
    try:
        candidate_issues = validate_document("candidate", candidate_document)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, TypeError):
        raise ParsePublicationError(
            "parse publication contract validation failed"
        ) from None
    if candidate_issues:
        raise ParsePublicationError("candidate document does not match parse report")
    candidates = candidate_document["candidates"]
    source_id = report["source_id"]
    if len(candidates) != report["accepted_candidate_count"]:
        raise ParsePublicationError("candidate document does not match parse report")
    for candidate in candidates:
        if candidate["source_id"] != source_id:
            raise ParsePublicationError("candidate document does not match parse report")
        if any(
            option["source_ref"]["source_id"] != source_id
            for option in candidate["options"]
        ):
            raise ParsePublicationError("candidate document does not match parse report")


def _discard_prepared_candidate_quietly(workspace: Workspace, prepared) -> None:
    if prepared is None:
        return
    try:
        workspace.discard_prepared_candidate_source(prepared)
    except (WorkspaceWriteError, PathPolicyError, OSError):
        pass


_ISSUE_DETAILS = {
    "QB-STRUCTURE-AMBIGUOUS": (
        "review_required",
        ["correct source", "retain", "exclude"],
    ),
    "QB-TYPE-UNSUPPORTED": (
        "blocking",
        ["retain", "mark unsupported"],
    ),
}


def _parse_issue_document(
    *,
    run_id: str,
    resolved: ResolvedSource,
    uuid_factory: Callable[[], UUID],
) -> dict:
    findings = list(resolved.parse_result.findings)
    if not findings:
        findings = [
            type(
                "SyntheticFinding",
                (),
                {
                    "code": "QB-STRUCTURE-AMBIGUOUS",
                    "locator": "line:1",
                    "summary": "No supported single-choice questions were found.",
                },
            )()
        ]
    issues = []
    for finding in findings:
        blocking_level, allowed_actions = _ISSUE_DETAILS[finding.code]
        issues.append(
            {
                "issue_id": str(uuid_factory()),
                "code": finding.code,
                "blocking_level": blocking_level,
                "status": "open",
                "source_id": resolved.source_id,
                "locator": finding.locator,
                "summary": finding.summary,
                "allowed_user_actions": allowed_actions,
            }
        )
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "source_id": resolved.source_id,
        "issues": issues,
    }


def _parse_report_document(
    *,
    run_id: str,
    resolved: ResolvedSource,
    status: str,
    finding_count: int,
    candidate_path: str | None,
    candidate_hash: str | None,
) -> dict:
    return {
        "schema_version": "1.0",
        "parser_contract_version": "m2-single-choice-v1",
        "run_id": run_id,
        "status": status,
        "source_id": resolved.source_id,
        "source_revision": resolved.source_revision,
        "source_relative_path": resolved.relative_path,
        "source_content_hash": resolved.content_hash,
        "question_like_block_count": resolved.parse_result.question_like_block_count,
        "accepted_candidate_count": len(resolved.parse_result.questions),
        "rejected_block_count": resolved.parse_result.rejected_block_count,
        "finding_count": finding_count,
        "candidate_artifact_relative_path": candidate_path,
        "candidate_artifact_content_hash": candidate_hash,
    }


def _parse_run_document(
    *,
    run_id: str,
    resolved: ResolvedSource,
    status: str,
    started_at: str,
    updated_at: str,
    input_fingerprint: str,
    workspace_fingerprint: str,
    report: dict,
    parse_issues: dict,
    candidate_path: str | None,
    candidate_hash: str | None,
) -> dict:
    artifacts = [
        {
            "kind": "parse_report",
            "relative_path": f"runs/{run_id}/parse-report.json",
            "content_hash": _content_hash(report),
        },
        {
            "kind": "parse_issues",
            "relative_path": f"runs/{run_id}/parse-issues.json",
            "content_hash": _content_hash(parse_issues),
        },
    ]
    if candidate_path is not None and candidate_hash is not None:
        artifacts.append(
            {
                "kind": "candidate",
                "relative_path": candidate_path,
                "content_hash": candidate_hash,
            }
        )
    return {
        "schema_version": "1.0",
        "run_id": run_id,
        "source_id": resolved.source_id,
        "phase": "complete",
        "status": status,
        "started_at": started_at,
        "updated_at": updated_at,
        "input_root_fingerprint": input_fingerprint,
        "workspace_root_fingerprint": workspace_fingerprint,
        "artifacts": artifacts,
    }


def _load_json_object(path: Path) -> dict | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _repair_incomplete_publication(
    *,
    workspace: Workspace,
    resolved: ResolvedSource | ResolvedSourceSnapshot,
    now: Callable[[], datetime],
) -> ParseServiceResult | None:
    candidate_path = (
        workspace.root / "candidates" / "sources" / f"{resolved.source_id}.json"
    )
    try:
        candidate_bytes = candidate_path.read_bytes()
        candidate_document = json.loads(candidate_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    if not isinstance(candidate_document, dict) or validate_document(
        "candidate", candidate_document
    ):
        return None
    if any(
        candidate["source_id"] != resolved.source_id
        or any(
            option["source_ref"]["source_id"] != resolved.source_id
            for option in candidate["options"]
        )
        for candidate in candidate_document["candidates"]
    ):
        return None

    candidate_hash = sha256(candidate_bytes).hexdigest()
    candidate_relative = candidate_path.relative_to(workspace.root).as_posix()
    matches: list[tuple[str, dict]] = []
    for run_path in sorted(workspace.root.glob("runs/*/parse-run.json")):
        parse_run = _load_json_object(run_path)
        if (
            parse_run is None
            or parse_run.get("source_id") != resolved.source_id
            or parse_run.get("phase") != "publication"
            or parse_run.get("status") != "running"
        ):
            continue
        run_id = parse_run.get("run_id")
        if run_path.parent.name != run_id:
            continue
        report = _load_json_object(run_path.parent / "parse-report.json")
        parse_issues = _load_json_object(run_path.parent / "parse-issues.json")
        if report is None or parse_issues is None:
            continue
        if (
            report.get("source_revision") != resolved.source_revision
            or report.get("source_relative_path") != resolved.relative_path
            or report.get("source_content_hash") != resolved.content_hash
            or report.get("candidate_artifact_relative_path") != candidate_relative
            or report.get("candidate_artifact_content_hash") != candidate_hash
            or report.get("accepted_candidate_count")
            != len(candidate_document["candidates"])
        ):
            continue
        complete_run = deepcopy(parse_run)
        complete_run["phase"] = "complete"
        complete_run["status"] = "complete"
        complete_run["updated_at"] = _utc_z(now())
        artifact_hashes = {
            candidate_relative: candidate_hash,
            f"runs/{run_id}/parse-report.json": sha256(
                (run_path.parent / "parse-report.json").read_bytes()
            ).hexdigest(),
            f"runs/{run_id}/parse-issues.json": sha256(
                (run_path.parent / "parse-issues.json").read_bytes()
            ).hexdigest(),
        }
        if _validate_publication_contracts(
            report,
            parse_issues,
            complete_run,
            artifact_content_hashes=artifact_hashes,
        ):
            continue
        matches.append((run_id, complete_run))

    if len(matches) != 1:
        return None
    run_id, complete_run = matches[0]
    try:
        workspace.write_parse_run_artifact(run_id, "parse-run.json", complete_run)
    except (WorkspaceWriteError, PathPolicyError, OSError):
        raise ParsePublicationError("parse artifact publication failed") from None
    return ParseServiceResult(run_id, "complete", workspace.root)


def _existing_candidate_matches_complete_run(
    *,
    workspace: Workspace,
    resolved: ResolvedSource | ResolvedSourceSnapshot,
) -> bool:
    candidate_path = (
        workspace.root / "candidates" / "sources" / f"{resolved.source_id}.json"
    )
    try:
        candidate_bytes = candidate_path.read_bytes()
        candidate_document = json.loads(candidate_bytes.decode("utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return False
    if not isinstance(candidate_document, dict) or validate_document(
        "candidate", candidate_document
    ):
        return False
    if any(
        candidate["source_id"] != resolved.source_id
        or any(
            option["source_ref"]["source_id"] != resolved.source_id
            for option in candidate["options"]
        )
        for candidate in candidate_document["candidates"]
    ):
        return False

    candidate_hash = sha256(candidate_bytes).hexdigest()
    candidate_relative = candidate_path.relative_to(workspace.root).as_posix()
    for run_path in sorted(workspace.root.glob("runs/*/parse-run.json")):
        parse_run = _load_json_object(run_path)
        if (
            parse_run is None
            or parse_run.get("source_id") != resolved.source_id
            or parse_run.get("phase") != "complete"
            or parse_run.get("status") != "complete"
            or parse_run.get("run_id") != run_path.parent.name
        ):
            continue
        run_id = parse_run["run_id"]
        report_path = run_path.parent / "parse-report.json"
        issues_path = run_path.parent / "parse-issues.json"
        report = _load_json_object(report_path)
        parse_issues = _load_json_object(issues_path)
        if report is None or parse_issues is None:
            continue
        if (
            report.get("source_revision") != resolved.source_revision
            or report.get("source_relative_path") != resolved.relative_path
            or report.get("source_content_hash") != resolved.content_hash
            or report.get("candidate_artifact_relative_path") != candidate_relative
            or report.get("candidate_artifact_content_hash") != candidate_hash
            or report.get("accepted_candidate_count")
            != len(candidate_document["candidates"])
        ):
            continue
        try:
            artifact_hashes = {
                candidate_relative: candidate_hash,
                f"runs/{run_id}/parse-report.json": sha256(
                    report_path.read_bytes()
                ).hexdigest(),
                f"runs/{run_id}/parse-issues.json": sha256(
                    issues_path.read_bytes()
                ).hexdigest(),
            }
        except OSError:
            continue
        if not _validate_publication_contracts(
            report,
            parse_issues,
            parse_run,
            artifact_content_hashes=artifact_hashes,
        ):
            return True
    return False


def run_single_choice_parse(
    *,
    input_root: str | Path,
    workspace_root: str | Path,
    source_id: str,
    now: Callable[[], datetime] = system_now,
    uuid_factory: Callable[[], UUID] = system_uuid,
) -> ParseServiceResult:
    snapshot = _resolve_single_choice_source_snapshot(
        input_root=input_root,
        workspace_root=workspace_root,
        source_id=source_id,
    )
    policy = validate_roots(input_root, workspace_root)
    workspace = Workspace.initialize(policy)
    candidate_target = (
        workspace.root / "candidates" / "sources" / f"{snapshot.source_id}.json"
    )
    if candidate_target.exists():
        repaired = _repair_incomplete_publication(
            workspace=workspace,
            resolved=snapshot,
            now=now,
        )
        if repaired is not None:
            return repaired
        if not _existing_candidate_matches_complete_run(
            workspace=workspace,
            resolved=snapshot,
        ):
            raise ParseServiceError(
                "candidate artifact does not match its completed run",
                issue_code="QB-IDENTITY-AMBIGUOUS",
            )
        raise ParseServiceError(
            "source already has a candidate artifact",
            issue_code="QB-IDENTITY-AMBIGUOUS",
        )

    resolved = ResolvedSource(
        source_id=snapshot.source_id,
        source_revision=snapshot.source_revision,
        relative_path=snapshot.relative_path,
        content_hash=snapshot.content_hash,
        text=snapshot.text,
        parse_result=parse_single_choice(snapshot.text),
    )

    run_id = str(uuid_factory())
    started_at = _utc_z(now())
    candidate_document = None
    candidate_path = None
    candidate_hash = None
    if resolved.parse_result.publishable:
        candidate_document = materialize_candidates(
            resolved.parse_result.questions,
            source_id=resolved.source_id,
            uuid_factory=uuid_factory,
        )
        candidate_path = f"candidates/sources/{resolved.source_id}.json"
        candidate_hash = _content_hash(candidate_document)
        parse_issues = {
            "schema_version": "1.0",
            "run_id": run_id,
            "source_id": resolved.source_id,
            "issues": [],
        }
        status = "complete"
    else:
        parse_issues = _parse_issue_document(
            run_id=run_id,
            resolved=resolved,
            uuid_factory=uuid_factory,
        )
        status = "needs_review"

    report = _parse_report_document(
        run_id=run_id,
        resolved=resolved,
        status=status,
        finding_count=len(parse_issues["issues"]),
        candidate_path=candidate_path,
        candidate_hash=candidate_hash,
    )
    parse_run = _parse_run_document(
        run_id=run_id,
        resolved=resolved,
        status=status,
        started_at=started_at,
        updated_at=_utc_z(now()),
        input_fingerprint=policy.input_fingerprint,
        workspace_fingerprint=policy.workspace_fingerprint,
        report=report,
        parse_issues=parse_issues,
        candidate_path=candidate_path,
        candidate_hash=candidate_hash,
    )
    publish_parse_artifacts(
        workspace=workspace,
        report=report,
        parse_issues=parse_issues,
        parse_run=parse_run,
        candidate_document=candidate_document,
    )
    return ParseServiceResult(run_id, status, workspace.root)


def publish_parse_artifacts(
    *,
    workspace: Workspace,
    report: dict,
    parse_issues: dict,
    parse_run: dict,
    candidate_document: dict | None,
) -> None:
    """Publish validated terminal parse artifacts with recoverable ordering."""

    status = parse_run.get("status")
    if status not in {"complete", "needs_review"}:
        raise ParsePublicationError("terminal parse run status is not publishable")
    if (status == "complete") != (candidate_document is not None):
        raise ParsePublicationError("candidate presence does not match terminal status")

    contract_issues = _validate_publication_contracts(report, parse_issues, parse_run)
    if contract_issues:
        first = contract_issues[0]
        raise ParsePublicationError(
            f"invalid parse publication contract at {first.path}: {first.message}"
        )
    if candidate_document is not None:
        _require_candidate_matches_report(report, candidate_document)

    run_id = parse_run.get("run_id")
    source_id = parse_run.get("source_id")
    artifact_hashes = {
        f"runs/{run_id}/parse-report.json": _content_hash(report),
        f"runs/{run_id}/parse-issues.json": _content_hash(parse_issues),
    }
    prepared = None
    try:
        if candidate_document is not None:
            workspace.assert_candidate_source_absent(source_id)
            prepared = workspace.prepare_candidate_source(source_id, candidate_document)
            artifact_hashes[prepared.relative_path] = prepared.content_hash

        contract_issues = _validate_publication_contracts(
            report,
            parse_issues,
            parse_run,
            artifact_content_hashes=artifact_hashes,
        )
        if contract_issues:
            first = contract_issues[0]
            raise ParsePublicationError(
                f"invalid parse publication contract at {first.path}: {first.message}"
            )

        workspace.write_parse_run_artifact(run_id, "parse-report.json", report)
        workspace.write_parse_run_artifact(run_id, "parse-issues.json", parse_issues)
        if prepared is None:
            workspace.write_parse_run_artifact(run_id, "parse-run.json", parse_run)
            return

        publication_run = deepcopy(parse_run)
        publication_run["phase"] = "publication"
        publication_run["status"] = "running"
        workspace.write_parse_run_artifact(run_id, "parse-run.json", publication_run)
        relative_path, content_hash = workspace.publish_prepared_candidate_source(prepared)
        prepared = None
        if (
            relative_path != report.get("candidate_artifact_relative_path")
            or content_hash != report.get("candidate_artifact_content_hash")
        ):
            raise WorkspaceWriteError(
                "candidate artifact read-back did not match parse report"
            )
        workspace.write_parse_run_artifact(run_id, "parse-run.json", parse_run)
    except (WorkspaceWriteError, PathPolicyError, OSError):
        raise ParsePublicationError("parse artifact publication failed") from None
    finally:
        _discard_prepared_candidate_quietly(workspace, prepared)


def _load_workspace_document(path: Path, kind: str, message: str) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise SourceResolutionError(message) from None
    if validate_workspace_document(kind, value):
        raise SourceResolutionError(message)
    assert isinstance(value, dict)
    return value


def _is_safe_relative_path(value: object) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if "\\" in value or ":" in value:
        return False
    if value.startswith("/") or _DRIVE_PATH.match(value):
        return False
    if any(unicodedata.category(character) == "Cc" for character in value):
        return False
    for part in value.split("/"):
        if part in {"", ".", ".."} or part.endswith((".", " ")):
            return False
        if any(character in _INVALID_WINDOWS_SEGMENT_CHARACTERS for character in part):
            return False
        if PureWindowsPath(part).is_reserved():
            return False
    return True


def _is_reparse_point(path: Path, metadata: os.stat_result) -> bool:
    attributes = getattr(metadata, "st_file_attributes", 0)
    return (
        stat.S_ISLNK(metadata.st_mode)
        or bool(attributes & _WINDOWS_REPARSE_ATTRIBUTE)
        or is_reparse_directory(path)
    )


def _resolve_registered_target(input_root: Path, relative_path: str) -> Path:
    target = input_root.joinpath(*relative_path.split("/"))
    current = input_root
    try:
        for part in relative_path.split("/"):
            current = current / part
            metadata = os.lstat(current)
            if _is_reparse_point(current, metadata):
                raise SourceResolutionError("registered source path is unsafe")
        resolved = target.resolve(strict=True)
    except SourceResolutionError:
        raise
    except (OSError, RuntimeError):
        raise SourceResolutionError(
            "registered source could not be read",
            issue_code=_READ_FAILED,
        ) from None

    try:
        resolved.relative_to(input_root)
    except ValueError:
        raise SourceResolutionError("registered source path is unsafe") from None

    try:
        metadata = os.lstat(resolved)
    except OSError:
        raise SourceResolutionError(
            "registered source could not be read",
            issue_code=_READ_FAILED,
        ) from None
    if _is_reparse_point(resolved, metadata):
        raise SourceResolutionError("registered source path is unsafe")
    if not stat.S_ISREG(metadata.st_mode):
        raise SourceResolutionError(
            "registered source could not be read",
            issue_code=_READ_FAILED,
        )
    return resolved


def _read_exact_bytes(path: Path) -> tuple[bytes, str]:
    content = bytearray()
    digest = sha256()
    try:
        with path.open("rb") as stream:
            while chunk := stream.read(_CHUNK_SIZE):
                digest.update(chunk)
                content.extend(chunk)
    except OSError:
        raise SourceResolutionError(
            "registered source could not be read",
            issue_code=_READ_FAILED,
        ) from None
    return bytes(content), digest.hexdigest()


def _resolve_single_choice_source_snapshot(
    *,
    input_root: str | Path,
    workspace_root: str | Path,
    source_id: str,
) -> ResolvedSourceSnapshot:
    """Resolve, verify, and decode one explicitly identified source."""

    try:
        policy = validate_roots(input_root, workspace_root)
    except (PathPolicyError, OSError, RuntimeError):
        raise SourceResolutionError("source resolution roots are invalid") from None
    if not policy.workspace_root.is_dir():
        raise SourceResolutionError("initialized workspace is required")

    project = _load_workspace_document(
        policy.workspace_root / "project.json",
        "workspace-project",
        "workspace project document is invalid",
    )
    registry = _load_workspace_document(
        policy.workspace_root / "registry" / "sources.json",
        "source-registry",
        "source registry document is invalid",
    )
    if project["dataset_id"] != registry["dataset_id"]:
        raise SourceResolutionError(
            "workspace dataset_id does not match source registry"
        )
    if not isinstance(source_id, str) or UUID_PATTERN.fullmatch(source_id) is None:
        raise SourceResolutionError(
            "source_id must be a canonical lowercase UUID"
        )

    matching = [
        source for source in registry["sources"] if source["source_id"] == source_id
    ]
    if len(matching) != 1:
        raise SourceResolutionError(
            "source_id is not present exactly once in registry"
        )
    source = matching[0]
    if source["presence"] != "present":
        raise SourceResolutionError("registered source is not present")

    relative_path = source["current_relative_path"]
    if not _is_safe_relative_path(relative_path):
        raise SourceResolutionError("registered source path is unsafe")
    if Path(relative_path).suffix.casefold() not in _SUPPORTED_SUFFIXES:
        raise SourceResolutionError(
            "registered source type is unsupported",
            issue_code=_UNSUPPORTED,
        )

    target = _resolve_registered_target(policy.input_root, relative_path)
    raw_bytes, content_hash = _read_exact_bytes(target)
    if content_hash != source["current_content_hash"]:
        raise SourceResolutionError(
            "registered source hash is stale; rerun inventory"
        )
    try:
        text = raw_bytes.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise SourceResolutionError(
            "registered source could not be read",
            issue_code=_READ_FAILED,
        ) from None

    return ResolvedSourceSnapshot(
        source_id=source_id,
        source_revision=source["revision"],
        relative_path=relative_path,
        content_hash=content_hash,
        text=text,
    )


def resolve_single_choice_source(
    *,
    input_root: str | Path,
    workspace_root: str | Path,
    source_id: str,
) -> ResolvedSource:
    """Resolve, verify, decode, and parse one explicitly identified source."""

    snapshot = _resolve_single_choice_source_snapshot(
        input_root=input_root,
        workspace_root=workspace_root,
        source_id=source_id,
    )
    return ResolvedSource(
        source_id=snapshot.source_id,
        source_revision=snapshot.source_revision,
        relative_path=snapshot.relative_path,
        content_hash=snapshot.content_hash,
        text=snapshot.text,
        parse_result=parse_single_choice(snapshot.text),
    )
