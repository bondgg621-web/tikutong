# Milestone 2 — Markdown/TXT 单选题解析与首次候选物化规格

状态：已冻结（用户于 2026-08-14 确认；实施尚未开始）  
日期：2026-08-14  
前置门禁：Milestone 1 已完成并通过 90 项测试

## 1. 目标

Milestone 2 建立第一个可审计的题目内容适配器：从用户显式选择、已进入 Milestone 1 SourceIdentity registry 的 UTF-8 Markdown/TXT 文件中，解析严格标记的 `single_choice` 题干和选项，并在满足全部发布门禁时首次物化符合 Milestone 0 Candidate/Option 契约的候选文档。

本阶段只回答三个问题：

1. 哪些行构成一条结构明确的单选题；
2. 如何确定性地产生 locator、规范化文本和三类 fingerprint；
3. 如何在不破坏持久身份的前提下完成该 source 的第一次 Candidate/Option ID 分配和原子发布。

Milestone 2 不解析答案，不把答案标签绑定到 option ID，不产生有效 Decision，也不把 Candidate 提升为 `validated`。

## 2. 已比较方案与设计决定

### 2.1 方案 A：严格标记、逐行状态机（采用）

只接受形如 `1. [single_choice] Stem` 的题头，以及其后的 `- A. Option` 选项。解析器为 stdlib-only 的逐行有限状态机，先生成无身份的内部表示，再单独计算 fingerprint、分配 UUID 并发布。

优点：语法可冻结、误识别率低、locators 可追溯、测试矩阵有限、无需新增依赖。代价：不能直接兼容任意教师讲义或非规范题库，需要后续 adapter 扩展。

### 2.2 方案 B：无标记启发式识别（拒绝）

根据编号、问号、选项数量和附近文本猜测题目。该方案更宽容，但会把正文编号、目录、答案说明或示例误判为题目；其置信度和人工复核机制超出本阶段边界。

### 2.3 方案 C：Markdown AST 或第三方 parser（拒绝）

使用 Markdown AST 能保留更多结构，但 TXT 仍需另一套路径，并会增加依赖、版本能力和格式差异。本阶段语法足够窄，不值得扩大运行时表面积。

### 2.4 冻结决定

采用方案 A。解析、身份物化、持久化是三个明确边界；任何一层不得把指纹、题号、路径或 locator 当作持久身份键。

## 3. 本阶段范围

### 3.1 包含

- `.md`、`.markdown` 和 `.txt`，后缀大小写不敏感；
- UTF-8 和带 UTF-8 BOM 的文本，严格解码；
- 调用方用 `source_id` 显式声明本次解析的题目源；
- 精确的 `[single_choice]` 题型标记；
- 单行题干与单行选项；
- 每题 2–26 个、标签为连续 `A`–`Z` 的选项；
- 行级 locator、规范化和 SHA-256 fingerprint；
- 首次 Candidate/Option UUID 分配；
- 同一 source 本批次内的完全相同内容分组，但不合并身份；
- parse run、parse report、parse issues 和候选文档的工作区持久化；
- CLI、Skill 能力声明、安全、故障注入、可携带性和回归测试。

### 3.2 明确不包含

- 答案、解析、评分、知识点、难度、标签或元数据抽取；
- `multiple_choice`、`true_false`、判断题、填空题、简答题；
- 未标记题目、中文序号、Roman numeral、表格题、HTML、LaTeX block 或多行选项；
- PDF、DOCX、XLSX、PPTX、图片、OCR、ZIP 或远程文档 adapter；
- 文件名或正文启发式角色分类；
- 多 source 批量解析、跨文件答案关联或跨文件重复检测；
- Candidate/Option 重扫匹配、revision 增长、迁移、删除、归档或 Decision 继承；
- HTML quiz、GUI、Electron、SQLite、MCP、网络调用、模型调用或依赖安装；
- 修改 Milestone 0 的六个冻结 Schema 或既有身份语义。

## 4. 权威契约和边界

Milestone 2 必须继续服从：

