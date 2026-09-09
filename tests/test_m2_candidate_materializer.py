from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace
from pathlib import Path
from uuid import UUID

import pytest

from qbcore.candidate_materializer import (
    CandidateMaterializationError,
    materialize_candidates,
)
from qbcore.single_choice_parser import ParsedOption, ParsedSingleChoice
from qbcore.single_choice_parser import parse_single_choice
from qbcore.validation import ValidationIssue, validate_document


SOURCE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
FIXTURE_ROOT = Path(__file__).parent / "fixtures" / "m2-parser"
UUID_TEXTS = tuple(
    f"00000000-0000-4000-8000-{value:012x}" for value in range(1, 8)
)
BASE_CONTENT_HASH = "06ff6cf98ea027bc24887ccb42261143e43c2bcc857e102e60508150f567d084"
BASE_DUPLICATE_GROUP = f"content-sha256:{BASE_CONTENT_HASH}"
STRICT_SEVEN_DUPLICATE_HASH = (
    "79aadc5061eceab6d27aa27ec002a48d03a13249acb42775c2bf934aa1319f91"
)
STRICT_SEVEN_DUPLICATE_GROUP = f"content-sha256:{STRICT_SEVEN_DUPLICATE_HASH}"


class RecordingUUIDFactory:
    def __init__(self, values: Iterable[UUID]) -> None:
        self._values = iter(values)
        self.calls = 0

    def __call__(self) -> UUID:
        self.calls += 1
        return next(self._values)


class OnceIterable:
    def __init__(self, values: Iterable[ParsedSingleChoice]) -> None:
        self._values = tuple(values)
        self.iterations = 0

    def __iter__(self):
        self.iterations += 1
        if self.iterations > 1:
            raise AssertionError("parsed questions were iterated more than once")
        return iter(self._values)


class HostileUUID(UUID):
    def __str__(self) -> str:
        raise RuntimeError("hostile UUID string conversion")


def _questions() -> tuple[ParsedSingleChoice, ...]:
    return (
        ParsedSingleChoice(
            display_number="1",
            stem="Which  café?",
            header_line=10,
            options=(
                ParsedOption(source_label="A", text="Red  fox", line=11),
                ParsedOption(source_label="B", text="Blue whale", line=12),
            ),
        ),
        ParsedSingleChoice(
            display_number="2",
            stem="2 + 2?",
            header_line=20,
            options=(
                ParsedOption(source_label="A", text="3", line=21),
                ParsedOption(source_label="B", text="4", line=22),
                ParsedOption(source_label="C", text="5", line=23),
            ),
        ),
    )


def _factory() -> RecordingUUIDFactory:
    return RecordingUUIDFactory(UUID(value) for value in UUID_TEXTS)


