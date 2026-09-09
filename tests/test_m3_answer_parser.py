from __future__ import annotations
from hashlib import sha256
import pytest
from m2_helpers import UUIDSequence
from qbanswer.answer_parser import AnswerParseError,fingerprint,parse_answer_text

SID='00000000-0000-0000-0000-000000000001'

def test_strict_number_label_and_blank_lines():
    rows=parse_answer_text(' 1 : A \n\n2:\tB\n',source_id=SID,source_revision=3,uuid_factory=UUIDSequence(1))
    assert [(x.question_number,x.source_lexeme,x.locator) for x in rows]==[(1,'A','line:1'),(2,'B','line:3')]

def test_crlf_cr_lf_have_same_semantics_and_fingerprint():
    a=parse_answer_text('1: A\r\n2: B\r',source_id=SID,source_revision=1,uuid_factory=UUIDSequence(1))
    b=parse_answer_text('1: A\n2: B\n',source_id=SID,source_revision=1,uuid_factory=UUIDSequence(10))
    assert [(x.question_number,x.source_lexeme,x.evidence_fingerprint) for x in a]==[(x.question_number,x.source_lexeme,x.evidence_fingerprint) for x in b]

def test_any_nonempty_invalid_line_fails_whole_source():
    with pytest.raises(AnswerParseError):parse_answer_text('1: A\ncomment\n2: B\n',source_id=SID,source_revision=1,uuid_factory=UUIDSequence(1))

def test_lowercase_or_zero_number_is_rejected():
    for text in ('1: a\n','0: A\n','1: AA\n'):
        with pytest.raises(AnswerParseError):parse_answer_text(text,source_id=SID,source_revision=1,uuid_factory=UUIDSequence(1))

def test_fingerprint_ignores_locator_and_whitespace_but_not_number_or_label():
    assert fingerprint(1,'A')==sha256(b'm3-answer-evidence-v1\x001\x00A').hexdigest()
    assert fingerprint(1,'A')!=fingerprint(2,'A')!=fingerprint(2,'B')
