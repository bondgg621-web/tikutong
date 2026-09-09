from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
from uuid import uuid4

from qbcore.paths import RootPolicy
from qbcore.parse_contracts import validate_parse_document
from qbcore.validation import validate_document
from qbcore.workspace_contracts import UUID_PATTERN, validate_workspace_document


class WorkspaceWriteError(RuntimeError):
    pass


_PARSE_KIND_BY_NAME = {
    "parse-report.json": "single-choice-parse-report",
    "parse-issues.json": "single-choice-parse-issues",
    "parse-run.json": "single-choice-parse-run",
}


def workspace_json_payload(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    ).encode("utf-8")


@dataclass(frozen=True)
class PreparedCandidateSource:
    source_id: str
    temporary_path: Path
    target_path: Path
    relative_path: str
    content_hash: str


@dataclass(frozen=True)
class Workspace:
    policy: RootPolicy

    @property
    def root(self) -> Path:
        return self.policy.workspace_root

    @classmethod
    def initialize(cls, policy: RootPolicy) -> "Workspace":
        policy.assert_write_target(policy.workspace_root)
        policy.workspace_root.mkdir(parents=True, exist_ok=True)
        workspace = cls(policy)
        for relative in ("registry", "runs", "checkpoints", "logs", "outputs"):
            target = policy.assert_write_target(policy.workspace_root / relative)
            target.mkdir(exist_ok=True)
        return workspace

    def write_json_atomic(self, target: Path, value: object) -> str:
        target = self.policy.assert_write_target(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.policy.assert_write_target(target.parent / f".{target.name}.{uuid4()}.tmp")
        payload = workspace_json_payload(value)
        try:
            with temporary.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            json.loads(temporary.read_text(encoding="utf-8"))
            os.replace(temporary, target)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise WorkspaceWriteError("atomic JSON publication failed") from exc
        return target.relative_to(self.root).as_posix()

    def _stage_json_payload(self, target: Path, value: object) -> tuple[Path, bytes, str]:
        target = self.policy.assert_write_target(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.policy.assert_write_target(
            target.parent / f".{target.name}.{uuid4()}.tmp"
        )
        payload = workspace_json_payload(value)
        content_hash = sha256(payload).hexdigest()
        try:
            with temporary.open("xb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            read_back = temporary.read_bytes()
            if read_back != payload:
                raise WorkspaceWriteError("staged JSON read-back did not match written bytes")
            json.loads(read_back.decode("utf-8"))
        except (OSError, ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            if isinstance(exc, WorkspaceWriteError):
                raise exc
            raise WorkspaceWriteError("atomic JSON publication failed") from exc
        return temporary, payload, content_hash

    def _publish_staged_json(self, temporary: Path, target: Path) -> str:
        try:
            os.replace(temporary, target)
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise WorkspaceWriteError("atomic JSON publication failed") from exc
        return target.relative_to(self.root).as_posix()

    def _snapshot_existing_json_target(self, target: Path) -> Path | None:
        snapshot = self.policy.assert_write_target(
            target.parent / f".{target.name}.{uuid4()}.rollback"
        )
        try:
            os.link(target, snapshot)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise WorkspaceWriteError("existing JSON artifact could not be snapshotted") from exc
        return snapshot

    @staticmethod
    def _discard_json_snapshot(snapshot: Path | None) -> None:
        if snapshot is None:
            return
        try:
            snapshot.unlink(missing_ok=True)
        except OSError:
            # The validated target is authoritative; a rollback snapshot is not.
            pass

    @staticmethod
    def _restore_json_snapshot(target: Path, snapshot: Path | None) -> None:
        try:
            if snapshot is None:
                target.unlink(missing_ok=True)
            else:
                os.replace(snapshot, target)
        except OSError as exc:
            raise WorkspaceWriteError("JSON artifact rollback failed") from exc

    def _publish_staged_json_no_overwrite(self, temporary: Path, target: Path) -> tuple[str, str]:
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise WorkspaceWriteError("candidate artifact already exists") from exc
        except OSError as exc:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass
            raise WorkspaceWriteError("candidate artifact publication failed") from exc

        try:
            read_back = target.read_bytes()
            content_hash = sha256(read_back).hexdigest()
        except OSError as exc:
            raise WorkspaceWriteError("candidate artifact publication failed") from exc
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

        return target.relative_to(self.root).as_posix(), content_hash

    @staticmethod
    def _require_valid(kind: str, document: dict) -> None:
        issues = validate_workspace_document(kind, document)
        if issues:
            first = issues[0]
            raise WorkspaceWriteError(f"invalid {kind} document at {first.path}: {first.message}")

    @staticmethod
    def _require_valid_parse(kind: str, document: dict) -> None:
        issues = validate_parse_document(kind, document)
        if issues:
            first = issues[0]
            raise WorkspaceWriteError(
                f"invalid {kind} document at {first.path}: {first.message}"
            )

    @staticmethod
    def _require_valid_candidate(document: dict) -> None:
        issues = validate_document("candidate", document)
        if issues:
            first = issues[0]
            raise WorkspaceWriteError(
                f"invalid candidate document at {first.path}: {first.message}"
            )

    def write_project(self, document: dict) -> str:
        self._require_valid("workspace-project", document)
        return self.write_json_atomic(self.root / "project.json", document)

    def write_registry(self, document: dict) -> str:
        self._require_valid("source-registry", document)
        return self.write_json_atomic(self.root / "registry" / "sources.json", document)

    def write_run_artifact(self, run_id: str, name: str, document: dict) -> str:
        kind_by_name = {
            "preflight.json": "capability-matrix",
            "discovery.json": "discovery-inventory",
            "workspace-run.json": "workspace-run",
            "issues.json": "workspace-issues",
        }
        if UUID_PATTERN.fullmatch(run_id) is None:
            raise WorkspaceWriteError("run_id must be a lowercase UUID")
        try:
            kind = kind_by_name[name]
        except KeyError as exc:
            raise WorkspaceWriteError("run artifact name is not allowed") from exc
        if Path(name).name != name:
            raise WorkspaceWriteError("run artifact name cannot contain a path")
        if kind in {"workspace-run", "workspace-issues"} and document.get("run_id") != run_id:
            raise WorkspaceWriteError("run artifact run_id does not match its directory")
        self._require_valid(kind, document)
        return self.write_json_atomic(self.root / "runs" / run_id / name, document)

    def write_parse_run_artifact(self, run_id: str, name: str, document: dict) -> str:
        if UUID_PATTERN.fullmatch(run_id) is None:
            raise WorkspaceWriteError("run_id must be a lowercase UUID")
        if Path(name).name != name:
            raise WorkspaceWriteError("parse run artifact name is not allowed")
        try:
            kind = _PARSE_KIND_BY_NAME[name]
        except KeyError as exc:
            raise WorkspaceWriteError("parse run artifact name is not allowed") from exc
        if document.get("run_id") != run_id:
            raise WorkspaceWriteError("parse run artifact run_id does not match its directory")
        self._require_valid_parse(kind, document)
        target = self.policy.assert_write_target(self.root / "runs" / run_id / name)
        temporary, payload, _ = self._stage_json_payload(target, document)
        try:
            snapshot = self._snapshot_existing_json_target(target)
        except WorkspaceWriteError:
            temporary.unlink(missing_ok=True)
            raise
        try:
            relative_path = self._publish_staged_json(temporary, target)
        except WorkspaceWriteError:
            self._discard_json_snapshot(snapshot)
            raise
        try:
            read_back = target.read_bytes()
            if read_back != payload:
                raise WorkspaceWriteError("parse run artifact read-back failed")
            persisted = json.loads(read_back.decode("utf-8"))
            if not isinstance(persisted, dict):
                raise WorkspaceWriteError("parse run artifact read-back failed")
            self._require_valid_parse(kind, persisted)
        except (WorkspaceWriteError, OSError, UnicodeError, json.JSONDecodeError) as exc:
            self._restore_json_snapshot(target, snapshot)
            raise WorkspaceWriteError("parse run artifact read-back failed") from exc
        self._discard_json_snapshot(snapshot)
        return relative_path

    def publish_candidate_source(self, source_id: str, document: dict) -> tuple[str, str]:
        prepared = self.prepare_candidate_source(source_id, document)
        return self.publish_prepared_candidate_source(prepared)

    def assert_candidate_source_absent(self, source_id: str) -> None:
        if not isinstance(source_id, str) or UUID_PATTERN.fullmatch(source_id) is None:
            raise WorkspaceWriteError("source_id must be a lowercase UUID")
        target = self.policy.assert_write_target(
            self.root / "candidates" / "sources" / f"{source_id}.json"
        )
        try:
            os.lstat(target)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise WorkspaceWriteError("candidate artifact state could not be checked") from exc
        raise WorkspaceWriteError("candidate artifact already exists")

    def prepare_candidate_source(
        self,
        source_id: str,
        document: dict,
    ) -> PreparedCandidateSource:
        if not isinstance(source_id, str) or UUID_PATTERN.fullmatch(source_id) is None:
            raise WorkspaceWriteError("source_id must be a lowercase UUID")
        self._require_valid_candidate(document)
        if any(
            candidate["source_id"] != source_id
            or any(
                option["source_ref"]["source_id"] != source_id
                for option in candidate["options"]
            )
            for candidate in document["candidates"]
        ):
            raise WorkspaceWriteError("candidate source does not match target source_id")
        target = self.root / "candidates" / "sources" / f"{source_id}.json"
        target = self.policy.assert_write_target(target)
        temporary, _, content_hash = self._stage_json_payload(target, document)
        return PreparedCandidateSource(
            source_id=source_id,
            temporary_path=temporary,
            target_path=target,
            relative_path=target.relative_to(self.root).as_posix(),
            content_hash=content_hash,
        )

    def publish_prepared_candidate_source(
        self,
        prepared: PreparedCandidateSource,
    ) -> tuple[str, str]:
        if not self._prepared_candidate_is_valid(prepared):
            self._discard_safe_candidate_staging(prepared)
            raise WorkspaceWriteError("prepared candidate target is invalid")
        temporary = self.policy.assert_write_target(prepared.temporary_path)
        target = self.policy.assert_write_target(prepared.target_path)
        try:
            self._validate_prepared_candidate_staging(prepared)
        except WorkspaceWriteError:
            self._discard_safe_candidate_staging(prepared)
            raise
        relative_path, content_hash = self._publish_staged_json_no_overwrite(
            temporary,
            target,
        )
        if relative_path != prepared.relative_path or content_hash != prepared.content_hash:
            self._remove_invalid_candidate_target(target)
            raise WorkspaceWriteError("candidate artifact read-back did not match staged bytes")
        try:
            read_back = json.loads(target.read_text(encoding="utf-8"))
        except OSError as exc:
            raise WorkspaceWriteError("candidate artifact publication failed") from exc
        except (UnicodeError, json.JSONDecodeError) as exc:
            self._remove_invalid_candidate_target(target)
            raise WorkspaceWriteError("candidate artifact read-back failed") from exc
        if not isinstance(read_back, dict):
            self._remove_invalid_candidate_target(target)
            raise WorkspaceWriteError("candidate artifact read-back failed")
        try:
            self._require_valid_candidate(read_back)
        except WorkspaceWriteError as exc:
            self._remove_invalid_candidate_target(target)
            raise WorkspaceWriteError("candidate artifact read-back failed") from exc
        return relative_path, content_hash

    def _validate_prepared_candidate_staging(
        self,
        prepared: PreparedCandidateSource,
    ) -> None:
        try:
            payload = prepared.temporary_path.read_bytes()
        except OSError as exc:
            raise WorkspaceWriteError("candidate artifact read-back failed") from exc
        if sha256(payload).hexdigest() != prepared.content_hash:
            raise WorkspaceWriteError("candidate artifact read-back failed")
        try:
            document = json.loads(payload.decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise WorkspaceWriteError("candidate artifact read-back failed") from exc
        if not isinstance(document, dict):
            raise WorkspaceWriteError("candidate artifact read-back failed")
        try:
            self._require_valid_candidate(document)
        except WorkspaceWriteError as exc:
            raise WorkspaceWriteError("candidate artifact read-back failed") from exc

    @staticmethod
    def _remove_invalid_candidate_target(target: Path) -> None:
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:
            raise WorkspaceWriteError("invalid candidate artifact cleanup failed") from exc

    def discard_prepared_candidate_source(
        self,
        prepared: PreparedCandidateSource,
    ) -> None:
        if not self._prepared_candidate_is_valid(prepared):
            raise WorkspaceWriteError("prepared candidate target is invalid")
        self._discard_safe_candidate_staging(prepared)

    def _prepared_candidate_is_valid(
        self,
        prepared: PreparedCandidateSource,
    ) -> bool:
        if (
            not isinstance(prepared.source_id, str)
            or UUID_PATTERN.fullmatch(prepared.source_id) is None
        ):
            return False
        expected_target = self.policy.assert_write_target(
            self.root / "candidates" / "sources" / f"{prepared.source_id}.json"
        )
        if prepared.target_path != expected_target:
            return False
        if prepared.relative_path != expected_target.relative_to(self.root).as_posix():
            return False
        return self._candidate_staging_path_is_safe(prepared)

    def _candidate_staging_path_is_safe(
        self,
        prepared: PreparedCandidateSource,
    ) -> bool:
        if (
            not isinstance(prepared.source_id, str)
            or UUID_PATTERN.fullmatch(prepared.source_id) is None
        ):
            return False
        expected_target = self.policy.assert_write_target(
            self.root / "candidates" / "sources" / f"{prepared.source_id}.json"
        )
        temporary = self.policy.assert_write_target(prepared.temporary_path)
        prefix = f".{expected_target.name}."
        suffix = ".tmp"
        name = temporary.name
        if temporary.parent != expected_target.parent:
            return False
        if not name.startswith(prefix) or not name.endswith(suffix):
            return False
        token = name[len(prefix) : -len(suffix)]
        return UUID_PATTERN.fullmatch(token) is not None

    def _discard_safe_candidate_staging(
        self,
        prepared: PreparedCandidateSource,
    ) -> None:
        if not self._candidate_staging_path_is_safe(prepared):
            return
        temporary = self.policy.assert_write_target(prepared.temporary_path)
        try:
            temporary.unlink(missing_ok=True)
        except OSError as exc:
            raise WorkspaceWriteError("candidate staging cleanup failed") from exc
