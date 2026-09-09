# Milestone 3 两个 blocker 修订清单

本轮只修改 M3 规格和必要的审查/交接文档，没有实现 M3 功能。

## 基线与当前版本

- 基线：`6a076b8090a57d5a36fb4916f4c2f4e49e90687ce639e0636b0895c752e0375d`
- 当前：`84c4fbe8a02346df4b05761ca8345199c88ffb033c4fd9e7d9a42e7b643a4374`

## P1 闭环

- prepare 与 reverify 共用 `adjudication_still_applies` 机械谓词。
- 原 selected evidence 必须仍支持当前 Decision；当前异义 evidence 只能是原样 rejected keys。
- 谓词成立时使用 audit-only `adjudicated` proposal entry，不重开 conflict、不 recurrence、不再次确认、不降级。
- 新增、改变、消失或 lineage 失效时，两条入口进入同一 stale/conflict/failed 语义。

## P2 闭环

- canonical truth 只依赖 current、transaction、commit 和 immutable operation artifacts。
- run.json 不进入 canonical hash graph，只单向声明已存在事实。
- snapshot operation 的成功 run terminal 只能在 transaction complete 后发布。
- run 采用 atomic replace/read-back；缺失 terminal 可确定性补写，矛盾 terminal 不静默覆盖。
- A–E 五个 crash point 均冻结唯一结果。

## 未继续修改

新独立审查发现 `archive_stale` 缺少合法 proposal payload。该问题不在本轮唯一 P1/P2 修订授权内，因此按要求停止，没有继续自由设计。
