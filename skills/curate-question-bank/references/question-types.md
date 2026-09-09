# Question type contract

Milestone 0 freezes only these semantic answer contracts:

| Question type | Contract | Validated rule |
| --- | --- | --- |
| `single_choice` | `resolved_option_ids` binds one persistent option ID. | Exactly one owned option ID. |
| `multiple_choice` | `resolved_option_ids` is an unordered, non-repeating set. | Two or more owned option IDs. |
| `true_false` | `boolean_value` is normalized and `source_lexeme` retains the source wording. | Boolean value plus nonempty source lexeme. |
| `unsupported` / `ambiguous` | Preserve source evidence only. | Never enter `validated`. |

`option_id` is persistent identity. `source_label` (such as A/B/C/D) and
`current_position` are revision-specific presentation fields. `source_lexeme`
is the unmodified answer notation. They are never interchangeable.

The golden fixture is intentionally `single_choice` only. Multiple choice and
true/false are validated through Contract tests, not a parser or adapter.