def test_materializes_exact_two_question_candidate_document_in_source_allocation_order() -> None:
    factory = _factory()

    document = materialize_candidates(
        _questions(), source_id=SOURCE_ID, uuid_factory=factory
    )

    assert document == {
        "schema_version": "1.0",
        "candidates": [
            {
                "candidate_id": UUID_TEXTS[0],
                "candidate_revision": 1,
                "source_id": SOURCE_ID,
                "locator": "line:10",
                "question_type": "single_choice",
                "status": "candidate",
                "stem": "Which  café?",
                "fingerprints": {
                    "stem_fingerprint": "80e63c8482bad6b351ecf546592527ad6dc41e9649bbcd3a2d8be1a3cba0b40c",
                    "option_set_fingerprint": "c74e232886489dca9e097d2112fe9155f1356b40d844c1ea2c174e4d27e522ce",
                    "content_revision_fingerprint": "06ff6cf98ea027bc24887ccb42261143e43c2bcc857e102e60508150f567d084",
                },
                "options": [
                    {
                        "option_id": UUID_TEXTS[1],
                        "candidate_id": UUID_TEXTS[0],
                        "option_revision": 1,
                        "normalized_text_fingerprint": "dc802453901ddad9f0528ff5c2cbe72e80f0b692e3494fa60228a2855f488779",
                        "current_position": 1,
                        "source_label": "A",
                        "source_ref": {"source_id": SOURCE_ID, "locator": "line:11"},
                        "previous_labels": [],
                    },
                    {
                        "option_id": UUID_TEXTS[2],
                        "candidate_id": UUID_TEXTS[0],
                        "option_revision": 1,
                        "normalized_text_fingerprint": "e394083542579eb885e10cf34ebe29f615e826436f4068712eb3158ee223f27a",
                        "current_position": 2,
                        "source_label": "B",
                        "source_ref": {"source_id": SOURCE_ID, "locator": "line:12"},
                        "previous_labels": [],
                    },
                ],
                "duplicate_group": None,
            },
            {
                "candidate_id": UUID_TEXTS[3],
                "candidate_revision": 1,
                "source_id": SOURCE_ID,
                "locator": "line:20",
                "question_type": "single_choice",
                "status": "candidate",
                "stem": "2 + 2?",
                "fingerprints": {
                    "stem_fingerprint": "70b499c547e0a11fc693677f477746c45a8133b4dadeb0a2090a1c44cf783b20",
                    "option_set_fingerprint": "446c3ea50b5675edcba37685693fdc1680df2f7be0809f5cd0f4f8532719da67",
                    "content_revision_fingerprint": "d3549351cde95de86dac2d1e470b877a44c58845b9555c8bd197ea94c1d6748d",
                },
                "options": [
                    {
                        "option_id": UUID_TEXTS[4],
                        "candidate_id": UUID_TEXTS[3],
                        "option_revision": 1,
                        "normalized_text_fingerprint": "4e07408562bedb8b60ce05c1decfe3ad16b72230967de01f640b7e4729b49fce",
                        "current_position": 1,
                        "source_label": "A",
                        "source_ref": {"source_id": SOURCE_ID, "locator": "line:21"},
                        "previous_labels": [],
                    },
                    {
                        "option_id": UUID_TEXTS[5],
                        "candidate_id": UUID_TEXTS[3],
                        "option_revision": 1,
                        "normalized_text_fingerprint": "4b227777d4dd1fc61c6f884f48641d02b4d121d3fd328cb08b5531fcacdabf8a",
                        "current_position": 2,
                        "source_label": "B",
                        "source_ref": {"source_id": SOURCE_ID, "locator": "line:22"},
                        "previous_labels": [],
                    },
                    {
                        "option_id": UUID_TEXTS[6],
                        "candidate_id": UUID_TEXTS[3],
                        "option_revision": 1,
                        "normalized_text_fingerprint": "ef2d127de37b942baad06145e54b0c619a1f22327b2ebbcfbec78f5564afe39d",
                        "current_position": 3,
                        "source_label": "C",
                        "source_ref": {"source_id": SOURCE_ID, "locator": "line:23"},
                        "previous_labels": [],
                    },
                ],
                "duplicate_group": None,
            },
        ],
    }
    assert factory.calls == 7
    assert validate_document("candidate", document) == []


def test_snapshots_input_once_without_mutating_parsed_records() -> None:
    questions = _questions()
    iterable = OnceIterable(questions)

    materialize_candidates(iterable, source_id=SOURCE_ID, uuid_factory=_factory())

    assert iterable.iterations == 1
    assert questions == _questions()


def test_sorts_snapped_questions_by_header_line_before_uuid_allocation() -> None:
    descending = tuple(reversed(_questions()))
    before = tuple(descending)
    factory = _factory()

    document = materialize_candidates(
        descending, source_id=SOURCE_ID, uuid_factory=factory
    )

    assert [candidate["locator"] for candidate in document["candidates"]] == [
        "line:10",
        "line:20",
    ]
    assert [candidate["candidate_id"] for candidate in document["candidates"]] == [
        UUID_TEXTS[0],
        UUID_TEXTS[3],
    ]
    assert [
        option["option_id"] for option in document["candidates"][0]["options"]
    ] == [UUID_TEXTS[1], UUID_TEXTS[2]]
    assert [
        option["option_id"] for option in document["candidates"][1]["options"]
    ] == [UUID_TEXTS[4], UUID_TEXTS[5], UUID_TEXTS[6]]
    assert descending == before