- `references/question-types.md`：`single_choice` 最终答案必须是一项持久 option ID，但本阶段不创建答案；
- `references/identity-contract.md`：UUID 是身份，fingerprint 只是证据；相同内容 Candidate 仍保持不同 ID；
- `references/state-contract.md`：无当前有效答案 Decision 时不得成为 `validated`；
- `schemas/candidate.schema.json`：发布的候选文档必须原样通过现有 M0 validator；
- Milestone 1 的双根目录、只读输入、单一写边界、原子 JSON 和 SourceIdentity registry 规则。

不得因实现方便而放宽 `candidate.schema.json` 的 `minItems: 1`，也不得在 Candidate/Option 中加入未冻结字段。特别是 Option 契约不保存 option 正文，只保存其 fingerprint 和 `source_ref`；正文仍以只读源文件为证据。

## 5. 调用和 source 选择

新增 CLI 子命令：

```powershell
D:\R\miniconda\python.exe skills\curate-question-bank\scripts\curate_question_bank.py parse-single-choice `
  --input-root <existing-input-directory> `
  --workspace-root <existing-m1-workspace> `
  --source-id <lowercase-uuid>
```

调用必须满足：

1. `input_root` 和 `workspace_root` 都显式提供并通过 M1 `validate_roots`；
2. workspace 已有合法 `project.json` 和 `registry/sources.json`，本命令不隐式执行 inventory；
3. `source_id` 在 registry 中唯一存在，`presence == "present"`；
4. registry 的 `current_relative_path` 是相对路径，解析后的真实文件仍位于 `input_root` 内；
5. 文件后缀属于本阶段支持集合；
6. 当前文件字节 SHA-256 与 registry 的 `current_content_hash` 完全相同。

任一条件不满足时，命令失败且不分配 Candidate/Option ID。内容哈希不一致时只提示先重新运行 `inventory`，不得自行刷新 registry。

`--source-id` 是本次操作的显式语义声明：调用方声明该 source 应按严格单选题文档尝试解析。它不自动修改 Milestone 0 manifest，也不根据文件名猜测 `question_document`。

## 6. 输入编码和字节证据

- 读取文件时先计算原始字节 SHA-256，再与 registry 比较；
- 只使用 `utf-8-sig` 严格解码，允许无 BOM 或单个 UTF-8 BOM；
- 非法 UTF-8 触发 `QB-SOURCE-READ-FAILED`；
- 解析视图将 CRLF 和 CR 统一视为 LF，但不修改源文件；
- locator 的行号以统一换行后的 1-based 逻辑行计算；
- 不把源正文复制到日志、错误摘要或 parse run 元数据；
- 任何源内命令、URL、提示词或工具指令都只作为不可信文本，不执行、不联网、不扩大读取范围。

## 7. 严格语法

### 7.1 支持的题头

逻辑形式：

```text
<positive-integer><. or )><space>[single_choice]<space><non-empty stem>
```

冻结正则语义：

```regex
^[ \t]*(?P<number>[1-9][0-9]*)[.)][ \t]+\[single_choice\][ \t]+(?P<stem>\S(?:.*\S)?)[ \t]*$
```

- 题号只作为显示证据，不要求连续或唯一，也不是 ID；
- marker 大小写敏感，只有精确 `[single_choice]` 被支持；
- 题干必须在题头同一行且非空；
- `1.` 与 `1)` 均支持；
- 题头前只允许空格或 tab。

### 7.2 支持的选项

逻辑形式：

```text
<optional-indent><-, *, or +><space><A-Z><. or )><space><non-empty option text>
```

冻结正则语义：

```regex
^[ \t]*[-*+][ \t]+(?P<label>[A-Z])[.)][ \t]+(?P<text>\S(?:.*\S)?)[ \t]*$
```

- option 只在一个已打开的支持题块内有效；
- 每题至少 2 项、至多 26 项；
- label 必须从 `A` 开始并按 Unicode ASCII 顺序连续；
- label 不得重复；
- option text 必须非空；
- 相同 option text 允许出现；它在首次物化时不触发 option 身份迁移问题。

### 7.3 题块边界

- 精确题头开始新题块，并关闭前一题块；
- 下一条任何“编号 + 点或右括号”的 question-like 行都关闭当前题块；
- EOF 关闭当前题块；
- 题头与第一项之间、选项之间允许空行；
- 当前题块内出现非空、既非 option 也非下一题头的行时，该题块为结构不明确；
- 文件级 Markdown 标题、普通段落和空行在题块之外被忽略；
- 题块之外的 option-like 行、缺 marker 的 question-like 行和未知 marker 行均产生结构或题型 issue；
- 不识别围栏代码块中的题目；进入三反引号或三波浪号 fence 后，直到匹配 fence 关闭前，所有行均作为普通数据忽略。未关闭 fence 产生结构 issue。

### 7.4 混合题型和答案文本

- `[multiple_choice]`、`[true_false]` 或其他 bracket marker 触发 `QB-TYPE-UNSUPPORTED`；
- 本阶段对含不支持题型的 source 不发布任何候选；
- `Answer:`、`答案：` 等文本没有特殊语义；位于题块外时忽略，位于题块内且不符合 option 时导致该题块结构不明确；
- parser 不读取 answer 文件，不扫描相邻文件，也不把任何标签解释为正确答案。

## 8. 解析内部表示

纯 parser 只返回内存对象，不生成 UUID、不访问 workspace：

```text
ParsedSingleChoice
├─ display_number: string
├─ stem: string
├─ header_line: positive integer
└─ options[]
   ├─ source_label: A-Z
   ├─ text: string
   └─ line: positive integer
