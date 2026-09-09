# Milestone 3 本地答案证据关联与人工核验规格

状态：设计草案，已按多轮独立规格审查修订，等待最终复审与人工批准。未获人工批准前不得实施。

## 1. 目标

Milestone 3 在 Milestone 2 已物化的严格单选题之上，增加一条本地、可审计、失败关闭的答案治理路径：

1. 用户显式选择一个已物化题目源和一个或多个本地答案源；
2. 系统只解析答案源中明确存在的严格答案记录；
3. 系统把答案记录关联到当前 Candidate 和持久 Option ID，形成待确认提案；
4. 用户确认具体证据，或在冲突中选择具体证据；
5. 系统持久化 Decision、确认记录和 ReviewItem；
6. 只有完整门禁通过的 Candidate 才从 `candidate` 提升为 `validated`；
7. 后续重新核验发现证据失效或冲突时，Decision 进入 `needs_revalidation`，Candidate 回到 `candidate`，等待再次人工确认。

本阶段处理的是“已有答案证据是否足以支持一个答案决定”，不是“题目的正确答案是什么”。

## 2. 明确禁止

Milestone 3 不得：

- 生成、补全、推荐、推测或纠正答案；
- 根据题干、学科知识、选项含义、频率、上下文或模型判断哪个选项正确；
- 把用户手工点选一个无本地证据支持的选项当成答案；
- 联网、调用模型、connector、MCP、搜索引擎或远程服务；
- 扫描未显式选择的相邻文件，或根据文件名、目录位置猜测答案文件；
- 实现刷题 UI、HTML quiz、正式判分、得分统计、错题本或学习分析；
- 支持多选、判断、填空、简答或 M2 未物化的题型；
- 执行 Candidate/Option 重扫迁移、题目 revision 增长、重复题合并或 Decision 跨身份继承；
- 修改 Milestone 0 已冻结 Schema、身份语义、问题代码或 `validation.py`；
- 放宽 Milestone 1/2 的安全、路径、只读输入、首次物化或历史 scope guard；
- 初始化 Git、创建 worktree、提交、联网或安装依赖。

## 3. 方案比较与决定

### 3.1 方案 A：解析后直接创建有效答案决定

系统看到唯一的 `题号: 选项标签` 后，直接创建 `valid` Decision 并提升 Candidate。

优点是步骤少。缺点是“格式唯一”不等于“证据正确”，会绕过用户确认，也无法安全处理错配、重复题号和来源冲突。本阶段拒绝。

### 3.2 方案 B：提案与确认分离（采用）

准备阶段不会创建 `valid` Decision 或提升 Candidate；它生成不可变提案和问题清单，并可通过完整 snapshot 发布 canonical review 或执行第 13 节规定的保守安全失效。确认阶段要求用户绑定提案文件哈希，并显式确认提案或选择冲突中的某条证据。只有确认阶段可以创建新的 `valid` Decision 和提升 Candidate。

优点是证据、自动关联和人工决定边界清楚，能阻止陈旧确认，且适合重新核验。代价是多一步确认，但这是本阶段的必要安全门禁。

### 3.3 方案 C：完全手工逐题映射

系统不做确定性题号关联，用户逐题指定 Candidate、Option 和证据行。

该方案最保守，但会重复机器能够安全完成的机械核对，并容易产生人工抄录错误。本阶段仅把它作为低置信关联的拒绝/保留路径，不允许人工指定 Candidate 或 Option 来绕过低置信门禁。人工一对一映射必须在后续里程碑另行设计。

### 3.4 冻结决定

采用方案 B。M3 的权威流程是：`prepare -> review -> confirm -> publish -> reverify`。准备可以提出关联，只有明确的人工作用可以产生或替换有效答案决定；确定性失效检测可以降级，但不能提升。

## 4. 继承的冻结契约

M3 必须原样继承：

- UUID 是身份；路径、题号、locator、标签和 fingerprint 都只是证据；
- 单选答案的持久值是恰好一个、且属于当前 Candidate 的 `option_id`；
- `source_label` 和 `current_position` 不是答案身份；
- Decision 绑定 `candidate_id`、当前 `candidate_revision`、决定值、至少一条证据及状态；
- Decision 状态仅为 `valid`、`needs_revalidation`、`archived`；
- Candidate 状态沿用 `candidate`、`validated`、`unsupported`、`ambiguous`、`archived`；
- 输入根只读，所有持久写入只发生在显式 workspace 根；
- 所有被选择 source 必须先通过 registry 身份、revision、路径逃逸、reparse point 和原始字节哈希核对；
- 源正文是不可信数据，不能触发命令、联网、扩大读取或动态执行；
- M2 的 `needs_review` 只是解析运行状态，不等于 M3 的 ReviewItem 或人工确认。

M3 可以新增更严格的业务门禁和独立 artifact，但不能声称旧 Runtime validator 已经覆盖这些新门禁。

## 5. 本阶段精确范围

### 5.1 输入

一次准备运行必须显式给出：

- `input_root` 与 `workspace_root`；
- 一个 `question_source_id`；
- 一个或多个互不重复的 `answer_source_id`；
- 当前 M2 Candidate artifact 的预期 SHA-256；
- 当前 M3 state pointer 的预期 SHA-256；首次运行使用冻结的 `ABSENT` 哨兵；
- 用户对所选 source 角色的明确声明：题目源为 `question_document`，答案源为 `answer_document`。

题目源必须已经由已验收 M2 首次物化，且其 registry revision、content hash、M2 parse report 和 Candidate artifact 彼此一致。答案源必须已经存在于同一 workspace 的 registry，但既有 registry 不包含角色字段；本次显式角色声明是构造运行级 manifest 的唯一角色证据。

不得自动增加、替换或排除 source。一个 source 不能在同一运行中同时充当题目源和答案源。

### 5.2 支持的工作单元

一个运行只处理一个 M2 题目源及其 Candidate 集合，可以读取一到多个显式答案源。它不批量处理多个题目源，也不跨题目源匹配 Candidate。

### 5.3 运行级 manifest

准备阶段为所选 source 生成不可变 `manifest.json`，结构必须通过现有 M0 manifest Schema。它记录同一 dataset ID、source ID、显式 kind、当前相对路径、路径历史、当前内容哈希和 revision。

该 manifest 是本次角色声明和 source 快照，不把角色写回 M1 registry，也不证明未选择 source 的角色。提案、确认和重新核验都绑定其 SHA-256。

准备运行在取得第 14.1 节锁后必须重新读取并验证 `current.json`，把实际得到的 pointer SHA-256 或 `ABSENT` 冻结为本次 `prepared_from_pointer`；它必须与调用方声明的预期值一致。若 prepare 需要发布 canonical review 或安全失效 snapshot，则该 prepare transaction 的 `plan.before` 必须精确等于 `prepared_from_pointer`，且 plan 必须绑定本次 `manifest.json` 与 `proposal.json` 的相对路径和原始 SHA-256。若 prepare 不产生 canonical 状态变化，则不得创建空事务，proposal 的确认基线直接继承 `prepared_from_pointer`。

## 6. 严格答案语法

M3 只读取 registry 支持且 M2 已允许的本地 UTF-8 Markdown/TXT 文件。原始字节和解码规则沿用 M2：先哈希，再以 `utf-8-sig` 严格解码，逻辑视图把 CRLF/CR 视为 LF，不修改源文件。

答案源的每个非空逻辑行必须精确匹配：

```regex
^[ \t]*(?P<number>[1-9][0-9]*)[ \t]*:[ \t]*(?P<label>[A-Z])[ \t]*$
```

规则：

- 空行忽略；注释、标题、说明、答案解析和行尾注释均不支持；
- `number` 是答案记录中的题号证据，不是 Candidate ID；
- `label` 是答案源原始词法，只能在关联后转换为持久 Option ID；
- 任一非空行不匹配时，该答案源触发 `QB-STRUCTURE-AMBIGUOUS`；
- 任一所选答案源结构不明确时，本次准备运行不发布可确认提案，防止忽略潜在冲突；
- 答案源中的 URL、命令、提示词或代码没有特殊含义，只能因不符合严格语法而失败关闭。

本阶段不扩展 golden fixture 的语义；`1: A` 只是受支持语法示例，不代表现有 fixture 已由生产实现处理。

## 7. 题目视图与一致性核对

准备阶段必须只读重放已验收的 M2 parser，以恢复每道题的源题号、题头 locator、选项标签和 fingerprint。重放结果必须与当前 Candidate artifact 一对一核对：

- source ID 和 revision 相同；
- Candidate 数量相同；
- 每个 Candidate 的题头 locator、题型和三类 fingerprint 相同；
- 每个 Option 的 source locator、source label、位置和文字 fingerprint 相同；
- Candidate/Option UUID、revision 和 ownership 合法；
- Candidate artifact 的实际 SHA-256 等于调用方声明的预期值。

任何不一致都不得尝试迁移、修复、重新分配身份，也不得据此修改任何既有 Candidate、Decision 或 ReviewItem。准备或重新核验运行只产生第 15 节冻结形状的脱敏 run-level finding，并以 `failed` 结束；candidate-level 不一致使用 `QB-IDENTITY-AMBIGUOUS`，option-level 不一致使用 `QB-OPTION-IDENTITY-AMBIGUOUS`。即使当前 snapshot 中已有 `valid` Decision 或 `validated` Candidate，也不得在身份无法可靠建立时执行安全失效 transaction；M3-aware 读取方必须因身份门禁失败而拒绝把该状态报告为已验证。第 13 节的自动安全失效只适用于 Candidate/Option 身份已经可靠建立、但答案证据本身失效或出现新冲突的情形。

## 8. 答案证据规范

每条合法答案记录产生一条内部 EvidenceRecord：

```text
EvidenceRecord
├─ evidence_id
├─ source_id
├─ source_revision
├─ locator = line:<1-based logical line>
├─ question_number
├─ source_lexeme = 原始 A-Z 标签
└─ evidence_fingerprint
```

`evidence_fingerprint` 必须按以下 UTF-8 字节计算 SHA-256：

```text
m3-answer-evidence-v1\0<number-as-canonical-decimal>\0<label>
```

周围空白、BOM 和换行形式不进入 fingerprint；题号和标签进入。相同语义记录移动到另一行时 fingerprint 不变，locator 更新。完整原始答案行不写入日志或错误摘要；运行 artifact 可以保存规范化题号和单字符 `source_lexeme`，因为它们正是用户需要核对的本地证据。

## 9. 确定性关联

关联只使用题目源中解析出的题号与答案记录的 `question_number` 相等这一条规则，不使用文件顺序、距离、题干相似度、选项语义或任何置信度模型。

对每个 Candidate：

1. 题目源中该题号必须只对应一个当前 Candidate；重复题号触发 `QB-ASSOCIATION-LOW-CONFIDENCE`，不自动关联；
2. 收集所有所选答案源中相同题号的 EvidenceRecord；
3. 没有记录时触发 `QB-ANSWER-MISSING`；
4. 每条 label 必须精确匹配该 Candidate 当前唯一 `source_label`，否则触发 `QB-ANSWER-CONFLICT`；
5. 所有合法记录若解析到同一 Option ID，则形成一个待确认提案，所有相同结论的记录都作为支持证据；
6. 若合法记录解析到不同 Option ID，则形成一个冲突组并触发 `QB-ANSWER-CONFLICT`，不得选择多数票、首条、最新文件或任意优先级；
7. 答案记录题号在题目源中不存在时触发无 Candidate 绑定的 `QB-ASSOCIATION-LOW-CONFIDENCE`；
8. 相同答案源中的重复同义记录不是冲突，但保留各自 locator；重复异义记录是冲突。