def test_repeated_runs_are_deterministic_with_fresh_identical_factories() -> None:
    first = materialize_candidates(
        _questions(), source_id=SOURCE_ID, uuid_factory=_factory()
    )
    second = materialize_candidates(
        _questions(), source_id=SOURCE_ID, uuid_factory=_factory()
    )

    assert first == second


def test_equal_content_gets_hash_group_without_reusing_candidate_or_option_ids() -> None:
    question = _questions()[0]
    duplicate = replace(
        question,
        display_number="2",
        header_line=30,
        options=tuple(
            replace(option, line=option.line + 20) for option in question.options
        ),
    )
    factory = RecordingUUIDFactory(UUID(int=index, version=4) for index in range(1, 7))

    document = materialize_candidates(
        (question, duplicate), source_id=SOURCE_ID, uuid_factory=factory
    )

    assert [candidate["duplicate_group"] for candidate in document["candidates"]] == [
        BASE_DUPLICATE_GROUP,
        BASE_DUPLICATE_GROUP,
    ]
    assert [
        candidate["fingerprints"]["content_revision_fingerprint"]
        for candidate in document["candidates"]
    ] == [BASE_CONTENT_HASH, BASE_CONTENT_HASH]
    assert [candidate["candidate_id"] for candidate in document["candidates"]] == [
        str(UUID(int=1, version=4)),
        str(UUID(int=4, version=4)),
    ]
    assert [
        option["option_id"]
        for candidate in document["candidates"]
        for option in candidate["options"]
    ] == [str(UUID(int=value, version=4)) for value in (2, 3, 5, 6)]


def test_three_identical_records_group_without_collapsing_or_hash_ordering() -> None:
    first = _questions()[0]
    second = replace(
        first,
        display_number="2",
        header_line=30,
        options=tuple(replace(option, line=option.line + 20) for option in first.options),
    )
    third = replace(
        first,
        display_number="3",
        header_line=50,
        options=tuple(replace(option, line=option.line + 40) for option in first.options),
    )
    unique = ParsedSingleChoice(
        display_number="4",
        stem="Unique question?",
        header_line=70,
        options=(
            ParsedOption("A", "Yes", 71),
            ParsedOption("B", "No", 72),
        ),
    )
    factory = RecordingUUIDFactory(UUID(int=index, version=4) for index in range(1, 13))

    document = materialize_candidates(
        (third, unique, second, first), source_id=SOURCE_ID, uuid_factory=factory
    )

    assert [candidate["locator"] for candidate in document["candidates"]] == [
        "line:10",
        "line:30",
        "line:50",
        "line:70",
    ]
    assert [candidate["duplicate_group"] for candidate in document["candidates"]] == [
        BASE_DUPLICATE_GROUP,
        BASE_DUPLICATE_GROUP,
        BASE_DUPLICATE_GROUP,
        None,
    ]
    assert [candidate["candidate_id"] for candidate in document["candidates"]] == [
        str(UUID(int=value, version=4)) for value in (1, 4, 7, 10)
    ]
    assert len(document["candidates"]) == 4
    assert factory.calls == 12


