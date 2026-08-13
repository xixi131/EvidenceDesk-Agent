# 下载工作流程构件

您可以在存档的制品自动过期之前下载它们。

GitHub 默认会存储构建日志和工件 90 天；你可以根据仓库类型来自定义此保留期。 有关详细信息，请参阅“[管理存储库的GitHub Actions设置](https://docs.github.com/zh/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository#configuring-the-retention-period-for-github-actions-artifacts-and-logs-in-your-repository)”。

执行这些步骤需要对仓库的读取访问权限。

1. 在 GitHub 上，导航到存储库的主页面。1. 在仓库名称下，单击“play Actions”\*\*\*\*。

   ![“github/docs”存储库的选项卡的屏幕截图。 “操作”选项卡以橙色边框突出显示。](/assets/images/help/repository/actions-tab-global-nav-update.png)1. 在左侧边栏中，单击您想要查看的工作流程。

   ![“操作”选项卡的左侧边栏的屏幕截图。工作流“CodeQL”以深橙色标出。](/assets/images/help/actions/superlinter-workflow-sidebar.png)1. 在工作流运行列表中，单击运行的名称以查看工作流运行摘要。
2. 在“工件”部分，单击你想要下载的工件。

   ![工作流运行的“工件”部分的屏幕截图。 运行生成的构件名称“artifact”以橙色轮廓显示。](/assets/images/help/repository/artifact-drop-down-updated.png)

> 注意：
> 若要详细了解 GitHub CLI，请参阅“[关于 GitHub CLI](https://docs.github.com/zh/github-cli/github-cli/about-github-cli)”。

GitHub CLI 将根据构件名称将每个构件下载到单独的目录中。 如果只指定了单个构件, 它将被提取到当前目录。

要下载工作流运行产生的所有项目，请使用 `run download` 子命令。 将 `run-id` 替换为你要从中下载项目的运行的 ID。 如果没有指定 `run-id`，GitHub CLI 将返回交互式菜单供你选择最近的运行结果。

```shell
gh run download RUN_ID
```

要从运行中下载特定的项目，请使用 `run download` 子命令。 将 `run-id` 替换为你要从中下载项目的运行的 ID。 将 `artifact-name` 替换为你要下载的项目的名称。

```shell
gh run download RUN_ID -n ARTIFACT_NAME
```

您可以指定多个构件。

```shell
gh run download RUN_ID> -n ARTIFACT_NAME-1 -n ARTIFACT_NAME-2
```

要从存储库的所有运行中下载特定的项目，请使用 `run download` 子命令。

```shell
gh run download -n ARTIFACT_NAME-1 ARTIFACT_NAME-2
```