### 9.1 既有冲突裁决的共用适用谓词

第 9 节先计算不考虑历史人工裁决的 raw association。若 Candidate 当前已有一个由 `choose_evidence` 产生且状态为 `valid` 的答案 Decision，prepare 和 reverify 必须在生成 issue、ReviewItem recurrence、提案结论或安全失效差分之前，调用同一个 `adjudication_still_applies` 谓词；不得各自实现不同规则。

该谓词只能在第 7 节 Candidate/Option 身份门禁已经可靠通过后求值。它从当前完整重解析结果、当前 Decision、原 confirmation 和 canonical provenance 恢复原 `considered = selected ∪ rejected` 分区，并仅在以下条件全部成立时返回 true：

1. 当前 Candidate ID/revision、Decision ID/value、resolved Option ownership、question source identity、不可缩减答案 source identity 集合和 proposal/confirmation base lineage 仍与原裁决绑定完全一致；
2. 原 selected semantic keys 中每个 key 都在当前完整 source 集合中至少重现一次，且仍解析到当前 Decision 的唯一 Option ID；新增但同样解析到该 Option ID 的同义 evidence 不使谓词失败，也不自动写入旧 Decision；
3. 当前所有解析到其他 Option ID 或无法解析到 Option 的异义 semantic keys，逐项都是原 rejected set 中 byte-for-byte 相同的 semantic key；它们可以减少或消失，但不得新增、改变或来自原 considered set 之外；
4. 没有新的重复题号、非法关联、source 缩减、不可读 source、stale hash/revision、失效 adjudication 引用或其他现有门禁失败。

semantic key 的相等沿用第 13 节 `(source_id, question_number, evidence_fingerprint)`，数量和 locator 变化不改变语义相等；source identity、revision 覆盖和当前实例映射仍按第 13 节单独验证。谓词不得根据 Option 文字、标签相似度、文件顺序或时间猜测等价性。

谓词为 true 时，raw conflict 被归类为 `adjudicated`，而不是当前 `QB-ANSWER-CONFLICT` trigger：prepare 和 reverify 都必须保持原 Decision `valid` 和 Candidate 当前状态不变；已 `validated` 的 Candidate 不得降级，因其他独立门禁仍为 `candidate` 的 Candidate 也不得借旧裁决自动提升。原 conflict ReviewItem 保持 closed，不创建 recurrence，不要求再次人工确认。prepare 只在 proposal 中记录第 10 节的 audit-only `adjudicated` entry；reverify 写当前实例映射和“原裁决仍适用”的 audit。

谓词为 false 时，两种入口使用同一既有门禁顺序：身份/ownership/revision 无法可靠建立按第 7 节 `failed` 且 canonical 不变；selected key 改变、消失或原 source 不可证明时进入 `QB-DECISION-STALE`；新增、改变或超出原 rejected/considered set 的异义 key 进入 `QB-ANSWER-CONFLICT`；其他 base-lineage、source、合同或哈希失败沿用其既有 fail-closed 语义。只有应用全部仍有效的历史 adjudication 后，当前 issue trigger predicate 仍为 true，才允许生成新 issue 或 ReviewItem recurrence。

提案排序固定为：Candidate-bound entry 先按 Candidate 在题目源中的顺序，再按 source ID、locator 和 evidence fingerprint；第 9.7 条无 Candidate 的 source-level entry 排在全部 Candidate-bound entry 之后，再按 question number、source ID、locator、evidence fingerprint。文件系统枚举顺序、locale、时区和随机 UUID 不得改变语义排序。

## 10. 提案与 ReviewItem

准备阶段发布不可变 proposal artifact。proposal 顶层至少包含 proposal run ID、manifest SHA-256、Candidate artifact SHA-256、唯一 `question_source_id`、第 5.3 节 `prepared_from_pointer`，以及 `confirmation_base`。`confirmation_base` 只能是以下两种之一：

- `direct`：prepare 没有发布 canonical snapshot，确认基线就是 `prepared_from_pointer`；
- `prepare_result`：prepare 发布了 canonical review/安全失效 snapshot，记录该 prepare transaction ID 和 result snapshot ID。它不保存 result `current.json` 的文件哈希，避免 proposal -> plan -> commit -> current -> proposal 的哈希环。

每个 proposal entry 使用按 `conclusion` 冻结的 payload：

- Candidate-bound `confirmable` / `conflict` / `missing` / duplicate-question `low_confidence`：包含 Candidate ID/revision、题目 locator、显示题号、结论对应的 proposed Option/alternatives/evidence，以及 `review_item_id`；
- Candidate-bound audit-only `adjudicated`：只允许第 9.1 节谓词为 true；包含当前 valid Decision ID、原 confirmation/provenance 相对引用及原始哈希、原 considered/selected/rejected semantic-key 分区、当前匹配实例和当前 resolved Option ID，`review_item_id = null`。它不是可确认动作，不创建或重开 ReviewItem，也不改变旧 Decision evidence；
- Candidate-bound `stale`：只允许绑定当前 proposal/manifest 命名空间中一个可机械证明的 stale 事实；必须包含 exact Candidate ID/revision、题目 locator、显示题号、exact `decision_id`、exact 非空 `review_item_id` 和该 ReviewItem 的 lowercase SHA-256 `review_issue_key`。`proposed_option_id = null`、`proposed_source_label = null`、`alternatives = []`、`evidence = []`，不得携带答案值、Option、可由用户填写的 reason 或自由文本。canonical provenance 必须用同一个 `review_issue_key` 把该 Decision、`QB-DECISION-STALE` ReviewItem 和触发它的 stale audit 唯一连接；仅 Candidate 相同不足以建立该关系；
- 无 Candidate 的 source-level `low_confidence`（答案记录题号在题目源中不存在）：`candidate_id = null`、`candidate_revision = null`、`question_locator = null`、`proposed_option_id = null`、`proposed_source_label = null`、`alternatives = []`，`question_number` 取该答案记录的规范化题号，`evidence` 必须非空且只含触发该问题的 EvidenceRecord，`review_item_id` 必须非空。对应 ReviewItem 因冻结 Schema 不接受 null Candidate，必须省略 `candidate_id` 属性，而不是写 null；
- `missing` 的 `evidence = []`；`confirmable` 至少一条 supporting evidence；`conflict` 的 evidence 必须非空，并完整表示所有触发冲突的记录：可解析 label 按 resolved Option ID 分组为 alternatives，非法 label 以 `resolved_option_id = null` 保留。`conflict` 在“至少两个不同 resolved Option groups”或“存在任一 unresolved invalid-label evidence”时成立；`choose_evidence` 只能选择非空且共同解析到同一 Option ID 的现有 evidence，若没有任何可解析组则只能保留问题或以后重新 prepare 新证据。

`stale` entry 只能由以下两种 canonical 来源产生，且来源决定 confirmation base：

1. prepare 本轮在 Candidate/Option 身份可靠的前提下新发现既有 Decision stale，并按第 13、14 节安全失效 transaction 发布 result snapshot。proposal 使用 `confirmation_base = prepare_result`，绑定旧 Decision ID、本次 operation 预分配且将在 result snapshot 中成为 `open` 的 stale ReviewItem ID，以及相同的 `review_issue_key`；result snapshot 必须把该 exact Decision 置为 `needs_revalidation`、Candidate 置为 `candidate`，并在 provenance 中发布上述唯一连接。prepare transaction 未恢复并验证为 `complete` 时，该 entry 不可确认；
2. prepare 锁内验证的 current baseline 已经包含 exact `needs_revalidation` Decision、同 Candidate 的 exact open `QB-DECISION-STALE` ReviewItem，以及二者在 provenance 中相同 `review_issue_key` 的唯一连接。若本轮没有任何其他 canonical 差分，proposal 使用 `confirmation_base = direct`；若同一 prepare 因其他对象产生 canonical 差分，则使用 `prepare_result`，并要求 result snapshot 原样保留该绑定。

历史 `archived` Decision、`resolved/archived` stale ReviewItem、不同 Candidate/revision、不同 question source/manifest 命名空间、缺失或不唯一的 provenance/stable-issue 连接，都不得产生可执行 `stale` entry。新证据重新确认必须由新的 prepare 产生 `confirmable` 或 `conflict` entry，再走 `confirm`/`choose_evidence`；不得把答案塞入 `stale` entry。

proposal 不保存自身文件哈希，避免自引用。文件发布后，其原始字节 SHA-256 由 run artifact 记录，并由后续 confirmation 请求精确绑定。proposal entry 的 `review_item_id`：普通 `confirmable` 和 audit-only `adjudicated` 项为 `null`，其余项绑定一个 ReviewItem ID。

M3 使用现有 ReviewItem Schema 写 canonical review queue，并用 proposal artifact 承载 ReviewItem Schema 无法表达的证据细节。不得修改冻结 ReviewItem Schema。

固定映射：

| 条件 | issue code | blocking level | 允许的用户动作 |
|---|---|---|---|
| Candidate 无答案记录 | `QB-ANSWER-MISSING` | `blocking` | `provide evidence`, `retain` |
| 多条证据指向不同 Option ID，或 label 不属于当前 Candidate | `QB-ANSWER-CONFLICT` | `blocking` | `choose evidence`, `retain` |
| 题号不能唯一映射 Candidate，或答案题号不存在 | `QB-ASSOCIATION-LOW-CONFIDENCE` | `review_required` | `reject`, `retain` |
| Candidate 快照/身份不一致 | `QB-IDENTITY-AMBIGUOUS` | frozen `blocking`；run-level finding | M3 不创建新的 canonical ReviewItem，不提供 mapping；失败关闭且 canonical 状态不变 |
| Option 快照/身份不一致 | `QB-OPTION-IDENTITY-AMBIGUOUS` | frozen `review_required`；run-level finding | M3 不创建新的 canonical ReviewItem，不提供 rebind；仍按身份门禁失败关闭且 canonical 状态不变 |
| 既有 Decision 的当前证据无法重新证明 | `QB-DECISION-STALE` | `blocking` | `revalidate`, `archive` |

普通 `confirmable` 提案也必须人工确认，但不需要人为制造 ReviewItem。确认记录本身是人工门禁证据。

### 10.1 ReviewItem 状态机

canonical review queue 按稳定 issue key 去重。issue key 不是 ReviewItem 身份，其输入对象冻结为：

```json
{
  "answer_source_ids": ["sorted unique UUIDs"],
  "candidate_id": "UUID or null",
  "evidence_group": [
    {
      "evidence_fingerprint": "sha256",
      "question_number": 1,
      "resolved_option_id": "UUID or null",
      "source_id": "UUID"
    }
  ],
  "issue_code": "QB-*",
  "question_source_id": "UUID"
}
```

`question_source_id` 对所有 M3 answer-association ReviewItem 都是必需的命名空间字段，尤其用于防止同一答案 source 中的无 Candidate 记录在不同题目源运行之间产生相同 key。`evidence_group` 按 source ID、question number、evidence fingerprint、nullable resolved Option ID 排序并去重；其中 nullable `resolved_option_id` 使用固定总序：`null` 先于任何 UUID，非空 UUID 再按 Unicode code point 升序。missing 使用空数组，无 Candidate 的 source-level 问题使用 `candidate_id = null`。issue key 是上述精确对象的 M2 compact canonical JSON bytes 的 SHA-256。