def test_reordered_option_multiset_does_not_group() -> None:
    first = ParsedSingleChoice(
        display_number="1",
        stem="Order?",
        header_line=10,
        options=(
            ParsedOption("A", "Alpha", 11),
            ParsedOption("B", "Beta", 12),
            ParsedOption("C", "Gamma", 13),
        ),
    )
    reordered = ParsedSingleChoice(
        display_number="2",
        stem="Order?",
        header_line=20,
        options=(
            ParsedOption("A", "Gamma", 21),
            ParsedOption("B", "Beta", 22),
            ParsedOption("C", "Alpha", 23),
        ),
    )
    factory = RecordingUUIDFactory(UUID(int=index, version=4) for index in range(1, 9))

    document = materialize_candidates(
        (first, reordered), source_id=SOURCE_ID, uuid_factory=factory
    )

    first_candidate, second_candidate = document["candidates"]
    assert first_candidate["fingerprints"]["option_set_fingerprint"] == (
        second_candidate["fingerprints"]["option_set_fingerprint"]
    )
    assert [
        candidate["fingerprints"]["content_revision_fingerprint"]
        for candidate in document["candidates"]
    ] == [
        "df9db5f5d2d31e21aea5554079d168cedd8527621b8768594d08ba447059892f",
        "23ffba7990ae28d0a2b87f7d0034f5fa8418660f1b2e5c20d334fd101277374d",
    ]
    assert [candidate["duplicate_group"] for candidate in document["candidates"]] == [
        None,
        None,
    ]


def test_normalized_equivalent_whitespace_and_nfc_content_groups() -> None:
    normalized = ParsedSingleChoice(
        display_number="1",
        stem="Caf\u00e9 prompt",
        header_line=10,
        options=(
            ParsedOption("A", "Red fox", 11),
            ParsedOption("B", "Blue whale", 12),
        ),
    )
    equivalent = ParsedSingleChoice(
        display_number="2",
        stem="Cafe\u0301 \t prompt",
        header_line=20,
        options=(
            ParsedOption("A", "Red\u00a0fox", 21),
            ParsedOption("B", "Blue   whale", 22),
        ),
    )
    expected_hash = "83980f6316bf7384950b3e2332c37ba1bcab9489bb7502996712fa4aa6e167f6"
    expected_group = f"content-sha256:{expected_hash}"
    factory = RecordingUUIDFactory(UUID(int=index, version=4) for index in range(1, 7))

    document = materialize_candidates(
        (normalized, equivalent), source_id=SOURCE_ID, uuid_factory=factory
    )

    assert [
        candidate["fingerprints"]["content_revision_fingerprint"]
        for candidate in document["candidates"]
    ] == [expected_hash, expected_hash]
    assert [candidate["duplicate_group"] for candidate in document["candidates"]] == [
        expected_group,
        expected_group,
    ]


def test_duplicate_option_text_remains_distinct_on_first_materialization() -> None:
    question = ParsedSingleChoice(
        display_number="1",
        stem="Keep repeated options?",
        header_line=10,
        options=(
            ParsedOption("A", "Retention", 11),
            ParsedOption("B", "Retention", 12),
            ParsedOption("C", "Merge", 13),
        ),
    )
    factory = RecordingUUIDFactory(UUID(int=index, version=4) for index in range(1, 5))

    document = materialize_candidates(
        (question,), source_id=SOURCE_ID, uuid_factory=factory
    )

    candidate = document["candidates"][0]
    assert candidate["duplicate_group"] is None
    assert len(candidate["options"]) == 3
    assert [option["option_id"] for option in candidate["options"]] == [
        str(UUID(int=value, version=4)) for value in (2, 3, 4)
    ]
    assert [option["current_position"] for option in candidate["options"]] == [1, 2, 3]
    assert [option["source_ref"]["locator"] for option in candidate["options"]] == [
        "line:11",
        "line:12",
        "line:13",
    ]
    assert (
        candidate["options"][0]["normalized_text_fingerprint"]
        == candidate["options"][1]["normalized_text_fingerprint"]
    )
    assert candidate["options"][0]["option_id"] != candidate["options"][1]["option_id"]


