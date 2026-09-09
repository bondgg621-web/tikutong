from __future__ import annotations

from collections.abc import Sequence
import re

import pytest


def normalization_module():
    from qbcore import text_normalization

    return text_normalization


def nested_list(depth: int) -> object:
    value: object = "leaf"
    for _ in range(depth):
        value = [value]
    return value


def test_normalize_text_composes_nfc_and_collapses_unicode_whitespace() -> None:
    source = "\u00a0Cafe\u0301\talpha\n\u2003beta\u202f"

    assert normalization_module().normalize_text(source) == "Caf\u00e9 alpha beta"
    assert source == "\u00a0Cafe\u0301\talpha\n\u2003beta\u202f"


@pytest.mark.parametrize("value", ["", " \t\r\n ", "\u00a0\u2003\u202f"])
def test_normalize_text_rejects_empty_result(value: str) -> None:
    with pytest.raises(ValueError):
        normalization_module().normalize_text(value)


@pytest.mark.parametrize("value", [None, b"text", 1, True, ["text"]])
def test_normalize_text_requires_string(value: object) -> None:
    with pytest.raises(TypeError):
        normalization_module().normalize_text(value)  # type: ignore[arg-type]


def test_normalize_text_preserves_case_punctuation_fullwidth_and_html_text() -> None:
    value = "  MiXeD? \uff21 &amp;  "

    assert normalization_module().normalize_text(value) == "MiXeD? \uff21 &amp;"


def test_canonical_json_bytes_uses_sorted_compact_non_ascii_utf8() -> None:
    value = {
        "stem": "Caf\u00e9 \u8336",
        "options": ["\uff21", "\u84dd\u8272"],
        "question_type": "single_choice",
    }
    expected = bytes.fromhex(
        "7b226f7074696f6e73223a5b22efbca1222c22e8939de889b2225d2c22"
        "7175657374696f6e5f74797065223a2273696e676c655f63686f69636522"
        "2c227374656d223a22436166c3a920e88cb6227d"
    )

    assert normalization_module().canonical_json_bytes(value) == expected


@pytest.mark.parametrize(
    "value",
    [b"bytes", {"set"}, ("tuple",), 1, 1.5, True, None],
    ids=("bytes", "set", "tuple", "integer", "float", "boolean", "null"),
)
def test_canonical_json_bytes_rejects_unsupported_root_shapes(value: object) -> None:
    with pytest.raises(TypeError):
        normalization_module().canonical_json_bytes(value)


@pytest.mark.parametrize(
    "value",
    [
        {1: "non-string key"},
        {"nested": ["valid", 2]},
        ["valid", {"nested": None}],
        {"nested": ("tuple",)},
    ],
    ids=("non-string-key", "nested-number", "nested-null", "nested-tuple"),
)
def test_canonical_json_bytes_rejects_invalid_nested_shapes(value: object) -> None:
    with pytest.raises(TypeError):
        normalization_module().canonical_json_bytes(value)


def test_canonical_json_bytes_accepts_string_list_and_nested_object_values() -> None:
    module = normalization_module()

    assert module.canonical_json_bytes("Caf\u00e9") == b'"Caf\xc3\xa9"'
    assert module.canonical_json_bytes(["A", {"b": ["B"]}]) == b'["A",{"b":["B"]}]'


def test_canonical_json_bytes_rejects_list_subclass_without_traversing_override() -> None:
    class DivergentList(list):
        def __init__(self) -> None:
            super().__init__([1])
            self.iteration_count = 0

        def __iter__(self):
            self.iteration_count += 1
            return iter(["different validation view"])

    value = DivergentList()

    with pytest.raises(TypeError, match="exact built-in dict, list, and str"):
        normalization_module().canonical_json_bytes(value)
    assert value.iteration_count == 0


