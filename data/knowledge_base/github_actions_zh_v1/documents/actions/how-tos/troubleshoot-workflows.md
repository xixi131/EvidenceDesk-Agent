# 故障排除工作流

您可以使用 GitHub Actions 中的工具来调试工作流。

## 初始故障排除建议

可通过多种方式排查工作流运行失败的问题。

> \[!NOTE] 如果你使用的是GitHub Copilot 免费订阅，这将计入你每月的聊天消息限额。

### 使用 GitHub Copilot

若要就某次失败的工作流运行与 GitHub Copilot 打开聊天，您可以选择以下任一方式：

* 在合并框中失败的复选框旁边，单击 **<svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-kebab-horizontal" aria-label="kebab-horizontal" role="img"><path d="M8 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM1.5 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Zm13 0a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path></svg>**，然后单击“ **<svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-copilot" aria-label="copilot" role="img"><path d="M7.998 15.035c-4.562 0-7.873-2.914-7.998-3.749V9.338c.085-.628.677-1.686 1.588-2.065.013-.07.024-.143.036-.218.029-.183.06-.384.126-.612-.201-.508-.254-1.084-.254-1.656 0-.87.128-1.769.693-2.484.579-.733 1.494-1.124 2.724-1.261 1.206-.134 2.262.034 2.944.765.05.053.096.108.139.165.044-.057.094-.112.143-.165.682-.731 1.738-.899 2.944-.765 1.23.137 2.145.528 2.724 1.261.566.715.693 1.614.693 2.484 0 .572-.053 1.148-.254 1.656.066.228.098.429.126.612.012.076.024.148.037.218.924.385 1.522 1.471 1.591 2.095v1.872c0 .766-3.351 3.795-8.002 3.795Zm0-1.485c2.28 0 4.584-1.11 5.002-1.433V7.862l-.023-.116c-.49.21-1.075.291-1.727.291-1.146 0-2.059-.327-2.71-.991A3.222 3.222 0 0 1 8 6.303a3.24 3.24 0 0 1-.544.743c-.65.664-1.563.991-2.71.991-.652 0-1.236-.081-1.727-.291l-.023.116v4.255c.419.323 2.722 1.433 5.002 1.433ZM6.762 2.83c-.193-.206-.637-.413-1.682-.297-1.019.113-1.479.404-1.713.7-.247.312-.369.789-.369 1.554 0 .793.129 1.171.308 1.371.162.181.519.379 1.442.379.853 0 1.339-.235 1.638-.54.315-.322.527-.827.617-1.553.117-.935-.037-1.395-.241-1.614Zm4.155-.297c-1.044-.116-1.488.091-1.681.297-.204.219-.359.679-.242 1.614.091.726.303 1.231.618 1.553.299.305.784.54 1.638.54.922 0 1.28-.198 1.442-.379.179-.2.308-.578.308-1.371 0-.765-.123-1.242-.37-1.554-.233-.296-.693-.587-1.713-.7Z"></path><path d="M6.25 9.037a.75.75 0 0 1 .75.75v1.501a.75.75 0 0 1-1.5 0V9.787a.75.75 0 0 1 .75-.75Zm4.25.75v1.501a.75.75 0 0 1-1.5 0V9.787a.75.75 0 0 1 1.5 0Z"></path></svg> 解释错误**”。
* 在合并框中，单击失败的检查。 在工作流运行摘要页顶部，单击“ **<svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-copilot" aria-label="copilot" role="img"><path d="M7.998 15.035c-4.562 0-7.873-2.914-7.998-3.749V9.338c.085-.628.677-1.686 1.588-2.065.013-.07.024-.143.036-.218.029-.183.06-.384.126-.612-.201-.508-.254-1.084-.254-1.656 0-.87.128-1.769.693-2.484.579-.733 1.494-1.124 2.724-1.261 1.206-.134 2.262.034 2.944.765.05.053.096.108.139.165.044-.057.094-.112.143-.165.682-.731 1.738-.899 2.944-.765 1.23.137 2.145.528 2.724 1.261.566.715.693 1.614.693 2.484 0 .572-.053 1.148-.254 1.656.066.228.098.429.126.612.012.076.024.148.037.218.924.385 1.522 1.471 1.591 2.095v1.872c0 .766-3.351 3.795-8.002 3.795Zm0-1.485c2.28 0 4.584-1.11 5.002-1.433V7.862l-.023-.116c-.49.21-1.075.291-1.727.291-1.146 0-2.059-.327-2.71-.991A3.222 3.222 0 0 1 8 6.303a3.24 3.24 0 0 1-.544.743c-.65.664-1.563.991-2.71.991-.652 0-1.236-.081-1.727-.291l-.023.116v4.255c.419.323 2.722 1.433 5.002 1.433ZM6.762 2.83c-.193-.206-.637-.413-1.682-.297-1.019.113-1.479.404-1.713.7-.247.312-.369.789-.369 1.554 0 .793.129 1.171.308 1.371.162.181.519.379 1.442.379.853 0 1.339-.235 1.638-.54.315-.322.527-.827.617-1.553.117-.935-.037-1.395-.241-1.614Zm4.155-.297c-1.044-.116-1.488.091-1.681.297-.204.219-.359.679-.242 1.614.091.726.303 1.231.618 1.553.299.305.784.54 1.638.54.922 0 1.28-.198 1.442-.379.179-.2.308-.578.308-1.371 0-.765-.123-1.242-.37-1.554-.233-.296-.693-.587-1.713-.7Z"></path><path d="M6.25 9.037a.75.75 0 0 1 .75.75v1.501a.75.75 0 0 1-1.5 0V9.787a.75.75 0 0 1 .75-.75Zm4.25.75v1.501a.75.75 0 0 1-1.5 0V9.787a.75.75 0 0 1 1.5 0Z"></path></svg> 解释”错误**。

