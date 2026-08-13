# 重新运行工作流程和作业

你可在初始运行后 30 天内重新运行工作流运行、工作流运行中所有失败的作业或工作流运行中的特定作业。

> 注意：
> “重新运行”工作流使用最初触发工作流的参与者的权限，而不是发起重新运行的参与者的权限。 该工作流还将使用与触发工作流运行的原始事件相同的 `GITHUB_SHA`（提交 SHA）和 `GITHUB_REF` (git ref)。

> 工作流运行最多可以重新运行 50 次。 仅重新运行单个作业或失败的作业会计入此限制。

## 重新运行工作流程中的所有作业

1. 在 GitHub 上，导航到存储库的主页面。

2. 在仓库名称下，单击“play Actions”\*\*\*\*。

   ![“github/docs”存储库的选项卡的屏幕截图。 “操作”选项卡以橙色边框突出显示。](/assets/images/help/repository/actions-tab-global-nav-update.png)

3. 在左侧边栏中，单击您想要查看的工作流程。

   ![“操作”选项卡的左侧边栏的屏幕截图。工作流“CodeQL”以深橙色标出。](/assets/images/help/actions/superlinter-workflow-sidebar.png)

4. 在工作流运行列表中，单击运行的名称以查看工作流运行摘要。

5. 在工作流的右上角，重新运行作业。

   * 如果任何作业失败，请选择 **sync “重新运行作业** ”下拉菜单，然后单击“ **重新运行所有作业**”。
   * 如果没有作业失败，请单击“重新运行所有作业”。

6. （可选）若要为重新运行启用运行程序诊断日志记录和步骤调试日志记录，请选择“启用调试日志记录”。 有关详细信息，请参阅“[启用调试日志记录](https://docs.github.com/zh/actions/how-tos/monitor-workflows/enable-debug-logging)”。

7. 单击“重新运行作业\*\*\*\*”。

1. 若要重新运行失败的工作流运行，请使用 `run rerun` 子命令，将 `RUN_ID` 替换为要重新运行的失败运行的 ID。 如果未指定`run-id`，GitHub CLI将返回一个交互式菜单，以便您选择最近失败的一次运行。

   ```shell copy
   gh run rerun RUN_ID
   ```

   若要为重新运行启用运行器诊断日志记录和单步调试日志记录，请使用 `--debug` 标志。

   ```shell copy
   gh run rerun RUN_ID --debug
   ```

2. 要查看工作流运行的进度，请使用 `run watch` 子命令，并从交互式列表中选择运行。

   ```shell copy
   gh run watch
   ```


## 重新运行工作流程中失败的作业

1. 在 GitHub 上，导航到存储库的主页面。
2. 在仓库名称下，单击“play Actions”\*\*\*\*。

   ![“github/docs”存储库的选项卡的屏幕截图。 “操作”选项卡以橙色边框突出显示。](/assets/images/help/repository/actions-tab-global-nav-update.png)
3. 在左侧边栏中，单击您想要查看的工作流程。

   ![“操作”选项卡的左侧边栏的屏幕截图。工作流“CodeQL”以深橙色标出。](/assets/images/help/actions/superlinter-workflow-sidebar.png)
4. 在工作流运行列表中，单击运行的名称以查看工作流运行摘要。
5. 在工作流的右上角，选择 **sync “重新运行作业** ”下拉菜单，然后单击“ **重新运行失败的作业**”。
6. （可选）若要为重新运行启用运行程序诊断日志记录和步骤调试日志记录，请选择“启用调试日志记录”。 有关详细信息，请参阅“[启用调试日志记录](https://docs.github.com/zh/actions/how-tos/monitor-workflows/enable-debug-logging)”。
7. 单击“重新运行作业\*\*\*\*”。

若要在工作流运行中重新运行失败的作业，请使用带有 `run rerun` 标志的 `--failed` 子命令。 将 `RUN_ID` 替换为其重新运行失败作业的运行的 ID。 如果未指定`run-id`，GitHub CLI将返回一个交互式菜单，供您选择最近失败的运行。

```shell
gh run rerun RUN_ID --failed
```

若要为重新运行启用运行器诊断日志记录和单步调试日志记录，请使用 `--debug` 标志。

```shell
gh run rerun RUN_ID --failed --debug
```


## 重新运行工作流程中的特定作业

1. 在 GitHub 上，导航到存储库的主页面。

2. 在仓库名称下，单击“play Actions”\*\*\*\*。

   ![“github/docs”存储库的选项卡的屏幕截图。 “操作”选项卡以橙色边框突出显示。](/assets/images/help/repository/actions-tab-global-nav-update.png)

3. 在左侧边栏中，单击您想要查看的工作流程。

   ![“操作”选项卡的左侧边栏的屏幕截图。工作流“CodeQL”以深橙色标出。](/assets/images/help/actions/superlinter-workflow-sidebar.png)

4. 在工作流运行列表中，单击运行的名称以查看工作流运行摘要。

5. 在左侧边栏的“作业”部分下，单击要重新运行的作业旁边的The re-run icon。

6. （可选）若要为重新运行启用运行程序诊断日志记录和步骤调试日志记录，请选择“启用调试日志记录”。 有关详细信息，请参阅“[启用调试日志记录](https://docs.github.com/zh/actions/how-tos/monitor-workflows/enable-debug-logging)”。

7. 单击“重新运行作业\*\*\*\*”。

若要在工作流运行中重新运行特定作业，请使用带有 `run rerun` 标志的 `--job` 子命令。 将 `JOB_ID` 替换为要重新运行的作业的 ID。

```shell
gh run rerun --job JOB_ID
```

若要为重新运行启用运行器诊断日志记录和单步调试日志记录，请使用 `--debug` 标志。

```shell
gh run rerun --job JOB_ID --debug
```


## 检查以前的工作流程运行

1. 在 GitHub 上，导航到存储库的主页面。
2. 在仓库名称下，单击“play Actions”\*\*\*\*。

   ![“github/docs”存储库的选项卡的屏幕截图。 “操作”选项卡以橙色边框突出显示。](/assets/images/help/repository/actions-tab-global-nav-update.png)
3. 在左侧边栏中，单击您想要查看的工作流程。

   ![“操作”选项卡的左侧边栏的屏幕截图。工作流“CodeQL”以深橙色标出。](/assets/images/help/actions/superlinter-workflow-sidebar.png)
4. 在工作流运行列表中，单击运行的名称以查看工作流运行摘要。
5. 在运行名称的右侧，选择“最新”下拉菜单，然后单击上一次运行尝试。
