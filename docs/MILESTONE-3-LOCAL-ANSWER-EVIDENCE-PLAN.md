# Milestone 3 本地答案证据关联与人工核验｜实施计划

> **状态：本机本地化实施计划。独立计划审查结论记录在外部审查证据中；未获用户对本文件精确 SHA-256 的再次批准前，禁止编码。**
>
> 本计划只定义未来实施顺序、文件白名单、TDD 门和审查门；计划审查轮只允许创建本文件，不得创建 M3 runtime、Schema、test 或 fixture。

## 0. 权威基线与执行纪律

项目根：包含本文件的 repository root；所有相对路径和命令都从该根解析，实施 Task 0 必须先验证其确为当前保存项目，不在计划中冻结某台主机的绝对路径。

```text
.
```

唯一权威 M3 规格：

```text
docs/MILESTONE-3-LOCAL-ANSWER-EVIDENCE-SPEC.md
SHA-256 = 8d17742f4158647ac821becd917211e15b83a93fb8f63fa27bf64c0bf2d6dc8e
```

当前项目状态：

```text
M3_SPEC_REVIEW = PASS
M3_SPEC_APPROVAL = GRANTED
M3_ACCEPTANCE = NOT_GRANTED
IMPLEMENTATION_PLAN_AUTHORIZED = YES
IMPLEMENTATION_AUTHORIZED = NO
```

最近一次本机既有回归证据：

```text
661 passed, 3 skipped
```

该历史结果只说明 M0/M1/M2 在规格文档修订后无回归，不是 M3 功能测试。Task 0 必须在本机重新核验，不能把历史结果当作当前实施证据。

### 0.1 实施总原则

未来获批实施时，每个 Task 必须遵循：

1. 核对冻结规格 SHA-256；不匹配立即 STOP。
2. 记录本 Task 允许修改/新增文件的基线存在性与 SHA-256。
3. 先写 RED 测试；确认失败原因恰好是缺少当前 Task 行为，而不是环境/导入/旧回归故障。
4. 只写使当前 RED 变 GREEN 的最小实现。
5. 运行 targeted GREEN。
6. 运行全套既有 + 已新增测试。
7. 重新核对冻结文件 hash guard、隐私/范围 guard。
8. 做本 Task 独立只读质量审查；PASS 后才进入下一个 Task。
9. 任一 blocker 不得跨 Task “顺手修复”；STOP 并回网页端设计。

### 0.2 本地化调整原则

本计划由网页端基于脱敏快照和已冻结规格设计。本机 Codex 在**计划审查阶段**必须核对真实项目的：

- 目录结构；
- `qbcore` 公开/内部接口；
- Schema 加载方式；
- M1 workspace/registry/lock/recovery API；
- M2 parser/parse-service/Candidate materialization API；
- 当前测试 helper 约定；
- Python 版本与 pytest 配置。

如果网页端候选文件名或复用接口与真实项目不兼容，只允许对**实施计划文字**做必要、最小、本地化调整；不得改变冻结规格语义、扩大功能或提前编码。

---

## 1. 冻结实施范围

### 1.1 必须保持 byte-for-byte 不变

未来 M3 实施不得修改：

- M0 六个顶层权威 Schema；
- `skills/curate-question-bank/references/question-types.md`；
- `skills/curate-question-bank/references/identity-contract.md`；
- `skills/curate-question-bank/references/state-contract.md`；
- `skills/curate-question-bank/references/issue-codes.md`；
- `skills/curate-question-bank/scripts/qbcore/validation.py`；
- 全部已验收 M1/M2 runtime；
- 全部既有 M1/M2 Schema；
- 全部既有 M1/M2 tests、fixtures、expected artifacts、规格与实施计划；
- 已批准的 M3 规格本身。

如果真实实施必须修改上述任一项，视为规格/计划 incompatibility：立即 STOP，不得自行放宽。

### 1.2 未来允许新增的 runtime 白名单

本机核对后的物理拆分：

