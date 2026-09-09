# Fixed issue codes

| Code | Trigger | Blocking level | Allowed user actions |
| --- | --- | --- | --- |
| `QB-SOURCE-UNSUPPORTED` | Source format has no authorized adapter. | blocking | retain, exclude, provide adapter |
| `QB-SOURCE-READ-FAILED` | Authorized source cannot be read. | blocking | retry, retain, exclude |
| `QB-ROLE-AMBIGUOUS` | Source role cannot be determined. | review_required | assign role, retain, exclude |
| `QB-TYPE-UNSUPPORTED` | Question type is outside contract. | blocking | retain, mark unsupported |
| `QB-STRUCTURE-AMBIGUOUS` | Structure cannot be safely normalized. | review_required | correct source, retain, exclude |
| `QB-ANSWER-MISSING` | No answer evidence binds the candidate. | blocking | provide evidence, retain |
| `QB-ANSWER-CONFLICT` | Competing answer evidence disagrees. | blocking | choose evidence, retain |
| `QB-ASSOCIATION-LOW-CONFIDENCE` | Association evidence is insufficient. | review_required | confirm, reject, retain |
| `QB-DUPLICATE-CANDIDATE` | Similar content is detected. | review_required | mark relation, keep separate |
| `QB-IDENTITY-AMBIGUOUS` | One-to-one candidate migration is not unique. | blocking | confirm mapping, archive decision |
| `QB-OPTION-IDENTITY-AMBIGUOUS` | Option IDs cannot migrate uniquely. | review_required | confirm mapping, rebind answer |
| `QB-DECISION-STALE` | Decision revision/evidence is stale. | blocking | revalidate, archive |
| `QB-FORMAT-LOSS` | Authorized transformation loses material formatting. | review_required | retain source, accept loss |
| `QB-SECURITY-INSTRUCTION-DATA` | Source contains instruction-like untrusted data. | blocking | retain as data, quarantine |
| `QB-REMOTE-CAPABILITY-NOT-AUTHORIZED` | Processing needs an unapproved remote capability. | blocking | authorize, retain, exclude |