ReviewItem 去重与 recurrence 只处理“应用第 9.1 节全部仍有效的历史 adjudication 后仍为 true”的当前 issue trigger。相同 key 的 `open` 问题重现时保留原 review ID，不重复创建。`resolved` 或 `archived` ReviewItem 永不重新打开；同一 key 的 trigger 后来真正再次为 true 时创建新 review ID，并在 provenance 记录 `supersedes_review_id`。仅仅再次扫描到原 evidence group，若 `adjudication_still_applies = true`，不构成 recurrence。`supersedes_review_id` 只允许用于“同一稳定 issue key 在先前 item 已关闭后、过滤有效历史裁决后仍再次发生”：复发的新 item 必须恰好指向父链中同 key 的最近一个 `resolved` 或 `archived` ReviewItem；非复发 item 不得携带该字段。它不得指向 `open` item、自身、后代或不同 key，supersession 链必须无环。仅因触发事实消失而把旧 item 标记为 `resolved` 不构成 supersession，也不得创建新的 review ID。因此父子 snapshot 中 ReviewItem 状态只单向前进。

M3 创建或继承 ReviewItem 时，`issue_code`、`candidate_id`（存在时）、`blocking_level` 和 `allowed_user_actions` 均为不可变字段。`blocking_level` 必须逐项等于冻结 `references/issue-codes.md` 的定义；M3 可以对某些 `review_required` 条件采用更严格的运行级失败关闭，但不得把其持久 blocking level 改写成 `blocking`。

| 当前提案/问题 | 用户动作或后续事实 | ReviewItem 结果 | Candidate/Decision 结果 |
|---|---|---|---|
| `confirmable` | `confirm` | 无 ReviewItem | 通过完整门禁后发布有效 Decision 并提升 |
| `confirmable` | `reject` | 不伪造 missing issue；只在 confirmation 记录拒绝 | 保持 `candidate`，不创建 Decision |
| `adjudicated` | 无用户动作；旧裁决仍适用 | 原 conflict item 保持 `resolved/archived`，不 recurrence | 原 Decision 保持 `valid`，Candidate 不降级 |
| `conflict` | `choose_evidence` 且其余门禁通过 | 对应 conflict item 变为 `resolved` | 旧决定按第 12.1 节处理，再发布新决定 |
| `conflict` | `retain_unresolved` | 保持 `open` | 不提升；已有有效决定必须安全失效 |
| `missing` | `retain_unresolved` | 保持 `open` | 不提升 |
| `missing` | 新 prepare 出现可确认证据并被确认 | 原 missing item 变为 `resolved` | 通过完整门禁后提升 |
| `low_confidence` | `reject_association` | 变为 `resolved` | 不创建 Decision，不提升 |
| `low_confidence` | `retain_unresolved` | 保持 `open` | 不创建 Decision，不提升 |
| open `stale` ReviewItem | 新 prepare 的 `confirmable`/`conflict` entry 被重新确认 | stale item 变为 `resolved` | 旧决定归档，新决定按门禁发布；不得直接确认 stale entry 来创建答案 |
| `stale` | `archive_stale` | stale item 变为 `resolved` | 旧决定归档；不创建新决定，Candidate 保持 `candidate` |
| 任意问题 | Candidate 或 source 被明确归档 | 相关 open/resolved item 可变为 `archived` | 不删除历史 |

同一 Candidate 的其他 open `blocking` 或 `review_required` 答案问题不因一个问题被解决而自动关闭，并继续阻断 `validated`。

旧问题只有在不可缩减的原 source 集合及本次新增 source 全部可读、完整通过严格解析和一致性核对后，才能因“触发事实已消失”被标记为 `resolved`。例如原 conflict 的异义 evidence 已从可读新 revision 中消失，或原 missing Candidate 现在出现可确认证据。这个 resolve 本身不创建 supersession；只有以后同一 stable issue key 再次发生时，才按上段创建新的 review ID 并指向该 closed item。若任一原 source 缺失、不可读、结构不明确或未参与本次完整重解析，不得宣称旧问题消失；相关 stale/conflict item 保持 open。

## 11. 人工确认

人工确认通过本地 CLI 操作表达，M3 不实现 GUI。确认请求必须同时绑定：

- proposal run ID；
- proposal artifact 的实际 SHA-256；
- 要确认、拒绝或保留的 proposal ID；
- 冲突时被选择的精确 evidence ID；
- 调用时重新读取到的 M2 Candidate 基线 SHA-256，以及当前 M3 `current.json` pointer SHA-256 或 `ABSENT`。

允许的动作：

- `confirm`：确认一个 `confirmable` 提案；
- `confirm_all_unambiguous`：显式批量确认该提案 artifact 中全部 `confirmable` 项；
- `choose_evidence`：在冲突组中选择一条或多条共同指向同一 Option ID 的现有证据，并把本次看过但未选择的异义证据记录为明确 rejected evidence set；
- `reject`：拒绝一个 `confirmable` 提案，仅记录拒绝，Candidate 保持 `candidate`；
- `reject_association`：拒绝 low-confidence 关联，不能指定替代 Candidate 或 Option；
- `retain_unresolved`：不作答案决定，保留问题供以后处理；
- `archive_stale`：归档旧 Decision，不创建新答案。

禁止在确认命令中直接输入 Option ID、选项标签或自由文本答案来绕过 proposal。用户只能确认或选择 proposal 中已经存在的本地证据。

### 11.1 `archive_stale` proposal binding 与唯一状态转换

`archive_stale` action 必须引用同一 proposal run/hash 中恰好一个 `conclusion = stale` entry。创建 confirmation artifact 前，除第 11、14、15.2 节的通用 proposal hash、Candidate baseline、base-lineage、current pointer、transaction 和 anti-replay 门禁外，必须在锁内从 actual current 完整重算并同时满足：

1. entry 的 Candidate ID/revision 与 canonical Candidate 完全一致，Candidate 当前状态为 `candidate`；
2. exact Decision ID 存在、属于该 Candidate/revision、`decision_type = answer_resolution`，且当前状态恰为 `needs_revalidation`；
3. exact ReviewItem ID 存在、属于同一 Candidate、`issue_code = QB-DECISION-STALE`、`status = open`，`blocking_level = blocking`，`allowed_user_actions` 恰为冻结的 `revalidate, archive`；
4. entry 的 `review_issue_key` 等于按第 10.1 节精确对象重算的 stable issue key；canonical provenance 中恰有一条 stale audit 用该 key 同时引用该 Decision 和 ReviewItem，且 source/manifest、question source、Candidate revision 与本 proposal 一致；
5. `confirmation_base = direct` 时 actual current 精确等于 `prepared_from_pointer`；`confirmation_base = prepare_result` 时 actual current 精确等于已 complete 的指定 prepare result，且其 parent 精确对应 `prepared_from_pointer`；
6. proposal 之后没有 intervening generation，proposal、Decision、ReviewItem、Candidate、source、manifest、base-lineage 或 provenance 任一绑定均未改变；
7. entry 的答案承载字段保持第 10 节冻结的 null/empty 形状，confirmation action 不携带 Option ID、label、evidence、reason 或自由文本；
8. 该 action 的 result transaction/snapshot 预分配 ID 与 confirmation artifact、plan、commit 和最终 current 一致。

任一条件不满足都必须在创建 confirmation artifact 前失败关闭并要求重新 prepare；Decision 已 `archived`、ReviewItem 已 `resolved/archived`、Candidate revision 改变、错误 Decision/ReviewItem ID、同 Candidate 但 stale provenance 不同、跨 dataset/proposal 或旧 proposal 重放都不能被“当前看起来仍 stale”替代。`archive_stale` 不得引用 `confirmable`、`conflict`、`missing`、`low_confidence` 或 audit-only `adjudicated`；反向地，`confirm`、`confirm_all_unambiguous`、`choose_evidence`、`reject`、`reject_association` 和 `retain_unresolved` 也不得引用 `stale` entry。ReviewItem 的 `revalidate` 文本动作只表示“新 prepare 后对新的 `confirmable`/`conflict` entry 执行 `confirm`/`choose_evidence`”，不是一个直接确认 stale entry 的 CLI action。

合法 `archive_stale` 必须通过新的 confirmation transaction 发布一个 child snapshot，且相对 parent 的业务差分恰好为：entry 绑定的 Decision `needs_revalidation -> archived`；entry 绑定的 ReviewItem `open -> resolved`；Candidate 保持 `candidate`；追加且仅追加本次 confirmation audit。不得创建 Decision、改变答案/evidence、提升 `validated`、删除或重绑历史 provenance，也不得关闭同 Candidate 的其他 open `blocking`/`review_required` item。child provenance 必须唯一引用本次 confirmation，并证明被归档/解决的正是 entry 绑定的两个对象。

`adjudicated` entry 是审计结果而不是待确认提案，任何 confirmation action 引用它都必须失败关闭。若 prepare 只产生 `adjudicated` entries 且没有 canonical review/安全失效差分，则不得创建空 transaction，run 在 artifact read-back 和第 15 节 run 收口后使用 `complete`；若同一 run 还有 confirmable 或真实 open issue，则仍按第 15 节终态优先级处理。

每次确认发布不可变 confirmation artifact，记录 confirmation ID、请求绑定、动作、选择的 proposal/evidence、冲突时完整 considered/selected/rejected evidence semantic keys、proposal base-lineage 所需的 transaction/snapshot 引用、锁内 `expected_current_pointer`、记录时间、预分配的结果 transaction/snapshot ID。confirmation artifact 必须先 immutable 发布并 read-back，随后 transaction plan 绑定其原始 SHA-256；不得在 transaction 完成后回写同一 artifact。系统只能记录“通过显式本地 CLI 提交”，不得声称已认证某个自然人身份。

每一种 confirmation 动作都必须发布一个新 snapshot，并把 confirmation audit 追加到 canonical provenance；即使 `reject`、`reject_association` 或 `retain_unresolved` 没有创建 Decision、没有改变 ReviewItem，也不得只留下孤立 run artifact。

确认开始时必须先验证 proposal 的 `confirmation_base`，再允许创建 confirmation artifact：`direct` 分支要求锁内实际 current pointer hash/`ABSENT` 精确等于 proposal 的 `prepared_from_pointer`；`prepare_result` 分支要求实际 current 精确指向 proposal 记录的 prepare transaction/result snapshot，且该 prepare transaction 已恢复为 `complete`；若 `prepared_from_pointer` 为 live hash，则该 result snapshot 的 `parent-pointer.json` 原始 SHA-256 必须等于它，若为 `ABSENT` 则 parent-pointer 必须是精确 ABSENT 对象。confirmation 记录锁内实际 current pointer SHA-256 或 `ABSENT` 作为 `expected_current_pointer`；随后 confirmation transaction 的 `plan.before` 必须与它完全相同，并同时绑定 proposal run/hash 与 confirmation artifact hash。这样允许 prepare 自己发布 review snapshot，但任何其他介入 snapshot 都会使旧 proposal 失效。

陈旧 proposal、哈希不匹配、source revision 变化、Candidate revision 变化、review/decision 状态变化、proposal base lineage 不匹配或其他 canonical artifact 变化必须拒绝确认，要求重新 prepare，不得静默刷新后沿用旧选择，也不得把旧 proposal 重放到另一 transaction。

