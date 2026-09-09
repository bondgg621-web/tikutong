# Milestone 1 — Skill 运行骨架、输入发现与可恢复工作区设计

状态：已冻结  
日期：2026-08-13  
前置门禁：Milestone 0 已通过 30 项测试

## 1. 目标

Milestone 1 建立 `curate-question-bank` 的可携带 Skill 运行骨架，以及在任何题目解析、答案关联或增量执行发生之前所需的本地基础设施：

- 调用方显式提供 `input_root` 与 `workspace_root`；
- `input_root` 始终只读，所有状态和输出只写入 `workspace_root`；
- 目录扫描不会重新读入工作区或越过授权范围；
- preflight 以可审计 capability matrix 描述实际可用能力，不安装依赖、不夸大支持；
- discovery inventory 确定性记录文件发现结果，但不猜测题目或文档角色；
- SourceIdentity registry 为后续重命名、版本和增量处理提供持久身份基础；
- checkpoint 与恢复机制能够从结构化状态继续，不依赖模型上下文记忆；
- Skill 包复制到仓库外后仍能定位自身文档、Schema 和运行时代码。

## 2. 本阶段范围

Milestone 1 只覆盖：

1. 创建 `SKILL.md` 和 `agents/openai.yaml`；
2. 定义并实现 preflight/capability matrix；
3. 定义并实现双根目录校验和单一写入边界；
4. 定义确定性的只读目录扫描与 discovery inventory；
5. 定义并实现 SourceIdentity registry 的持久化和本阶段允许的身份演化；
6. 定义工作区目录、run metadata、checkpoint、日志和恢复结果；
7. 为上述行为建立 Contract、单元、集成和可携带性测试。

Milestone 1 明确不覆盖：

- 题目、答案、解析或文档 parser；
- 文件内容角色判定和跨文件答案关联；
- candidate、review item 或 decision 的生成；
- 基于旧状态跳过处理的增量执行器；
- 题目身份迁移、重复题一对一匹配或决定继承；
- PDF、DOCX、XLSX、PPTX、图片、OCR 或 ZIP 内容适配器；
- GUI、HTML quiz、Electron、MCP server、Plugin 或远程能力；
- SQLite、数据库迁移、桌面端项目锁或多进程单写入者；
- 修改 Milestone 0 已冻结的题型、Candidate、Option 和 Decision 契约。

## 3. Skill 与组件边界

### 3.1 Skill 入口

`SKILL.md` 只描述可验证的当前能力、调用输入、工作区输出、隐私边界、失败语义和阶段限制。它不得宣称已经能够识别题目、关联答案或处理未实现格式。

`agents/openai.yaml` 仅提供 Agent 发现和调用所需的最小 metadata，不复制业务规则，不保存用户目录，不引入宿主专属永久假设。

### 3.2 运行组件

Milestone 1 的运行代码保持 stdlib-only，并按职责分为：

- `paths`：规范化路径、包含关系和写入目标校验；
- `capabilities`：本机能力探测和 capability matrix；
- `discovery`：只读枚举、工作区剪枝、普通文件哈希和稳定排序；
- `registry`：持久 SourceIdentity、路径历史和 revision；
- `workspace`：工作区布局、原子 JSON 写入、checkpoint 和恢复；
- `cli`：显式接收双根目录并串联 preflight 与发现流程。

现有 `validation.py` 继续只负责 Milestone 0 Contract 校验，不扩展为扫描器或状态管理器。

## 4. 路径术语与隔离契约

### 4.1 `input_root`

`input_root` 是用户明确授权扫描的既有资料目录：

- 必须由调用方显式提供；
- 必须存在并且是目录；
- 只允许读取目录项、文件元数据和计算内容哈希所需的文件字节；
- 不得在其中创建临时文件、缓存、锁、日志、manifest 或任何输出；
- 不得根据资料中的文字、链接或指令扩大读取范围。

### 4.2 `workspace_root`

`workspace_root` 是本项目状态和派生产物的唯一写入根目录：

- 必须由调用方显式提供，不得默认为当前目录、输入目录旁、用户主目录、系统临时目录或仓库目录；
- 可以尚不存在，但目标位置必须能够在不越过写入边界的前提下创建；
- 必须与 `input_root` 不同；
- 可以位于 `input_root` 内；
- `input_root` 不得位于 `workspace_root` 内。

