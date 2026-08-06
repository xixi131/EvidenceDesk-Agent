# 禁用和启用工作流

您可以使用 GitHub UI、REST API 或 GitHub CLI 禁用并重新启用工作流程。

禁用工作流程允许您停止触发工作流程，而不必从仓库中删除文件。 您可以轻松地在 GitHub 上重新启用工作流程。

在许多情况下，暂时禁用工作流程可能很有用。 以下是禁用工作流程可能有帮助的几个例子：

* 产生请求过多或错误的工作流程错误，对外部服务产生负面影响。
* 不重要但会耗费您帐户上太多分钟数的工作流程。
* 向已关闭的服务发送请求的工作流程。
* 复刻仓库上不需要的工作流程（例如预定的工作流程）。

> \[!WARNING]
> 为防止不必要的工作流程运行，可能会自动禁用计划的工作流程。 在复刻公共仓库时，默认情况下将禁用计划的工作流程。 在公共仓库中，当 60 天内未发生仓库活动时，将自动禁用计划的工作流程。

您也可以使用 REST API 禁用和启用工作流程。 有关详细信息，请参阅“[工作流的 REST API 终结点](/zh/rest/actions/workflows)”。

## 禁用工作流程

<div class="ghd-tool webui">

1. 在 GitHub 上，导航到存储库的主页面。
2. 在仓库名称下，单击“<svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-play" aria-label="play" role="img"><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Zm4.879-2.773 4.264 2.559a.25.25 0 0 1 0 .428l-4.264 2.559A.25.25 0 0 1 6 10.559V5.442a.25.25 0 0 1 .379-.215Z"></path></svg> Actions”\*\*\*\*。

   ![“github/docs”存储库的选项卡的屏幕截图。 “操作”选项卡以橙色边框突出显示。](/assets/images/help/repository/actions-tab-global-nav-update.png)
3. 在左侧边栏中，单击您想要禁用的工作流程。
4. 单击 <svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-kebab-horizontal" aria-label="Show workflow options" role="img"><path d="M8 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM1.5 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Zm13 0a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path></svg> 以显示下拉菜单，然后单击“禁用工作流”。

   ![工作流屏幕截图。 以橙色框出了显示有烤肉串图标的“显示工作流选项”按钮和“禁用工作流”菜单项。](/assets/images/help/repository/actions-disable-workflow-2022.png)

</div>

<div class="ghd-tool cli">

> \[!NOTE]
> 若要详细了解 GitHub CLI，请参阅“[关于 GitHub CLI](/zh/github-cli/github-cli/about-github-cli)”。

要禁用工作流，请使用 `workflow disable` 子命令。 将 `workflow` 替换为要禁用的工作流的名称、ID 或文件名。 例如，`"Link Checker"`、`1234567` 或 `"link-check-test.yml"`。 如果您没有指定工作流程，GitHub CLI 将返回交互式菜单供您选择工作流程。

```shell
gh workflow disable WORKFLOW
```

</div>

## 启用工作流程

<div class="ghd-tool webui">

您可以重新启用以前禁用过的工作流程。

1. 在 GitHub 上，导航到存储库的主页面。

2. 在仓库名称下，单击“<svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-play" aria-label="play" role="img"><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Zm4.879-2.773 4.264 2.559a.25.25 0 0 1 0 .428l-4.264 2.559A.25.25 0 0 1 6 10.559V5.442a.25.25 0 0 1 .379-.215Z"></path></svg> Actions”\*\*\*\*。

   ![“github/docs”存储库的选项卡的屏幕截图。 “操作”选项卡以橙色边框突出显示。](/assets/images/help/repository/actions-tab-global-nav-update.png)

3. 在左侧边栏中，单击您想要启用的工作流程。

   ![“Actions”页面的屏幕截图。 在左侧边栏中，工作流名称用深橙色边框突出显示。](/assets/images/help/repository/actions-select-disabled-workflow-2022.png)

4. 单击“启用工作流”。

</div>

<div class="ghd-tool cli">

要启用工作流，请使用 `workflow enable` 子命令。 将 `workflow` 替换为要启用的工作流的名称、ID 或文件名。 例如，`"Link Checker"`、`1234567` 或 `"link-check-test.yml"`。 如果您没有指定工作流程，GitHub CLI 将返回交互式菜单供您选择工作流程。

```shell
gh workflow enable WORKFLOW
```

</div>