```text
skills/curate-question-bank/
├─ scripts/
│  ├─ qbanswer_cli.py
│  └─ qbanswer/
│     ├─ __init__.py
│     ├─ contracts.py
│     ├─ artifacts.py
│     ├─ answer_parser.py
│     ├─ source_snapshot.py
│     ├─ association.py
│     ├─ review.py
│     ├─ state_graph.py
│     ├─ transaction.py
│     ├─ run_audit.py
│     ├─ prepare.py
│     ├─ confirmation.py
│     ├─ reverify.py
│     └─ service.py
└─ schemas/
   └─ m3/
      ├─ answer-association-run.schema.json
      ├─ answer-association-proposal.schema.json
      ├─ answer-association-confirmation.schema.json
      ├─ answer-association-reverify.schema.json
      ├─ answer-association-provenance.schema.json
      ├─ answer-association-transaction.schema.json
      ├─ answer-association-pointer.schema.json
      └─ answer-association-commit.schema.json
```

这是冻结的 M3 物理拆分，不是新增产品语义。未来若实际实现证明其中两个内部模块必须合并或更名，属于 plan incompatibility，必须 STOP 并重新走计划批准，不能在编码 Task 中自行偏离。

### 1.3 未来允许新增的测试白名单

```text
tests/
├─ m3_helpers.py
├─ test_m3_scope_guard.py
├─ test_m3_contracts.py
├─ test_m3_answer_parser.py
├─ test_m3_source_snapshot.py
├─ test_m3_association.py
├─ test_m3_review.py
├─ test_m3_state_graph.py
├─ test_m3_transaction.py
├─ test_m3_run_audit.py
├─ test_m3_prepare.py
├─ test_m3_confirmation.py
├─ test_m3_reverify.py
├─ test_m3_cli.py
├─ test_m3_safeguards.py
├─ test_m3_privacy.py
├─ test_m3_portability.py
└─ test_m3_end_to_end.py

tests/fixtures/m3-answer-association/
├─ questions-strict-two.md
├─ questions-duplicate-number.md
├─ answers-confirmable.txt
├─ answers-conflict.txt
├─ answers-invalid-line.txt
├─ answers-invalid-label.txt
├─ answers-unknown-number.txt
├─ answers-duplicate-same.txt
└─ answers-duplicate-conflict.txt
```

fixture 只允许 synthetic 数据，不得复制真实题库、真实答案或个人资料。UTF-8 BOM、CRLF/CR 和故障注入变体在测试临时目录按硬编码 exact bytes 运行时生成，不再增加持久 fixture。

### 1.4 既有文件的未来允许修改

只有在所有核心 M3 runtime/contract tests 已通过，并经过对应 Task 审查后，才允许：

- `skills/curate-question-bank/SKILL.md`：增加已经真实实现且验证通过的 M3 能力与边界说明；
- `skills/curate-question-bank/agents/openai.yaml`：只更新与已实现能力一致的最小元数据。

以下文件**不属于实施阶段修改范围**；只有 M3 最终验收后才能更新：

- `START-HERE.md`；
- `NEW-THREAD-PROMPT.md`；
- `docs/SIDE-CONVERSATION-HANDOFF.md`。

---

## 2. 架构责任冻结

### 2.1 `qbanswer` 只能只读复用 `qbcore`

允许复用 M1/M2 已验收能力：

- workspace/path confinement；
- registry/source resolution；
- M2 UTF-8 文本规范化/严格 parser；
- Candidate artifact 读取；
- M0 基础 Schema/validator 的只读验证。

本机核对确认当前 `qbcore` **没有**可复用的 exclusive lock；M3 必须在 `qbanswer/transaction.py` 内实现规格 §14.1 的 stdlib Windows/POSIX non-blocking advisory lock。

禁止：

- 修改 `qbcore` 以“方便 M3”；
- 通过 monkey patch 改变 M1/M2 行为；
- 复制后改写旧 Candidate/Option identity 规则；
- 把 M3 功能塞回 M2 CLI/runtime。

### 2.2 内部模块责任

