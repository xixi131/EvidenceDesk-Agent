# 查看工作流程运行历史记录

您可以查看工作流程每次运行的日志。 日志包括工作流程中每个作业和步骤的状态。

执行这些步骤需要对仓库的读取访问权限。

1. 在 GitHub 上，导航到存储库的主页面。1. 在仓库名称下，单击“play Actions”\*\*\*\*。

   ![“github/docs”存储库的选项卡的屏幕截图。 “操作”选项卡以橙色边框突出显示。](/assets/images/help/repository/actions-tab-global-nav-update.png)1. 在左侧边栏中，单击您想要查看的工作流程。

   ![“操作”选项卡的左侧边栏的屏幕截图。工作流“CodeQL”以深橙色标出。](/assets/images/help/actions/superlinter-workflow-sidebar.png)1. 在工作流运行列表中，单击运行的名称以查看工作流运行摘要。

> 注意：
> 若要详细了解 GitHub CLI，请参阅“[关于 GitHub CLI](https://docs.github.com/zh/github-cli/github-cli/about-github-cli)”。

## 查看最近的工作流程运行

要列出最近的工作流运行，请使用 `run list` 子命令。

```shell
gh run list
```

要指定返回的最大运行次数，可使用 `-L` 或 `--limit` 标记。 默认为 `10`。

```shell
gh run list --limit 5
```

要仅返回指定工作流的运行，可使用 `-w` 或 `--workflow` 标记。 将 `workflow` 替换为工作流名称、工作流 ID 或工作流文件名。 例如，`"Link Checker"`、`1234567` 或 `"link-check-test.yml"`。

```shell
gh run list --workflow WORKFLOW
```

## 查看特定工作流程运行的详细信息

要显示特定工作流运行的详细信息，请使用 `run view` 子命令。 将 `run-id` 替换为要查看的运行的 ID。 如果没有指定 `run-id`，GitHub CLI 将返回交互式菜单供你选择最近的运行结果。

```shell
gh run view RUN_ID
```

要在输出中包含作业步骤，请使用 `-v` 或 `--verbose` 标记。

```shell
gh run view RUN_ID --verbose
```

要查看运行中特定作业的详细信息，请使用 `-j` 或 `--job` 标记。 将 `job-id` 替换为要查看的作业的 ID。

```shell
gh run view --job JOB_ID
```

要查看作业的完整日志，请使用 `--log` 标记。

```shell
gh run view --job JOB_ID --log
```

如果运行失败，请使用 `--exit-status` 标记以非零状态退出。 例如：

```shell
gh run view 0451 --exit-status && echo "run pending or passed"
```