### 4.3 规范化与包含关系

相等、包含和排除判断基于规范化后的真实绝对路径，而不是用户输入字符串。规范化至少消除相对片段、大小写表现差异和可解析的符号链接、junction 或其他重解析跳转。

| 关系 | 结果 |
|---|---|
| 两者相同 | 拒绝，且不得留下运行产物 |
| `workspace_root` 位于 `input_root` 内 | 允许，但扫描必须完整排除工作区子树 |
| 两者互不包含 | 允许 |
| `input_root` 位于 `workspace_root` 内 | 拒绝，且不得留下运行产物 |

目录扫描默认不跟随目录符号链接、junction 或其他目录重解析点。后续如需开放，必须另行设计授权和环检测。

### 4.4 单一写入边界

所有写入必须同时满足：

1. 规范化目标路径位于 `workspace_root` 内；
2. 既有父级不得通过链接或重解析点跳出工作区；
3. 临时文件、备份文件、checkpoint 和日志也不得越界；
4. 无效路径关系应在扫描和工作区创建前失败。

## 5. Preflight 与 capability matrix

preflight 每次运行都生成本次能力快照，只报告实际探测结果。至少记录：

- Skill/runtime 版本和 Python 版本；
- `input_root` 是否存在、可读且为目录；
- `workspace_root` 的边界关系和可用状态；
- 内置文本发现能力：普通文件枚举、SHA-256、UTF-8/BOM TXT 和基础 Markdown 的阶段地位；
- 未实现格式的 `unsupported` 状态；
- 网络策略为未授权，未发生联网；
- capability matrix 的生成时间和稳定格式版本。

能力状态只使用明确枚举，例如 `available`、`unavailable`、`unsupported`、`not_authorized`。缺少能力不得触发自动安装，也不得把宿主临时工具写成 Skill 永久保证。

## 6. Discovery inventory

### 6.1 允许行为

- 从已校验的 `input_root` 开始枚举；
- 在进入目录前按规范化真实路径剪枝 `workspace_root`；
- 不跟随目录链接、junction 或其他目录重解析点；
- 对普通文件记录相对路径、内容 SHA-256、字节数和基于后缀的支持状态；
- 对结果使用与文件系统枚举顺序无关的稳定排序；
- 对不可读文件使用现有 `QB-SOURCE-READ-FAILED`；
- 空输入成功产生空 inventory。

### 6.2 禁止行为

- 读取 `input_root` 之外的相邻目录；
- 扫描或哈希工作区产物；
- 根据正文触发命令、URL、connector、MCP 或远程请求；
- 识别题目、答案、解析、题型或重复题；
- 仅凭文件名或后缀猜测 `question_document`、`answer_document`、`unrelated` 或 `duplicate_version`；
- 根据旧 registry 跳过扫描或哈希。

### 6.3 与 manifest 的关系

Discovery inventory 不是 Milestone 0 manifest：

- inventory 可以为空；
- inventory item 不包含语义化 `kind`；
- inventory 不分配 Candidate/Option/Decision 身份；
- manifest 要求至少一个 source 且具有语义化 `kind`，只能在后续取得角色证据后构造；
- 本阶段不得放宽 manifest Schema 或用 `unrelated` 伪填未知文件。

## 7. SourceIdentity registry

### 7.1 职责

Registry 为每个已发现普通文件保留：

- 持久 `source_id`；
- `current_relative_path`；
- `path_history`；
- `current_content_hash`；
- 正整数 `revision`；
- 本次出现状态和必要的身份审核记录。

路径与内容哈希仍是身份证据，不是身份键。Registry 必须写在 `workspace_root` 内，并与 Milestone 0 `SourceIdentity` 契约一致。

### 7.2 本阶段允许的身份演化

