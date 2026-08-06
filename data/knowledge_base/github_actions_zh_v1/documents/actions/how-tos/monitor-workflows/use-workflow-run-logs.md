# 使用工作流运行日志

您可以查看、搜索和下载工作流程运行中每个作业的日志。

您可以从工作流程运行页面查看工作流程运行是在进行中，还是已完成。 必须登录到 GitHub 帐户才能查看工作流运行信息，包括公共存储库。 有关详细信息，请参阅“[对GitHub的访问权限](/zh/get-started/learning-about-github/access-permissions-on-github)”。

如果运行已完成，则可查看运行结果是成功、失败、已取消还是中性。 如果运行失败，您可以查看并搜索构建日志，来诊断失败原因并重新运行工作流程。 您也可以查看可计费作业执行分钟数，或下载日志和创建构件。

GitHub Actions 使用检查 API 输出工作流的状态、结果和日志。
GitHub 为每个工作流运行创建新的检查套件。 检查套件包含检查工作流程中每项作业的运行，而每项作业包含步骤。
GitHub Actions 作为工作流中的一个步骤运行。 有关检查 API 的详细信息，请参阅“[检验的 REST API 端点](/zh/rest/checks)”。

> \[!NOTE]
> 确保只将有效的工作流文件提交到存储库。 如果 `.github/workflows` 含有无效的工作流文件，则 GitHub Actions 将为每次新提交生成失败的工作流运行。

## 查看日志以诊断故障

如果工作流程运行失败，您可以查看是哪个步骤导致了失败，然后审查失败步骤的创建日志进行故障排除。 您可以查看每个步骤运行的时长。 也可以将永久链接复制到日志文件中的特定行，与您的团队分享。 执行这些步骤需要对仓库的读取访问权限。

除了工作流文件中配置的步骤外， GitHub 还向每个作业添加两个附加步骤以设置和完成作业的执行。 这些步骤以名称"设置作业"和"完成作业"记录在工作流程运行中。

对于在 GitHub 托管的运行器上运行的作业，“设置作业”会记录运行器映像的详细信息，它还包含一个链接，指向运行器机器上的预安装工具列表。

1. 在 GitHub 上，导航到存储库的主页面。
2. 在仓库名称下，单击“<svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-play" aria-label="play" role="img"><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Zm4.879-2.773 4.264 2.559a.25.25 0 0 1 0 .428l-4.264 2.559A.25.25 0 0 1 6 10.559V5.442a.25.25 0 0 1 .379-.215Z"></path></svg> Actions”\*\*\*\*。

   ![“github/docs”存储库的选项卡的屏幕截图。 “操作”选项卡以橙色边框突出显示。](/assets/images/help/repository/actions-tab-global-nav-update.png)
3. 在左侧边栏中，单击您想要查看的工作流程。

   ![“操作”选项卡的左侧边栏的屏幕截图。工作流“CodeQL”以深橙色标出。](/assets/images/help/actions/superlinter-workflow-sidebar.png)
4. 在工作流运行列表中，单击运行的名称以查看工作流运行摘要。
5. 在“作业”或可视化图中，选择要查看的作业。
6. 任何失败的步骤都会自动展开以显示结果。
7. （可选）要获取指向日志中特定行的链接，请单击该步骤的行号。 然后，您可以从 web 浏览器的地址栏中复制链接。

   ![作业日志的屏幕截图。 已展开失败步骤的日志，并以橙色轮廓突出显示行号。](/assets/images/help/repository/copy-link-button-updated-2.png)

## 搜索日志

您可以搜索特定步骤的创建日志。 在搜索日志时，只有已展开的步骤会包含在结果中。 执行这些步骤需要对仓库的读取访问权限。

1. 在 GitHub 上，导航到存储库的主页面。
2. 在仓库名称下，单击“<svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-play" aria-label="play" role="img"><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Zm4.879-2.773 4.264 2.559a.25.25 0 0 1 0 .428l-4.264 2.559A.25.25 0 0 1 6 10.559V5.442a.25.25 0 0 1 .379-.215Z"></path></svg> Actions”\*\*\*\*。

   ![“github/docs”存储库的选项卡的屏幕截图。 “操作”选项卡以橙色边框突出显示。](/assets/images/help/repository/actions-tab-global-nav-update.png)
3. 在左侧边栏中，单击您想要查看的工作流程。

   ![“操作”选项卡的左侧边栏的屏幕截图。工作流“CodeQL”以深橙色标出。](/assets/images/help/actions/superlinter-workflow-sidebar.png)
4. 在工作流运行列表中，单击运行的名称以查看工作流运行摘要。
5. 在“作业”或可视化图中，选择要查看的作业。
6. 在日志输出右上角的“搜索日志”搜索框中，输入搜索查询。

## 下载日志

您可以从工作流程运行中下载日志文件。 您也可以下载工作流程的构件。 有关详细信息，请参阅“[使用工作流工件存储和共享数据](/zh/actions/tutorials/store-and-share-data)”。 执行这些步骤需要对仓库的读取访问权限。

