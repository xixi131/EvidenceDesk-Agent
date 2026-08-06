# 变量

了解工作流中的 GitHub Actions 变量。

## 关于

变量提供了一种存储和重用非敏感配置信息的方法。 可以将任何配置数据（如编译器标志、用户名或服务器名称）存储为变量。 变量在运行工作流的运行器计算机上插值。 在操作或工作流步骤中运行的命令可以创建、读取和修改变量。

可以设置自己的自定义变量或使用自动设置的默认环境变量 GitHub 。

可以通过两种方式设置自定义变量。

* 若要定义要在单个工作流中使用的环境变量，可以在工作流文件中使用 `env` 键。 有关详细信息，请参阅“[为单个工作流定义环境变量](/zh/actions/how-tos/write-workflows/choose-what-workflows-do/use-variables#defining-environment-variables-for-a-single-workflow)”。
* 若要跨多个工作流定义配置变量，可以在组织、存储库或环境级别定义它。 在组织中创建变量时，可以使用策略来限制仓库的访问。 例如，您可以将访问权限授予所有仓库，也可以限制仅私有仓库或指定的仓库列表拥有访问权限。 有关详细信息，请参阅“[为多个工作流定义配置变量](/zh/actions/how-tos/write-workflows/choose-what-workflows-do/use-variables#defining-configuration-variables-for-multiple-workflows)”。

> \[!WARNING]
> 默认情况下，变量在生成输出中未经屏蔽地呈现。 如果需要提高敏感信息（如密码）的安全性，请改用机密。 有关详细信息，请参阅“[机密](/zh/actions/concepts/security/secrets)”。

有关参考文档，请参阅“[变量参考](/zh/actions/reference/workflows-and-actions/variables)”。