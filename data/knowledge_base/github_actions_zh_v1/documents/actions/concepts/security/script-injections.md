# 脚本注入

了解与脚本注入和 GitHub Actions 工作流相关的安全风险。

## 了解脚本注入的风险

创建工作流、[自定义操作](/zh/actions/concepts/workflows-and-actions/custom-actions)和[复合操作](/zh/actions/tutorials/create-actions/create-a-composite-action)操作时，应始终考虑代码是否可能执行来自攻击者的不受信任的输入。 当攻击者将恶意命令和脚本添加到上下文时可能发生这种情况。 当您的工作流程运行时，这些字符串可能会被解释为代码，然后在运行器上执行。

攻击者可以将其自己的恶意内容添加到 [`github` 上下文](/zh/actions/reference/workflows-and-actions/contexts#github-context)中，这应被视为潜在的不受信任的输入。 这些上下文通常以 `body`、`default_branch`、`email`、`head_ref`、`label`、`message`、`name`、`page_name`、`ref` 和 `title` 结尾。 例如：`github.event.issue.title` 或 `github.event.pull_request.body`。

您应该确保这些值不会直接流入工作流程、操作、API 调用，或任何可能被解释为可执行代码的其它地方。 通过采用与处理其他任何特权应用程序代码时相同的防御性编程方式，你可以帮助提升对 GitHub Actions 的使用安全性。 若要了解攻击者可能采取的某些步骤，请参阅“[安全使用指南](/zh/actions/reference/security/secure-use)”。

此外，还有其他不太明显的潜在不信任输入来源，如分支名称和电子邮件地址，这些输入在允许的内容方面可能相当灵活。 例如，`zzz";echo${IFS}"hello";#` 将是一个有效的分支名称，并将成为目标存储库可能的攻击途径。

以下部分解释了如何帮助降低脚本注入的风险。

### 脚本注入攻击示例

脚本注入攻击可直接发生在工作流程的内联脚本中。 在下列示例中，操作使用表达式来测试拉取请求标题的有效性，但也增加了脚本注入的风险：

```yaml
      - name: Check PR title
        run: |
          title="${{ github.event.pull_request.title }}"
          if [[ $title =~ ^octocat ]]; then
          echo "PR title starts with 'octocat'"
          exit 0
          else
          echo "PR title did not start with 'octocat'"
          exit 1
          fi
```

此示例易受脚本注入的影响，因为 `run` 命令在运行器的临时 shell 脚本中执行。 在运行 shell 脚本之前，将计算内部 `${{ }}` 的表达式，然后将其替换为生成的值，从而使它容易受到 shell 命令注入攻击。

要将命令注入此工作流，攻击者可以创建标题为 `a"; ls $GITHUB_WORKSPACE"` 的拉取请求：

![编辑模式下拉取请求标题的屏幕截图。 已在字段中输入新标题：a"; ls $GITHUB\_WORKSPACE"。](/assets/images/help/actions/example-script-injection-pr-title.png)

在此示例中，`"`该字符用于中断`title="${{ github.event.pull_request.title }}"`语句，从而允许`ls`在运行程序上执行命令。 可以在日志中看到 `ls` 命令的输出：

```shell
Run title="a"; ls $GITHUB_WORKSPACE""
README.md
code.yml
example.js
```

有关保持运行器安全性的最佳做法，请参阅 [安全使用指南](/zh/actions/reference/security/secure-use#good-practices-for-mitigating-script-injection-attacks)。