- `contracts.py`：加载/验证八个 M3 Schema；执行 M3 特有 cross-field 条件，但不做业务发布。
- `artifacts.py`：严格 JSON 类型门、compact canonical JSON、workspace JSON bytes、SHA-256、immutable/atomic read-back primitives；不得包含业务状态机。
- `answer_parser.py`：严格答案语法、EvidenceRecord、evidence fingerprint；纯逻辑，不访问 workspace。
- `source_snapshot.py`：显式 source role/registry/revision/hash/path 核验；只读重放 M2 parser并执行 Candidate/Option identity gate。
- `association.py`：raw association、semantic key、确定性排序、`adjudication_still_applies` 唯一实现。
- `review.py`：stable issue key、ReviewItem 去重/recurrence/supersession、blocking/allowed-action 映射；不直接发布 snapshot。
- `state_graph.py`：构造/读取 candidate-review-decision-provenance snapshot 视图和第 15.2 节完整跨对象 validator；纯验证优先，不持锁写入。
- `transaction.py`：workspace 锁内 plan/state/commit/current 发布与五 crash-point 恢复；canonical truth source 实现。
- `run_audit.py`：`run.json` 原子更新、terminal reconciliation；明确从属于 transaction，不反向决定 canonical 状态。
- `prepare.py`：prepare operation orchestration；只组合已冻结的 source/association/review/transaction primitives。
- `confirmation.py`：confirmation action validator、Decision/Review/Candidate 精确父子差分，包括 `archive_stale`。
- `reverify.py`：required Decision set、不可缩减 source set、历史实例→当前语义/实例映射、安全失效。
- `service.py`：公开 prepare/confirm/reverify 服务入口和恢复入口；不得重复内部规则。
- `qbanswer_cli.py`：参数解析、稳定 JSON stdout、退出码映射；不放业务判断。

任何规则只能有一个权威实现位置。尤其：

- `adjudication_still_applies` 只能有一个实现；
- transaction recovery 只能有一个实现；
- validated gate 只能有一个实现；
- proposal confirmation-base validation 只能有一个实现；
- `archive_stale` cross-object binding 只能有一个实现。

### 2.3 本机真实接口映射

计划冻结时已核对以下实际接口；未来实现不得发明不存在的 M1/M2 API：

- 根目录与写入边界：`qbcore.paths.validate_roots(input_root, workspace_root) -> RootPolicy`，所有 M3 写目标必须先经 `RootPolicy.assert_write_target(path)`；`Workspace.initialize()` 会写目录，纯只读 source/snapshot 路径不得调用它。
- 注册 source 的安全 raw snapshot：`qbcore.parse_service._resolve_single_choice_source_snapshot(...) -> ResolvedSourceSnapshot`。这是当前唯一同时完成 registry、revision、hash、path/reparse 和严格 UTF-8 核对且不强制把答案源解析成题目的冻结只读入口；M3 只包装调用，不复制其安全规则、不修改 `qbcore`。
- 完整 M2 publication 基线：用 `Workspace(policy)`（不 initialize）配合 `qbcore.parse_service._existing_candidate_matches_complete_run(workspace=..., resolved=...)` 做只读一致性门；它必须为 true，且 M3 仍需独立读取并 hash `candidates/sources/<question_source_id>.json`。
- 题目重放与 Candidate 结构：`qbcore.single_choice_parser.parse_single_choice(text) -> ParseResult`；随后调用 `qbcore.candidate_materializer.materialize_candidates(...)`，其 `uuid_factory` 按 M2 Candidate artifact 的 source 顺序依次返回 existing Candidate/Option UUID，只用于重建并逐字段比较结构，绝不分配、迁移或写回身份。
- 冻结基础对象校验：`qbcore.validation.validate_document(kind, value)` 只支持 `manifest/candidate/review-item/decision`，`validate_bundle(bundle)` 只覆盖 M0 overlap；M3 增强跨对象规则必须留在 `qbanswer/state_graph.py`。
- M1/M2 Schema loader 不可扩展：`workspace_contracts.DOCUMENT_KINDS` 和 `parse_contracts.PARSE_DOCUMENT_KINDS` 都是冻结集合；M3 `contracts.py` 直接从 sibling `schemas/m3/` 加载八个 Schema，并自行实现所需 `oneOf/$ref/format/cross-field` 校验，不能修改旧集合。
- JSON 发布：`qbcore.workspace.workspace_json_payload()` 和 `Workspace.write_json_atomic()` 不满足 M3 全部 exact-type、NaN/subclass、replace 后 read-back 与 transaction 语义，M3 只能在 `artifacts.py/transaction.py` 复用 `RootPolicy` 边界并实现更严格的新 primitives。
- 恢复：`qbcore.recovery` 是 M1 checkpoint 恢复，不是 M3 canonical transaction recovery；M3 不调用它收口 plan/state/commit/current。
- 测试基础：`tests/conftest.py` 提供 `REPOSITORY_ROOT/SCRIPTS_ROOT`，`tests/m2_helpers.py` 已有 `UUIDSequence`、fixed clock、exact-bytes/tree hash、M1 workspace bootstrap 和 CLI subprocess harness；`m3_helpers.py` 可只读复用这些 helper，但 expected M3 bytes/hash 必须独立硬编码。
- 当前运行基线是 Python 3.12，runtime dependencies 为空；`jsonschema` 仅是 dev extra。M3 runtime 不得新增依赖，也不得依赖 dev-only `jsonschema` 才能运行。

