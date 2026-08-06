# GITHUB_TOKEN

了解什么是 GITHUB_TOKEN 工作原理，以及它对于工作流中 GitHub Actions 安全自动化很重要的原因。

## 关于 `GITHUB_TOKEN`

在每个工作流作业开始时，GitHub都会自动创建一个唯一的`GITHUB_TOKEN`密钥，供你在工作流中使用。 可以使用 `GITHUB_TOKEN` 在工作流作业中进行身份验证。

启用 GitHub Actions 后，GitHub 会向您的存储库安装一个 GitHub App。
`GITHUB_TOKEN` 密钥是 GitHub App 安装访问令牌。 您可以使用安装访问令牌代表存储库中安装的 GitHub App 进行身份验证。 令牌的权限仅限于包含您的工作流程的仓库。 有关详细信息，请参阅 [GitHub Actions 的工作流语法](/zh/actions/reference/workflows-and-actions/workflow-syntax#permissions)。

在每个作业开始之前，GitHub 会获取该作业的安装访问令牌。 作业完成或在其有效最长生存期之后，`GITHUB_TOKEN` 会过期。

令牌的最大有效寿命取决于运行器的类型：

* ```
            **              GitHub 托管运行器** 最长作业执行时间为 6 小时，因此 `GITHUB_TOKEN` 的最长生存时间为 6 小时。
  ```
* **自托管运行器** 最长作业执行时间为 5 天。 但是，由于 `GITHUB_TOKEN` 是安装访问令牌，因此最多只能刷新 24 小时。 如果作业运行时间超过 24 小时，请改用 personal access token 其他身份验证方法。

令牌也可以在 `github.token` 上下文中使用。 有关详细信息，请参阅 [上下文参考](/zh/actions/reference/workflows-and-actions/contexts#github-context)。

## 当 `GITHUB_TOKEN` 触发工作流运行时

使用存储库 `GITHUB_TOKEN` 执行任务时，由 `GITHUB_TOKEN` 该存储库触发的事件不会创建新的工作流运行，但有以下例外：

* `workflow_dispatch` 和 `repository_dispatch` 事件始终会触发工作流运行。
* 具有 `opened`、`synchronize` 或 `reopened` 活动类型的 `pull_request` 事件：当使用 `GITHUB_TOKEN` 的工作流创建或更新拉取请求时，生成的 `pull_request` 事件会创建处于 **需要审批** 状态的工作流运行。 该拉取请求会在合并框中显示一条横幅，拥有该仓库写入权限的用户可通过选择**批准工作流运行**来启动运行。 其他 `pull_request` 活动类型（例如 `labeled`， `edited`或 `closed`）不创建工作流运行。 这样可以防止递归工作流运行，同时仍允许 CI 工作流在自动化创建的拉取请求上运行。 有关批准工作流运行的详细信息，请参阅 [批准来自分支的工作流运行](/zh/actions/how-tos/manage-workflow-runs/approve-runs-from-forks)。

对于所有其他事件，此行为可防止意外创建递归的工作流运行实例。 例如，如果工作流运行使用存储库的 `GITHUB_TOKEN` 推送代码，则即使存储库包含配置为在 `push` 事件发生时运行的工作流，新工作流也不会运行。

> \[!NOTE]
> 如果您需要在无需批准的情况下执行工作流创建的拉取请求中的工作流运行，请在创建或更新拉取请求时使用 GitHub App 安装访问令牌或 personal access token，而不是使用 `GITHUB_TOKEN`。

由使用 `GITHUB_TOKEN` 的 GitHub Actions 工作流推送的提交不会触发 GitHub Pages 生成。

## 后续步骤

* [在工作流中使用 GITHUB\_TOKEN 进行身份验证](/zh/actions/tutorials/authenticate-with-github_token)
* [GitHub Actions 的工作流语法](/zh/actions/reference/workflows-and-actions/workflow-syntax#permissions)