def test_canonical_json_bytes_rejects_dict_subclass_without_traversing_override() -> None:
    class DivergentDict(dict):
        def __init__(self) -> None:
            super().__init__({1: 2})
            self.items_count = 0

        def items(self):
            self.items_count += 1
            return [("different", "validation view")]

    value = DivergentDict()

    with pytest.raises(TypeError, match="exact built-in dict, list, and str"):
        normalization_module().canonical_json_bytes(value)
    assert value.items_count == 0


def test_canonical_json_bytes_rejects_string_subclasses_by_documented_policy() -> None:
    class StringSubclass(str):
        pass

    with pytest.raises(TypeError, match="exact built-in dict, list, and str"):
        normalization_module().canonical_json_bytes(StringSubclass("text"))


def test_canonical_json_bytes_accepts_maximum_documented_depth() -> None:
    module = normalization_module()
    assert module.MAX_CANONICAL_JSON_DEPTH == 64

    assert module.canonical_json_bytes(nested_list(64)) == (
        (b"[" * 64) + b'"leaf"' + (b"]" * 64)
    )


def test_canonical_json_bytes_rejects_depth_above_documented_maximum() -> None:
    module = normalization_module()

    with pytest.raises(ValueError, match="canonical JSON nesting exceeds maximum depth 64"):
        module.canonical_json_bytes(nested_list(module.MAX_CANONICAL_JSON_DEPTH + 1))


def test_canonical_json_bytes_rejects_direct_cycle() -> None:
    value: list[object] = []
    value.append(value)

    with pytest.raises(ValueError, match="canonical JSON value must not contain cycles"):
        normalization_module().canonical_json_bytes(value)


def test_canonical_json_bytes_rejects_mutual_cycle() -> None:
    left: list[object] = []
    right: dict[str, object] = {"left": left}
    left.append(right)

    with pytest.raises(ValueError, match="canonical JSON value must not contain cycles"):
        normalization_module().canonical_json_bytes(left)


def test_canonical_json_bytes_rejects_deep_cycle_before_recursion_error() -> None:
    root: list[object] = []
    current = root
    for _ in range(32):
        child: list[object] = []
        current.append(child)
        current = child
    current.append(root)

    with pytest.raises(ValueError, match="canonical JSON value must not contain cycles"):
        normalization_module().canonical_json_bytes(root)


def test_canonical_json_bytes_allows_shared_non_cyclic_references() -> None:
    shared = ["shared"]

    assert normalization_module().canonical_json_bytes([shared, shared]) == (
        b'[["shared"],["shared"]]'
    )


@pytest.mark.parametrize(
    "value",
    ["\ud800", ["\udfff"], {"\ud800": "value"}, {"key": "\ud800"}],
    ids=("root-string", "list-value", "dict-key", "dict-value"),
)
def test_canonical_json_bytes_rejects_lone_surrogates_as_invalid_utf8(value: object) -> None:
    with pytest.raises(ValueError, match="canonical JSON strings must contain valid UTF-8 text"):
        normalization_module().canonical_json_bytes(value)


def test_normalized_text_fingerprints_match_fixed_vectors() -> None:
    module = normalization_module()
    vectors = {
        " Cafe\u0301\tQuestion? \uff21 ": "2ab4a1f3c60c4d64070b51799864f0c39c1f683beaa685cddbe452592888a958",
        "caf\u00e9 question? \uff21": "cffc8d4e599d6c30541914c314ac4c0a0331b3af47783659d62a2da5e6db202c",
        "Caf\u00e9 Question! \uff21": "f185f6d3c6682694e1a3709e7e15597b7d2f58316b7e57439dc8e651f3e878f5",
        "Caf\u00e9 Question? A": "043740aadf8cbbde3fb99ca0ae18d1d335b29576017fd7b4659b6c13402fa51f",
    }

    actual = {value: module.normalized_text_fingerprint(value) for value in vectors}
    assert actual == vectors
    assert module.stem_fingerprint(" Cafe\u0301\tQuestion? \uff21 ") == vectors[
        " Cafe\u0301\tQuestion? \uff21 "
    ]
    assert all(re.fullmatch(r"[0-9a-f]{64}", digest) for digest in actual.values())


