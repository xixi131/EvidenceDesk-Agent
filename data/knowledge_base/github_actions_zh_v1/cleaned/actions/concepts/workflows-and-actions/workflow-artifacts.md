# 工作流工件

了解如何将数据作为 GitHub Actions 工作流的工件进行存储并共享。

## 关于工作流程构件

构件是指在工作流程运行过程中产生的文件或文件集。 构件允许您在作业完成后保留数据，并与同一工作流程中的另一个作业共享该数据。 例如，在工作流程运行结束后，您可以使用构件保存您的构建和测试输出。

GitHub 提供了两个可用于上传和下载生成工件的操作：[upload-artifact](https://github.com/actions/upload-artifact) 和 [download-artifact](https://github.com/actions/download-artifact)。

常见成果物包括：

* 日志文件和核心转储文件
* 测试结果、失败和屏幕截图
* 二进制或压缩文件
* 压力测试性能输出和代码覆盖结果

## 构件与依赖项缓存

制品和缓存相似，因为它们都可以将文件存储在 GitHub 上，但两者的适用场景不同，不能相互替代。

* 如果您希望在多次工作流运行之间重复使用那些不经常变化的文件，例如包管理系统下载的依赖项、中间构建输出，或其他重新生成成本高昂的文件，请使用缓存。 缓存这些文件可以加快工作流运行的速度，但如果缓存不可用，作业应始终能够重新下载或重新生成这些文件。
* 如果要保存作业生成的文件，以在工作流运行结束后使用或查看文件（例如生成的二进制文件或生成日志），或者想要在工作流中的作业之间传递文件时，请使用项目。

有关依赖项缓存的详细信息，请参阅“[依赖项缓存参考](https://docs.github.com/zh/actions/reference/workflows-and-actions/dependency-caching)”。

## 为生成生成项目证明

工件证明使您能够为所构建的软件提供不可伪造的来源可追溯性和完整性保障。 反过来，使用软件的人员可以验证软件是在哪里以及如何构建的。

当您使用您的软件生成工件证明时，您会创建经密码学签名的声明，用于确立您的构建来源，并包含以下信息：

* 与该构件关联的工作流链接
* 该工件的仓库、组织、环境、提交 SHA 值以及触发事件
* OIDC 令牌中用于确立来源的其他信息。 有关详细信息，请参阅“[OpenID Connect](https://docs.github.com/zh/actions/concepts/security/openid-connect)”。

您还可以生成包含相关软件物料清单 (SBOM) 的制品证明。 将你的版本与它们中使用的开放源代码依赖项列表相关联可提供透明度，并使使用者能够遵守数据保护标准。

在构建运行完成后，你可以在构建生成的工件列表下方访问证明文件。

有关详细信息，请参阅“[使用项目证明确立生成的来源](https://docs.github.com/zh/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations)”。

## 已删除的工作流运行记录中的产物

删除某个工作流运行时，也会从存储中删除与该运行关联的所有工件。 可以使用 GitHub Actions UI、REST API 或使用 GitHub CLI 删除工作流运行，请参阅“[删除工作流程运行](https://docs.github.com/zh/actions/how-tos/manage-workflow-runs/delete-a-workflow-run)”、[删除工作流运行](https://docs.github.com/zh/rest/actions/workflow-runs?apiVersion=2022-11-28#delete-a-workflow-run)或 [gh run delete](https://cli.github.com/manual/gh_run_delete)。