---

## 3. Task 0｜冻结 authority、baseline、helpers 与 scope guard

**未来允许创建：** `tests/m3_helpers.py`、`tests/test_m3_scope_guard.py`。本 Task 不创建 runtime。

### RED

1. 本机重算 M3 spec SHA，必须等于批准值。
2. 运行全套既有测试；历史参考为 `661 passed, 3 skipped`，实际必须 exit 0。
3. 建立 immutable authority hash map：M0/M1/M2 受保护文件全部记录 SHA-256。
4. 写 scope-guard RED：未来 M3 只能出现于第 1 节白名单；旧 authority 任何字节变化都失败；禁用网络/进程/动态执行/任意路径/API token。

### GREEN

5. 建立 synthetic-only helper：从 `tests/conftest.py` 与 `tests/m2_helpers.py` 只读复用 repository roots、UUID/clock、exact-bytes/tree hash 和 CLI subprocess harness，再增加 M3 artifact read-back；不得复制真实题库。
6. helper 不得调用未来被测实现生成 expected bytes/hash。
7. scope guard 在“只有 helper + 测试”状态 GREEN。
8. 全套回归 GREEN。

### Gate

- 规格 SHA、authority hashes、baseline tests 任一不匹配：STOP。
- 不得在 Task 0 顺手创建 M3 runtime 或 Schema。

---

## 4. Task 1｜八个 M3 Schema + JSON/hash 合同

**未来创建：** `qbanswer/__init__.py`、八个 `schemas/m3/*.schema.json`、`qbanswer/contracts.py`、`qbanswer/artifacts.py`、`tests/test_m3_contracts.py`。

### RED

覆盖：

- 八个 Schema 最小合法文档；
- `additionalProperties: false`；
- UUID、小写 SHA-256、相对路径、UTC RFC3339 Z；
- proposal 六类 conclusion：`confirmable/conflict/missing/low_confidence/adjudicated/stale`；
- `low_confidence` Candidate-bound/no-Candidate nested `oneOf`；
- `stale` 必须精确绑定 Candidate/revision + stale Decision + open `QB-DECISION-STALE` ReviewItem + stable issue lineage；
- confirmation action payload `oneOf`；
- direct/transaction-backed run claim；
- transaction plan/state、ABSENT/hash before；
- pointer live/ABSENT、generation；
- nullable total ordering 规则；
- 两组冻结 JSON bytes/hash vectors，expected bytes/hash 独立硬编码。

### GREEN

实现最小 strict JSON/contracts 层：

- 只接受 built-in JSON 类型；
- workspace JSON：`ensure_ascii=False, sort_keys=True, indent=2` + 单 LF；
- compact canonical JSON：`ensure_ascii=False, sort_keys=True, separators=(",", ":")` 无 LF；
- 禁止 NaN/Infinity、BOM、容器子类、非字符串 key；
- artifact hash 只对已发布 raw bytes；
- artifact 不保存自身 hash。

### Gate

- 不修改 M0/M1/M2 Schema/validator。
- Schema 正文、runtime validator 和测试对 proposal 分支数/required fields 必须完全一致。

---

## 5. Task 2｜严格答案解析 + source snapshot + M2 identity gate

**未来创建：** `qbanswer/answer_parser.py`、`qbanswer/source_snapshot.py`、`tests/test_m3_answer_parser.py`、`tests/test_m3_source_snapshot.py` 和 `tests/fixtures/m3-answer-association/` 中本 Task 所需的 synthetic-only 文件。

### RED

至少覆盖：

- 精确 `number: label` 语法；
- 空行、BOM、LF/CRLF/CR；
- 非空非法行全源 fail-closed；
- 多个显式 answer source；
- 未选择/重复/跨 dataset/source role 冲突；
- stale registry/hash/revision；
- 路径/链接逃逸；
- 题目源必须已有完整 M2 materialization；
- 只读重放 M2 parser 与 Candidate/Option artifact 逐字段核对；
- Candidate identity mismatch -> `QB-IDENTITY-AMBIGUOUS` run finding；
- Option identity mismatch -> `QB-OPTION-IDENTITY-AMBIGUOUS` run finding；
- identity 不可靠时 canonical 绝对不变；
- evidence fingerprint 与 locator 分离。