def test_duplicate_grouping_is_limited_to_each_materialization_call() -> None:
    question = _questions()[0]

    first = materialize_candidates(
        (question,), source_id=SOURCE_ID, uuid_factory=_factory()
    )
    second = materialize_candidates(
        (question,), source_id=SOURCE_ID, uuid_factory=_factory()
    )

    assert first["candidates"][0]["duplicate_group"] is None
    assert second["candidates"][0]["duplicate_group"] is None


def test_strict_seven_parser_materialization_groups_last_two_without_identity_merge() -> None:
    parsed = parse_single_choice(
        (FIXTURE_ROOT / "strict-seven.md").read_text(encoding="utf-8")
    )
    factory = RecordingUUIDFactory(UUID(int=index, version=4) for index in range(1, 34))

    document = materialize_candidates(
        parsed.questions, source_id=SOURCE_ID, uuid_factory=factory
    )

    assert parsed.findings == ()
    assert len(document["candidates"]) == 7
    assert [len(candidate["options"]) for candidate in document["candidates"]] == [
        4,
        4,
        4,
        4,
        4,
        3,
        3,
    ]
    assert [candidate["duplicate_group"] for candidate in document["candidates"]] == [
        None,
        None,
        None,
        None,
        None,
        STRICT_SEVEN_DUPLICATE_GROUP,
        STRICT_SEVEN_DUPLICATE_GROUP,
    ]
    sixth, seventh = document["candidates"][5:]
    assert [
        sixth["fingerprints"]["content_revision_fingerprint"],
        seventh["fingerprints"]["content_revision_fingerprint"],
    ] == [STRICT_SEVEN_DUPLICATE_HASH, STRICT_SEVEN_DUPLICATE_HASH]
    assert [sixth["candidate_id"], seventh["candidate_id"]] == [
        str(UUID(int=26, version=4)),
        str(UUID(int=30, version=4)),
    ]
    assert [option["option_id"] for option in sixth["options"]] == [
        str(UUID(int=value, version=4)) for value in (27, 28, 29)
    ]
    assert [option["option_id"] for option in seventh["options"]] == [
        str(UUID(int=value, version=4)) for value in (31, 32, 33)
    ]
    assert len({sixth["candidate_id"], seventh["candidate_id"]}) == 2
    assert len(
        {
            option["option_id"]
            for candidate in (sixth, seventh)
            for option in candidate["options"]
        }
    ) == 6
    assert len(sixth["options"]) == len(seventh["options"]) == 3
    assert (
        sixth["options"][0]["normalized_text_fingerprint"]
        == sixth["options"][1]["normalized_text_fingerprint"]
    )
    assert factory.calls == 33


def test_empty_input_is_rejected_without_consuming_a_uuid() -> None:
    factory = RecordingUUIDFactory(())

    with pytest.raises(CandidateMaterializationError, match="must not be empty"):
        materialize_candidates((), source_id=SOURCE_ID, uuid_factory=factory)

    assert factory.calls == 0


@pytest.mark.parametrize(
    "source_id",
    [
        SOURCE_ID.upper(),
        f" {SOURCE_ID}",
        f"{SOURCE_ID} ",
        "11111111-1111-6111-8111-111111111111",
        "11111111-1111-4111-7111-111111111111",
        "00000000-0000-0000-0000-000000000000",
        UUID(SOURCE_ID),
    ],
)
def test_rejects_noncanonical_or_ineligible_source_ids_without_uuid_calls(
    source_id: object,
) -> None:
    factory = _factory()

    with pytest.raises(CandidateMaterializationError, match="source_id"):
        materialize_candidates(
            _questions(), source_id=source_id, uuid_factory=factory  # type: ignore[arg-type]
        )

    assert factory.calls == 0