def test_nfc_equivalent_inputs_have_identical_text_and_stem_fingerprints() -> None:
    module = normalization_module()
    expected = "18c4ffda28012ce93fb9ccf50436ce7d57b63af63d5380a2aed29604a9c2e20e"
    composed = "Caf\u00e9 question"
    decomposed = "Cafe\u0301 question"

    assert module.normalized_text_fingerprint(composed) == expected
    assert module.normalized_text_fingerprint(decomposed) == expected
    assert module.stem_fingerprint(composed) == expected
    assert module.stem_fingerprint(decomposed) == expected


def test_unicode_whitespace_equivalent_inputs_have_identical_fingerprints() -> None:
    module = normalization_module()
    expected = "64989ccbf3efa9c84e2afe7cee9bc5828bf0fcb91e44f8c1e591638a2c2e90e3"
    plain = "alpha beta gamma"
    varied = "\u00a0alpha\tbeta\n\u2003gamma\u202f"

    assert module.normalized_text_fingerprint(plain) == expected
    assert module.normalized_text_fingerprint(varied) == expected
    assert module.stem_fingerprint(plain) == expected
    assert module.stem_fingerprint(varied) == expected


def test_fingerprint_apis_reject_lone_surrogates_as_invalid_utf8() -> None:
    module = normalization_module()

    for fingerprint in (module.normalized_text_fingerprint, module.stem_fingerprint):
        with pytest.raises(ValueError, match="text value must contain valid UTF-8 text"):
            fingerprint("\ud800")
    with pytest.raises(ValueError, match="canonical JSON strings must contain valid UTF-8 text"):
        module.option_set_fingerprint(["\ud800"])
    with pytest.raises(ValueError, match="canonical JSON strings must contain valid UTF-8 text"):
        module.content_revision_fingerprint("Stem", ["\ud800"])


def test_option_set_fingerprint_is_reorder_invariant_and_preserves_duplicates() -> None:
    module = normalization_module()
    repeated = [" B ", "A", "A"]
    reordered = ("A", " B ", "A")

    assert module.option_set_fingerprint(repeated) == (
        "a01a382ae06885b7d878b7dea3f2b23477f51519bda50a398331afed7726ca17"
    )
    assert module.option_set_fingerprint(reordered) == (
        "a01a382ae06885b7d878b7dea3f2b23477f51519bda50a398331afed7726ca17"
    )
    assert module.option_set_fingerprint(["A", "B"]) == (
        "b64e3448a83a5b86466465080361c1a7e1157a27ddccd4b68069cb18caffb74a"
    )


def test_option_set_fingerprint_normalizes_non_ascii_values_before_sorting() -> None:
    assert normalization_module().option_set_fingerprint(
        [" \u84dd\u3000\u8272 ", "Cafe\u0301", "A"]
    ) == "7302a959edf1eced4e72e244b21b9545e96a5f9c895eeef42d97e0c65809baff"


@pytest.mark.parametrize("value", [[], "AB", b"AB", {"A", "B"}, (item for item in ["A"])])
def test_option_set_fingerprint_rejects_empty_or_non_sequence_inputs(value: object) -> None:
    expected_error = ValueError if value == [] else TypeError
    with pytest.raises(expected_error):
        normalization_module().option_set_fingerprint(value)  # type: ignore[arg-type]


@pytest.mark.parametrize("value", [["A", 2], [None], [True]])
def test_option_set_fingerprint_rejects_non_string_elements(value: list[object]) -> None:
    with pytest.raises(TypeError):
        normalization_module().option_set_fingerprint(value)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "fingerprint_name",
    ["option_set_fingerprint", "content_revision_fingerprint"],
)
def test_option_fingerprints_reject_a_once_captured_empty_iteration(
    fingerprint_name: str,
) -> None:
    class ClaimsNonEmptyYieldsEmpty(list[str]):
        def __init__(self) -> None:
            super().__init__(["hidden value"])
            self.iteration_count = 0

        def __len__(self) -> int:
            return 1

        def __iter__(self):
            self.iteration_count += 1
            return iter(())

    module = normalization_module()
    options = ClaimsNonEmptyYieldsEmpty()
    fingerprint = getattr(module, fingerprint_name)

    with pytest.raises(ValueError, match="option_texts must not be empty"):
        if fingerprint_name == "content_revision_fingerprint":
            fingerprint("Stem", options)
        else:
            fingerprint(options)
    assert options.iteration_count == 1


