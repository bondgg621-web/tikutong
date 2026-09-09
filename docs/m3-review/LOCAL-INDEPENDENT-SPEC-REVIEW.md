# Milestone 3 本机独立规格审查

审查日期：2026-08-29

审查对象：`docs/MILESTONE-3-LOCAL-ANSWER-EVIDENCE-SPEC.md`

冻结指纹：

- 640 行
- 71,339 bytes
- UTF-8，无 BOM
- 仅 LF，文件末尾恰好一个 LF
- SHA-256 `6a076b8090a57d5a36fb4916f4c2f4e49e90687ce639e0636b0895c752e0375d`

## 结论

独立只读审查发现两个阻断问题，因此本轮规格审查未通过。

```text
M3_SPEC_REVIEW = FAIL
M3_ACCEPTANCE = NOT_GRANTED
IMPLEMENTATION_PLAN_AUTHORIZED = NO
IMPLEMENTATION_AUTHORIZED = NO
```

## 阻断问题

### P1：已人工裁决的原冲突在 prepare 与 reverify 中结果不一致

规格要求不同 Option 的证据形成冲突，人工选择证据后把对应问题关闭；同一稳定问题以后复发时又应创建新问题。另一方面，重新核验规定原先已明确拒绝的证据若原样存在，旧人工裁决仍然有效。

因此，同一组完全未变化的冲突证据在“再次 prepare”与“reverify”入口下没有唯一结果：重新打开会阻断原本已经 validated 的题目，不重新打开又会违反当前复发规则。实现会因入口不同产生不同 canonical 状态。

涉及规格位置：第 9、10、12、13 节，尤其第 173、232、240、302、341、361、370 行附近。

### P2：run.json 的发布终态和崩溃恢复没有闭合

规格要求运行记录保存 proposal 哈希、终态和输入输出引用，但事务的精确 artifact 白名单与恢复协议没有包含运行记录本身。

如果 transaction/current 已完整成功，而进程在写 run 终态前崩溃，规格没有规定应如何确定性收口；如果提前写成功终态，而事务随后 aborted，又会留下虚假的成功记录。实现无法同时保证运行记录真实、可审计和可恢复。

涉及规格位置：第 10、14、15 节，尤其第 192、421、438、440、492 行附近。

## 已覆盖且未发现其他 blocker 的范围

- 本地证据、人工确认、不生成或推测答案、不联网、无 UI/判分/学习统计边界。
- 与已冻结 M0/M1/M2 Schema 和 issue code 的兼容性。
- prepare/reverify 的 before pointer 与 transaction 绑定。
- proposal 基线到 confirmation/transaction 的 anti-replay。
- 无 Candidate 的 source-level payload 和带 question source 的稳定 issue key。
- 身份不一致时 canonical 不变、脱敏 finding、operation failed。
- 完整 path history suffix、terminal transaction、operation relabel 防护。
- ReviewItem recurrence/resolve/supersession 基础约束、nullable 总序、run finding 隐私和冻结 blocking level。
- 两组固定 JSON/hash 向量独立重算正确。

## 独立性声明

审查者未读取网页候选审查结论，未联网，未修改文件，也未把 M0/M1/M2 回归测试表述为 M3 功能测试。