## 12. Decision 与 `validated` 提升

确认后创建的答案决定必须：

- 使用现有 Decision Schema，`decision_type = answer_resolution`；
- 绑定当前 Candidate ID 和当前 Candidate revision；
- `value.resolved_option_ids` 恰好包含一个当前归属 Option ID；
- `evidence` 只包含用户确认的支持证据，不把未选冲突证据伪装为支持证据；
- 初始状态为 `valid`；
- 与 confirmation artifact 双向可追溯，但不得为此修改冻结 Decision Schema；关联记录放在 M3 transaction/confirmation artifact 中。

Candidate 只有同时满足以下全部条件才可进入 `validated`：

1. `question_type = single_choice`，且当前状态不是 `unsupported`、`ambiguous` 或 `archived`；
2. 恰好存在一个绑定当前 Candidate revision 的 `valid answer_resolution` Decision；
3. 该 Decision 恰好解析到一个归属当前 Candidate 的 Option ID；
4. 每条 Decision evidence 都有当前证明：source revision/locator 未变时可在当前 source 直接精确找到；source revision 或 locator 已变化时，必须存在覆盖当前 registry revision 的成功 reverify audit，把该历史实例键映射到当前语义键和当前实例键；
5. 用户 confirmation 绑定当前 proposal 和所有 canonical 输入哈希；
6. 该 Candidate 没有 open 的 `blocking` 或 `review_required` 答案关联问题；
7. 同一 Candidate 不存在另一个当前 `valid answer_resolution` Decision；
8. M0 Runtime validator 和 M3 增强业务 validator 均通过；
9. staged artifact 写入、read-back、canonical JSON 和哈希校验全部通过。

任一条件失败都不得部分提升。`validated` 只表示“当前本地证据已由用户确认且合同门禁通过”，不表示系统独立证明了学科答案正确，也不提供正式判分能力。

### 12.1 既有答案决定转换矩阵

确认事务开始前和发布后都必须验证同一 Candidate 最多有一个当前 `valid answer_resolution` Decision。若输入状态已有两个或以上，视为 canonical corruption，失败关闭，不自动选择或归档。

| 既有当前决定 | 当前已确认提案 | 同一 snapshot transaction 的结果 |
|---|---|---|
| 无 | 任一可发布答案 | 创建一个新 `valid` Decision |
| `valid`，Option ID 和已确认 source/evidence 集合完全相同 | 相同答案重复确认 | 不创建第二个 Decision；保留原决定，新增 confirmation audit |
| `valid`，Option ID 相同但已确认 source/evidence 集合改变 | 相同答案的新证据集合 | 旧决定 `archived`，创建一个新 `valid` Decision |
| `valid`，Option ID 不同 | 异义答案 | 准备阶段先把旧决定置为 `needs_revalidation` 并打开 conflict；只有 `choose_evidence` 后才归档旧决定并创建新决定 |
| `needs_revalidation` | 任一重新确认答案 | 旧决定 `archived`，创建一个新 `valid` Decision |
| `archived` | 任一可发布答案 | 历史不变，创建一个新 `valid` Decision |

旧 Decision 不得原地改写 evidence、value 或 Candidate binding。替换必须保留旧 ID 和历史状态，并为新决定分配新 ID。

## 13. 重新核验与安全失效

重新核验必须显式选择现有 Decision 或一个题目源，不扫描未选 workspace。取得锁后必须把实际 current pointer SHA-256 冻结为 `expected_before_pointer`（首次 canonical 状态不存在时 reverify 本身无可核验 Decision，因而不适用 `ABSENT` 分支）；reverify artifact 必须在发布事务前 immutable 写出并绑定该值，随后 reverify transaction 的 `plan.before` 必须与之完全相同并绑定 reverify artifact 原始哈希。required Decision set 由这个 before snapshot 计算，调用方不能传入一个更小列表：

- 按 Decision 核验：恰好包含被选 Decision；若其 Candidate 另有当前 `valid`/`needs_revalidation` 答案决定，因唯一性异常而失败关闭；
- 按题目源核验：包含父 snapshot 中所有 Candidate `source_id` 等于该题目源，且状态为 `valid` 或 `needs_revalidation` 的 `answer_resolution` Decision；同时每个 `validated` Candidate 必须在该集合中有其唯一 valid Decision，否则先按 canonical corruption 失败关闭；
- `archived` Decision 只做父子历史完整性校验，不重新判断答案有效性。

每个 required Decision 分别沿 `Decision -> provenance -> confirmation -> proposal -> manifest` 恢复自己的完整原答案 source ID 集合。调用方不得删除其中任何 source；本次可显式增加 source。运行级读取集合是所有 required Decision 原集合的并集再加显式 additions，但第 15.2 节按 Decision 分别验证不可缩减关系。任何缩减请求都使对应旧 Decision `needs_revalidation`，且只能通过新的 prepare/confirm 建立新决定，不能以缩减后的集合保持旧决定有效。

EvidenceRecord 有两层键：

- 历史实例键：`(source_id, source_revision, locator, evidence_fingerprint)`，精确表示 Decision 当时引用的证据；
- 当前语义键：`(source_id, question_number, evidence_fingerprint)`，用于在同一持久 source 身份的新 revision 中重找相同证据。

同一当前语义键出现一次或多次都表示同义证据仍存在，数量变化不构成冲突；只要至少存在一条即可重现。不同 label 会产生不同 fingerprint，并按异义证据处理。旧 Decision binding 保持为历史事实，不原地更新 locator 或 source revision；每次成功 reverify 都写不可变 audit，把每个历史实例键映射到当前一个或多个实例键。若 registry revision 高于 Decision 中的 evidence revision，M3-aware 读取方必须看到覆盖当前 revision 的成功 audit，才可继续把该决定视为当前有效。

`choose_evidence` 形成的冲突裁决保存在 confirmation/provenance，而不塞入冻结 Decision Schema。prepare 与 reverify 都必须使用第 9.1 节同一个 `adjudication_still_applies` 谓词：完全相同的 rejected semantic keys 可以继续存在而不再次推翻已做出的人工裁决，也不得仅因此重开 conflict；任何未出现在原 considered/rejected set 中的新异义 semantic key、rejected key 的语义改变、selected key 的改变/消失或 adjudication binding 失效，按第 9.1 节统一进入 conflict/stale/failed。旧 rejected key 消失或转为支持原 Option 的同义证据，只记入 audit，不使有效决定失效。

每个既有有效答案决定按以下顺序核验：

1. Candidate ID 和 revision 是否仍存在且一致；
2. resolved Option ID 是否仍属于当前 Candidate；
3. 原证据 source 是否仍在 registry，且当前字节、路径和 revision 合法；
4. 每个原 evidence 的当前语义键是否能在不可缩减的答案源集合中至少重现一次；
5. 当前证据是否全部属于支持原 Option ID 的证据、已明确 rejected 的原异义证据，或同义重复；
6. 是否出现新的、尚未由 confirmation 裁决的异义证据、重复题号、非法 label 或其他阻断问题。

结果矩阵：

| 变化 | 结果 |
|---|---|
| 仅文件重命名，唯一 source 身份保持，证据不变 | Decision 保持 `valid` |
| 答案源其他内容变化，但所引证据仍唯一且结论不变 | Decision 保持 `valid`，写 reverify audit |
| 同一证据仅移动行号，当前语义键仍存在且结论不变 | Decision 保持 `valid`，audit 记录当前实例键 |
| 新增同义证据且全部指向原 Option ID | Decision 可保持 `valid`，新增证据不自动加入旧 Decision |
| selected semantic key 改变或消失，或其 source 缺失/无法读取/无法完整解析 | `needs_revalidation`，Candidate 回到 `candidate`，打开 `QB-DECISION-STALE` |
| 原 confirmation 已明确 rejected 的异义证据原样存在 | Decision 可保持 `valid`，audit 记录人工裁决仍适用 |
| rejected key 在全部原 source 可读并完整重解析后消失或转为同义 | Decision 可保持 `valid`，audit 记录旧冲突事实已消失 |
| 新增或改变后的异义证据指向不同 Option ID，且不在原 considered/rejected set | `needs_revalidation`，Candidate 回到 `candidate`，打开 `QB-ANSWER-CONFLICT` |
| Candidate revision、题干、Candidate 身份或 Option 身份不一致 | 不能可靠建立身份；按第 7 节产生 run-level finding 并 `failed`，不迁移、不发布安全失效 snapshot、不改写旧 Decision/Candidate |
| Candidate 在 M2 基线/重放中缺失 | 属于第 7 节身份无法建立；run-level finding + `failed`，canonical 状态不变 |
| 同一 Candidate ID 在 canonical parent 中已经是 `archived` | 旧 Decision 可转为 `archived`，历史保留；不得借此解释基线缺失或身份歧义 |

自动重新核验只能保持有效或执行保守降级，不能自动把 `needs_revalidation` 恢复为 `valid`。恢复有效必须重新 prepare，并由用户确认当前证据。

如果准备或重新核验在 **Candidate/Option 身份已经可靠建立** 的前提下，确定性发现一个既有 `validated` Candidate 因答案证据 stale、新增未裁决冲突、source 不可读等原因不再满足门禁，允许执行安全失效 transaction：先把相关 Decision 标记 `needs_revalidation` 或 `archived`，再把 Candidate 降为 `candidate` 并打开相应 ReviewItem。该动作不需要用户批准，因为它不会创造答案，只撤销无法继续证明的有效性；失败时必须保持旧 canonical 集合或完整发布新集合，不能半降级。若失败原因是第 7 节的 Candidate/Option 身份不一致，则本段不适用，必须保持 canonical 状态不变并失败关闭。

## 14. 持久布局与原子发布

逻辑布局冻结为：

M3 不原地改写 M2 Candidate artifact，也不把 Candidate、Decision 和 Review 拆成多个独立 canonical 文件。每次 canonical 状态变化先构造一个不可变完整快照，最后只原子替换一个 current pointer：

```text
workspace_root/
├─ candidates/sources/<question_source_id>.json      # M2 不可变基线
├─ runs/answer-association/<run_id>/
│  ├─ run.json
│  ├─ manifest.json                                  # prepare only
│  ├─ proposal.json                                  # prepare only
│  ├─ review-queue.json                              # prepare snapshot
│  ├─ confirmation.json                              # confirmation run only
│  └─ reverify.json                                  # reverify run only
├─ state/answer-association/
│  ├─ current.json                                   # 唯一 canonical 指针
│  └─ snapshots/<snapshot_id>/
│     ├─ parent-pointer.json                         # before pointer 原始快照或 ABSENT 对象
│     ├─ interchange.json                            # 现有 M0 interchange Schema
│     ├─ provenance.json                             # M3 决定/确认/源集合链路
│     └─ commit.json                                 # 最后写入的快照 commit marker
├─ transactions/answer-association/<transaction_id>/
│  ├─ plan.json                                      # immutable transaction plan
│  └─ state.json                                     # atomic latest state
└─ locks/answer-association.lock
```

一旦 `current.json` 存在，M3-aware 读取方只认它指向且完整验证通过的 snapshot；M2 Candidate artifact 仍是结构与身份基线，不再单独代表 M3 当前状态。`interchange.json` 同时包含 manifest、Candidate document、canonical review queue 和 Decision document，因此同一 Candidate 的状态与其决定永远来自同一个快照。

