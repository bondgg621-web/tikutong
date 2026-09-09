# Question Bank Curator

## Current Accepted Milestone

Milestones 1 and 2 are accepted. Milestone 2 Tasks 1-12 passed independent
specification review, independent quality review, final synthetic CLI acceptance,
and two identical authoritative full-suite runs on 2026-08-14.

Milestone 2 adds one explicit, registry-backed strict single-choice parse and
first Candidate/Option materialization. It does not add answer association,
Decision creation, validated promotion, rescans, identity migration, batch
parsing, remote/model calls, PDF/OCR, databases, or dependency installation.

## Authorities

- M2 specification: `docs/MILESTONE-2-SINGLE-CHOICE-PARSER-SPEC.md`
- M2 specification SHA-256: `A4E6CFCEE04A497243DA9282931B1BAA99BA1589702420AF3C5034D88A6A809C`
- M2 plan: `docs/MILESTONE-2-SINGLE-CHOICE-PARSER-PLAN.md`
- M2 plan SHA-256: `07ED596F2842D513C5CE0224777698A5E38724216DF7FD58A5BFEF4FA8DC262A`
- M1 specification SHA-256: `C61A5A79F3443318B1E35B0C793404D3D3F57F027156B84E60FA1B10ACFF96A5`

Use this single authoritative read order before further work:

1. `START-HERE.md`
2. `docs/PRODUCT-BASELINE.md`
3. `docs/MILESTONE-2-SINGLE-CHOICE-PARSER-SPEC.md`
4. `docs/MILESTONE-2-SINGLE-CHOICE-PARSER-PLAN.md`
5. `docs/THINKING-INTENSITY-REMINDER-POLICY.md`
6. `docs/SIDE-CONVERSATION-HANDOFF.md`

## Current Evidence

- Latest accepted root run after Task 11: `661 passed, 3 skipped in 81.82s`.
- The three skips are direct symlink tests unavailable under this Windows host;
  junction and hardlink defenses passed.
- Final synthetic CLI acceptance passed: 7 Candidates with option counts
  `4,4,4,4,4,3,3`; repeat parse returned `2` without byte or ID churn;
  needs-review returned `3`; stale registry returned `2`; all JSON read back.
- Reproducible evidence manifest: `C:\Users\lenovo\AppData\Local\Temp\qbc-m2-final-acceptance-l4pmrtyz\acceptance-evidence.json`. It records all seven command results, stdout/stderr, before/after candidate hashes and IDs, input-tree hashes, and 25 JSON artifact hashes.
- Final authoritative double regression, run from the repository root with the
  command below: run 1 exited `0` with `661 passed, 3 skipped in 35.75s`; run 2
  exited `0` with `661 passed, 3 skipped in 36.60s`.

## Acceptance Map

Each M2 specification section 19 item has named executable evidence:

| Item | Primary test evidence |
|---|---|
| 1 | `test_run_inventory_publishes_complete_workspace_without_touching_input` plus the full suite |
| 2 | `test_supported_suffixes_are_case_insensitive_and_source_id_declares_role`; `test_utf8_bom_and_newline_byte_forms_have_equal_parse_results` |
| 3 | `test_strict_seven_fixture_yields_exact_questions_and_option_counts` |
| 4 | `test_materializes_exact_two_question_candidate_document_in_source_allocation_order` |
| 5 | `test_option_owners_source_refs_positions_and_locators_are_coherent` |
| 6 | `test_normalized_text_fingerprints_match_fixed_vectors`; `test_option_set_fingerprint_is_reorder_invariant_and_preserves_duplicates`; `test_content_revision_fingerprint_uses_exact_keys_and_source_option_order` |
| 7 | `test_strict_seven_parser_materialization_groups_last_two_without_identity_merge` |
| 8 | `test_duplicate_option_text_remains_distinct_on_first_materialization` |
| 9 | `test_invalid_option_cardinality_or_labels_rejects_the_whole_block`; `test_missing_marker_header_and_outside_option_have_distinct_structure_findings`; `test_unclosed_fence_reports_opening_locator_without_counting_fenced_blocks` |
| 10 | `test_unsupported_fixture_and_valid_block_return_diagnostics_without_publication` |
| 11 | `test_headings_prose_blanks_and_answer_like_text_outside_blocks_are_ignored` |
| 12 | `test_answer_like_text_inside_block_is_ordinary_unknown_text_and_rejects_block`; `test_executable_m2_scope_has_no_forbidden_capabilities` |
| 13 | `test_only_the_explicit_registry_source_is_read_from_input` |
| 14 | `test_missing_or_noncanonical_source_id_is_rejected`; `test_unsupported_extension_has_frozen_issue_code`; `test_stale_content_hash_requires_inventory_without_registry_update`; `test_symlink_escape_is_rejected_where_supported`; `test_windows_junction_escape_is_rejected_where_supported` |
| 15 | `test_service_no_questions_publishes_sanitized_needs_review_issue`; `test_service_findings_publish_needs_review_without_candidate` |
| 16 | `test_existing_candidate_fails_closed_without_uuid_allocation_or_mutation`; `test_repeating_completed_publication_preserves_all_authoritative_bytes` |
| 17 | `test_schema_valid_candidate_tampering_is_detected_against_complete_run_hash` |
| 18 | `test_invalid_publication_contract_is_rejected_before_candidate_staging`; `test_successful_publication_finishes_only_after_candidate_read_back`; `test_parse_run_artifact_reports_final_read_back_mismatch`; `test_cross_document_validator_compares_declared_hashes_without_filesystem_io` |
| 19 | `test_candidate_staging_failure_prevents_any_publication`; `test_injected_candidate_publish_failure_cleans_staging_and_preserves_absence`; `test_candidate_read_back_failure_leaves_candidate_and_publication_run`; `test_final_run_update_failure_leaves_recoverable_publication_state` |
| 20 | `test_existing_candidate_with_exact_incomplete_run_repairs_only_run_status` |
| 21 | `test_valid_registry_lookup_decodes_hashes_parses_and_changes_nothing`; `test_success_preserves_input_tree_and_does_not_read_adjacent_source`; `test_stale_source_fails_before_uuid_allocation_and_writes`; `test_incomplete_run_mismatch_fails_without_uuid_or_file_mutation`; `test_tampered_registry_traversal_fails_before_uuid_or_workspace_mutation`; `test_read_only_source_is_parsed_without_mutation` |
| 22 | `test_inventory_and_parse_write_only_inside_explicit_workspace` |
| 23 | `test_copied_skill_runs_inventory_and_parse_outside_repository` |
| 24 | `test_executable_m2_scope_has_no_forbidden_capabilities`; `test_m2_runtime_has_no_remote_process_package_database_or_text_execution` |
| 25 | Task 12 authoritative command ran twice with identical `661 passed, 3 skipped` counts and exit code `0` |

## Next Action

Stop at the accepted M2 boundary. If work resumes, the single next atomic action
is to design and approve a separate Milestone 3 before any implementation. Do
not begin answer association, initialize Git, commit, push, install dependencies,
or access a network without separate authorization.
