# 自托管运行程序

您可以托管自己的运行器，并自定义在 GitHub Actions 工作流中运行作业所使用的环境。

自托管运行器是一个由你部署和管理、用于在 GitHub Actions 上执行来自 GitHub 的作业的系统。

自托管运行器

* 与 GitHub 托管的运行器相比，您可以更好地控制硬件、操作系统和软件工具。 请注意，你负责更新作系统和其他所有软件。
* 允许你使用公司已维护和付费使用的计算机和服务。
* 可随意与 GitHub Actions 一起使用，但你负责维护运行程序计算机的成本。
* 使你可以创建满足自身需求的自定义硬件配置，具备所需的处理能力或内存以运行更大型的作业，并可安装你本地网络中可用的软件。
* 仅接收自托管运行器应用程序的自动更新，但你可以禁用运行器的自动更新。
* 无需为每个作业执行创建一个干净的实例。
* 可以是物理设备、虚拟设备，可以在容器中、在本地或在云中。

你可以在管理层次结构的各个层级使用自托管运行器。 仓库级运行器专用于处理单个仓库的作业，而组织级运行器可以处理组织中多个仓库的作业。 组织所有者可以选择哪些仓库被允许创建仓库级自托管运行器。 请参阅“[禁用或限制组织的 GitHub Actions](https://docs.github.com/zh/organizations/managing-organization-settings/disabling-or-limiting-github-actions-for-your-organization#limiting-the-use-of-self-hosted-runners)”。 最后，企业级运行器可以分配到企业帐户中的多个组织。

## 后续步骤

若要在工作区中设置自托管运行器，请参阅 [添加自托管的运行器](https://docs.github.com/zh/actions/how-tos/manage-runners/self-hosted-runners/add-runners)。

如需查找有关自托管运行器的要求和受支持的软件和硬件的信息，请参阅 [自托管运行程序参考](https://docs.github.com/zh/actions/reference/runners/self-hosted-runners)。