每个新 snapshot 的 manifest 必须是父 snapshot manifest 与本次显式 source 快照的身份并集，并保留所有 Candidate、当前/历史 Decision 和 ReviewItem 仍引用的 source 条目。每个 `source_id` 恰好出现一次，按 `source_id` Unicode code point 升序排列；M3 validator 必须在调用 M0 validator 前拒绝重复 ID。

合并规则固定为：父 entry 是历史基线；同 ID 的当前 registry entry 只有在身份核对成功、revision 不回退、dataset 相同且显式 kind 与父 kind 相同时，才能更新 current path/path history/content hash/revision。首次加入的 source 使用本次显式角色；已存在 source 的 kind 不可改变，冲突触发 `QB-ROLE-AMBIGUOUS` 并失败关闭。当前 registry 中仍存在的 source 使用已核对的新字段；已删除或当前无法读取但被历史 artifact 引用的 source 保留父 snapshot 最后已知 entry，只能支持历史审计，不能让相关 Decision 保持当前 `valid`。不得因 source 不可用而删除历史证据身份，也不得依赖 M0 validator 对重复 ID 的折叠行为。

`path_history` 合同固定为：首次加入时逐项完整复制已验证 registry `path_history`，要求非空且最后一项等于 current relative path。后继 snapshot 必须验证父 `path_history` 是当前已验证 registry `path_history` 的**精确前缀**；随后把 registry 中该前缀之后的全部 suffix 按原顺序逐项追加，不能只比较父最后路径与当前路径，否则会丢失两个 M3 snapshot 之间发生的多次 rename。若父 history 不是 registry history 的精确前缀、registry history 回退/缺项，或最后一项不等于 current relative path，则身份历史合同失败并 `failed`，不得猜测合并。合并后父 history 仍须原样成为新 history 前缀；不得删除、重排或全局去重。曾经使用过的旧路径可以在以后改名回来，因此非相邻重复合法；连续重复若已存在于经验证的 registry history 则原样保留，M3 自身不得合成新的连续重复。

### 14.1 单写者协议

每个 prepare、confirm、reverify、recover 和 M3-aware read 操作都必须先取得同一个 workspace 级 OS advisory exclusive lock。锁由 stdlib 的 Windows/POSIX 适配实现，进程退出或崩溃时由操作系统释放；锁文件是否残留不代表仍持锁。无法取得锁时立即失败，不等待、不并发写、不根据 PID 猜测清理。该 advisory lock 只保证遵守 M3 协议的进程互斥；不遵守协议的外部写入必须靠紧邻发布的 before-hash 复核检测并失败，不能声称被锁阻止。

取得锁后，操作必须先读取 current pointer、所有未完成 transaction 和所有缺失/非终态 run。恢复顺序固定为：先按第 14.3 节把每个可确定恢复的 transaction 收口为 `complete` 或 `aborted`，再按第 15 节从 durable 事实收口对应 `run.json`；存在无法恢复或失败关闭的 transaction/run 矛盾时不得开始新业务操作。存在 `staged` 或 `publishing` transaction 时，只允许精确恢复或失败关闭，不得开始新业务操作。

### 14.2 Snapshot 发布协议

每个状态变化使用以下冻结顺序。若本 operation 将发布 snapshot，则 transaction ID 与 snapshot ID 先在内存中分配，仅作为未来身份，不产生写入；随后业务 operation artifact（prepare 的 manifest/proposal、confirm 的 confirmation、reverify 的 reverify artifact）必须已经在同一把锁内按第 14.4 节 immutable 发布并 read-back，其记录的 base pointer 来自本次锁内已验证状态，并可引用上述预分配 ID；本序列不会回写这些 artifact。`run.json` 是第 15 节的可收口 operational/audit artifact，明确不属于 transaction canonical hash graph 或下列 operation artifact 白名单：

1. 紧邻发布再次读取并验证 before pointer；不存在时使用字符串哨兵 `ABSENT`，存在时记录其原始文件 SHA-256；该值必须与 operation artifact 冻结的 base pointer 一致，否则本 operation 立即 stale/failed，不创建 plan；
2. 在全新 snapshot 目录写入 `parent-pointer.json`、`interchange.json` 和 `provenance.json`，逐个 read-back 并记录原始文件哈希；`parent-pointer.json` 是步骤 1 before pointer 的精确 JSON 对象，首次状态使用 `{"state":"ABSENT"}`；
3. 原子发布 immutable `plan.json`，记录 operation、before pointer、after snapshot 路径、parent-pointer/interchange/provenance staged hashes、生成 commit 所需的全部非自引用字段，以及本次 operation artifact 的相对路径和原始 SHA-256。operation artifact 集合必须按 `plan.operation` 使用互斥且精确的白名单分支：prepare 恰好绑定 `manifest.json` + `proposal.json`，confirm 恰好绑定 `confirmation.json` 并重复绑定被确认 proposal 的 run/hash，reverify 恰好绑定 `reverify.json`；不得缺少、混入、加入 `run.json` 或用另一 operation 的 artifact 集合冒充。这些 operation artifact 必须已 immutable 发布并 read-back，各自记录的 base pointer 与 `plan.before` 满足第 5.3、11、13 节规则，且 plan operation 必须与对应章节允许的父子 canonical 语义差分一致；plan read-back 后不得再修改；
4. 按第 14.3 节 state 协议原子发布 `state.json`，sequence=1、status=`staged`、plan 原始哈希匹配；
5. 原子发布 immutable `commit.json`；它由 plan 字段和 plan 自身原始哈希确定性生成，并列出 snapshot ID、parent-pointer/interchange/provenance 原始哈希、transaction ID 和 plan 原始哈希。commit 使用与 state 相同的临时文件、flush、fsync、read-back、单次 `os.replace` 纪律；若目标已存在，只允许 byte-for-byte 等于确定性期望值，否则失败关闭，绝不覆盖；
6. read-back 完整 snapshot 和 commit，并原子发布 sequence=2、status=`publishing` 的 state；
7. 生成只引用已提交 snapshot 及 `commit.json` 原始哈希的 `current.json`；在 pointer replace 紧前重新读取当前 pointer 原始 bytes。若仍精确等于步骤 1 的 before hash 或 `ABSENT`，才可继续；若已经精确等于本 transaction 的 after pointer，则转入第 14.3 节“after -> complete”恢复；任何其他值都是未知/外部修改，必须失败关闭，**不得**写 `aborted` 来掩盖未知 pointer；
8. before 复核通过后，用同目录临时文件、flush、fsync、read-back 和单次 `os.replace` 原子替换 `current.json`；
9. 再次从 current pointer 解析完整 snapshot，全部通过后原子发布 terminal `complete` state。
10. 只有步骤 9 的 terminal transaction state 已按原始 bytes read-back 后，才允许按第 15 节发布成功类 run terminal；transaction 不反向引用 run，步骤 10 崩溃不影响 canonical snapshot，并由下一次持锁恢复确定性补写 run terminal。

`commit.json` 不引用自身哈希；`current.json` 记录其原始文件哈希。任何读取方都必须在持锁后依次验证 current、commit、parent-pointer、interchange 和 provenance 的路径边界、Schema、哈希及第 15.2 节跨对象不变量，才可返回状态。

promotion、review 解决和安全失效都通过新 snapshot 表达。候选正文、Option 身份、fingerprint、locator 和 revision 必须与 M2 基线或父 snapshot 一致；本阶段只允许 Candidate `status` 在 `candidate <-> validated` 间按门禁变化。

### 14.3 崩溃恢复

- 每次 `state.json` 转换都使用同目录临时文件、严格 JSON bytes、file flush、fsync、read-back、单次 `os.replace` 和替换后 read-back；旧 state 在 replace 前保持有效，不能原地截断。合法组合固定为 sequence=1/status=`staged`、sequence=2/status=`publishing`、sequence=3/status=`complete|aborted`；正常发布只允许 `1 -> 2 -> 3 complete`，仅在 current 仍为 before、有效 commit 尚未发布且 staged 集合不能完成时允许 `1 -> 3 aborted`，不存在其他跳转；
- `plan.json` 是恢复根。`state.json` 缺失、损坏或 plan hash 不匹配时，只能依据 immutable plan、实际 current pointer、staged snapshot 和 commit **存在性/有效性**重建；`state.json` 存在但 `plan.json` 缺失或 plan 本身无效时直接失败关闭；
- “commit 不存在”和“commit 已存在但无效”必须严格区分。commit 路径不存在时才叫“不存在”；只要路径存在却无法通过精确 JSON、Schema、确定性 bytes/hash 或 staged-hash 核对，就属于已出现未知/损坏 commit，必须失败关闭，不得退回 `staged` 或 `aborted`；
- current=before 且 commit 不存在时，可重建 `staged`。plan 绑定的 operation artifacts 属于 plan 之前已经 immutable 发布的输入：任一缺失或哈希不匹配都表示外部改写/损坏，必须失败关闭。只有 operation artifacts 全部有效后，才检查 parent-pointer/interchange/provenance；三者与 plan hashes 全部匹配时按 plan + plan 原始哈希确定性原子补写 commit，若这些**尚未 commit 的 staged snapshot 文件**缺失或不匹配且 current 仍精确为 before，则原子发布 terminal `aborted`，保留非 canonical 残片供审计；
- current=before 且存在**有效 commit**时，只能重建/保持 `publishing`，并允许重新执行一次 pointer replace；若 state 声称 `publishing` 但 commit 不存在或无效，则失败关闭，因为 protocol 中 `publishing` 只会在 commit read-back 成功后出现；
- current=after 时，只有 snapshot、commit、plan、operation artifacts 和 after pointer 全部完整验证通过，才能重建/收口为 `complete`；否则失败关闭；
- current 既不是 before 也不是该 transaction 的 after 时，一律视为未知/外部修改并失败关闭，不覆盖、不删除、不猜测，也不得写 `aborted`；
- 新 snapshot 未被 current 引用时不是 canonical 状态，可以保留供审计；本阶段不自动删除；
- 不存在 Candidate 已提升而 Decision 尚未可见的中间 canonical 状态，因为两者位于同一 `interchange.json`，且 pointer 最后切换。

`complete` 和 `aborted` 是 terminal transaction 状态。`aborted` 只表示“plan 已存在、current 仍精确为 before、且在任何有效 commit 发布前发现 staged 集合无法按 plan 完成”；因此 aborted transaction 必须验证 current=before 且不存在有效 commit，之后不阻断新的业务 operation。`complete` 必须验证 current=after 且完整对象图通过。任何已经合法编码但与这些现实条件矛盾的 terminal state（例如 `aborted` + after pointer，或 `complete` + before pointer）都属于 canonical transaction corruption，必须失败关闭，不得把 terminal 状态反向改写。pointer 未知、commit 已出现但损坏、或 commit 后 snapshot 被破坏时都不得借 `aborted` 收口。若 `plan.json` 尚未成功发布便崩溃，未被 current 引用的新 snapshot 只是孤立非 canonical artifact，不形成阻断 transaction。