def _structurally_invalid_questions() -> tuple[object, ...]:
    good = _questions()[0]
    return (
        (object(),),
        (replace(good, stem=""),),
        (replace(good, header_line=0),),
        (replace(good, header_line=True),),
        (replace(good, options=good.options[:1]),),
        (replace(good, options=(good.options[0], object())),),
        (replace(good, options=(good.options[0], replace(good.options[1], line=11))),),
        (replace(good, options=(good.options[0], replace(good.options[1], line=10))),),
        (replace(good, options=(good.options[0], replace(good.options[1], source_label="A"))),),
        (replace(good, options=(good.options[0], replace(good.options[1], source_label="C"))),),
        (replace(good, options=(good.options[0], replace(good.options[1], text=""))),),
        (good, replace(good, display_number="2")),
    )


@pytest.mark.parametrize("questions", _structurally_invalid_questions())
def test_structural_preflight_rejects_bad_records_before_uuid_consumption(
    questions: object,
) -> None:
    factory = _factory()

    with pytest.raises(CandidateMaterializationError):
        materialize_candidates(
            questions, source_id=SOURCE_ID, uuid_factory=factory  # type: ignore[arg-type]
        )

    assert factory.calls == 0


def test_uuid_factory_exhaustion_is_stably_wrapped() -> None:
    factory = RecordingUUIDFactory((UUID(UUID_TEXTS[0]),))

    with pytest.raises(
        CandidateMaterializationError, match="uuid_factory exhausted"
    ) as raised:
        materialize_candidates(
            (_questions()[0],), source_id=SOURCE_ID, uuid_factory=factory
        )

    assert isinstance(raised.value.__cause__, StopIteration)
    assert factory.calls == 2


def test_uuid_factory_exception_is_stably_wrapped() -> None:
    calls = 0

    def raising_factory() -> UUID:
        nonlocal calls
        calls += 1
        raise RuntimeError("private factory detail")

    with pytest.raises(
        CandidateMaterializationError, match="uuid_factory raised an exception"
    ) as raised:
        materialize_candidates(
            (_questions()[0],), source_id=SOURCE_ID, uuid_factory=raising_factory
        )

    assert isinstance(raised.value.__cause__, RuntimeError)
    assert calls == 1


@pytest.mark.parametrize(
    "bad_value",
    [
        UUID_TEXTS[0],
        UUID(int=0),
        UUID("00000000-0000-6000-8000-000000000001"),
        UUID("00000000-0000-4000-7000-000000000001"),
    ],
)
def test_uuid_factory_rejects_non_uuid_or_ineligible_uuid_values(
    bad_value: object,
) -> None:
    factory = RecordingUUIDFactory((bad_value,))  # type: ignore[arg-type]

    with pytest.raises(CandidateMaterializationError, match="uuid_factory returned"):
        materialize_candidates(
            (_questions()[0],), source_id=SOURCE_ID, uuid_factory=factory
        )


def test_rejects_duplicate_ids_across_candidate_and_option_namespaces() -> None:
    repeated = UUID(UUID_TEXTS[0])
    factory = RecordingUUIDFactory((repeated, repeated))

    with pytest.raises(CandidateMaterializationError, match="duplicate UUID"):
        materialize_candidates(
            (_questions()[0],), source_id=SOURCE_ID, uuid_factory=factory
        )

    assert factory.calls == 2


@pytest.mark.parametrize(
    ("values", "expected_calls"),
    [
        ((UUID(SOURCE_ID),), 1),
        ((UUID(UUID_TEXTS[0]), UUID(SOURCE_ID)), 2),
    ],
)
def test_rejects_candidate_or_option_uuid_collision_with_source_id(
    values: tuple[UUID, ...], expected_calls: int
) -> None:
    factory = RecordingUUIDFactory(values)

    with pytest.raises(
        CandidateMaterializationError, match="duplicate UUID.*source_id"
    ):
        materialize_candidates(
            (_questions()[0],), source_id=SOURCE_ID, uuid_factory=factory
        )

    assert factory.calls == expected_calls


