# 手动运行工作流

当工作流配置为在发生 workflow_dispatch 事件时运行时，可以使用 GitHub、GitHub CLI 或 REST API 上的“Actions”选项卡运行工作流。

## 配置工作流手动运行

要手动运行工作流，必须将工作流配置为在 `workflow_dispatch` 事件上运行。

要触发 `workflow_dispatch` 事件，工作流必须位于默认分支中。 有关配置 `workflow_dispatch` 事件的详细信息，请参阅 [触发工作流的事件](/zh/actions/using-workflows/events-that-trigger-workflows#workflow_dispatch)。

执行这些步骤需要对仓库的写入访问权限。

## 运行工作流

<div class="ghd-tool webui">

1. 在 GitHub 上，导航到存储库的主页面。

2. 在仓库名称下，单击“<svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-play" aria-label="play" role="img"><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Zm4.879-2.773 4.264 2.559a.25.25 0 0 1 0 .428l-4.264 2.559A.25.25 0 0 1 6 10.559V5.442a.25.25 0 0 1 .379-.215Z"></path></svg> Actions”\*\*\*\*。

   ![“github/docs”存储库的选项卡的屏幕截图。 “操作”选项卡以橙色边框突出显示。](/assets/images/help/repository/actions-tab-global-nav-update.png)

3. 在左侧边栏中，单击要运行的工作流的名称。

   ![“Actions”页面的屏幕截图。 在左侧边栏中，工作流名称用深橙色边框突出显示。](/assets/images/help/repository/actions-select-workflow-2022.png)

4. 在工作流运行列表的上方，单击“运行工作流”\*\*\*\* 按钮。

   > \[!NOTE]
   > 若要查看“运行工作流”\*\*\*\* 按钮，工作流文件必须使用 `workflow_dispatch` 事件触发器。 只有使用 `workflow_dispatch` 事件触发器的工作流文件才能选择使用“运行工作流”\*\*\*\* 按钮手动运行工作流。 有关配置 `workflow_dispatch` 事件的详细信息，请参阅 [触发工作流的事件](/zh/actions/using-workflows/events-that-trigger-workflows#workflow_dispatch)。

   ![工作流页面的屏幕截图。 在工作流运行列表上方，一个标有“运行工作流”的按钮用深橙色框出。](/assets/images/help/actions/actions-workflow-dispatch.png)

5. 选择“分支”\*\*\*\* 下拉菜单，然后单击要运行工作流的分支。

6. 如果工作流需要输入，请填写字段。

7. 单击“运行工作流”\*\*\*\*。

</div>

<div class="ghd-tool cli">

> \[!NOTE]
> 若要详细了解 GitHub CLI，请参阅“[关于 GitHub CLI](/zh/github-cli/github-cli/about-github-cli)”。

要运行工作流，请使用 `workflow run` 子命令。 将 `workflow` 参数替换为要运行的工作流的名称、ID 或文件名。 例如，`"Link Checker"`、`1234567` 或 `"link-check-test.yml"`。 如果你没有指定工作流，GitHub CLI 将返回交互式菜单供你选择工作流。

```shell
gh workflow run WORKFLOW
```

如果你的工作流接受输入，GitHub CLI 将提示你输入它们。 或者，可以使用 `-f` 或 `-F` 添加 `key=value` 格式的输入。 使用 `-F` 从文件中读取。

```shell
gh workflow run greet.yml -f name=mona -f greeting=hello -F data=@myfile.txt
```

你也可以使用标准输入以 JSON 的身份传递输入。

```shell
echo '{"name":"mona", "greeting":"hello"}' | gh workflow run greet.yml --json
```

要在存储库的默认分支以外的分支上运行工作流，请使用 `--ref` 标记。

```shell
gh workflow run WORKFLOW --ref BRANCH
```

要查看工作流运行的进度，请使用 `run watch` 子命令，并从交互式列表中选择运行。

```shell
gh run watch
```

</div>

## 使用 REST API 运行工作流

使用 REST API 时，应将 `inputs` 和 `ref` 配置为请求正文参数。 如果忽略输入，则使用工作流文件中定义的默认值。

> \[!NOTE]
> 最多可以为 `inputs` 事件定义 25  个 `workflow_dispatch`。

有关使用 REST API 的详细信息，请参阅 [工作流的 REST API 终结点](/zh/rest/actions/workflows#create-a-workflow-dispatch-event)。