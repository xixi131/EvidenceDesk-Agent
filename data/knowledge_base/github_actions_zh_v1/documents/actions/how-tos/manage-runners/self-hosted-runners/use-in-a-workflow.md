# 在工作流中使用自托管运行程序

要在工作流中使用自托管运行器，你可以使用标签或组来为作业指定运行器。

## 查看存储库可用的运行器

如果对存储库具有 `repo: write` 访问权限，则可以查看存储库可用的运行器列表。

1. 在 GitHub 上，导航到存储库的主页面。
2. 在仓库名称下，单击“<svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-play" aria-label="play" role="img"><path d="M8 0a8 8 0 1 1 0 16A8 8 0 0 1 8 0ZM1.5 8a6.5 6.5 0 1 0 13 0 6.5 6.5 0 0 0-13 0Zm4.879-2.773 4.264 2.559a.25.25 0 0 1 0 .428l-4.264 2.559A.25.25 0 0 1 6 10.559V5.442a.25.25 0 0 1 .379-.215Z"></path></svg> Actions”\*\*\*\*。

   ![“github/docs”存储库的选项卡的屏幕截图。 “操作”选项卡以橙色边框突出显示。](/assets/images/help/repository/actions-tab-global-nav-update.png)
3. 在左边栏中的“Management”部分下，单击 <svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-server" aria-label="server" role="img"><path d="M1.75 1h12.5c.966 0 1.75.784 1.75 1.75v4c0 .372-.116.717-.314 1 .198.283.314.628.314 1v4a1.75 1.75 0 0 1-1.75 1.75H1.75A1.75 1.75 0 0 1 0 12.75v-4c0-.358.109-.707.314-1a1.739 1.739 0 0 1-.314-1v-4C0 1.784.784 1 1.75 1ZM1.5 2.75v4c0 .138.112.25.25.25h12.5a.25.25 0 0 0 .25-.25v-4a.25.25 0 0 0-.25-.25H1.75a.25.25 0 0 0-.25.25Zm.25 5.75a.25.25 0 0 0-.25.25v4c0 .138.112.25.25.25h12.5a.25.25 0 0 0 .25-.25v-4a.25.25 0 0 0-.25-.25ZM7 4.75A.75.75 0 0 1 7.75 4h4.5a.75.75 0 0 1 0 1.5h-4.5A.75.75 0 0 1 7 4.75ZM7.75 10h4.5a.75.75 0 0 1 0 1.5h-4.5a.75.75 0 0 1 0-1.5ZM3 4.75A.75.75 0 0 1 3.75 4h.5a.75.75 0 0 1 0 1.5h-.5A.75.75 0 0 1 3 4.75ZM3.75 10h.5a.75.75 0 0 1 0 1.5h-.5a.75.75 0 0 1 0-1.5Z"></path></svg>“Runners”\*\*\*\*。
4. 单击运行器列表顶部的**自托管**选项卡。
5. 查看存储库可用的自托管运行器列表。 此列表包括自托管运行器以及使用 Actions Runner Controller 创建的运行器缩放集。 有关详细信息，请参阅“[操作运行器控制器](/zh/actions/concepts/runners/actions-runner-controller)”。
6. （可选）要复制运行器标签以在工作流中使用，请单击运行器右侧的 <svg version="1.1" width="16" height="16" viewBox="0 0 16 16" class="octicon octicon-kebab-horizontal" aria-label="More options" role="img"><path d="M8 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3ZM1.5 9a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Zm13 0a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3Z"></path></svg>，然后单击“复制标签”。\*\*\*\*

> \[!NOTE]
> 企业和组织所有者可以在此页面创建运行器。 若要创建新的运行器，请单击运行器列表右上角的“新建运行器”\*\*\*\*，将运行器添加到存储库。
>
> 有关详细信息，请参阅 [管理较大的运行器](/zh/actions/how-tos/manage-runners/larger-runners/manage-larger-runners) 和 [添加自托管的运行器](/zh/actions/how-tos/manage-runners/self-hosted-runners/add-runners)。

## 使用默认标签路由作业

在被添加到 GitHub Actions 后，自托管运行器将自动收到某些标签。 这些被用于指出其操作系统和硬件平台：

* `self-hosted`：应用于自托管运行器的默认标签。
* `linux`、`windows` 或 `macOS`：根据操作系统应用。
* `x64`、`ARM` 或 `ARM64`：根据硬件体系结构应用。

您可以使用您工作流程的 YAML 将作业发送到这些标签的组合。 在此示例中，与所有三个标签匹配的自托管运行器将有资格运行该作业：

```yaml
runs-on: [self-hosted, linux, ARM64]
```

* `self-hosted` - 在自托管运行器上运行此作业。
* `linux` - 仅使用基于 Linux 的运行器。
* `ARM64` - 仅使用基于 ARM64 硬件的运行器。

若要创建没有默认标签的单独自托管运行器，请在创建运行器时传递 `--no-default-labels` 标志。

## 使用自定义标签路由作业

你可以随时创建自定义标签并将其分配给你的自托管运行器。 自定义标签允许你根据其标注将作业发送给特定的自托管运行器类型。

例如，如果某个作业需要特定类型的图形硬件，则可以创建名为 `gpu` 的自定义标签，并将其分配给安装了该硬件的运行器。 然后，与所有已分配的标签匹配的自托管运行器将有资格运行该作业。

此示例显示组合默认标签和自定义标签的作业：

```yaml
runs-on: [self-hosted, linux, x64, gpu]
```

* `self-hosted` - 在自托管运行器上运行此作业。
* `linux` - 仅使用基于 Linux 的运行器。
* `x64` - 仅使用基于 x64 硬件的运行器。
* `gpu` - 此自定义标签已被手动分配给安装了 GPU 硬件的自托管运行器。

这些标签累计运行，所以自托管运行器必须拥有所有四个标签才能处理该作业。

## 使用组来路由作业

在此示例中，运行器已添加到名为 `build-runners` 的组。
`runs-on` 键将作业发送到 `build-runners` 组中的任何可用运行器：

```yaml
name: learn-github-actions
on: [push]
jobs:
  check-bats-version:
    runs-on: 
      group: build-runners
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v4
        with:
          node-version: '14'
      - run: npm install -g bats
      - run: bats -v
```

## 使用标签和组来路由作业

组合组和标签时，运行器必须满足这两项要求才能运行作业。

在此示例中，`runs-on` 键结合了 `group` 和 `labels`，从而将该作业路由到组内任何具有匹配标签的可用运行器：

```yaml
name: learn-github-actions
on: [push]
jobs:
  check-bats-version:
    runs-on:
      group: ubuntu-runners
      labels: ubuntu-24.04-16core
    steps:
      - uses: actions/checkout@v6
      - uses: actions/setup-node@v4
        with:
          node-version: '14'
      - run: npm install -g bats
      - run: bats -v
```