### GREEN

- parser 只产生 EvidenceRecord；
- source snapshot 按第 2.3 节只读调用 `_resolve_single_choice_source_snapshot`、`_existing_candidate_matches_complete_run`、`parse_single_choice` 和 `materialize_candidates`；
- 不写 registry，不扫描未选 source；
- 不执行安全失效，直到 identity gate 完整通过。

### Gate

任何需要修改 M1/M2 runtime 才能复用的情况都属于 plan incompatibility，STOP。

---

## 6. Task 3｜raw association、P1 adjudication、proposal 与 ReviewItem 纯逻辑

**未来创建：** `qbanswer/association.py`、`qbanswer/review.py`、`tests/test_m3_association.py`、`tests/test_m3_review.py`；只按需要扩展 `tests/test_m3_contracts.py`。

### RED

覆盖：

1. 唯一题号 + 同 Option 多证据 -> `confirmable`；
2. missing -> `QB-ANSWER-MISSING`；
3. 多 Option / invalid label -> `QB-ANSWER-CONFLICT`；
4. duplicate question number / unknown answer number -> `QB-ASSOCIATION-LOW-CONFIDENCE`；
5. no-Candidate source-level payload 的 null/empty 形状；
6. stable issue key 必含 `question_source_id`；
7. `resolved_option_id` null-first；其余 nullable UUID non-null-first；
8. open 同 key 去重；closed 后真实 recurrence 新 ID + 最近 closed `supersedes_review_id`；
9. `adjudication_still_applies=true` 时 prepare/reverify 都不 recurrence、不降级；
10. selected 改变/消失、新 rejected semantic key、source 缩减、lineage 失效时两入口进入同一 stale/conflict/failed 结果；
11. `adjudicated` 只审计、不可 confirmation；
12. `stale` proposal 只在 canonical 中存在合法 `needs_revalidation` Decision + open stale ReviewItem 时生成。

### GREEN

- 建立唯一 `adjudication_still_applies`；prepare/reverify 以后只能调用它；
- proposal builder 与 ReviewItem planner 都保持纯逻辑，不写磁盘；
- proposal 排序完全按规格，与 filesystem/locale/time/random 无关。

### Gate

禁止把“相同旧 rejected evidence 又扫描到”误当 recurrence。

---

## 7. Task 4｜纯 snapshot builder + 第 15.2 节跨对象 validator

**未来创建：** `qbanswer/state_graph.py`、`tests/test_m3_state_graph.py`。

先实现**内存对象图和 validator**，暂不实现 current pointer 写入。

### RED

逐项一对一覆盖规格第 15.2 节关系：

- current -> commit；
- commit -> transaction；
- operation artifact -> transaction；
- proposal -> confirmation base；
- commit -> snapshot files；
- confirmation -> lineage；
- current -> parent；
- recursive parent；
- snapshot identity；
- dataset/manifest；
- Candidate/Option；
- Decision；
- child -> parent Candidate；
- child -> parent Decision；
- child -> parent ReviewItem；
- review supersession；
- child -> parent provenance；
- provenance -> run artifacts；
- stale proposal -> canonical graph；
- confirmation -> proposal；
- archive_stale -> child；
- evidence partition；
- adjudication applicability；
- Decision -> confirmation；
- ReviewItem；
- reverify required set；
- reverify source set；
- reverify evidence；
- validated gate；
- standalone confirmation audit；
- run canonical claim；
- reverse references。

### 攻击测试

每种关系至少有一个“内容篡改后重新合法 JSON 编码，并同步重算所有直接文件 hash”负例，证明 hash 自洽不能绕过语义 validator。

### GREEN

- snapshot builder 只构造候选 parent/child 内存对象；
- validator 对完整对象图 fail-closed；
- validated gate 只存在一份实现。

### Gate

在 state graph 纯逻辑未独立 PASS 前，不进入事务写入。

---

## 8. Task 5｜transaction publisher / recovery + P2 run reconciliation

**未来创建：** `qbanswer/transaction.py`、`qbanswer/run_audit.py`、`tests/test_m3_transaction.py`、`tests/test_m3_run_audit.py`。

### RED：transaction

冻结五 crash point：

```text
A operation artifact 已写，plan 未写
B staged 已写，commit 未写
C valid commit/publishing 已写，pointer 未切换
D pointer 已切换，complete state 未写
E complete state 已写，run terminal 未写
```