transaction 恢复到 terminal 后必须继续执行第 15 节 run reconciliation，二者顺序不可交换。五个冻结 crash point 的 canonical 结果为：A. operation artifact 已写而 plan 未写时没有 canonical transaction，任何 staged snapshot 只是孤立 artifact；B. staged 已写而 commit 未写时按本节确定性补写 commit 或在唯一允许条件下 aborted；C. valid commit/publishing 已写而 pointer 未切换时继续唯一 pointer replace；D. pointer 已切换而 complete state 未写时验证完整对象图后只补写 complete；E. complete 已写而 run terminal 未写时 canonical 已完成，只按第 15 节补写 run，不重做业务判断、不请求人工确认、不创建第二个 snapshot。

### 14.4 JSON 字节与哈希合同

所有 M3 JSON artifact 使用与现有 workspace JSON 相同的原始文件编码：仅接受精确 built-in JSON 类型，`ensure_ascii=False`、`sort_keys=True`、`indent=2`，末尾恰好一个 LF，再以严格 UTF-8 编码。禁止 NaN/Infinity、容器子类、非字符串 object key、BOM 和额外尾随字节。artifact SHA-256 一律计算已发布文件的完整原始字节。

需要语义 fingerprint 时沿用 M2 compact canonical JSON：`ensure_ascii=False`、`sort_keys=True`、`separators=(",", ":")`、无末尾 LF，再以 UTF-8 编码。任何 artifact 都不得包含自身文件哈希；父 run、transaction、commit 或 pointer 记录子 artifact 哈希。

编码 test vector 冻结为对象 `{"a":"题","b":["A"]}`：

- compact canonical JSON 字节精确为 `{"a":"题","b":["A"]}` 的 UTF-8，共 21 bytes，SHA-256 为 `8fe664ef5335c949424a347dd901141cb1a68b0e8db91a318991e26ba8f5dc11`；
- workspace JSON 字节精确为下列 UTF-8，共 39 bytes，SHA-256 为 `8c64fdc1fd7928af1840909f9afd41a55c9f9746375076129fdaeb8544d7bec9`：

```json
{
  "a": "题",
  "b": [
    "A"
  ]
}
```

代码块末尾包含一个 LF。合同测试的 expected bytes 和 hash 必须独立硬编码，不得调用被测编码器生成。

## 15. 运行状态、退出语义与隐私

准备、确认和重新核验使用独立 M3 run schema，不修改 M1/M2 run schema。运行阶段至少区分 `source_resolution`、`snapshot_validation`、`answer_parse`、`association`、`review`、`confirmation`、`publication`、`read_back`、`complete`。

`run.json` 只是 operational/audit artifact，不是 canonical truth source，不进入 transaction/commit/current 哈希图，也不得被 plan、commit、current 或 snapshot 反向引用。canonical 发布事实只由完整验证通过的 `current.json + transaction plan/state + commit + immutable operation artifacts` 确定；run 只能单向声明并验证这些既存事实，不能使 transaction 成功、修复 canonical corruption 或覆盖 before/after 判断。proposal/confirmation/reverify/manifest 仍可由 run 记录其原始哈希，但后续 confirmation 和 provenance 必须直接验证实际 immutable artifact，不能只相信 run 的声明。

首次 run write 必须冻结 run ID、operation、schema/contract version、确定性的 workspace 内相对 run 路径和已存在输入引用；后续 phase 更新只允许单向追加 phase 状态、已 read-back 的 output artifact 相对引用/原始哈希、issue counts、冻结形状的 run findings、预分配或实际 transaction/snapshot 引用和审计时间，不得删除、重排、改绑既有引用或改变 run identity/operation。任何引用加入 run 前，其目标必须已存在且通过 bytes、Schema、路径和哈希 read-back。

每次创建或更新 `run.json` 都必须使用同目录临时文件、严格 JSON bytes、file flush、fsync、read-back、单次 `os.replace` 和替换后再次 read-back；不得原地截断。terminal 一经合法发布不可逆，非 terminal 更新必须保持已记录 phase 的单向进展。run target 已存在但既有 immutable 字段或已记录 artifact hash 不同，属于 run/audit corruption，不得覆盖。

M3 run artifact 的 `run_findings` 只承载不创建 canonical ReviewItem 的脱敏结构化 finding，当前至少用于第 7 节身份不一致。每个 finding 精确包含 `issue_code`、冻结 `blocking_level`、nullable `source_id`、nullable `candidate_id`、nullable `option_id`，不得包含自由文本、题干、选项或答案行；nullable UUID 的稳定排序统一使用 `(is_null, value)`，其中非 null 先于 null，同类 UUID 再按 Unicode code point 升序。`blocking_level` 必须来自冻结 issue-code 表；操作是否 `failed` 由 M3 门禁决定，不通过篡改 blocking level 表达。

运行终态：

- `complete`：操作已完整发布并通过 read-back；
- `needs_confirmation`：prepare 至少有一个 `confirmable` 提案，且没有任何 open review 问题；
- `needs_review`：存在任一 missing/conflict/low-confidence/stale 或其他 open review 问题；即使同一 run 也有 `confirmable` 提案，仍优先使用该终态；
- `failed`：输入、路径、合同、哈希、恢复或发布失败，优先级最高。

终态优先级固定为 `failed > needs_review > needs_confirmation > complete`。

对会发布 snapshot 的 prepare、confirm 和 reverify，`complete`、`needs_confirmation`、`needs_review` 这些成功类 terminal 只能在对应 transaction 已恢复并验证为 terminal `complete` 后发布；run 必须记录 transaction ID、terminal state 原始 SHA-256、result snapshot ID 和已验证 current/commit claim。transaction=`aborted` 时 run 只能收口为 `failed`。unknown pointer、invalid commit、hash/contract/recovery failure 均不得留下成功 run terminal。

不发布 snapshot 的 direct prepare 只有在 manifest/proposal 已 immutable read-back、实际 current 仍等于 `prepared_from_pointer`、且 proposal 证明没有 canonical review/安全失效差分时，才可直接按内容收口：存在绑定 current 中既有 open ReviewItem 的 missing/conflict/low-confidence/stale entry 时为 `needs_review`；不存在 open review entry 但存在 confirmable 时为 `needs_confirmation`；只含 `adjudicated` 或无待处理项时为 `complete`。direct proposal 不能凭空声明 open issue：对应 ReviewItem 不存在、不是 open 或需要新建/改变 canonical ReviewItem、Decision、Candidate 时，必须发布 prepare transaction，否则 run 必须 `failed`。confirm 和 reverify 不存在无 transaction 的成功分支。

持锁恢复 run 时不得重新解析答案、重新执行关联/裁决、再次请求人工确认或创建 transaction/snapshot。恢复器只读取 immutable operation artifacts 和已经按第 14.3 节收口的 durable transaction/current 图：transaction=`complete` 且 run 缺失或非 terminal 时，按 operation artifact 已冻结的结果和终态优先级确定性创建/补写成功 terminal；transaction=`aborted` 或 plan 从未发布但 operation artifact 声明将发布 snapshot 时，确定性补写 `failed`；direct prepare 按上段唯一规则收口。这样 crash point E 只补写 audit，不重复 canonical 行为。

若 run 声称成功但其 transaction ID/state hash/result snapshot/current/commit 不能证明 terminal complete，该 run 不得作为成功证据：若 transaction 图本身完整且为 aborted/before，则仅为 run/audit corruption，canonical 前态仍有效；若 pointer、commit、plan、snapshot 或 terminal state 本身无法验证，则同时属于 canonical transaction corruption，所有 M3-aware 操作失败关闭。只有第 14.3 节已经授权的确定性 transaction 恢复，以及“canonical complete + run 缺失/非 terminal”的 run 补写可自动修复；既有矛盾 terminal、改绑引用或篡改 hash 不得静默改写。`failed` run 与已证明 complete transaction 的矛盾同样属于 run/audit corruption，但不撤销 canonical complete。

退出码设计沿用项目习惯：`0` 表示 complete，`3` 表示 needs_confirmation 或 needs_review，`2` 表示失败。stdout 只输出稳定 JSON 摘要；stderr 和日志不得输出题干、选项正文、完整答案行、绝对输入路径或未净化异常文本。

### 15.1 M3 Schema manifest

`schemas/m3/` 只允许以下八个 Schema，全部使用 JSON Schema 2020-12、`additionalProperties: false`、严格 UUID/小写 SHA-256/相对路径约束和显式 enum：

| Schema | 必需的顶层语义 |
|---|---|
| `answer-association-run.schema.json` | schema/contract version、run ID、operation、不可变 identity/input、单向 phase 状态、终态、输入/输出 artifact 引用、nullable transaction/current complete claim、issue 计数、冻结形状的 `run_findings`、时间 |
| `answer-association-proposal.schema.json` | run/manifest 引用与哈希、`prepared_from_pointer`、`confirmation_base`、题目 source、稳定排序 proposal entries；entry 用 conclusion `oneOf` 冻结 Candidate-bound confirmable/conflict/missing/low-confidence/adjudicated/stale 与无 Candidate source-level payload、evidence/alternatives、nullable review ID；stale 分支必须绑定 exact Decision、非空 stale ReviewItem、stable issue key 和 null/empty 答案字段 |
| `answer-association-confirmation.schema.json` | confirmation/run ID、proposal 引用与哈希、proposal base-lineage 核验、锁内 `expected_current_pointer`、动作数组、transaction/snapshot 结果引用、记录时间 |
| `answer-association-reverify.schema.json` | run ID、锁内 `expected_before_pointer`、被核验 Decision、不可缩减原 source 集合、显式新增 source、历史到当前 evidence instance 映射、检查结果、transaction/result snapshot |
| `answer-association-provenance.schema.json` | snapshot/parent ID、每个当前或历史 Decision 到 proposal/confirmation/manifest/source-set/reverify audit 的链路、selected/rejected conflict adjudication、ReviewItem 链路，以及 stale audit 中 exact Decision/ReviewItem/stable issue key 的唯一连接 |
| `answer-association-transaction.schema.json` | `plan` 分支：transaction ID、operation、before pointer/hash 或 `ABSENT`、after snapshot、parent-pointer/interchange/provenance staged hashes、按 operation `oneOf` 冻结的精确 artifact 白名单及相对路径+原始哈希、commit 非自引用字段；`state` 分支：transaction ID、plan hash、sequence、`staged/publishing/complete/aborted`、read-back 结果与合法跳转 |
| `answer-association-pointer.schema.json` | live pointer 分支：state format version、snapshot ID/相对路径、commit 原始哈希、generation、parent pointer hash；ABSENT parent 分支：仅 `state=ABSENT` |
| `answer-association-commit.schema.json` | snapshot ID、parent-pointer/interchange/provenance 原始哈希、transaction ID 和 immutable transaction plan 原始哈希 |

Schema 必须进一步冻结每个数组的最小长度、唯一性和排序要求。跨 artifact 固定排序键为：manifest source 按 source ID；Candidate 沿 M2 source 顺序；Option 沿 current position；Candidate-bound proposal 先按 Candidate 的 M2 source ordinal，再按 evidence 的 source ID/locator/fingerprint；无 Candidate source-level proposal 排在 Candidate-bound proposal 之后，再按 question number、source ID、locator、fingerprint；Decision 按 Candidate source 顺序、status、decision ID；Candidate-bound ReviewItem 先按 Candidate source ordinal、issue code、review ID，无 Candidate ReviewItem 排在其后并按 question source ID、issue code、review ID；confirmation action 按 proposal ID；reverify result 按 decision ID。凡排序字段允许 null/缺省时，必须在对应 Schema/validator 中使用显式 type-tag 总序，不能依赖语言对 null 与字符串的默认比较；本规格另有规定的 `resolved_option_id` 使用 null-first，其余 nullable UUID 使用 non-null-first。时间统一为 UTC RFC 3339 `Z`，只用于审计，不参与关联、排序、ID 或 fingerprint。所有 artifact ID 都是运行内持久 UUID，不作为跨运行语义匹配键。