```

另返回按 `(line, code, summary)` 稳定排序的 `ParseFinding[]`。内部表示不是持久 artifact，不承诺跨版本兼容。

parser 的确定性要求：同一 Unicode 文本和同一 parser contract version 必须产生完全相同的内部表示与 finding 顺序，不依赖文件系统枚举、locale、时区或随机数。

## 9. 文本保留、规范化和 fingerprint

### 9.1 展示文本

- `stem` 去掉语法前缀以及两端空格/tab，保留内部字符；
- option 正文不进入 Candidate schema，只用于 fingerprint 并通过 locator 回指源证据；
- parser 不做拼写修正、全半角替换、大小写折叠、标点改写或 HTML 解码。

### 9.2 fingerprint 规范化函数

`normalize_text(value)` 固定为：

1. Unicode NFC；
2. 使用 Python `str.split()` 语义把一个或多个 Unicode whitespace 折叠为单个 U+0020；
3. 去除首尾 whitespace；
4. 以 UTF-8 编码，不写 BOM。

### 9.3 hash 公式

所有摘要均为小写 64 位十六进制 SHA-256：

- `stem_fingerprint = SHA256(UTF8(normalize_text(stem)))`；
- 每项 `normalized_text_fingerprint = SHA256(UTF8(normalize_text(option_text)))`；
- `option_set_fingerprint`：将所有规范化 option text 按 Unicode code point 排序，保留重复项，以 `ensure_ascii=False`、`sort_keys=True`、`separators=(",", ":")` 编码为 canonical JSON array 后计算 SHA-256；
- `content_revision_fingerprint`：对下列对象按相同 canonical JSON 参数编码后计算 SHA-256，options 保留源顺序：

```json
{"options":["normalized A","normalized B"],"question_type":"single_choice","stem":"normalized stem"}
```

实现和测试必须共享明确的规范说明，但测试不得直接调用被测实现生成 expected 值。

## 10. locator 和排序

- Candidate locator：`line:<header-line>`；
- Option source locator：`line:<option-line>`；
- locator 是 source revision 内的证据位置，不是身份键；
- Candidate 按 `header_line` 升序物化；
- Option 按源中出现顺序物化，`current_position` 从 1 开始；
- `source_label` 保存解析到的 A–Z；
- 首次物化时 `previous_labels = []`。

## 11. 首次 Candidate/Option 物化

仅当整个 source 没有任何 parse issue 且至少解析到一题时，才允许物化。

每个 Candidate：

- `candidate_id`：由注入的 UUID factory 按 source 顺序分配；
- `candidate_revision = 1`；
- `source_id`：调用方显式选择的 SourceIdentity；
- `locator`：题头 locator；
- `question_type = "single_choice"`；
- `status = "candidate"`；
- `stem`：保留后的题干；
- 三类 fingerprints：按第 9 节；
- `options`：按源顺序；
- `duplicate_group`：按第 12 节。

每个 Option：

- `option_id`：在其 Candidate ID 之后由同一注入 UUID factory 顺序分配；
- `candidate_id`：所属 Candidate；
- `option_revision = 1`；
- `normalized_text_fingerprint`：按第 9 节；
- `current_position`：1-based；
- `source_label`：源标签；
- `source_ref.source_id`：同一 source；
- `source_ref.locator`：option 行 locator；
- `previous_labels = []`。

物化后的整个文档必须由现有 `validate_document("candidate", document)` 校验，并额外验证本地 ID 唯一、Option ownership 和 source 引用一致性。

## 12. 重复内容处理

本阶段只检测同一次、同一 source 解析结果中的完全相同 `content_revision_fingerprint`：

- 计数为 1：`duplicate_group = null`；
- 计数大于 1：组内每题保留不同 Candidate/Option UUID，`duplicate_group = "content-sha256:" + content_revision_fingerprint`；
- 同组 Candidate 顺序不变，不合并、不删除、不选择“主记录”；
- 产生 `QB-DUPLICATE-CANDIDATE` 的 informational parse issue 将与“零 issue 才发布”的规则冲突，因此本阶段不把完全重复本身记为阻断 parse issue；duplicate_group 已是显式证据；
- 相似题、跨 source 重复和未来重扫中的重复组迁移全部推迟。

## 13. 持久状态和工作区布局

新增布局：

```text
workspace_root/
├─ candidates/
│  └─ sources/
│     └─ <source_id>.json
└─ runs/
   └─ <run_id>/
      ├─ parse-run.json
      ├─ parse-report.json
      └─ parse-issues.json