这将打开一个与 GitHub Copilot 的聊天窗口，其中会提供解决该问题的说明。

### 使用工作流运行日志

每个工作流程运行都会生成活动日志，您可以查看、搜索和下载这些日志。 有关详细信息，请参阅“[使用工作流运行日志](/zh/actions/how-tos/monitor-workflows/use-workflow-run-logs)”。

### 启用调试日志记录

如果工作流程日志没有提供足够的详细信息来诊断工作流程、作业或步骤未按预期工作的原因，您可以启用额外的调试日志。 有关详细信息，请参阅“[启用调试日志记录](/zh/actions/how-tos/monitor-workflows/enable-debug-logging)”。

如果工作流使用特定工具或操作，则启用其调试或详细日志记录选项有助于生成更详细的输出，以便进行故障排除。
例如，可以将 `npm install --verbose` 用于 npm，或将 `GIT_TRACE=1 GIT_CURL_VERBOSE=1 git ...` 用于 git。

## 查看计费错误

操作使用情况包括[工作流工件](/zh/actions/tutorials/store-and-share-data)的执行器分钟数和存储。 有关详细信息，请参阅“[GitHub Actions计费](/zh/billing/concepts/product-billing/github-actions)”。

### 设置预算

配置 Actions 预算可能有助于立即恢复因计费或存储错误而中断的工作流。 这将使额外的通话分钟数和存储空间使用量可在设定的预算限额内进行计费。 若要了解详细信息，请参阅“[设置预算以控制按流量计费的产品的支出](/zh/billing/how-tos/set-up-budgets)”。

## 通过指标查看 GitHub Actions 活动情况

若要使用指标分析工作流的效率和可靠性，请参阅“[查看 GitHub Actions 指标](/zh/actions/how-tos/administer/view-metrics)”。

## 排查工作流触发器的问题

首先，请确保您的工作流未被手动禁用，请参阅 [禁用和启用工作流](/zh/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows)。 禁用的工作流不会响应其触发器。

可查看工作流的 `on:` 字段，以了解触发工作流的预期内容。 有关详细信息，请参阅“[触发工作流程](/zh/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)”。

有关可用事件的完整列表，请参阅“[触发工作流的事件](/zh/actions/reference/workflows-and-actions/events-that-trigger-workflows)”。

### 触发事件条件

某些触发事件仅从默认分支（即 `issues` 和 `schedule`）运行。 位于默认分支之外的工作流文件版本不会响应这些事件的触发。

如果拉取请求存在合并冲突，工作流将不会在 `pull_request` 活动上运行。

如果提交信息中包含跳过注释，则触发 `push` 或 `pull_request` 活动的工作流将不会运行。 有关详细信息，请参阅“[跳过工作流程运行](/zh/actions/how-tos/manage-workflow-runs/skip-workflow-runs)”。

### 预定的工作流在非预期时间运行

在大量工作流运行期间 GitHub Actions ，计划事件可能会延迟。

