# 批准来自分支的工作流运行

您可以手动批准由参与者的拉取请求触发的工作流运行。

由参与者从分支拉取请求触发的工作流运行可能需要具有写权限的维护人员手动批准。 可以为[存储库](/zh/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository#controlling-changes-from-forks-to-workflows-in-public-repositories)、[组织](/zh/organizations/managing-organization-settings/disabling-or-limiting-github-actions-for-your-organization#configuring-required-approval-for-workflows-from-public-forks)或[企业](/zh/enterprise-cloud@latest/admin/enforcing-policies/enforcing-policies-for-your-enterprise/enforcing-policies-for-github-actions-in-your-enterprise#fork-pull-request-workflows-from-outside-collaborators)配置工作流审批要求。

已等待批准超过 30 天的工作流程运行将自动删除。

## 批准公共复刻中拉取请求的工作流程运行

具有写入权限的仓库维护者可以按照以下步骤审查和运行需要审批的来自贡献者的拉取请求工作流程。

1. 在仓库名称下，单击 <svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-git-pull-request" aria-label="git-pull-request" role="img"><path d="M1.5 3.25a2.25 2.25 0 1 1 3 2.122v5.256a2.251 2.251 0 1 1-1.5 0V5.372A2.25 2.25 0 0 1 1.5 3.25Zm5.677-.177L9.573.677A.25.25 0 0 1 10 .854V2.5h1A2.5 2.5 0 0 1 13.5 5v5.628a2.251 2.251 0 1 1-1.5 0V5a1 1 0 0 0-1-1h-1v1.646a.25.25 0 0 1-.427.177L7.177 3.427a.25.25 0 0 1 0-.354ZM3.75 2.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm0 9.5a.75.75 0 1 0 0 1.5.75.75 0 0 0 0-1.5Zm8.25.75a.75.75 0 1 0 1.5 0 .75.75 0 0 0-1.5 0Z"></path></svg>“Pull requests”\*\*\*\*。

   ![存储库的主页的屏幕截图。 在水平导航栏中，标记为“拉取请求”的选项卡以深橙色标出。](/assets/images/help/repository/repo-tabs-pull-requests-global-nav-update.png)
2. 在拉取请求列表中，单击要审查的拉取请求。
3. 在拉取请求上，单击“<svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-file-diff" aria-label="file-diff" role="img"><path d="M1 1.75C1 .784 1.784 0 2.75 0h7.586c.464 0 .909.184 1.237.513l2.914 2.914c.329.328.513.773.513 1.237v9.586A1.75 1.75 0 0 1 13.25 16H2.75A1.75 1.75 0 0 1 1 14.25Zm1.75-.25a.25.25 0 0 0-.25.25v12.5c0 .138.112.25.25.25h10.5a.25.25 0 0 0 .25-.25V4.664a.25.25 0 0 0-.073-.177l-2.914-2.914a.25.25 0 0 0-.177-.073ZM8 3.25a.75.75 0 0 1 .75.75v1.5h1.5a.75.75 0 0 1 0 1.5h-1.5v1.5a.75.75 0 0 1-1.5 0V7h-1.5a.75.75 0 0 1 0-1.5h1.5V4A.75.75 0 0 1 8 3.25Zm-3 8a.75.75 0 0 1 .75-.75h4.5a.75.75 0 0 1 0 1.5h-4.5a.75.75 0 0 1-.75-.75Z"></path></svg> Files changed”\*\*\*\*。

   ![拉取请求的选项卡的屏幕截图。 “已更改的文件”选项卡以深橙色突出显示。](/assets/images/help/pull_requests/pull-request-tabs-changed-files.png)
4. 检查拉取请求中的拟议更改，确保您在拉取请求分支上自由运行您的工作流程。 应特别注意 `.github/workflows/` 目录中影响工作流文件的任何拟议更改。
5. 如果熟悉在拉取请求分支上运行工作流，请单击右上角标记为 **“等待审批**”的按钮，这将打开 **“合并状态** ”面板。
6. 查找并单击“ **批准工作流”以运行**。