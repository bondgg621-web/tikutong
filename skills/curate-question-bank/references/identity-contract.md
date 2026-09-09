# Identity contract

## SourceIdentity

`source_id` and `dataset_id` are persistent UUIDs. A SourceIdentity records
`current_relative_path`, `path_history`, `current_content_hash`, and positive
`revision`. Paths and hashes are evidence, never persistent identity keys. A
pure rename can be automatically recognized only when the content hash has one
unique match; a non-unique hash match or simultaneous path/content change must
create an identity review item.

## CandidateIdentity and fingerprints

Every candidate has a persistent UUID `candidate_id` and a positive revision;
a displayed question number is not an ID. It retains these three fingerprints:

- `stem_fingerprint`: normalized stem;
- `option_set_fingerprint`: order-independent option multiset, including
  duplicate counts;
- `content_revision_fingerprint`: question type, stem, and ordered options.

Fingerprint 只是匹配证据，不是身份键。 They may identify matching evidence but
cannot merge, replace, or independently create an identity.

## OptionIdentity

Every option retains `option_id`, owning `candidate_id`, `option_revision`,
`normalized_text_fingerprint`, `current_position`, `source_label`,
`source_ref`, and `previous_labels`. An option ID may migrate through a reorder
only when its text fingerprint is unique in both the old and new question.
Duplicate text or a changed text fingerprint requires review and emits
`QB-OPTION-IDENTITY-AMBIGUOUS`; it never migrates automatically.

## Candidate matching and duplicates

Rescans use a one-to-one (一对一) process in this strict evidence order:
unique content-revision fingerprint; unique stem plus option-set fingerprint;
structural locator; uniquely matched neighboring anchors; local sequence order;
then user confirmation. A matched node leaves the candidate set.

Identical-content candidates remain separate candidate IDs. They may migrate in
group order only if duplicate counts agree, both outer anchors are stable, and
the group has no insertion, deletion, or edit. Otherwise create
`QB-IDENTITY-AMBIGUOUS` and do not inherit a decision. Duplicate detection is
therefore separate from identity migration.

## Frozen transition examples

- 文件内容不变但重命名: retain the source ID and valid decisions only after the
  unique content-hash rule succeeds.
- 文件前方插题: a changed question number is locator evidence only; it cannot
  replace a candidate ID.
- 题干修改: increment the candidate revision and require related decisions to
  be revalidated.
- 唯一选项文字重排: option IDs may migrate only under the uniqueness rule.
- 重排后答案仍指向原 option ID: the answer decision may remain valid after the
  label is reparsed and audited.
- 重排后答案指向另一 option ID: mark the answer decision
  `needs_revalidation`.
- 选项文字修改: do not auto-migrate the option identity.
- 重复组之前插入普通题, 删除重复组中的一道题, or 向重复组新增相同题: group-order
  migration is no longer automatic; emit `QB-IDENTITY-AMBIGUOUS` unless a user
  supplies a one-to-one confirmation.
