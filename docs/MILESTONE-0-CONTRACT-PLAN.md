# Milestone 0 — Contract 设计实施计划

状态：Approved  
执行边界：只做 Contract、Schema、fixtures、expected artifacts 和 contract tests，不提前实现核心 parser。

## 1. 目标

在实现扫描、解析和跨文件关联之前，冻结并验证：

- MVP 题型；
- SourceIdentity；
- CandidateIdentity；
- OptionIdentity；
- DecisionBinding；
- fingerprints 与一对一身份匹配；
- 决定失效规则；
- runtime validator 与 JSON Schema 的职责；
- 固定问题代码；
- golden fixture 和 expected artifacts。

## 2. 计划目录

运行时所需资源全部随 Skill 本体分发，不依赖仓库根目录：

```text
question-bank-curator/
├─ pyproject.toml
├─ README.md
├─ LICENSE
├─ skills/
│  └─ curate-question-bank/
│     ├─ SKILL.md                  # Milestone 1 创建，不属于本阶段
│     ├─ agents/                   # Milestone 1 创建
│     ├─ scripts/
│     │  └─ qbcore/
│     │     └─ validation.py       # 本阶段允许的最小确定性 validator
│     ├─ references/
│     │  ├─ question-types.md
│     │  ├─ identity-contract.md
│     │  ├─ state-contract.md
│     │  └─ issue-codes.md
│     └─ schemas/
│        ├─ manifest.schema.json
│        ├─ run-state.schema.json
│        ├─ candidate.schema.json
│        ├─ review-item.schema.json
│        ├─ decision.schema.json
│        └─ question-bank-interchange.schema.json
└─ tests/
   ├─ fixtures/golden-course/course/
   ├─ expected/golden-course/
   ├─ test_contract_schema.py
   ├─ test_identity_contract.py
   ├─ test_option_identity_contract.py
   ├─ test_decision_invalidation_contract.py
   └─ test_golden_fixture_contract.py
```

不得在根目录保留第二套 Schema。

## 3. Task 0.1 — 题型契约

冻结：

- `single_choice`：一个 resolved `option_id`；
- `multiple_choice`：两个及以上、无序且不重复的 resolved `option_id`；
- `true_false`：规范化布尔值并保留源词法；
- 其他题型：保留来源，标记 unsupported/ambiguous，不进入 validated。

正式区分：

- `option_id`：持久身份；
- `source_label`：A/B/C/D 等当前标签；
- `current_position`：当前顺序；
- `source_lexeme`：答案文件中的原始表示；
- `resolved_option_ids`：本版本实际绑定的选项身份。

## 4. Task 0.2 — 身份契约

### 4.1 SourceIdentity

使用持久 UUID，不把相对路径或内容哈希直接作为身份。

记录：

- `source_id`；
- `dataset_id`；
- `current_relative_path`；
- `path_history`；
- `current_content_hash`；
- `revision`。

仅在内容哈希唯一匹配时自动识别纯重命名。存在多个匹配或路径和内容同时变化时生成身份审核项。

### 4.2 CandidateIdentity

每道题拥有持久 `candidate_id` 和 revision。不得使用题号作为持久身份。

保存三类指纹：

- `stem_fingerprint`：规范化题干；
- `option_set_fingerprint`：与顺序无关，但保留重复次数；
- `content_revision_fingerprint`：题型、题干和有序选项，与顺序有关。

### 4.3 OptionIdentity

每个选项保存：

- `option_id`；
- `candidate_id`；
- `option_revision`；
- `normalized_text_fingerprint`；
- `current_position`；
- `source_label`；
- `source_ref`；
- `previous_labels`。

仅当旧、新选项文字指纹在各自题目内均唯一时，允许在重排中迁移 `option_id`。重复选项文本或文字变化时不得自动迁移。

### 4.4 DecisionBinding

每个决定绑定：

- candidate ID 与 revision；
- decision type/value；
- 一个或多个 evidence bindings；
- source ID、revision、locator 和 evidence fingerprint；
- `valid`、`needs_revalidation` 或 `archived` 状态。

## 5. Task 0.3 — 一对一身份匹配规则

Fingerprint 只是匹配证据，不是身份键。

重新扫描时，旧、新 candidate 必须进行一对一匹配：

1. 唯一 `content_revision_fingerprint`；
2. 唯一 `stem_fingerprint + option_set_fingerprint`；
3. structural locator；
4. 已唯一匹配的前后邻接锚点；
5. 局部序列顺序；
6. 用户确认。

一个节点匹配后必须退出候选集合。

相同 fingerprint 的重复题不得自动合并。只有重复数量相同、两端邻接锚点稳定且组内无插删改时，才允许按组内顺序迁移。否则产生 `QB-IDENTITY-AMBIGUOUS`，不继承决定。

Duplicate detection 与 identity migration 必须分离。

## 6. Task 0.4 — 决定失效矩阵

| 变化 | 处理 |
|---|---|
| 文件仅重命名，内容不变 | 决定继续有效 |
| 题号/定位变化，题目内容不变 | 更新 locator，决定继续有效 |
| 答案文件变化，但被引用证据不变 | 决定继续有效 |
| 答案证据变化 | `needs_revalidation` |
| 题干变化 | 相关答案、重复和关联决定重新校验 |
| 选项重排且 option identity 可唯一迁移 | 重新解析答案标签并审计 |
| 重排后答案仍指向原 option ID | 决定可继续有效 |
| 重排后答案指向另一 option ID | `needs_revalidation` |
| 选项文本变化或迁移不唯一 | 不自动继承 |
| 无法确认是否同一道题 | `QB-IDENTITY-AMBIGUOUS` |
| 原题删除 | 历史决定归档，不删除 |

