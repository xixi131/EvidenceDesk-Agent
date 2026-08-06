# 启用调试日志记录

如果工作流程日志没有提供足够的详细信息来诊断工作流程、作业或步骤未按预期工作的原因，你可以启用额外的调试日志。

这些额外的日志将通过在包含工作流的仓库中设置机密或变量来启用，因而将适用相同的权限要求：

* 要在 GitHub 上为组织存储库创建机密或变量，你必须拥有 `write` 访问权限。对于个人帐户存储库，你必须是存储库协作者。
* 要为个人帐户存储库中的环境创建密码或变量，你必须是存储库所有者。 要为组织存储库中的环境创建密码或变量，必须具有 `admin` 访问权限。 有关环境的详细信息，请参阅“[管理部署环境](/zh/actions/how-tos/deploy/configure-and-manage-deployments/manage-environments)”。
* 组织所有者可以在组织级别创建机密或变量。

有关设置机密和变量的详细信息，请参阅 [在 GitHub Actions 中使用机密](/zh/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets) 和 [在变量中存储信息](/zh/actions/how-tos/write-workflows/choose-what-workflows-do/use-variables)。

此外，有权运行工作流的任何人都可以为工作流重新运行启用运行器诊断日志记录和步骤调试日志记录。 有关详细信息，请参阅“[重新运行工作流程和作业](/zh/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs)”。

## 启用运行程序诊断日志

运行程序诊断日志记录提供额外的日志文件，其中包含有关运行器如何执行作业的信息。 两个额外的日志文件被添加到日志存档中：

* 运行程序进程日志，其中包含关于如何协调和设置运行程序执行作业的信息。
* 工作程序进程日志，用于记录作业执行情况。

1. 要启用运行器诊断日志记录，请设置包含工作流的存储库中的以下机密或变量设置：`ACTIONS_RUNNER_DEBUG` 至 `true`。 如果同时设置了机密和变量，则机密的值优先于变量。
2. 要下载运行程序诊断日志，请下载工作流程运行情况的日志存档。 运行程序诊断日志包含在 `runner-diagnostic-logs` 文件夹中。 有关下载日志的详细信息，请参阅 [使用工作流运行日志](/zh/actions/how-tos/monitor-workflows/use-workflow-run-logs#downloading-logs)。

## 启用步骤调试日志

步骤调试日志增加了作业执行期间和执行之后的作业日志的详细程度。

1. 要启用步骤调试日志记录，请设置包含工作流的存储库中的以下机密或变量设置：`ACTIONS_STEP_DEBUG` 至 `true`。 如果同时设置了机密和变量，则机密的值优先于变量。
2. 设置机密或变量后，步骤日志中将显示更多的调试事件。 有关详细信息，请参阅“[使用工作流运行日志](/zh/actions/how-tos/monitor-workflows/use-workflow-run-logs#viewing-logs-to-diagnose-failures)”。

你还可以使用 `runner.debug` 上下文，仅在启用调试日志时有条件地运行步骤。 有关详细信息，请参阅“[上下文参考](/zh/actions/reference/workflows-and-actions/contexts#runner-context)”。