@pytest.mark.parametrize(
    ("questions", "message"),
    [
        (
            (
                replace(
                    _questions()[0],
                    options=(
                        _questions()[0].options[0],
                        replace(_questions()[0].options[1], line=21),
                    ),
                ),
                _questions()[1],
            ),
            "duplicate source locator line:21",
        ),
        (
            (
                replace(
                    _questions()[0],
                    options=(
                        _questions()[0].options[0],
                        replace(_questions()[0].options[1], line=20),
                    ),
                ),
                _questions()[1],
            ),
            "duplicate source locator line:20",
        ),
        (
            (
                replace(
                    _questions()[0],
                    options=(
                        _questions()[0].options[0],
                        replace(_questions()[0].options[1], line=19),
                    ),
                ),
                replace(_questions()[1], header_line=18),
            ),
            "must be before next candidate locator line:18",
        ),
    ],
    ids=("cross-question-option", "header-option", "interleaved-block"),
)
def test_global_locator_preflight_rejects_collisions_and_overlaps_without_uuids(
    questions: tuple[ParsedSingleChoice, ...], message: str
) -> None:
    factory = _factory()

    with pytest.raises(CandidateMaterializationError, match=message):
        materialize_candidates(
            questions, source_id=SOURCE_ID, uuid_factory=factory
        )

    assert factory.calls == 0


def test_rejects_hostile_uuid_subclass_as_a_typed_materialization_error() -> None:
    factory = RecordingUUIDFactory((HostileUUID(UUID_TEXTS[0]),))

    with pytest.raises(
        CandidateMaterializationError, match="exact UUID object"
    ) as raised:
        materialize_candidates(
            (_questions()[0],), source_id=SOURCE_ID, uuid_factory=factory
        )

    assert raised.value.__cause__ is None
    assert factory.calls == 1


def test_sorted_preflight_diagnostic_uses_original_caller_index() -> None:
    later = _questions()[1]
    earlier_invalid = replace(
        _questions()[0],
        options=(
            _questions()[0].options[0],
            replace(_questions()[0].options[1], source_label="C"),
        ),
    )
    descending = (later, earlier_invalid)
    factory = _factory()

    with pytest.raises(
        CandidateMaterializationError,
        match=r"parsed_questions\[1\]\.options\[1\]\.source_label",
    ):
        materialize_candidates(
            descending, source_id=SOURCE_ID, uuid_factory=factory
        )

    assert factory.calls == 0


def test_option_owners_source_refs_positions_and_locators_are_coherent() -> None:
    document = materialize_candidates(
        _questions(), source_id=SOURCE_ID, uuid_factory=_factory()
    )
    all_ids: set[str] = set()

    for question, candidate in zip(_questions(), document["candidates"], strict=True):
        assert candidate["locator"] == f"line:{question.header_line}"
        assert candidate["source_id"] == SOURCE_ID
        assert candidate["candidate_id"] not in all_ids
        all_ids.add(candidate["candidate_id"])
        for position, (parsed_option, option) in enumerate(
            zip(question.options, candidate["options"], strict=True), start=1
        ):
            assert option["candidate_id"] == candidate["candidate_id"]
            assert option["current_position"] == position
            assert option["source_ref"] == {
                "source_id": SOURCE_ID,
                "locator": f"line:{parsed_option.line}",
            }
            assert option["option_id"] not in all_ids
            all_ids.add(option["option_id"])


def test_validator_issues_are_converted_to_public_materialization_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import qbcore.candidate_materializer as module

    monkeypatch.setattr(
        module,
        "validate_document",
        lambda kind, document: [
            ValidationIssue("QB-CONTRACT-TYPE", "candidate", "forced failure")
        ],
    )

    with pytest.raises(
        CandidateMaterializationError,
        match=r"candidate validation failed: QB-CONTRACT-TYPE at candidate: forced failure",
    ):
        materialize_candidates(
            (_questions()[0],),
            source_id=SOURCE_ID,
            uuid_factory=RecordingUUIDFactory(UUID(value) for value in UUID_TEXTS[:3]),
        )


def test_public_error_is_a_typed_value_error() -> None:
    assert issubclass(CandidateMaterializationError, ValueError)