Schema 的条件分支必须用 `oneOf` 冻结：proposal 的六种 conclusion payload，其中 `low_confidence` 再嵌套 Candidate-bound / no-Candidate source-level `oneOf`，`adjudicated` 必须绑定一个当前 valid Decision 和完整原裁决分区且禁止 confirmation action，`stale` 必须绑定一个 `needs_revalidation` Decision、一个 open `QB-DECISION-STALE` ReviewItem 和 stable issue key，且禁止答案承载字段；run 的 non-terminal/四种 terminal、transaction-backed/direct-prepare success claim；confirmation 的每种 action payload及第 11.1 节 action/conclusion 矩阵、transaction 的 plan/state、plan 的 `ABSENT`/hash before pointer、pointer 的 live/ABSENT 分支和 live pointer 的首代/后继 parent。`current.json` 只允许 live 分支；`parent-pointer.json` 首代使用 ABSENT 分支。`current.json.generation` 首代必须为 `1`，后继必须等于已验证 `parent-pointer.json` generation 加 `1`；该跨对象不变量由 M3 validator 强制。

冻结 M3-created ReviewItem 文本动作到 CLI 动作的映射：`choose evidence -> choose_evidence`、`retain -> retain_unresolved`、`reject -> reject_association`、`revalidate -> 新 prepare 后 confirm/choose_evidence`、`archive -> archive_stale`、`provide evidence -> 使用更新或扩展后的显式本地 source 重新 prepare`。ReviewItem 只允许使用冻结 issue-codes 文档已列出的动作子集，不新增同义自由文本。`confirm mapping`、`archive decision`、`rebind answer` 属于本阶段排除的身份迁移能力；M3 遇到对应身份歧义只写 run-level finding，不创建带有这些不可执行动作的新 canonical ReviewItem，也不关闭父 snapshot 中已存在的该类 item。run-level finding 的 `blocking_level` 同样必须保持冻结值：特别是 `QB-OPTION-IDENTITY-AMBIGUOUS` 仍为 `review_required`，但 M3 因缺乏授权迁移能力而对该运行执行 fail-closed。

### 15.2 M3 跨对象 validator

Schema 和文件哈希通过后，M3 validator 必须按下表验证完整对象图；任一不变量失败都使 snapshot 不可读、不可发布、不可恢复为 canonical：

| 对象关系 | 必须满足的不变量 |
|---|---|
| current -> commit | current 的 snapshot ID/相对路径与 commit 所在 snapshot 完全一致；current 记录的 commit 原始哈希匹配实际文件 |
| commit -> transaction | commit 的 transaction ID/plan hash 与 immutable plan 完全一致；被 current 引用时 state 经恢复后必须为 `complete`；plan 的 after snapshot、staged hashes、operation artifact refs/hashes 与实际 commit、snapshot、operation artifacts、current 完全一致；commit 必须能由 plan 字段和 plan 原始哈希唯一重建 |
| operation artifact -> transaction | prepare 的 proposal `prepared_from_pointer` 必须等于 prepare plan.before；reverify 的 `expected_before_pointer` 必须等于 reverify plan.before；confirmation 的锁内 `expected_current_pointer` 必须等于 confirmation plan.before；plan 对各 operation artifact 的相对路径和原始 SHA-256 必须逐一匹配，artifact 集合必须恰好满足 plan.operation 的互斥白名单，plan.operation 还必须与对应章节允许的父子 canonical 语义差分一致，禁止 operation relabel、混入额外 artifact 或把同一 artifact 重放到不同 before state |
| proposal -> confirmation base | proposal `direct` 基线要求 confirmation actual current hash/`ABSENT` 精确等于 prepared_from；`prepare_result` 基线要求 actual current 恰为记录的 complete prepare transaction/result snapshot，且该 snapshot 的 parent-pointer raw hash（或首代 ABSENT 对象）精确对应 prepared_from；confirmation transaction plan.before 必须等于这个 actual current hash/`ABSENT`，任何中间 generation 都使 proposal stale |
| commit -> snapshot files | commit 中 parent-pointer/interchange/provenance 的原始哈希逐一匹配，且三个文件都位于同一 snapshot 目录 |
| confirmation -> lineage | confirmation.`expected_current_pointer` 必须等于 confirmation transaction plan.before；在该 child snapshot 中，live before 时二者又必须等于 `SHA256(parent-pointer.json raw bytes)`，首次 before 时二者都为 `ABSENT` 且 parent-pointer 是精确 ABSENT 对象；confirmation 的预分配 result transaction/snapshot ID 必须等于 plan、commit 和最终 current |
| current -> parent | `parent-pointer.json` 原始哈希等于 current 的 parent pointer hash；首代 parent 是精确 ABSENT 对象且 generation=1；后继 parent 是前一 live `current.json` 的 byte-for-byte 完整对象，snapshot ID/hash/generation 均匹配，当前 generation=parent+1 |
| recursive parent | 非首代 parent pointer 指向的父 snapshot、父 commit、父 transaction plan/state 和父 snapshot files 必须仍存在，并递归通过本表全部验证；parent chain 不得循环、跳代或跨 dataset |
| snapshot identity | current、commit、provenance、transaction 的 snapshot ID 完全相同；所有相对路径规范化后仍位于显式 workspace |
| dataset/manifest | interchange manifest dataset ID 等于 workspace project dataset ID；source ID 唯一、排序和第 14 节合并规则通过；后继同 source 的 parent path_history 必须是当前 registry path_history 的精确前缀并完整吸收全部 intervening suffix；所有 Candidate 和 Decision evidence 的 source ID 均存在 |
| Candidate/Option | Candidate/Option ID 全局唯一；Option ownership、当前 revision、M2 基线结构和仅 status 可变规则通过 |
| Decision | Decision ID 唯一；candidate/revision 和 Option ownership 合法；每个 Candidate 最多一个当前 valid answer decision；每个 current/history Decision 在 provenance 恰有一条链路 |
| child -> parent Candidate | 父 Candidate/Option 必须在子 snapshot 中保留相同 ID 和全部结构字段；只允许 Candidate status 按 `candidate -> candidate/validated`、`validated -> validated/candidate` 变化；`unsupported/ambiguous/archived` 不得由 M3 改回可用状态 |
| child -> parent Decision | 父 Decision 必须全部保留；candidate binding、revision、decision type、value 和 evidence 永不可改；状态只允许 `valid -> valid/needs_revalidation/archived`、`needs_revalidation -> needs_revalidation/archived`、`archived -> archived`；禁止删除、反向恢复或复用旧 ID 表达新决定 |
| child -> parent ReviewItem | 父 ReviewItem 必须全部保留；issue code、Candidate、blocking level 和 allowed actions 永不可改；状态只允许 `open -> open/resolved/archived`、`resolved -> resolved/archived`、`archived -> archived`；复发问题必须新建 ID 并在 provenance 记录 supersession |
| review supersession | `supersedes_review_id` 只存在于新复发 item 的 provenance 链路；复发 item 必须恰好指向父链中同 stable issue key 最近的 closed item，非复发 item 必须无该字段；不得指向 open/不同 key/自身/后代，不得形成环；消失后单纯 resolve 不构成 supersession |
| child -> parent provenance | 父 provenance 的所有 Decision/Review/confirmation/reverify 链路必须逐项原样保留；子 snapshot 只允许追加新对象或 audit，不得替换、删除或重绑历史引用 |
| provenance -> run artifacts | proposal、confirmation、reverify 和 manifest 引用均为 workspace 内相对路径，实际原始哈希匹配，且被引用 ID 在对应 artifact 中恰好存在 |
| stale proposal -> canonical graph | stale entry 的 Candidate/revision、Decision ID、ReviewItem ID、`review_issue_key`、question source/manifest 和 confirmation base 必须与 direct baseline 或 complete prepare result 中的唯一对象图逐项一致；Decision 恰为 `needs_revalidation`、ReviewItem 恰为同 Candidate 的 open `QB-DECISION-STALE`，provenance 恰有同 key 的 stale audit 同时绑定二者；历史 archived/closed/mismatched 对象不得生成 stale entry |
| confirmation -> proposal | confirmation 的 proposal run/hash 匹配；每个 action 引用该 proposal 中恰好一个合法 entry；action/conclusion 必须满足第 11.1 节精确矩阵，特别是 `archive_stale` 只能引用 stale 且其他 action 都不能引用 stale；不得引用其他 run 的 Candidate、Option、Decision、ReviewItem 或 evidence |
| archive_stale -> child | child 中恰好把 stale entry 绑定的 Decision `needs_revalidation -> archived`、绑定的 ReviewItem `open -> resolved`，Candidate 保持 `candidate`，不创建 Decision、不提升 validated、不关闭其他 issue；confirmation/provenance/proposal/ReviewItem/Decision 的正反引用和 stable issue key 必须唯一闭合 |
| evidence partition | 普通 confirm 的 `considered = selected` 且 rejected 为空；冲突选择的 considered 集合必须恰好等于 selected 与 rejected 的不相交并集；selected 非空且全部解析到 Decision 的同一 Option ID；rejected 不得出现在 Decision evidence |
| adjudication applicability | prepare/reverify 必须从同一完整当前 evidence 集合和原 confirmation/provenance 分区重算第 9.1 节谓词；true 时 proposal `adjudicated` entry、reverify audit、Decision/Candidate 和 closed ReviewItem 结果一致且无 recurrence，false 时两种入口按同一 stale/conflict/failed 矩阵处理 |
| Decision -> confirmation | 新 valid Decision 的 Candidate/revision/value 与 confirmation selected evidence 完全一致；Decision evidence 的历史实例键与 selected evidence 一一对应，不得增加或遗漏 |
| ReviewItem | provenance 引用的 review ID 必须存在于 interchange review queue；issue code、Candidate、open/resolved/archived 状态与 proposal/confirmation/reverify 结果一致 |
| reverify required set | reverify operation 的 required Decision set 必须由父 snapshot 按第 13 节重新计算并精确相等；按题目源核验不得遗漏任何当前 `valid/needs_revalidation` 答案决定或任何 `validated` Candidate 的唯一决定 |
| reverify source set | 对 required set 中每个 Decision 分别验证：original source ID 集合精确等于 provenance 绑定的原 proposal manifest 答案 source 集合；该 Decision current set 必须是 original 与本次显式 additions 的集合并集；运行级读取集合必须等于各 Decision current set 的并集 |
| reverify evidence | 每个历史实例键、当前语义键、selected/rejected 裁决和 Decision status 必须满足第 13 节矩阵；audit 恰好覆盖 required Decision set，不得遗漏、多加或引用不存在的 evidence |
| validated gate | interchange 中每个 `validated` Candidate 重新执行第 12 节全部九项门禁；没有 confirmation/provenance 完整链路时不得依赖文件哈希维持 `validated` |
| standalone confirmation | 每个 confirmation，包括 reject/retain 等不创建 Decision/Review 变化的动作，都必须在子 provenance 中有且仅有一条 audit，并绑定本次 child snapshot/transaction；不得成为孤立 run artifact |
| run -> canonical claim | run 不被 canonical 图反向引用；transaction-backed 成功 terminal 的 transaction ID/state hash/result snapshot/current/commit claim 必须逐项匹配已验证 terminal complete 图；direct prepare success 必须无 transaction 且满足第 15 节唯一条件；aborted/unknown/corrupt transaction 不得被 run 声称成功 |
| reverse references | provenance 中每个 Decision/Review/confirmation/reverify 引用都有对应对象；同一 snapshot 不允许悬空、重复或指向另一 dataset/snapshot 的反向引用 |

