# 用你自己的题库试试题库通

题库通最有价值的测试，是整理一份你已经在使用的题库。请先完成项目提供的标准测试，再使用你有权处理的真实资料。

## Round A｜标准测试

1. Clone 或下载 TikuTong。
2. 让你的 Codex 或 compatible Agent 阅读 [`README.md`](../README.md) 和 [`skills/curate-question-bank/SKILL.md`](../skills/curate-question-bank/SKILL.md)。
3. 将 [`examples/user-trial/tikutong-standard-trial.md`](../examples/user-trial/tikutong-standard-trial.md) 作为输入。
4. 要求 Agent 输出 Canonical QuestionBank JSON 和 Standard Question Bank CSV。

测试前不要查看 [`EXPECTED_RESULTS.md`](../examples/user-trial/EXPECTED_RESULTS.md)。输出完成后，再用该文件核对题目总数、题型和答案，尤其确认 Q4、Q8、Q11 仍然没有答案。

这一步检查安装、Skill routing、结构提取、QuestionBank 和 CSV 输出链是否正常。它不是知识答题测试。

## Round B｜自己的真实题库

选择一份你有权使用的资料。它可以是 PDF、DOCX、image、TXT、Markdown，或其他你的 Agent environment 能读取的题目来源。第一次建议使用 20–100 题，便于人工抽查。

把下面的提示词复制给 Agent，并在最后追加你的本地文件路径：

```text
使用题库通 TikuTong 整理这个本地题库。

请尽量忠实保留已有题目、题干、选项、答案和解析。

识别单选题、多选题和判断题。

已有答案就保留，没有答案就保持为空，
不要根据知识或常识自行补答案。

不要因为排版异常而静默删除可能的题目。

如果内容无法确定，
请保留来源位置并记录不确定性。

最终输出 Canonical QuestionBank JSON 和 Standard CSV。
```

PDF、DOCX 和图片由你自己的 Agent 环境读取；TikuTong 核心不内置 PDF/DOCX reader 或 OCR。

## Round C｜检查结果

至少检查以下项目：

* 原始题数与输出题数
* 明显漏题与额外题目
* 题干错误与选项错误
* 题型识别错误
* 已有答案是否被改变
* 缺失答案是否被创造
* source locator 是否有帮助

如果原始资料中的某题没有答案，输出也应保持为空。不要把 Agent 猜出的答案当作整理结果。

## Round D｜Preview & Practice

使用你刚生成的 Standard CSV，在本地浏览器打开 [`tools/preview/index.html`](../tools/preview/index.html)，然后选择该 CSV。第一次也可以使用项目提供的 [`expected-standard-question-bank.csv`](../examples/user-trial/expected-standard-question-bank.csv) 熟悉界面。

至少实际检查：

1. 一道有答案的单选题
2. 一道有答案的多选题
3. 一道有答案的判断题
4. 一道没有参考答案的题

记录以下结果：

```text
QUESTION_DISPLAY_CORRECT=
OPTION_ORDER_CORRECT=
QUESTION_TYPE_CORRECT=
ANSWER_DISPLAY_CORRECT=
EXPLANATION_DISPLAY_CORRECT=
BLANK_ANSWER_NOT_GRADED=
CSV_LOADED_WITHOUT_MANUAL_EDITING=
```

没有参考答案的题仍然可以选择，但 Preview 不应判对或判错，不应加入错题，也不应降低正确率。确认 TikuTong 生成的 CSV 无需手工修改即可导入。

## User experience｜使用体验

完成后，请记录：

* 是否无需作者帮助就能完成
* README 是否足够
* 是否需要手写 Python
* 是否需要手动修改 JSON
* 是否需要理解 `qbassist`、`qbbank`、`QuestionItem`、`Candidate` 等内部知识
* FIRST_BLOCKER：第一次不知道下一步该做什么的位置
* 最困惑的步骤、最有用的部分，以及最希望优先改进的内容

可以使用仓库的 “Own-bank trial feedback” Issue template 提交反馈，不需要提交你的完整题库。

## Privacy｜隐私

不要上传私人完整题库，包括学校内部资料、受版权保护题库、个人数据和未公开课程材料。

如果需要提供复现材料，只提交你有权公开的最小样例，并删除与问题无关的敏感内容。
