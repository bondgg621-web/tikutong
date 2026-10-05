"""Strict local answer evidence parser."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import re

_LINE=re.compile(r"^[ \t]*(?P<number>[1-9][0-9]*)[ \t]*:[ \t]*(?P<label>[A-Z])[ \t]*$")
_NUMBERED_ENTRY=re.compile(r"(?P<number>[1-9][0-9]*)[ \t]*(?P<separator>[:.、）)])[ \t]*(?P<answer>[A-Za-z]+(?:[、,，;；/][A-Za-z]+)*)")
_INLINE_ANSWER=re.compile(r"^[ \t]*(?:答案|正确答案|参考答案|Ans)[ \t]*[:：]?[ \t]*(?P<answer>\S(?:.*\S)?)[ \t]*$",re.IGNORECASE)
_BRACKET_ANSWER=re.compile(r"^[ \t]*【答案】[ \t]*(?P<answer>\S(?:.*\S)?)[ \t]*$")
_JUDGMENT=frozenset({"正确","错误","√","×"})

class AnswerParseError(ValueError): pass

@dataclass(frozen=True)
class AnswerEvidence:
    """Runtime-only rich evidence outside the frozen M3 proposal contract."""
    raw_text: str
    source_id: str
    source_revision: int
    locator: str
    answer_kind: str
    question_number: int | None
    raw_answer: str
    normalized_labels: tuple[str, ...]
    confidence: str
    warnings: tuple[str, ...]

@dataclass(frozen=True)
class AnswerKeyEntry:
    question_number: int
    raw_answer: str
    normalized_labels: tuple[str, ...]
    raw_entry: str
    source_locator: str

@dataclass(frozen=True)
class AnswerKeyBlock:
    raw_text: str
    entries: tuple[AnswerKeyEntry, ...]
    source_locator: str
    warnings: tuple[str, ...]

@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    source_id: str
    source_revision: int
    locator: str
    question_number: int
    source_lexeme: str
    evidence_fingerprint: str
    def as_dict(self)->dict:
        return {"evidence_id":self.evidence_id,"source_id":self.source_id,"source_revision":self.source_revision,"locator":self.locator,"question_number":self.question_number,"source_lexeme":self.source_lexeme,"evidence_fingerprint":self.evidence_fingerprint}


def fingerprint(number:int,label:str)->str:
    payload=f"m3-answer-evidence-v1\0{number}\0{label}".encode('utf-8')
    return sha256(payload).hexdigest()


def parse_answer_text(text:str,*,source_id:str,source_revision:int,uuid_factory)->list[EvidenceRecord]:
    if type(text) is not str: raise AnswerParseError("answer source text is invalid")
    logical=text.replace("\r\n","\n").replace("\r","\n")
    out=[]
    for n,line in enumerate(logical.split("\n"),1):
        if line.strip()=="": continue
        m=_LINE.fullmatch(line)
        if not m: raise AnswerParseError("answer source structure is ambiguous")
        number=int(m.group('number')); label=m.group('label')
        out.append(EvidenceRecord(str(uuid_factory()),source_id,source_revision,f"line:{n}",number,label,fingerprint(number,label)))
    return out


def _normalized_labels(raw_answer: str) -> tuple[str, ...]:
    compact=re.sub(r"[ \t、,，;；/]","",raw_answer)
    if not compact or not compact.isascii() or not compact.isalpha():
        return ()
    return tuple(character.upper() for character in compact)


def _numbered_entries(line: str, line_number: int) -> tuple[AnswerKeyEntry, ...]:
    matches=list(_NUMBERED_ENTRY.finditer(line))
    if not matches or not re.fullmatch(r"[ \t;；,，]*",_NUMBERED_ENTRY.sub("",line)):
        return ()
    return tuple(AnswerKeyEntry(int(match.group("number")),match.group("answer"),_normalized_labels(match.group("answer")),match.group(0).strip(),f"line:{line_number}") for match in matches)


def parse_answer_key_blocks(text: str, *, source_id: str) -> tuple[AnswerKeyBlock, ...]:
    """Recognize multi-entry answer keys without attaching them to a question."""
    if type(text) is not str:
        raise AnswerParseError("answer source text is invalid")
    if type(source_id) is not str or not source_id:
        raise AnswerParseError("answer source identity is invalid")
    logical=text.replace("\r\n","\n").replace("\r","\n")
    return tuple(AnswerKeyBlock(line,entries,f"line:{line_number}",()) for line_number,line in enumerate(logical.split("\n"),1) if len(entries:=_numbered_entries(line,line_number))>=2)


def parse_answer_evidence(text: str, *, source_id: str, source_revision: int, current_question_number: int | None = None, current_context_unique: bool = False, structurally_adjacent: bool = False, unresolved_boundary: bool = False) -> tuple[AnswerEvidence, ...]:
    """Parse runtime-only rich answer evidence with fail-closed attachment."""
    if type(text) is not str:
        raise AnswerParseError("answer source text is invalid")
    if type(source_id) is not str or not source_id or type(source_revision) is not int or source_revision < 1:
        raise AnswerParseError("answer source identity is invalid")
    output=[]
    logical=text.replace("\r\n","\n").replace("\r","\n")
    for line_number,line in enumerate(logical.split("\n"),1):
        if not line.strip():
            continue
        locator=f"line:{line_number}"
        entries=_numbered_entries(line,line_number)
        if len(entries)>=2:
            output.extend(AnswerEvidence(line,source_id,source_revision,locator,"ANSWER_KEY_BLOCK",entry.question_number,entry.raw_answer,entry.normalized_labels,"high",()) for entry in entries)
            continue
        if len(entries)==1:
            entry=entries[0]
            output.append(AnswerEvidence(line,source_id,source_revision,locator,"NUMBERED_ANSWER",entry.question_number,entry.raw_answer,entry.normalized_labels,"high",()))
            continue
        inline=_INLINE_ANSWER.fullmatch(line) or _BRACKET_ANSWER.fullmatch(line)
        if inline is None:
            output.append(AnswerEvidence(line,source_id,source_revision,locator,"UNRESOLVED_ANSWER",None,line.strip(),(),"low",("ANSWER_ATTACHMENT_UNCERTAIN",)))
            continue
        raw_answer=inline.group("answer")
        labels=_normalized_labels(raw_answer)
        if raw_answer in _JUDGMENT:
            output.append(AnswerEvidence(line,source_id,source_revision,locator,"JUDGMENT_ANSWER",None,raw_answer,(),"runtime_only",()))
        elif not labels:
            output.append(AnswerEvidence(line,source_id,source_revision,locator,"TEXT_ANSWER",None,raw_answer,(),"runtime_only",()))
        elif current_question_number is not None and current_context_unique and structurally_adjacent and not unresolved_boundary:
            output.append(AnswerEvidence(line,source_id,source_revision,locator,"INLINE_CURRENT",current_question_number,raw_answer,labels,"medium",()))
        else:
            output.append(AnswerEvidence(line,source_id,source_revision,locator,"UNRESOLVED_ANSWER",None,raw_answer,labels,"low",("ANSWER_ATTACHMENT_UNCERTAIN",)))
    return tuple(output)


def semantic_key(e:dict|EvidenceRecord)->tuple[str,int,str]:
    if isinstance(e,EvidenceRecord): return (e.source_id,e.question_number,e.evidence_fingerprint)
    return (e['source_id'],e['question_number'],e['evidence_fingerprint'])


def instance_key(e:dict|EvidenceRecord)->tuple[str,int,str,str]:
    if isinstance(e,EvidenceRecord): return (e.source_id,e.source_revision,e.locator,e.evidence_fingerprint)
    return (e['source_id'],e['source_revision'],e['locator'],e['evidence_fingerprint'])