以及：

- current before/after/unknown；
- commit missing vs existing-corrupt；
- state missing/corrupt 重建；
- `staged -> publishing -> complete`；
- 仅 pre-commit + current=before 可 `aborted`；
- `publishing` without valid commit 必须 fail；
- terminal state 与真实 pointer 矛盾必须 fail；
- 并发 writer / 外部 pointer 改写；
- orphan snapshot 保留但不 canonical。

### RED：run audit

- transaction complete 后 run 缺失/非 terminal -> 只补 run；
- transaction aborted -> run failed；
- unknown/corrupt canonical graph -> 不得成功 run；
- 成功 run terminal 不得早于 transaction complete；
- run 不能反向修复 canonical；
- direct prepare 唯一无 transaction success 分支；
- terminal run 不可逆，不覆盖改绑引用。

### GREEN

- 事务写入严格遵循 temp/write/flush/fsync/read-back/single replace/read-back；
- `transaction.py` 同时实现第 2.3 节确认不存在于 `qbcore` 的 stdlib Windows/POSIX non-blocking advisory lock，prepare/confirm/reverify/recover/read 共用这一处实现；
- operation artifact 白名单按 operation 互斥；
- transaction canonical truth 与 run audit 完全单向。

### Gate

Task 5 必须通过故障注入和并发测试后，才允许任何业务 service 使用发布器。

---

## 9. Task 6｜prepare operation 端到端闭环

**未来创建：** `qbanswer/prepare.py`、`qbanswer/service.py`、`tests/test_m3_prepare.py`；本 Task 首次创建 service 并只加入最小 prepare route。

### RED

覆盖：

- direct prepare：无 canonical 差分，只发布 immutable manifest/proposal/run；
- prepare_result：产生 review 或安全失效 snapshot；
- `plan.before == prepared_from_pointer`；
- plan 精确绑定 manifest + proposal raw hashes；
- confirmable 不自动 Decision/validated；
- missing/conflict/low-confidence 创建/继承 ReviewItem；
- stale evidence/conflict 只有 identity gate 通过后才能安全失效；
- P1 adjudicated conflict 保持 Decision/Candidate/closed ReviewItem；
- prepare transaction crash recovery；
- terminal priority `failed > needs_review > needs_confirmation > complete`。

### GREEN

prepare 只编排 Task 1–5 primitives，不复制 validator/association/recovery 逻辑。

### Gate

prepare 完成时仍没有任何用户确认能力；不得为了方便测试直接创建 Decision。

---

## 10. Task 7｜confirmation、Decision、validated gate 与 `archive_stale`

**未来创建：** `qbanswer/confirmation.py`、`tests/test_m3_confirmation.py`；只扩展既有 `qbanswer/service.py` 的 confirmation route。

### RED：通用 confirmation

覆盖所有动作：

- `confirm`；
- `confirm_all_unambiguous`；
- `choose_evidence`；
- `reject`；
- `reject_association`；
- `retain_unresolved`；
- `archive_stale`。

必须验证：

- proposal run/hash/base lineage；
- actual current 与 direct/prepare_result baseline；
- stale proposal / intervening snapshot / revision change / review change / decision change 全部拒绝；
- 禁止直接输入 Option ID/label/自由文本答案；
- `adjudicated` 不可 confirmation；
- 每个 confirmation 必须新 child snapshot + provenance audit，即使无 Decision/Review 变化。

### RED：Decision / validated

- Decision 转换矩阵全部分支；
- 每 Candidate 最多一个 current valid answer Decision；
- old Decision value/evidence/binding 永不原地改写；
- `selected/rejected/considered` 分区完整且互斥；
- rejected evidence 绝不进入 Decision evidence；
- validated 九项门禁逐项负例。

### RED：`archive_stale`

至少覆盖批准规格冻结的 12 个攻击场景：

1. prepare-result stale -> archive 成功；
2. already-stale/direct -> archive 成功；
3. 错 Decision ID -> FAIL；
4. 错 Candidate/revision -> FAIL；
5. 非 `QB-DECISION-STALE` ReviewItem -> FAIL；
6. resolved/archived ReviewItem -> FAIL；
7. archived Decision -> FAIL；
8. intervening snapshot replay -> FAIL；
9. `archive_stale` 引用其他 conclusion -> FAIL；
10. 其他动作引用 stale conclusion -> FAIL；
11. child 只允许 `needs_revalidation -> archived`、对应 stale item `open -> resolved`，Candidate 保持 `candidate`；
12. proposal Schema / action validator / child graph 完全一致。