@pytest.mark.parametrize(
    ("fingerprint_name", "expected"),
    [
        (
            "option_set_fingerprint",
            "b64e3448a83a5b86466465080361c1a7e1157a27ddccd4b68069cb18caffb74a",
        ),
        (
            "content_revision_fingerprint",
            "377e51ace7ddbe06b4bb0f2a693b747fceb2c4c58daaa10ec9531132704e98b3",
        ),
    ],
)
def test_option_fingerprints_accept_a_once_captured_nonempty_iteration(
    fingerprint_name: str,
    expected: str,
) -> None:
    class ClaimsEmptyYieldsValues(Sequence[str]):
        def __init__(self) -> None:
            self.iteration_count = 0

        def __len__(self) -> int:
            return 0

        def __getitem__(self, index: int) -> str:
            raise IndexError(index)

        def __iter__(self):
            self.iteration_count += 1
            return iter([" A ", "B"])

    module = normalization_module()
    options = ClaimsEmptyYieldsValues()
    fingerprint = getattr(module, fingerprint_name)

    if fingerprint_name == "content_revision_fingerprint":
        actual = fingerprint(" Cafe\u0301 stem ", options)
    else:
        actual = fingerprint(options)

    assert actual == expected
    assert options.iteration_count == 1


def test_content_revision_fingerprint_uses_exact_keys_and_source_option_order() -> None:
    module = normalization_module()

    assert module.content_revision_fingerprint(" Cafe\u0301 stem ", [" A ", "B"]) == (
        "377e51ace7ddbe06b4bb0f2a693b747fceb2c4c58daaa10ec9531132704e98b3"
    )
    assert module.content_revision_fingerprint(" Cafe\u0301 stem ", ["B", " A "]) == (
        "5bf5180ea22ed4bed7c3b2f622e1a2728da692c99a0a8762fbe7df150c5eab25"
    )


def test_content_revision_fingerprint_preserves_duplicates_and_inputs() -> None:
    module = normalization_module()
    options = ["A", "A", "B"]

    first = module.content_revision_fingerprint("Synthetic", options)
    second = module.content_revision_fingerprint("Synthetic", options)

    assert first == "b25831765d72f4a12305d2bedc806c04bf241ffc2cedfb2c8aa1d058d38886aa"
    assert second == first
    assert options == ["A", "A", "B"]
    assert module.content_revision_fingerprint("Synthetic", ["A", "B"]) != first


@pytest.mark.parametrize("question_type", ["multiple_choice", "Single_Choice", "", None])
def test_content_revision_fingerprint_requires_exact_single_choice(question_type: object) -> None:
    expected_error = TypeError if question_type is None else ValueError
    with pytest.raises(expected_error):
        normalization_module().content_revision_fingerprint(
            "Stem",
            ["A"],
            question_type=question_type,  # type: ignore[arg-type]
        )


def test_content_revision_fingerprint_rejects_question_type_subclasses_early() -> None:
    class QuestionTypeSubclass(str):
        pass

    with pytest.raises(TypeError, match="question_type must be an exact built-in string"):
        normalization_module().content_revision_fingerprint(
            "Stem",
            ["A"],
            question_type=QuestionTypeSubclass("single_choice"),
        )


def test_content_revision_fingerprint_reuses_text_and_option_validation() -> None:
    module = normalization_module()

    with pytest.raises(TypeError):
        module.content_revision_fingerprint(1, ["A"])  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        module.content_revision_fingerprint("Stem", [])
    with pytest.raises(ValueError):
        module.content_revision_fingerprint("Stem", [" \u2003 "])