高负载时间包括每小时的开始时间。 如果负载足够高，可能会删除一些排队作业。 为了降低延迟的可能性，将您的工作流程安排在不同时间运行。 有关详细信息，请参阅“[触发工作流的事件](/zh/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)”。

### 筛选和差异限制

特定事件支持你自定义按分支、标签和/或路径进行筛选。 如果应用筛选条件筛选掉工作流，则不会创建该工作流运行。

可在筛选器中使用特殊字符。 有关详细信息，请参阅“[GitHub Actions 的工作流语法](/zh/actions/reference/workflows-and-actions/workflow-syntax#filter-pattern-cheat-sheet)”。

对于路径筛选，评估差异仅限于前 300 个文件。 如果更改的文件与筛选器返回的前 300 个文件不匹配，则工作流将不会运行。 有关详细信息，请参阅“[GitHub Actions 的工作流语法](/zh/actions/reference/workflows-and-actions/workflow-syntax#git-diff-comparisons)”。

## 排查工作流执行问题

工作流执行涉及在触发工作流并创建工作流运行后出现的任何问题。

### 调试作业条件

如果某个作业意外被跳过，或者在你希望其被跳过时却运行了，你可以查看表达式求值结果以了解原因：

1. 在工作流运行中单击相应的作业。
2. 从作业菜单下载日志存档。
3. 打开 `JOB-NAME/system.txt` 文件。
4. 查找`Evaluating`和`Expanded``Result`线条。

`Expanded` 行会显示被代入到 `if` 条件中的实际运行时值，从而明确说明为什么表达式求值结果为 `true` 或 `false`。

有关详细信息，请参阅“[查看作业条件表达式日志](/zh/actions/how-tos/monitor-workflows/view-job-condition-logs)”。

### 取消工作流

如果通过 [UI](/zh/actions/reference/workflows-and-actions/workflow-cancellation) 或 [API](/zh/rest/actions/workflow-runs?apiVersion=2022-11-28#cancel-a-workflow-run) 的常规取消操作未按预期执行，可能是正在运行的工作流作业配置了某个条件语句，导致其无法被取消。

在这些情况下，可以利用 API 强制取消运行。 有关详细信息，请参阅“[工作流运行的 REST API 终结点](/zh/rest/actions/workflow-runs?apiVersion=2022-11-28#force-cancel-a-workflow-run)”。

常见原因可能是使用了 `always()`[状态检查函数](/zh/actions/reference/workflows-and-actions/expressions#status-check-functions)，该函数即使在取消操作时也会返回 `true`。 另一种方法是使用 `cancelled()` 函数的反函数 `${{ !cancelled() }}`。

有关详细信息，请参阅 [使用条件控制作业执行](/zh/actions/how-tos/write-workflows/choose-when-workflows-run/control-jobs-with-conditions) 和 [取消工作流程运行](/zh/actions/how-tos/manage-workflow-runs/cancel-a-workflow-run)。

## 排查运行器错误

### 定义运行器标签

GitHub 托管运行器利用通过 [](/zh/actions/reference/runners/github-hosted-runners#standard-github-hosted-runners-for-public-repositories) 存储库维护的`actions/runner-images`。

建议对大型自托管运行器使用唯一的标签名称。 如果某个标签与现有的预设标签匹配，可能会出现运行器分配问题，导致无法保证作业将在哪个匹配的运行器上运行。

### 自托管运行程序

如果您使用自托管运行器，则可以查看其活动并诊断常见问题。

有关详细信息，请参阅“[对自托管运行程序进行监视和故障排除](/zh/actions/how-tos/manage-runners/self-hosted-runners/monitor-and-troubleshoot)”。

### 被安全扫描器标记的 Runner IP 地址

GitHub-托管运行器使用来自共享基础设施的动态分配 IP 地址。 这些 IP 地址通过 Meta API 发布（例如，通过 `actions` 和 `actions_macos` 键）。 有关详细信息，请参阅“[元数据的 REST API 端点](/zh/rest/meta/meta#get-github-meta-information)”。

第三方威胁情报服务、IP 信誉扫描程序或防火墙供应商可能会将这些 IP 地址标记为“恶意”或“可疑”。 由于底层基础结构是共享的，因此同一基础结构的其他用户的活动可能会影响分配给这些地址的信誉分数。

GitHub 不控制第三方 IP 信誉列表，也不能对其准确性或更新频率发表评论。 若要验证 IP 地址是否属于 GitHub托管运行程序，请检查 Meta API 返回的 IP 范围。

如果您对 Microsoft 所有的 IP 地址有安全方面的顾虑，请向 [Microsoft 安全响应中心（MSRC）](https://msrc.microsoft.com/report/) 报告。

## 网络故障排除建议

我们对涉及以下情况的网络问题支持范围有限：

* 你的网络
* 外部网络
* 第三方系统
* 一般 Internet 连接

GitHub若要查看实时平台状态，请检查[GitHub“状态](https://githubstatus.com/)”。

对于其他与网络相关的问题，请查看组织的网络设置，并验证你正在访问的任何第三方服务的状态。 如果问题仍然存在，请考虑联系网络管理员以获得进一步的帮助。

如果您不确定该问题，请联系 GitHub 支持。 有关如何联系支持人员的详细信息，请参阅“[联系 GitHub 支持团队](/zh/support/contacting-github-support)”。

### DNS

域名系统 (DNS) 配置、解析或解析程序问题都可能导致出现问题。 建议你查看可用日志、供应商文档，或咨询管理员以获取进一步帮助。

### 防火墙

活动可能会被防火墙阻止。 如果发生此情况，建议你查看可用日志、供应商文档，或咨询管理员以获取进一步帮助。

### 代理

使用代理进行通信时，活动可能会失败。 最佳做法是查看可用日志、供应商文档，或咨询管理员以获取进一步帮助。

有关将运行器应用程序配置为使用代理的信息，请参阅“[将代理服务器与运行器一起使用](/zh/actions/how-tos/manage-runners/use-proxy-servers)”。

### 子网

使用子网时，或当子网与现有网络（例如虚拟云服务商网络、Docker 网络等）存在重叠时，可能会遇到问题。 在这些情况下，建议查看正在使用的网络拓扑和子网。

### 证书

自签名或自定义证书链以及证书存储可能导致出现问题。 可以检查正在使用的证书是否尚未过期且当前处于受信任状态。 可以使用 `curl` 或类似的工具检查证书。 还可查看可用日志、供应商文档，或咨询管理员以获取进一步帮助。

### IP 列表

IP 允许或拒绝列表可能会干扰预期的通信。 如果出现问题，应查看可用日志、供应商文档，或咨询管理员以获取进一步帮助。

有关 GitHub 的 IP 地址信息（例如 GitHub 托管的运行器所使用的 IP 地址），请参阅 [关于GitHub的 IP 地址](/zh/authentication/keeping-your-account-and-data-secure/about-githubs-ip-addresses)。

静态 IP 地址可用于由 GitHub 托管的大型运行器。 有关详细信息，请参阅“[管理较大的运行器](/zh/actions/how-tos/manage-runners/larger-runners/manage-larger-runners)”。

### 操作系统和软件应用程序

除了防火墙或代理之外，对 GitHub托管运行程序执行的自定义（例如安装其他软件包）可能会导致通信中断。 有关可用自定义选项的信息，请参阅“[自定义 GitHub 托管的运行器](/zh/actions/how-tos/manage-runners/github-hosted-runners/customize-runners)”。

* 对于自托管运行器，如需了解更多关于必要终结点的信息，请参阅“[自托管运行程序参考](/zh/actions/reference/runners/self-hosted-runners)”。

* 有关配置 WireGuard 的帮助，请参阅“[使用 WireGuard 创建网络覆盖层](/zh/actions/how-tos/manage-runners/github-hosted-runners/connect-to-a-private-network/connect-with-wireguard)”。

* 有关配置 OpenID Connect (OIDC) 的详细信息，请参阅“[将 API 网关与 OIDC 配合使用](/zh/actions/how-tos/manage-runners/github-hosted-runners/connect-to-a-private-network/connect-with-oidc)”。

### 适用于 GitHub 托管运行器的 Azure 专用网络

在您配置的 Azure 虚拟网络（VNET）设置中使用由 GitHub 托管的运行器时，可能会出现问题。

如需故障排除建议，请参阅 [](/zh/organizations/managing-organization-settings/troubleshooting-azure-private-network-configurations-for-github-hosted-runners-in-your-organization) 文档[排查组织中的 GitHub 托管运行器的 Azure 专用网络配置问题](/zh/enterprise-cloud@latest/admin/configuring-settings/configuring-private-networking-for-hosted-compute-products/troubleshooting-azure-private-network-configurations-for-github-hosted-runners-in-your-enterprise)GitHub Enterprise Cloud。