## 7. Task 0.5 — Schema 与 Runtime Contract Validator

正式采用双层方案：

- Runtime：Python 标准库实现的最小 deterministic contract validator；
- Development/CI：`jsonschema` 作为开发依赖验证公开 Schema。

### 7.1 双方重叠检查集合

Runtime validator 与 JSON Schema 都应检查：

- required fields；
- JSON primitive/object/array type；
- enum；
- pattern，包括 UUID/hash 基本格式；
- array cardinality；
- 基本 schema reference shape，例如引用字段是否为规定形状。

只有在上述重叠集合上，测试才要求两者对同一 fixture 不得给出相反结论。

### 7.2 仅 Runtime validator 检查

- 跨对象 ID 是否真实存在；
- option 是否属于对应 candidate；
- decision evidence 是否存在；
- revision 和历史关系是否合法；
- validated gate；
- candidate/review/decision 业务状态不变量；
- 单选、多选、判断答案的跨对象业务约束。

JSON Schema 未表达这些业务规则不视为与 Runtime validator 冲突。

### 7.3 依赖边界

```toml
[project]
dependencies = []

[project.optional-dependencies]
dev = [
  "pytest",
  "jsonschema"
]
```

Milestone 0 不安装依赖，除非执行线程获得用户授权。可以先创建依赖声明和测试；运行前先检查当前环境是否已具备工具。

## 8. Task 0.6 — 固定问题代码

最低集合：

```text
QB-SOURCE-UNSUPPORTED
QB-SOURCE-READ-FAILED
QB-ROLE-AMBIGUOUS
QB-TYPE-UNSUPPORTED
QB-STRUCTURE-AMBIGUOUS
QB-ANSWER-MISSING
QB-ANSWER-CONFLICT
QB-ASSOCIATION-LOW-CONFIDENCE
QB-DUPLICATE-CANDIDATE
QB-IDENTITY-AMBIGUOUS
QB-OPTION-IDENTITY-AMBIGUOUS
QB-DECISION-STALE
QB-FORMAT-LOSS
QB-SECURITY-INSTRUCTION-DATA
QB-REMOTE-CAPABILITY-NOT-AUTHORIZED
```

每个代码必须定义触发条件、阻断级别和允许的用户操作。

## 9. Task 0.7 — Golden fixture

```text
tests/fixtures/golden-course/course/
├─ chapter-1-questions.md
├─ chapter-1-answer.txt
├─ chapter-2-questions.md
├─ unrelated.txt
└─ duplicate-version.md
```

Fixture 至少包含：

- 三道可匹配单选题；
- 一道缺失答案；
- 一道答案冲突；
- 两道内容完全相同但身份独立的题；
- 一个重复版本；
- 一个无关文件；
- 一个题号相同但内容不同的实例。

Expected artifacts：

```text
tests/expected/golden-course/
├─ manifest.json
├─ candidates.json
├─ review-queue.json
├─ decisions.json
└─ validated-after-decisions.json
```

Milestone 0 不通过 parser 生成这些 artifacts；它们是人工设计的 Contract 样本。

## 10. 必须覆盖的 Contract tests

### Candidate/Option identity

- 文件内容不变但重命名；
- 文件前方插题导致题号整体变化；
- 题干修改；
- 唯一选项文字重排并保留 option ID；
- 重排后答案仍指向原 option ID；
- 重排后答案指向另一 option ID；
- 两个选项文字相同而无法唯一迁移；
- 选项文字修改。

### Duplicate identity

- 两道相同题分别保留 candidate ID；
- 在重复组之前插入普通题；
- 删除重复组中的一道题；
- 向重复组新增相同题；
- duplicate relation 不合并 candidate。

### Validation layers

- 无 `jsonschema` 时 Runtime validator 可运行；
- 重叠检查集合中两层校验结论一致；
- Runtime validator 拦截悬空 option ID；
- Runtime validator 拦截 option 归属错误；
- Runtime validator 拦截不存在的 evidence；
- Runtime validator 拦截非法 revision；
- Runtime validator 拦截不满足 validated gate 的对象；
- JSON Schema 不表达业务不变量不视为冲突。

### Portable Skill package

独立复制 `skills/curate-question-bank/` 后，运行时资源仍可通过 Skill 根目录相对定位，不依赖仓库根目录。

## 11. Milestone 0 完成门禁

只有以下条件全部满足才可进入 Milestone 1：

- 题型边界冻结；
- Source、Candidate、Option、Decision 四层身份/绑定契约冻结；
- 三类 candidate fingerprint 冻结；
- 一对一匹配和重复歧义规则冻结；
- 决定失效矩阵冻结；
- Runtime/JSON Schema 校验边界冻结；
- Schema 全部位于 Skill 包内；
- golden fixture 和 expected artifacts 完成；
- contract tests 通过；
- Markdown lint 或等价静态检查通过；
- 未创建核心题目 parser、扫描器或关联引擎。

## 12. 完成报告要求

Milestone 0 执行线程结束时必须报告：

- 创建/修改的文件；
- 实际运行的测试命令及结果；
- Contract 门禁逐项状态；
- 未验证区域；
- 是否存在阻止 Milestone 1 的问题；
- 明确确认没有提前实现 parser。
