# State and decision contract

## DecisionBinding

A decision binds `candidate_id` and candidate revision, a decision type/value,
one or more evidence bindings, and a status: `valid`,
`needs_revalidation`, or `archived`. Each evidence binding records source ID,
source revision, locator, and evidence fingerprint.

Only the Runtime validator enforces cross-object existence, option ownership,
evidence existence, revision relationships, and the `validated` gate. JSON
Schema and Runtime validator overlap only on required fields, JSON types, enum,
patterns/UUIDs, array cardinality, and basic reference shape.

## Decision invalidation matrix

| Change | Required result |
| --- | --- |
| 文件仅重命名，内容不变 | Decision remains `valid`. |
| Question number/locator changes without content change | Update locator; decision remains valid. |
| Answer source changes but cited evidence does not | Decision remains valid. |
| Answer evidence changes | `needs_revalidation`. |
| Stem changes | Revalidate related answer, duplicate, and association decisions. |
| Options reorder with uniquely migrated option identities | Reparse labels and audit. |
| Reordered answer still identifies the original option ID | Decision may remain valid. |
| Reordered answer identifies a different option ID | `needs_revalidation`. |
| Option text changes or migration is non-unique | Do not inherit automatically. |
| Same candidate cannot be established | `QB-IDENTITY-AMBIGUOUS`. |
| Original candidate is removed | 历史决定归档; do not delete it. |

A candidate can be `validated` only with a current `valid` answer-resolution
decision that binds its current revision and satisfies its question-type rule.