- 首次发现：分配新 UUID，`revision = 1`；
- 同一路径、同一哈希：保留 ID 和 revision；
- 同一路径、哈希改变：保留 ID，revision 加一；
- 原路径消失且新路径具有唯一相同哈希：视为纯重命名，保留 ID 和 revision，更新路径历史；
- 同一哈希出现多个潜在重命名目标：登记 `QB-IDENTITY-AMBIGUOUS`，不得自动继承身份；
- 路径和内容同时改变：不得自动认定为同一 source；
- 相同内容的多个并存文件：各自保留独立 source ID，不合并。

这里实现的是文件级 SourceIdentity registry 更新，不是“跳过未变化文件”的增量执行器，也不涉及题目级身份迁移。

### 7.3 安全发布

Registry 更新先在内存中计算，只有 discovery 完成且状态验证通过后才原子替换工作区中的 registry 文件。失败不得留下半写 JSON；旧的完整 registry 必须可恢复。

## 8. 工作区布局、状态和日志

冻结逻辑布局如下；精确文件名在实施计划中保持一致：

```text
workspace_root/
├─ project.json
├─ registry/
│  └─ sources.json
├─ runs/
│  └─ <run_id>/
│     ├─ preflight.json
│     ├─ discovery.json
│     ├─ workspace-run.json
│     └─ issues.json
├─ checkpoints/
│  └─ <checkpoint_id>/
├─ logs/
└─ outputs/
```

- `project.json` 保存工作区格式版本和 dataset ID，不保存源文件正文；
- 每次运行使用 UUID `run_id`；
- `workspace-run.json` 记录本阶段的 `preflight`、`discovery`、`registry`、`checkpoint`、`complete` 阶段，及其状态、输入/工作区路径指纹、能力快照引用和已完成产物；
- Milestone 0 的 `run-state.schema.json` 要求 `manifest_source_id`，面向后续 candidate/review/decision 流程。本阶段不生成 manifest，因此不复用或修改该 Schema，而为 `workspace-run.json` 定义独立契约；
- 日志只写运行事件、路径相对标识、问题代码和通俗摘要，不复制题目正文；
- `outputs/` 本阶段只作为冻结归属目录，不生成题库导出；
- manifest、未来 candidates、review queue 和 decisions 只能写在工作区，但本阶段不生成。

## 9. Checkpoint 与恢复

### 9.1 Checkpoint

Checkpoint 是工作区控制状态的一致快照，至少包含：

- `project.json`；
- 当前完整 registry；
- 最近完整 run metadata；
- checkpoint ID、创建原因、时间和每个文件的 SHA-256 清单。

Checkpoint 不复制 `input_root` 文件，不复制题目正文，不包含未完成的临时文件。

Milestone 1 在发布 registry 新版本前建立 checkpoint。Checkpoint 只有在所有文件写完、哈希清单完成并通过读回校验后才标记 complete。

### 9.2 恢复

- 启动时发现未完成 run 或临时文件，应以最后完整 checkpoint 和原子发布文件为权威；
- 未引用的临时文件可以登记为可清理候选，但本阶段不自动删除用户原有文件；
- 当前 registry 损坏且存在完整 checkpoint 时，可显式恢复到最新完整 checkpoint；
- 没有完整 checkpoint 时必须失败并报告，不凭模型上下文或日志猜测状态；
- 恢复动作写入新的 run 记录和日志；
- 恢复只影响 `workspace_root`，绝不修改 `input_root`。

本阶段不实现桌面端多实例锁、PID 抢占、SQLite 事务或 schema migration。

## 10. 运行流程

一次 Milestone 1 运行按固定顺序执行：

1. 解析显式参数，不创建任何目录；
2. 规范化并验证双根目录关系；
3. 初始化或验证工作区结构；
4. 生成 preflight/capability matrix；
5. 只读扫描并生成 discovery inventory；
6. 读取旧 registry，在内存中计算 SourceIdentity 更新和 issues；
7. 验证所有拟发布状态；
8. 若将更新既有 registry，先创建并读回验证 checkpoint；
9. 原子发布 registry 和本次 run artifacts；
10. 将 run 标记为 complete。

任一步失败时，已发布的上一个完整 registry 仍为权威；失败状态和技术诊断只写入工作区。若失败发生在工作区安全创建之前，则不得留下运行产物。

## 11. 错误处理

以下情况在扫描前失败：

