# Stable Reasoning Effort Advisor v1.1（题库项目提醒方案）

状态：项目执行规则  
适用范围：所有题库项目里程碑及其规划、实施、验收和交接  

## 1. 目的

在工作难度实际改变时，用简短提醒帮助用户判断是否需要调整思考强度，同时优先保持主线程稳定；不把技术细节、模型名称或长计划塞进普通进度汇报。

## 2. 基本规则

1. 不自动更换模型或思考强度，始终由用户决定；建议动作只使用 `keep_current`、`switch_at_phase_boundary` 或 `switch_now`。
2. 当前设置足够、`actual_effort=unknown` 或 cache 影响未知时，默认 `keep_current`；未知 cache 风险不得被包装成确定收益。
3. `preferred_main_thread_switch_budget=1` 是每个任务的软预算，不是安全上限；建议 `2+` 次主线程切换时，必须给出与重大异常、需求冲突、安全边界或最终签署直接相关的 `exceptional justification`。
4. 只建议当前 runtime/model 实际支持的等级；不假设 `xhigh`、`max`、`ultra` 普遍存在，也不虚构 `actual_effort`、数字化质量收益、成本节省或 cache 命中情况。
5. 只有在阶段切换、出现重大异常，或准备变更模型/强度前才提醒；同一任务的日常进度不重复提醒，也不因短暂机械子步骤建议降级。
6. 提醒只说明“现在难在哪里”和建议动作，不把建议说成必须操作，也不作为备份、审批或验收门槛。
7. 该规则只存在于项目文档和全局执行规则，不写入 `C:\Users\lenovo\.codex\memories`。

## 3. 何时提醒

| 当前工作 | 稳定动作 | 原因 |
|---|---|---|
| 规格冻结、身份规则、原子发布、恢复设计或复杂审查 | 当前设置足够则 `keep_current`；不足且下一阶段持续复杂时 `switch_at_phase_boundary` | 错误代价高，但目标等级改变不等于必须切换 |
| 已冻结方案内的普通实现、测试修复 | `keep_current` | 范围清楚，可由测试持续约束 |
| 重复的 fixture、文档整理、格式核对 | 通常 `keep_current` | 短暂机械子步骤不足以抵消主线程切换和 cache 不确定性 |
| 出现未解释的失败、合同冲突或安全边界问题 | 必要时 `switch_now` | 属于重大异常；若这是第 `2+` 次建议，必须同时给出 `exceptional justification` |

这些是提醒条件，不是自动切换条件。

## 4. 固定提醒格式

只在需要时使用以下四行；除非运行时明确确认，始终把 `actual_effort` 写为 `unknown`，并保持现有设置：

```text
思考强度建议：<actual/unknown> → <recommended>
稳定动作：<keep_current | switch_at_phase_boundary | switch_now>
原因：<一句通俗原因；第 2+ 次切换建议必须包含 exceptional justification>
任务继续执行，不因该建议暂停。
```

普通进度仍使用实施计划规定的四行状态卡；不要在每次更新中重复本提醒。

## 5. 不在本方案内的事项

- 不规定具体模型名称；
- 不保证任何 runtime/model 支持特定高等级；
- 不估算未经遥测验证的数字化质量、成本或 cache 收益；
- 不改变任何已冻结 Milestone 的技术范围；
- 不创建持久化用户偏好、自动化或长期 memories；
- 不作为任务是否通过验收的条件。