1. 在 GitHub 上，导航到存储库的主页面。
2. 在仓库名称下，单击“<svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-play" aria-label="play" role="img"><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Zm4.879-2.773 4.264 2.559a.25.25 0 0 1 0 .428l-4.264 2.559A.25.25 0 0 1 6 10.559V5.442a.25.25 0 0 1 .379-.215Z"></path></svg> Actions”\*\*\*\*。

   ![“github/docs”存储库的选项卡的屏幕截图。 “操作”选项卡以橙色边框突出显示。](/assets/images/help/repository/actions-tab-global-nav-update.png)
3. 在左侧边栏中，单击您想要查看的工作流程。

   ![“操作”选项卡的左侧边栏的屏幕截图。工作流“CodeQL”以深橙色标出。](/assets/images/help/actions/superlinter-workflow-sidebar.png)
4. 在工作流运行列表中，单击运行的名称以查看工作流运行摘要。
5. 在“作业”或可视化图中，选择要查看的作业。
6. 在日志右上角，选择 <svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-gear" aria-label="Show options" role="img"><path d="M8 0a8.2 8.2 0 0 1 .701.031C9.444.095 9.99.645 10.16 1.29l.288 1.107c.018.066.079.158.212.224.231.114.454.243.668.386.123.082.233.09.299.071l1.103-.303c.644-.176 1.392.021 1.82.63.27.385.506.792.704 1.218.315.675.111 1.422-.364 1.891l-.814.806c-.049.048-.098.147-.088.294.016.257.016.515 0 .772-.01.147.038.246.088.294l.814.806c.475.469.679 1.216.364 1.891a7.977 7.977 0 0 1-.704 1.217c-.428.61-1.176.807-1.82.63l-1.102-.302c-.067-.019-.177-.011-.3.071a5.909 5.909 0 0 1-.668.386c-.133.066-.194.158-.211.224l-.29 1.106c-.168.646-.715 1.196-1.458 1.26a8.006 8.006 0 0 1-1.402 0c-.743-.064-1.289-.614-1.458-1.26l-.289-1.106c-.018-.066-.079-.158-.212-.224a5.738 5.738 0 0 1-.668-.386c-.123-.082-.233-.09-.299-.071l-1.103.303c-.644.176-1.392-.021-1.82-.63a8.12 8.12 0 0 1-.704-1.218c-.315-.675-.111-1.422.363-1.891l.815-.806c.05-.048.098-.147.088-.294a6.214 6.214 0 0 1 0-.772c.01-.147-.038-.246-.088-.294l-.815-.806C.635 6.045.431 5.298.746 4.623a7.92 7.92 0 0 1 .704-1.217c.428-.61 1.176-.807 1.82-.63l1.102.302c.067.019.177.011.3-.071.214-.143.437-.272.668-.386.133-.066.194-.158.211-.224l.29-1.106C6.009.645 6.556.095 7.299.03 7.53.01 7.764 0 8 0Zm-.571 1.525c-.036.003-.108.036-.137.146l-.289 1.105c-.147.561-.549.967-.998 1.189-.173.086-.34.183-.5.29-.417.278-.97.423-1.529.27l-1.103-.303c-.109-.03-.175.016-.195.045-.22.312-.412.644-.573.99-.014.031-.021.11.059.19l.815.806c.411.406.562.957.53 1.456a4.709 4.709 0 0 0 0 .582c.032.499-.119 1.05-.53 1.456l-.815.806c-.081.08-.073.159-.059.19.162.346.353.677.573.989.02.03.085.076.195.046l1.102-.303c.56-.153 1.113-.008 1.53.27.161.107.328.204.501.29.447.222.85.629.997 1.189l.289 1.105c.029.109.101.143.137.146a6.6 6.6 0 0 0 1.142 0c.036-.003.108-.036.137-.146l.289-1.105c.147-.561.549-.967.998-1.189.173-.086.34-.183.5-.29.417-.278.97-.423 1.529-.27l1.103.303c.109.029.175-.016.195-.045.22-.313.411-.644.573-.99.014-.031.021-.11-.059-.19l-.815-.806c-.411-.406-.562-.957-.53-1.456a4.709 4.709 0 0 0 0-.582c-.032-.499.119-1.05.53-1.456l.815-.806c.081-.08.073-.159.059-.19a6.464 6.464 0 0 0-.573-.989c-.02-.03-.085-.076-.195-.046l-1.102.303c-.56.153-1.113.008-1.53-.27a4.44 4.44 0 0 0-.501-.29c-.447-.222-.85-.629-.997-1.189l-.289-1.105c-.029-.11-.101-.143-.137-.146a6.6 6.6 0 0 0-1.142 0ZM11 8a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM9.5 8a1.5 1.5 0 1 0-3.001.001A1.5 1.5 0 0 0 9.5 8Z"></path></svg> 下拉菜单，然后单击“ **下载日志存档**”。

   ![作业日志的屏幕截图。 在标题中，齿轮图标以深橙色框出。](/assets/images/help/actions/download-logs-drop-down.png)