### GREEN

`archive_stale` 不创建新答案、不创建新 Decision、不提升 validated、不关闭同 Candidate 其他 open 问题。

---

## 11. Task 8｜reverify + 安全失效完整闭环

**未来创建：** `qbanswer/reverify.py`、`tests/test_m3_reverify.py`；只扩展既有 `qbanswer/service.py` 的 reverify route。

### RED

覆盖：

- 按 Decision required set；
- 按题目源 required set；
- validated Candidate 唯一 valid Decision 完整性；
- original answer source set 不可缩减；
- explicit additions；
- 运行级 source set = 各 Decision current set 并集；
- 历史实例键 / 当前 semantic key / 当前 instance key；
- line move、revision change、同义重复；
- selected evidence 消失；
- 原 rejected evidence 不变；
- 新 conflict；
- `adjudication_still_applies` 与 prepare 完全同结果；
- path_history 完整吸收所有 intervening suffix；
- valid -> needs_revalidation；
- 禁止 reverify 自动恢复 valid；
- reverify artifact `expected_before_pointer == plan.before`；
- reverify crash recovery + run reconciliation。

### GREEN

reverify 只能：

- 保持当前 valid；或
- 安全降级为 needs_revalidation/candidate 并打开/维持对应 review；
- 记录 audit。

不得直接创建新 valid Decision。

---

## 12. Task 9｜CLI、隐私、能力边界与 portability

**未来创建：** `qbanswer_cli.py`、`test_m3_cli.py`、`test_m3_safeguards.py`、`test_m3_privacy.py`、`test_m3_portability.py`。

### RED/GREEN

CLI 只提供与规格一致的 prepare/confirm/reverify/recovery 操作；参数必须显式 source/expected-hash/pointer 绑定。

验证：

- stdout 仅稳定 JSON 摘要；
- exit 0/3/2 精确映射；
- stderr/log 无题干、选项、完整答案行、绝对路径、用户名、env、traceback；
- 所有新增持久 artifact 递归隐私扫描；
- 输入树零写入、workspace 外零写入；
- no socket/HTTP/model/connector/MCP；
- M3 runtime 无 subprocess/process spawn；测试可且只能使用既有 `tests/m2_helpers.py::run_subprocess` 启动 `qbanswer_cli` 进行隔离验证，scope guard 必须区分测试 harness 与被测 runtime；
- no dynamic execution；
- no dependency install；
- copied Skill 在另一临时目录仍只写显式 workspace；
- 无 UI、评分、学习统计、答案推断、非 single-choice adapter。

### Gate

CLI 不得重新实现 service 规则；所有 action 只能调用已通过 Task 6–8 的 service API。

---

## 13. Task 10｜完整 integration、篡改矩阵、scope guard 与两次全量回归

**未来创建：** `test_m3_end_to_end.py`；只扩展 M3 tests/helpers/fixtures。

### 13.1 规格第 17 节 29 项矩阵必须全部映射到可执行测试

在测试文件/参数表中保存 `SPEC_ACCEPTANCE_CASE_ID -> pytest node` 的静态映射，保证第 17 节 1–29 每项至少有一个直接测试，不允许只写 prose 声称覆盖；第 29 项必须直接指向 Task 7 的 12 个 `archive_stale` 攻击测试集合。

### 13.2 端到端 synthetic workflow

至少形成以下完全 synthetic 场景：

- clean prepare -> confirm -> validated；
- conflict -> choose_evidence -> validated；
- unchanged rejected conflict -> prepare/reverify adjudicated；
- evidence stale -> needs_revalidation -> 新 prepare/confirm；
- evidence stale -> `archive_stale`；
- missing / low-confidence unresolved；
- stale proposal replay；
- transaction crash A–E；
- semantic tamper + recomputed direct hashes；
- concurrent/unknown pointer；
- portability copy。

### 13.3 全量 Gate