```

候选文档保持 Milestone 0 格式：

```json
{"schema_version":"1.0","candidates":[...]}
```

`parse-report.json` 至少记录：

- schema version、run ID 和 parser contract version；
- source ID、source revision、relative path、content hash；
- discovered question-like block count、accepted candidate count、rejected block count；
- status；
- candidate artifact 相对路径和 SHA-256，或均为 null；
- findings 数量。

`parse-issues.json` 只允许冻结代码的相关子集：

- `QB-SOURCE-UNSUPPORTED`；
- `QB-SOURCE-READ-FAILED`；
- `QB-TYPE-UNSUPPORTED`；
- `QB-STRUCTURE-AMBIGUOUS`；
- `QB-IDENTITY-AMBIGUOUS`；
- `QB-SECURITY-INSTRUCTION-DATA`（只在安全策略明确命中时使用，不因普通 URL 或命令文本自动触发）。

每项 issue 记录 issue UUID、code、blocking level、open status、source ID、locator、无正文的摘要和冻结 allowed user actions。

`parse-run.json` 使用独立 M2 schema，不修改 M1 `workspace-run.schema.json`。它记录 `source_resolution`、`parse`、`candidate_materialization`、`publication`、`complete` 阶段以及 `complete`、`needs_review`、`failed` 状态。

## 14. 首次物化门禁和重复调用

持久候选目标是：

```text
candidates/sources/<source_id>.json
```

规则：

1. 目标不存在且 source 无 parse issue、候选数大于 0：允许首次物化；
2. 目标已存在：不得重新解析后覆盖、追加、重排或重新分配 UUID；
3. 已存在目标通过 schema/read-back/hash 校验：命令失败关闭，并明确报告该 source 已物化，后续需要 CandidateIdentity migration milestone；
4. 已存在目标损坏：命令失败，不覆盖；
5. source content 或 revision 与已有 parse report 不同：仍不得自动迁移；
6. `--force`、`--overwrite` 和隐式删除均不在本阶段提供。

这样保证重跑不会悄悄制造第二套身份。重扫匹配与 revision 演化必须在后续里程碑依据冻结的 evidence order 设计。

## 15. 发布原子性和崩溃恢复

所有写入仍经 M1 `Workspace` 和 write-boundary 检查。发布顺序：

1. 在内存中完成 parse、finding、Candidate 和所有合同校验；
2. 在目标父目录创建随机命名 staging 文件，写入、fsync、JSON read-back、合同校验并计算 hash；
3. 原子写入 `parse-report.json`、`parse-issues.json` 和状态为 `publication` 的 `parse-run.json`；
4. 仅当候选目标不存在时，以不覆盖语义发布候选文档；Windows 上不得使用会静默覆盖既有目标的调用；
5. read-back 候选文档并核对 hash；
6. 原子更新 `parse-run.json` 为 `complete`。

故障规则：

- 候选发布前失败：不留下候选；失败 run 可保留诊断元数据；
- 候选发布后、run complete 前失败：候选文档是持久事实，后续恢复只允许在 source snapshot、candidate path 和 candidate hash 全部吻合时把该 run 补记 complete；不得重新分配 ID；
- 不完整 staging 文件永远不是权威状态；只登记为清理候选，不自动删除用户既有文件；
- 任意失败不得修改 `input_root`、SourceIdentity registry 或已有候选文档；
- 实现必须对实际 Windows 文件系统验证“目标不存在时原子发布”的能力；若无法证明，不得用普通覆盖替代，M2 实施应暂停并记录环境限制。

## 16. finding、状态和退出码

### 16.1 parse issue 映射

| 条件 | 代码 | 级别 | 发布候选 |
|---|---|---|---|
| 后缀不支持 | `QB-SOURCE-UNSUPPORTED` | blocking | 否 |
| 文件无法读取或 UTF-8 解码失败 | `QB-SOURCE-READ-FAILED` | blocking | 否 |
| 未支持的题型 marker | `QB-TYPE-UNSUPPORTED` | blocking | 否 |
| 题干为空、选项少于 2、label 不连续/重复、题块内出现未知行、游离 option、未闭合 fence | `QB-STRUCTURE-AMBIGUOUS` | review_required | 否 |
| 候选目标已存在、需要重扫身份迁移 | `QB-IDENTITY-AMBIGUOUS` | blocking | 否 |

源文件正文不能进入 summary；summary 只描述规则和 locator。

### 16.2 run 状态

- `complete`：候选文档已首次发布并通过 read-back；
- `needs_review`：source 被成功读取，但有 parse issue 或没有可接受题目；无候选文档；
- `failed`：前置状态、读写、合同或原子发布失败。

### 16.3 CLI 退出码

- `0`：`complete`；
- `3`：`needs_review`；
- `2`：参数、前置状态或运行失败；
- stdout 只输出稳定 JSON 摘要；诊断写 stderr，不输出题目正文。

## 17. 模块边界

建议新增：

- `qbcore/single_choice_parser.py`：严格语法和内部表示；
- `qbcore/text_normalization.py`：NFC、whitespace 和 canonical JSON hash；
- `qbcore/candidate_materializer.py`：首次 UUID 分配、fingerprint 和 duplicate group；
- `qbcore/parse_contracts.py`：M2 workspace schema validation；
- `qbcore/parse_service.py`：source resolution、门禁、事务编排和恢复；
- 在 `workspace.py` 增加受限的 M2 写入方法；
- 在 `cli.py` 仅增加参数路由，不放业务规则。

现有 `validation.py` 继续作为 M0 Candidate 合同校验器，不改题型或身份语义。

## 18. 安全与隐私

- 输入始终只读，测试对解析前后 byte hash 和树结构做比较；
- 所有路径来自经验证的 roots、registry relative path 和 UUID 文件名；
- 拒绝 absolute、`..`、ADS、链接/junction 逃逸或 source path 替换；
- 不执行、导入、eval 或 shell 解释正文；
- 不联网、不安装依赖、不调用模型；
- stdout、stderr、event log、parse run 和 issue summary 不复制题干或选项正文；
- 候选文档按 M0 契约保存题干，但只位于用户显式指定的 workspace；
- UUID factory、clock 和文件发布 primitive 可注入以支持确定性和故障测试。

## 19. 测试与验收

Milestone 2 必须证明：

1. M1 的 90 项测试仍通过；
2. 三种支持后缀和 UTF-8/BOM/CRLF 行为明确；
3. golden chapter 1 精确产生 7 个 Candidate，选项数为 `4,4,4,4,4,3,3`；
4. Candidate/Option UUID 顺序可由注入 factory 精确断言；
5. locators、positions、labels 和 ownership 全部正确；
6. 三类 fingerprint 与独立 expected vectors 相符，option-set 保留重复计数且与顺序无关；
7. 题 6/7 获得相同 duplicate group，但保留不同 ID；
8. 重复 option text 被保留，不在首次物化时错误迁移或合并；
9. 空题干、空 option、少于 2 项、重复/跳号 label、游离 option、未知行、未闭合 fence 均失败关闭；
10. 混合不支持题型不会部分发布 Candidate；
11. 题块外普通 Markdown/文本不会被误解析；
12. answer-like 文本不会生成 Decision、resolved option 或 validated Candidate；
13. source 必须显式按 ID 选择，文件名不会触发角色猜测；
14. source 缺失、registry stale、hash 不一致、链接逃逸和不支持后缀均在 UUID 分配前失败；
15. 零题和任何 issue 都不创建 M0 candidate artifact；
16. 首次成功发布后再次调用不覆盖、不追加、不重新分配 ID；
17. 候选目标损坏时不自动修复或覆盖；
18. 每个 JSON 在发布前和发布后均经过 schema/read-back/hash 校验；
19. 故障注入覆盖 staging write、fsync/read-back、候选发布和 run 完成更新；
20. 候选已发布但 run 未完成的精确恢复不重新生成 ID；
21. 输入 fixture 的字节和目录结构在全部成功/失败路径前后不变；
22. 所有持久写入都位于 workspace，所有临时写入也受边界保护；
23. Skill 复制到仓库外仍能定位 M0/M1/M2 schema、references 和运行代码；
24. 静态 scope guard 证明没有答案关联、远程调用、依赖安装、数据库或不支持格式 parser；
25. 完整测试可由单一、记录在计划中的命令运行。

## 20. 推迟到后续里程碑

下一里程碑至少需要另行设计：

- 已物化 source 的 Candidate/Option 一对一重扫迁移；
- source revision 变化后的 candidate revision 和 stale decision；
- 多 source 角色/manifest 构造；
- answer source 解析和证据关联；
- 跨 source duplicate relation；
- 宽松 adapter、人工映射和格式扩展。

## 21. 执行纪律和思考强度提醒

- 本文已经用户确认并冻结；开始 M2 实现仍需用户另行明确授权；
- 实施必须使用测试先行，每个原子任务都记录 RED、GREEN 和完整回归；
- 不初始化 Git、不提交、不创建 worktree，除非用户另行授权；
- 不读取真实题库，只使用仓库中的合成 fixture；
- 思考强度的提醒、用户确认与非自动切换规则服从
  `docs/THINKING-INTENSITY-REMINDER-POLICY.md`；本阶段不另行定义，也不写入长期 memories。

## 22. 未验证区域

本草案没有宣称以下事项已经成立：

- Windows 上“目标不存在时不覆盖”的原子发布 primitive 尚未实测；
- junction/symlink 在 parse source resolution 路径上的组合行为尚未实施阶段验证；
- M2 schema、parser、CLI 和测试尚未创建；
- 真实世界非规范 Markdown/TXT 的适配率未知，且不属于本阶段验收目标；
- M1 之后的完整测试基线需在计划 Task 1 重新记录。