> \[!NOTE]
> 下载部分重新运行的工作流的日志存档时，存档仅包括已重新运行的作业。 若要获取从工作流程运行的作业的完整日志集，必须下载运行其他作业的上一次运行尝试的日志存档。

## 删除日志

您可以通过 GitHub Web 界面或以编程方式删除工作流运行中的日志文件。 执行这些步骤需要对仓库的写入访问权限。

### 通过 GitHub Web 界面删除日志

1. 在 GitHub 上，导航到存储库的主页面。

2. 在仓库名称下，单击“<svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-play" aria-label="play" role="img"><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Zm4.879-2.773 4.264 2.559a.25.25 0 0 1 0 .428l-4.264 2.559A.25.25 0 0 1 6 10.559V5.442a.25.25 0 0 1 .379-.215Z"></path></svg> Actions”\*\*\*\*。

   ![“github/docs”存储库的选项卡的屏幕截图。 “操作”选项卡以橙色边框突出显示。](/assets/images/help/repository/actions-tab-global-nav-update.png)

3. 在左侧边栏中，单击您想要查看的工作流程。

   ![“操作”选项卡的左侧边栏的屏幕截图。工作流“CodeQL”以深橙色标出。](/assets/images/help/actions/superlinter-workflow-sidebar.png)

4. 在工作流运行列表中，单击运行的名称以查看工作流运行摘要。

5. 在右上角，选择 <svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-kebab-horizontal" aria-label="Show workflow options" role="img"><path d="M8 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM1.5 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Zm13 0a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path></svg> 下拉菜单，然后单击“ **删除所有日志**”。

   ![工作流运行页的屏幕截图。 在右上角，一个标有“更多”图标的按钮以深橙色框出。](/assets/images/help/actions/workflow-run-kebab-horizontal-icon.png)

6. 查看确认提示。

删除日志后，“删除所有日志”按钮将会移除，以表示在工作流运行中没有日志文件。

### 以编程方式删除日志

可以使用以下脚本自动删除工作流的所有日志。 通过该方法可有效清理多个工作流运行的日志。

要运行下列脚本示例，请执行以下操作：

1. 复制代码示例并将其保存到名为 `delete-logs.sh` 的文件中。
2. 通过 `chmod +x delete-logs.sh` 授予执行权限。
3. 运行以下命令，其中 `REPOSITORY_NAME` 为存储库的名称，`WORKFLOW_NAME` 为工作流的文件名。

   ```shell copy
   ./delete-logs.sh REPOSITORY_NAME WORKFLOW_NAME
   ```

   例如，要删除 `monalisa/octocat` 工作流 `.github/workflows/ci.yaml` 存储库中的所有日志，须运行 `./delete-logs.sh monalisa/octocat ci.yaml`。

#### 示例脚本

```bash copy
#!/usr/bin/env bash

# Delete all logs for a given workflow
# Usage: delete-logs.sh <repository> <workflow-name>

set -oe pipefail

REPOSITORY=$1
WORKFLOW_NAME=$2

# Validate arguments
if [[ -z "$REPOSITORY" ]]; then
  echo "Repository is required"
  exit 1
fi

if [[ -z "$WORKFLOW_NAME" ]]; then
  echo "Workflow name is required"
  exit 1
fi

echo "Getting all completed runs for workflow $WORKFLOW_NAME in $REPOSITORY"

RUNS=$(
  gh api \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "/repos/$REPOSITORY/actions/workflows/$WORKFLOW_NAME/runs" \
    --paginate \
    --jq '.workflow_runs[] | select(.conclusion != "") | .id'
)

echo "Found $(echo "$RUNS" | wc -l) completed runs for workflow $WORKFLOW_NAME"

# Delete logs for each run
for RUN in $RUNS; do
  echo "Deleting logs for run $RUN"
  gh api \
    --silent \
    --method DELETE \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "/repos/$REPOSITORY/actions/runs/$RUN/logs" || echo "Failed to delete logs for run $RUN"

  # Sleep for 100ms to avoid rate limiting
  sleep 0.1
done
```

## 使用 GitHub CLI 查看日志

> \[!NOTE]
> 若要详细了解 GitHub CLI，请参阅“[关于 GitHub CLI](/zh/github-cli/github-cli/about-github-cli)”。

若要查看特定作业的日志，请使用 `run view` 子命令。 将 `run-id` 替换为想要查看其日志的运行的 ID。               GitHub CLI 将返回一个交互式菜单，供您从运行中选择作业。 如果未指定 `run-id`， GitHub CLI 则返回交互式菜单供你选择最近的运行，然后返回另一个交互式菜单供你从运行中选择作业。

```shell
gh run view RUN_ID --log
```

还可以使用 `--job` 标记来指定作业 ID。 将 `job-id` 替换为想要查看其日志的作业的 ID。

```shell
gh run view --job JOB_ID --log
```

可使用 `grep` 搜索日志。 例如，此命令将返回包含 `error` 一词的所有日志条目。

```shell
gh run view --job JOB_ID --log | grep error
```

若要筛选任何失败步骤的日志，请使用 `--log-failed` 而不是 `--log`。

```shell
gh run view --job JOB_ID --log-failed
```