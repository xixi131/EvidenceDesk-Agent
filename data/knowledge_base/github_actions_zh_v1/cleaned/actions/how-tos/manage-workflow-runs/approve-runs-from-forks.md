# 批准来自分支的工作流运行

您可以手动批准由参与者的拉取请求触发的工作流运行。

由参与者从分支拉取请求触发的工作流运行可能需要具有写权限的维护人员手动批准。 可以为[存储库](https://docs.github.com/zh/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository#controlling-changes-from-forks-to-workflows-in-public-repositories)、[组织](https://docs.github.com/zh/organizations/managing-organization-settings/disabling-or-limiting-github-actions-for-your-organization#configuring-required-approval-for-workflows-from-public-forks)或[企业](https://docs.github.com/zh/enterprise-cloud@latest/admin/enforcing-policies/enforcing-policies-for-your-enterprise/enforcing-policies-for-github-actions-in-your-enterprise#fork-pull-request-workflows-from-outside-collaborators)配置工作流审批要求。

已等待批准超过 30 天的工作流程运行将自动删除。

## 批准公共复刻中拉取请求的工作流程运行

具有写入权限的仓库维护者可以按照以下步骤审查和运行需要审批的来自贡献者的拉取请求工作流程。

1. 在仓库名称下，单击 git-pull-request“Pull requests”\*\*\*\*。

   ![存储库的主页的屏幕截图。 在水平导航栏中，标记为“拉取请求”的选项卡以深橙色标出。](/assets/images/help/repository/repo-tabs-pull-requests-global-nav-update.png)
2. 在拉取请求列表中，单击要审查的拉取请求。
3. 在拉取请求上，单击“file-diff Files changed”\*\*\*\*。

   ![拉取请求的选项卡的屏幕截图。 “已更改的文件”选项卡以深橙色突出显示。](/assets/images/help/pull_requests/pull-request-tabs-changed-files.png)
4. 检查拉取请求中的拟议更改，确保您在拉取请求分支上自由运行您的工作流程。 应特别注意 `.github/workflows/` 目录中影响工作流文件的任何拟议更改。
5. 如果熟悉在拉取请求分支上运行工作流，请单击右上角标记为 **“等待审批**”的按钮，这将打开 **“合并状态** ”面板。
6. 查找并单击“ **批准工作流”以运行**。