父 pointer 的完整对象永久保存在子 snapshot 的 `parent-pointer.json`，不能只保存一个无法回读的 hash。历史 run artifact 一经被 provenance 引用不得覆盖；若缺失或哈希改变，当前 snapshot 失败关闭。

验收测试必须逐项构造“对象内容被篡改后重新按合法 JSON 编码并更新所有直接文件哈希”的负例，证明仅重算 hash 不能绕过上述语义关系。至少覆盖 snapshot ID 交叉、错误 transaction、stale confirmation 重放、父 snapshot 缺失/改写/循环、历史 Decision/Review/provenance 删除或反向状态迁移、悬空 Decision/Review、跨 proposal evidence、selected/rejected 重叠或未覆盖、Decision evidence 漏项、按题目源遗漏 reverify Decision、逐 Decision source 缩减和伪造 validated。

### 15.3 持久 artifact 隐私白名单

除 `interchange.json` 中按冻结 Candidate Schema 必须保存的题干外，M3 新增持久 artifact 只允许保存：schema/contract/state format version、UUID、revision/generation/sequence、相对路径、文件哈希、locator、规范化题号、单字符答案词法、Option ID、issue code/冻结 blocking level/状态/动作、计数、阶段、UTC 审计时间及 artifact/transaction 引用。

所有 run、proposal、confirmation、reverify、provenance、transaction、pointer、commit 和 review snapshot 都禁止保存：绝对 input/workspace 根、原始 CLI 参数数组、环境变量、用户名、完整答案行、题干、选项正文、任意源片段、未净化异常或 traceback。manifest 只能保存其现有 Schema 要求的相对路径元数据。测试必须对所有 M3 artifact 做递归字符串扫描，而不只检查 stdout/stderr/log。

## 16. 实现隔离与拟议 scope manifest

本节冻结未来实施可以触及的范围，但本轮不创建实现计划、不写代码。

### 16.1 必须保持字节不变

- Milestone 0 六个顶层 Schema；
- `references/question-types.md`、`identity-contract.md`、`state-contract.md`、`issue-codes.md`；
- `scripts/qbcore/validation.py`；
- 已验收的全部 M1/M2 runtime、顶层 Schema、测试、fixture、规格和计划；本规格不提供例外，若实施证明必须修改，先停止并重新走规格批准；
- M1/M2 fixture 的既有字节和历史期望。

### 16.2 允许新增

- 独立 sibling runtime package：`skills/curate-question-bank/scripts/qbanswer/`；
- 独立入口：`skills/curate-question-bank/scripts/qbanswer_cli.py`；
- 独立 Schema 子目录中的第 15.1 节八个精确文件：`skills/curate-question-bank/schemas/m3/`；
- M3 tests：`tests/test_m3_*.py`、`tests/m3_helpers.py`；
- M3 synthetic fixtures：`tests/fixtures/m3-answer-association/`；
- M3 scope guard：保护 M0/M1/M2 权威哈希，限制网络、进程、动态执行、输入写入、任意路径和越界格式支持。
- 人工批准后单独新增实施计划：`docs/MILESTONE-3-LOCAL-ANSWER-EVIDENCE-PLAN.md`。

采用 sibling package 是为了复用 `qbcore` 的只读路径、registry、parser 和基础 validator，同时不让新增答案能力伪装成 M2 已验收能力，也不通过放宽旧 scope guard 来制造通过。

### 16.3 允许修改的既有文件

- 实现任务完成并通过对应审查后，才可按计划更新 `skills/curate-question-bank/SKILL.md` 和 `skills/curate-question-bank/agents/openai.yaml`；
- 只有最终 M3 验收后，才可更新 `START-HERE.md`、`NEW-THREAD-PROMPT.md` 和 `docs/SIDE-CONVERSATION-HANDOFF.md`；
- 本规格人工批准后冻结 SHA-256；任何后续修改都必须撤销批准并重新审查；
- 除第 16.2 和本节列出的路径外，实施 scope 是封闭白名单，不得新增或修改其他项目文件。

在 M3 尚未验收时，任何能力描述都不得宣称答案关联、确认、重新核验或 `validated` 提升已经可用。

## 17. TDD 与验收矩阵

未来实现必须先写失败测试，再写最小实现，并依次经过规格审查、质量审查和根代理完整测试。至少覆盖：

1. 明确选择一个题目源和一个/多个答案源，角色 manifest 正确且不写回 registry；
2. 未选择、重复选择、跨 dataset、stale registry、路径逃逸、链接逃逸、哈希不符全部失败关闭；
3. 严格答案语法、UTF-8 BOM、LF/CRLF/CR、空行和非法非空行；
4. 同一规范答案在不同空白/换行下 fingerprint 一致，题号或标签变化时不同；
5. M2 重放与 Candidate/Option 快照逐字段一致性核对；
6. 唯一题号+唯一答案只产生 `confirmable` 提案，不自动创建 Decision 或提升；
7. 缺失答案、未知题号、重复题号、非法 label、同义重复、异义冲突的精确 issue 映射；无 Candidate source-level proposal 的精确 null/empty payload；issue-key 包含 question source、固定 bytes/hash、open 去重、resolved 后复发新建和严格 supersession 链验证；
8. 多答案源排序确定，与文件系统枚举、locale、时区无关；
9. 普通确认、显式批量确认、冲突选证据、confirmable 拒绝、low-confidence 拒绝/保留，以及 new-stale/prepare_result 与 already-stale/direct 两种 proposal-bound `archive_stale`；低置信项不能人工改绑 Candidate/Option；
10. 确认只能引用 proposal 中的 evidence，不能直接提交 Option ID/label/自由文本答案；
11. prepare/reverify operation artifact 与 transaction plan.before 精确绑定；proposal 的 direct/prepare_result base lineage 一直绑定到 confirmation 与 confirmation plan.before；proposal、manifest、Candidate、decision、review、base lineage 或 expected pointer 变化后陈旧确认和跨 transaction 重放被拒绝；
12. 既有 Decision 转换矩阵、父子 snapshot 差分和历史不可改写；每个 Candidate 最多一个当前有效答案决定；未选冲突证据不进入 Decision evidence；
13. 完整 `validated` 门禁，包括 open review、unsupported/ambiguous、current revision 和 evidence existence；
14. promotion 产生完整 immutable snapshot，M2 Candidate 基线字节不变，除状态外的 Candidate/Option 语义不变；
15. 按 Decision/按题目源计算完整 required Decision set；reverify expected_before 与 plan.before 绑定；每个 Decision 的原答案 source 集合不可缩减；运行级集合并集、新增 source、删减请求和新增冲突；registry 在两个 M3 snapshot 之间的全部 intervening path history 被完整合并；
16. 历史实例键、当前语义键、同义重复、行移动、revision 变化、已裁决冲突与新增冲突、reverify audit 映射；同一未变化 rejected evidence 经 prepare/reverify 均保持旧裁决，selected/rejected/considered 或 lineage 变化时两入口均进入同一 stale/conflict/failed 结果；
17. stale 自动降级、通过新 prepare 的 confirmable/conflict entry 人工重新确认恢复，以及 proposal-bound `archive_stale` 的唯一归档转换；禁止自动恢复 `valid`，禁止 stale entry 携带或创建答案；
18. workspace exclusive lock、两个并发写者、读写竞争、非协作外部 pointer 改写和无法取得锁时失败关闭；
19. transaction plan/state、snapshot/commit/current pointer 每个发布点和每个 state replace 前后故障注入；精确覆盖 operation artifact 后 plan 前、staged 后 commit 前、commit/publishing 后 pointer 前、pointer 后 complete 前、complete 后 run terminal 前五个 crash point；任何 M3 reader 只能看到完整前态或完整后态；
20. `ABSENT` before pointer、state 缺失/损坏重建、重跑、commit 不存在与 commit 已损坏的严格区分、确定性原子补写 commit、仅 pre-commit+before-unchanged 才允许 `aborted`、publishing-without-valid-commit 失败、未知 pointer/hash、孤立 snapshot 保留和 read-back；canonical complete 后只确定性补写 run terminal，不重做业务判断或 snapshot；
21. 八个 M3 Schema、additionalProperties、oneOf、Candidate-bound/no-Candidate/adjudicated/stale payload、stale 的 Decision/ReviewItem/stable-issue binding、nullable total ordering、run-level finding shape、run immutable/mutable 字段和 terminal claim、冻结 blocking level、pointer generation、两组冻结 JSON bytes/hash test vector；
22. 第 15.2 节每项跨对象不变量，包括 operation-artifact/base-pointer、proposal confirmation lineage、archive_stale child 精确差分、path-history suffix、ReviewItem blocking-level immutability 和 supersession；以及篡改后重算全部直接文件哈希仍被拒绝的负例；
23. 输入树全程只读，workspace 外零写入；所有新增持久 artifact、日志、stdout/stderr 通过递归隐私扫描；
24. 无 socket、HTTP、模型、connector、MCP、依赖安装、动态执行或进程启动；
25. M0/M1/M2 权威哈希和全部历史测试继续通过，既有 qbcore、顶层 Schema、测试和 fixture 字节不变；
26. copied skill package 在另一临时目录运行仍只写显式 workspace；
27. 不产生 quiz UI、评分、答案生成、人工无证据答案或非单选适配器；
28. 两次完整测试结果一致通过后，才可进入 M3 验收判断。
29. `archive_stale` 攻击矩阵至少覆盖：new-stale/prepare_result 成功、already-stale/direct 成功、错误 Decision ID、其他 Candidate/revision、非 `QB-DECISION-STALE` ReviewItem、closed ReviewItem、archived Decision、intervening snapshot replay、archive 动作引用五种非 stale conclusion、其他动作引用 stale、成功 child 出现额外业务差分或新答案、proposal Schema/正文/validator 分支计数与 required fields 不一致；除前两项外全部失败关闭。

## 18. 可用性边界

M3 验收后，用户将能够：

- 把明确选择的本地严格答案文件与已物化单选题建立可核对提案；
- 查看缺失、冲突和无法唯一关联的问题；
- 确认现有证据或在冲突中选择现有证据；
- 让满足全部门禁的题目进入 `validated`；
- 在本地文件变化后重新核验，并看到失效题目安全退回待确认状态。

M3 验收后，用户仍不能：

- 让系统生成或推测答案；
- 把没有本地证据的人工选择直接写成正确答案；
- 刷题、正式判分或查看学习统计；
- 处理任意格式答案文件、多选/判断题或自动扫描整套资料；
- 在题目源变化后自动迁移 Candidate/Option 身份。

## 19. 规格批准门

本文件通过规格审查只表示设计内部一致、边界明确、可进入人工评审，不表示 Milestone 3 已验收，也不授权编码。

人工批准后仍需单独起草并审查实施计划，冻结本规格 SHA-256、实施 scope manifest、任务顺序和每项 TDD/审查门。未获批准前必须停止。
