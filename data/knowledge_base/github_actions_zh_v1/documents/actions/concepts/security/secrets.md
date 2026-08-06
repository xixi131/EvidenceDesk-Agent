# 机密

了解如何在 GitHub Actions 工作流中使用密钥。

## 关于机密

借助密钥可以在组织、存储库或存储库环境中存储敏感信息。 密钥是你创建的变量，用于在组织、仓库或仓库环境中的 GitHub Actions 工作流中使用。

GitHub Actions 只有在您显式地将机密包含在工作流中时，才能读取该机密。

## 机密的工作原理

机密信息使用 [Libsodium 密封盒](https://libsodium.gitbook.io/doc/public-key_cryptography/sealed_boxes)，因此它们在到达 GitHub 之前就已加密。 当[使用 UI](/zh/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets#creating-secrets-for-a-repository) 或通过 [REST API](/zh/rest/actions/secrets) 提交机密时会发生这种情况。 这种客户端加密有助于尽可能降低 GitHub 的基础设施内因意外记录日志（例如异常日志和请求日志等）而产生的风险。 上传机密后， GitHub 即可对其进行解密，以便可以注入工作流运行时。

## 组织级机密

组织级密码允许在多个仓库之间共享密码，从而减少创建重复密码的需要。 在一个位置更新组织密码还可确保更改在使用该密码的所有仓库工作流程中生效。

为组织创建机密时，可以使用策略来限制存储库的访问。 例如，您可以将访问权限授予所有仓库，也可以限制仅私有仓库或指定的仓库列表拥有访问权限。

对于环境机密，可以启用所需的审阅者来控制对机密的访问。 在必要的审查者授予批准之前，工作流程作业无法访问环境机密。

为使机密用于操作，必须在工作流文件中将机密设置为输入或环境变量。 查看操作的自述文件以了解操作预期的输入和环境变量。 请参阅“[GitHub Actions 的工作流语法](/zh/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstepsenv)”。

## 限制凭据权限

生成凭据时，建议尽可能授予最低的权限。 例如，请改为使用[部署密钥](/zh/authentication/connecting-to-github-with-ssh/managing-deploy-keys#deploy-keys)或服务帐户，而不是使用个人凭据。 请考虑授予只读权限（如果这是所需的全部权限）并尽可能限制访问。

生成 personal access token (classic) 时，请选择必需的最少作用域。 生成 fine-grained personal access token 时，请选择所需的最低权限和存储库访问权限。

无需使用 personal access token，请考虑使用 GitHub App；它使用细粒度权限和短期令牌，类似于 fine-grained personal access token。 与 a personal access token不同，A GitHub App 不绑定到用户，因此即使安装应用的用户离开组织，工作流也会继续工作。 有关详细信息，请参阅“[在GitHub Actions工作流中使用GitHub应用发出经过身份验证的 API 请求](/zh/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow)”。

## 自动屏蔽的机密

GitHub Actions 会自动修订打印到工作流日志的所有 GitHub 机密的内容。

GitHub Actions 还会隐藏被识别为敏感信息但未作为机密存储的信息。 有关自动遮蔽的机密列表，请参阅“[机密参考](/zh/actions/reference/security/secrets#automatically-redacted-secrets)”。

由于机密值可以通过多种方式进行转换，因此无法保证该值会被遮蔽。 此外，运行器只能对当前作业使用的机密进行编辑。 因此，你应采取一些特定的主动安全措施，以帮助确保机密得到编校，并降低与机密相关的其他风险。 有关机密安全最佳做法的参考列表，请参阅“[安全使用指南](/zh/actions/reference/security/secure-use#use-secrets-for-sensitive-information)”。

## 其他阅读材料

* [在 GitHub Actions 中使用机密](/zh/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)
* [用于 GitHub Actions 秘钥的 REST API 端点](/zh/rest/actions/secrets)