- 缺少任一根目录；
- `input_root` 不存在或不是目录；
- 两个根目录相同；
- `input_root` 位于 `workspace_root` 内；
- 不能确定安全的规范化路径；
- 工作区目标不能满足单一写入边界。

其他规则：

- 单个文件不可读：登记 `QB-SOURCE-READ-FAILED`，不得伪造哈希；
- 格式未支持：登记 `QB-SOURCE-UNSUPPORTED`，但仍保留发现证据；
- 身份匹配不唯一：登记 `QB-IDENTITY-AMBIGUOUS`，不得继承旧 ID；
- JSON 临时写入、读回或替换失败：保留上一个完整版本，run 失败；
- checkpoint 不完整或哈希不符：不得用于恢复；
- 错误摘要不得包含源文件正文、token、密码或未经授权的绝对路径。

## 12. 测试与验收条件

Milestone 1 必须证明：

1. Skill skeleton 和 Agent metadata 能被静态校验；
2. Skill 包复制到仓库外后仍能定位包内 Schema、references 和脚本；
3. preflight 不联网、不安装依赖，并诚实报告支持和未授权能力；
4. 未显式提供 `workspace_root` 时拒绝运行；
5. 两根相同或 input 位于 workspace 内时拒绝，且无运行产物；
6. workspace 位于 input 内时允许，但工作区及指向它的链接不进入 inventory；
7. 扫描不跟随目录链接/junction 越出授权范围；
8. 扫描前后输入 fixture 的字节和目录结构不变；
9. 枚举顺序变化不会改变 inventory 顺序和内容；
10. 空输入产生空 inventory，不伪造 manifest；
11. 同路径同哈希、同路径改内容、唯一重命名、非唯一哈希和并存重复文件分别遵守冻结的 SourceIdentity 规则；
12. registry 更新具有原子性，故障注入不会破坏上一个完整版本；
13. checkpoint 只包含工作区控制状态，哈希清单通过读回验证；
14. 损坏 registry 可以从最新完整 checkpoint 显式恢复，不完整 checkpoint 被拒绝；
15. 所有 manifest、registry、checkpoint、日志、临时文件和输出均只能位于 workspace；
16. Milestone 0 的 30 项测试继续通过，既有 Contract 不被放宽；
17. 代码库中不存在题目 parser、答案关联、Candidate 生成或增量跳过执行器；
18. 完整 Milestone 1 测试可由单一、记录在项目中的命令运行。

## 13. 卡住、恢复与跨线程交接规则

Milestone 1 的实施计划必须拆为可独立验证的原子任务。任一任务卡住时：

1. 停在当前 Task/Step，不开始后续任务；
2. 保存准确命令、退出码、失败摘要和已修改文件列表；
3. 区分测试预期失败、实现缺陷、环境缺失、权限问题和规格冲突；
4. 只恢复当前任务造成的未完成变更，不回滚已通过任务，不删除用户既有文件；
5. 规格冲突必须回到设计门禁，不能靠放宽测试解决；
6. 环境缺失不得自动安装依赖，报告缺项并等待授权；
7. 新线程从计划文件、完成的 Task/Step、验证命令及失败证据继续，不重读整个历史对话。

交接摘要只需包含：

- 项目根目录；
- 权威规格与计划路径；
- 已完成的最后一个 Task/Step；
- 最近一次完整测试命令和结果；
- 当前失败命令与摘要；
- 本任务修改文件；
- 下一原子动作；
- 未验证风险。

## 14. 设计决策摘要

- 恢复原线程定义的完整基础设施型 Milestone 1，而非仅做扫描器；
- 复用旧工作台计划中的 SourceFile 发现、只读输入、工作区归属、checkpoint 和恢复原则；
- 不移植 Electron、SQLite、UI、适配器或桌面端项目锁；
- 显式双根目录，没有隐式 workspace 默认值；
- 允许 workspace 位于 input 内，以规范化真实路径强制排除；
- 不跟随目录链接和 junction；
- discovery inventory 与语义化 manifest 分离；
- 本阶段实现文件级 SourceIdentity registry，但不实现增量跳过执行器或题目身份迁移；
- 所有持久状态使用结构化文件，确保临时线程结束后仍可恢复实施。
