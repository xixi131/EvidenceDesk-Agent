# 查看作业条件表达式日志

了解如何访问和解析 GitHub Actions 中作业级 if 条件的表达式评估日志。

当评估作业的 `if` 条件时，GitHub Actions 会记录表达式评估日志，帮助你理解结果。 这对于调试作业为何被跳过或为何在预期应跳过时仍然运行非常有用。

## 访问表达式日志

1. 导航到工作流运行摘要。
2. 点击该作业。
3. 单击 **gear icon**。
4. 选择 **“下载日志存档**”。
5. 提取 ZIP 文件并打开 `JOB-NAME/system.txt` 文件。

## 了解日志输出

系统日志显示表达式评估过程：

```text
Evaluating: (success() && ((github.repository == 'octo-org/octo-repo-prod')))
Expanded: (true && (('my-username/octo-repo-prod' == 'octo-org/octo-repo-prod')))
Result: false
```

| 行            | Description                  |
| ------------ | ---------------------------- |
| **评价**       | 工作流文件中的原始 `if` 表达式。          |
| **Expanded** | 用上下文值替换的表达式。 这会显示在运行时使用的确切值。 |
| **结果**       | 最终计算结果（`true` 或 `false`）。    |

在此示例中，展开的行显示为 `github.repository``'my-username/octo-repo-prod'` （不是 `'octo-org/octo-repo-prod'`），这导致条件的计算结果为 `false`。

> 注意：
> 表达式日志仅适用于作业级 `if` 条件。 对于步骤级条件，可以启用调试日志，以在作业日志中查看表达式评估。 有关详细信息，请参阅“[启用调试日志记录](https://docs.github.com/zh/actions/how-tos/monitor-workflows/enable-debug-logging)”。