连续两次运行：

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
& python -m pytest -p no:cacheprovider tests -q
```

要求：

- 两次均 exit 0；
- 两次测试收集数量一致；
- 所有 deterministic artifact bytes/hash 一致；
- M0/M1/M2 authority hash map byte-for-byte 不变；
- 无 pytest/cache/bytecode 污染；
- scope/privacy guard 全 GREEN。

### Gate

本 Task PASS 只允许进入 M3 **实现质量审查**，不自动构成 M3 acceptance。

---

## 14. Task 11｜Skill capability metadata 最小更新

**前提：** Task 0–10 全部 PASS，且网页端/本机独立质量审查确认 runtime 能力真实存在。

**未来只允许修改：**

- `skills/curate-question-bank/SKILL.md`；
- `skills/curate-question-bank/agents/openai.yaml`。

只声明已经测试通过的能力：

- 显式本地答案 source prepare；
- 本地 evidence proposal/review；
- 人工 confirmation；
- validated gate；
- explicit reverify / safe invalidation。

必须同时声明：

- 不生成/推断答案；
- 不联网；
- 不自动扫描相邻文件；
- 不提供 UI/评分/学习统计；
- 不支持非 single-choice；
- identity migration 不在 M3。

更新后重新运行 scope/privacy/完整测试两次。

不得修改 `START-HERE.md`、`NEW-THREAD-PROMPT.md`、`SIDE-CONVERSATION-HANDOFF.md`；这些只能在最终 M3 acceptance 后更新。

---

## 15. Task 12｜独立实现质量审查与验收提交

本 Task 不修代码，只做只读审查；若发现问题返回对应最小 Task 修复，不能在审查中直接改代码。

### 15.1 独立质量审查

至少审查：

- spec -> plan -> tests -> runtime traceability；
- scope whitelist；
- duplicate business rule implementations；
- transaction/recovery/P2；
- P1 adjudication；
- `archive_stale` exact binding；
- schema/runtime validator parity；
- state graph semantic tamper resistance；
- fail-closed identity boundary；
- privacy；
- no remote/process/dynamic execution；
- M0/M1/M2 byte immutability；
- error handling 不吞异常、不泄露敏感正文；
- portability；
- test independence（expected 不从实现生成）。

### 15.2 M3 验收提交材料

生成脱敏证据包，至少包含：

- frozen spec SHA；
- frozen implementation-plan SHA；
- changed/new file manifest；
- M0/M1/M2 authority before/after hashes；
- targeted test matrix；
- 两次完整 pytest 输出摘要；
- 29 项 acceptance mapping；
- 12 项 archive_stale attack result；
- crash A–E result；
- privacy/scope/portability result；
- independent quality review PASS/FAIL；
- remaining unverified risks。

即使全部 PASS，状态仍只能提交为：

```text
M3_IMPLEMENTATION_REVIEW = PASS   # 若实际审查 PASS
M3_ACCEPTANCE = NOT_GRANTED
```

等待用户明确验收。不得由本地 Codex自行宣布 M3 accepted。

---

## 16. 原子任务执行边界

未来真正编码时，默认一次只授权一个 Task；Task 内也必须按 RED -> minimal GREEN -> targeted -> full regression -> read-back -> review 的顺序。

禁止：

- 一次把 Task 1–12 全部实现；
- 为“省事”修改 qbcore；
- 新增数据库、daemon、后台 watcher；
- 增加 GUI/web server；
- 依赖第三方新库；
- 增加自动答案推断；
- 改写冻结 Candidate/Decision/ReviewItem Schema；
- 把真实题库作为 fixture；
- 在未通过当前 Task gate 时提前实现下一 Task。

网页端在每个编码 Task 前应尽量提供：

- 精确候选 patch/代码；
- 对应 RED tests；
- expected failure；
- targeted command；
- review checklist。

本地 Codex主要执行：baseline 核对、必要本地化、最小应用、真实测试、typecheck/静态检查（若项目实际配置存在）、hash/scope/privacy 核对和 PASS/FAIL。

---

## 17. 当前计划批准门

本文件是经真实项目接口核对和必要最小本地化后的本机实施计划；独立审查与人工批准状态不写回本文件，以避免冻结 hash 自引用。

本机下一步只允许：

1. 精确核对 approved spec SHA；
2. 对照真实项目 API/目录审查本计划；
3. 必要时只修改计划文字做最小本地化；
4. 重新运行既有完整测试，证明只新增/修改计划文档未造成项目回归；
5. 独立只读实施计划审查；
6. 冻结最终本机实施计划 SHA-256；
7. STOP，等待用户明确批准该精确计划 SHA。

在此之前：

```text
IMPLEMENTATION_PLAN_REVIEW = PENDING
IMPLEMENTATION_PLAN_APPROVAL = NOT_GRANTED
IMPLEMENTATION_AUTHORIZED = NO
```
