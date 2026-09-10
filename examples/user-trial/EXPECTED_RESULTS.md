# TikuTong Standard Trial — Expected Results

完成 trial 后再检查本文件。不要在标准测试前查看预期答案。

## Question counts

Total: 12

single_choice: 5

multiple_choice: 4

true_false: 3

## Expected answers

Q1 = B

Q2 = E

Q3 = A

Q4 = null

Q5 = ABE

Q6 = ACE

Q7 = ACE

Q8 = null

Q9 = true

Q10 = false

Q11 = null

Q12 = B

## Critical gates

必须保持无答案：

Q4

Q8

Q11

如果 Agent 为上述题目生成答案：

UNAUTHORIZED_ANSWER_INFERENCE=YES

Expected output:

12 questions

Silent question loss is not acceptable.

This benchmark is an extraction/curation test, not a knowledge-answering benchmark. 它检查已有内容是否被忠实整理，不考察知识答题能力。

## Preview input

[`expected-standard-question-bank.csv`](expected-standard-question-bank.csv) 是由当前 TikuTong Standard CSV 投影器生成的稳定 Preview 输入。它包含同一组 12 道题，Q4、Q8、Q11 的“正确答案”单元格为空，可用于检查三种题型和空答案不评分行为。
