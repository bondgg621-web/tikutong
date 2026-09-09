"""Strict local answer evidence parser."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import re

_LINE=re.compile(r"^[ \t]*(?P<number>[1-9][0-9]*)[ \t]*:[ \t]*(?P<label>[A-Z])[ \t]*$")

class AnswerParseError(ValueError): pass

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


def semantic_key(e:dict|EvidenceRecord)->tuple[str,int,str]:
    if isinstance(e,EvidenceRecord): return (e.source_id,e.question_number,e.evidence_fingerprint)
    return (e['source_id'],e['question_number'],e['evidence_fingerprint'])


def instance_key(e:dict|EvidenceRecord)->tuple[str,int,str,str]:
    if isinstance(e,EvidenceRecord): return (e.source_id,e.source_revision,e.locator,e.evidence_fingerprint)
    return (e['source_id'],e['source_revision'],e['locator'],e['evidence_fingerprint'])
