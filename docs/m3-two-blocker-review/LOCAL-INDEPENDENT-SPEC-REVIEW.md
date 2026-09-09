# Milestone 3 本机独立规格审查

审查日期：2026-08-29

审查对象：`docs/MILESTONE-3-LOCAL-ANSWER-EVIDENCE-SPEC.md`

冻结指纹：

- 680 行
- 82,953 bytes
- UTF-8，无 BOM
- 仅 LF，文件末尾恰好一个 LF
- SHA-256 `84c4fbe8a02346df4b05761ca8345199c88ffb033c4fd9e7d9a42e7b643a4374`

## 结论

独立只读审查确认本轮 P1/P2 的核心闭环成立，但发现一个新的独立阻断问题，因此规格审查仍未通过。

```text
M3_SPEC_REVIEW = FAIL
M3_ACCEPTANCE = NOT_GRANTED
IMPLEMENTATION_PLAN_AUTHORIZED = NO
IMPLEMENTATION_AUTHORIZED = NO
```

## 阻断问题

### archive_stale 没有合法 proposal entry 可绑定

规格把 `archive_stale` 定义为正式 confirmation 动作，并要求每个 confirmation action 引用一个合法 proposal entry。当前 proposal 的冻结分支只有 `confirmable`、`conflict`、`missing`、`low_confidence` 和 `adjudicated`，没有 `stale` payload。

因此，实现无法同时满足 proposal、confirmation 和 lineage validator：若把 `archive_stale` 绑定到其他结论会语义错误，若私自新增 stale payload 又超出当前规格。实际使用时，用户无法按唯一、可审计的路径归档 stale Decision。

涉及规格位置：第 10、11、15.1、15.2 节，尤其第 203、265–266、275、291、531、541、569 行附近。

## 本轮 P1/P2 复核

- P1 通过：prepare 与 reverify 使用同一个机械谓词；原样 rejected evidence 不重开 conflict，不创建 recurrence，不使 validated Candidate 降级；真正新增或改变的异义证据进入相同 stale/conflict/failed 结果。
- P2 通过：canonical truth 不依赖 run；成功 run terminal 不能早于 transaction complete；aborted/unknown/corrupt 不得留下成功 run；A–E 五个 crash point 均有唯一恢复结果。

其余复核范围包括身份失败关闭、anti-replay、完整 path history、operation artifact 精确白名单、ReviewItem recurrence/supersession、隐私、nullable 总序、固定向量和 M0/M1/M2 兼容性，未发现其他 blocker。

## 独立性声明

审查者未读取下载目录、网页材料或上一轮结论，未联网，未修改文件，也未把 M0/M1/M2 回归测试表述为 M3 功能测试。
