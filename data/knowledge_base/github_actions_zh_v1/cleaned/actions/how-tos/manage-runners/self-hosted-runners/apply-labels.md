# 将标签与自托管运行程序结合使用

您可以使用标签以基于其特性来组织自托管运行器。

有关如何使用标签将作业路由到特定类型的自托管运行器的信息，请参阅 [在工作流中使用自托管运行程序](https://docs.github.com/zh/actions/how-tos/manage-runners/self-hosted-runners/use-in-a-workflow)。 你也可以将作业路由到特定组中的运行器。 有关详细信息，请参阅“[选择作业的运行器](https://docs.github.com/zh/actions/how-tos/write-workflows/choose-where-workflows-run/choose-the-runner-for-a-job#choosing-runners-in-a-group)”。

自托管运行器可位于存储库、组织或 GitHub 上的企业帐户设置中。 要管理自托管运行器，您必须拥有以下权限，具体取决于添加自托管运行器的位置：

* **用户存储库**：你必须是存储库所有者。
* **组织**：你必须是组织所有者。
* **组织存储库**：你必须是组织所有者，或者拥有对存储库的管理员访问权限。

## 创建自定义标签

您可以在仓库以及组织级别为运行器创建自定义标签。

* [为存储库运行器创建自定义标签](#creating-a-custom-label-for-a-repository-runner)
* [为组织级运行器创建自定义标签](#creating-a-custom-label-for-an-organization-runner)

> 注意：
> 标签不区分大小写。

### 为存储库运行器创建自定义标签

1. 导航到已注册自托管运行器组的存储库的主页。
2. 单击“gear Settings”\*\*\*\*。
3. 在左侧边栏中，单击“play Actions”，然后单击“Runners”\*\*\*\*\*\*\*\*。
4. 在运行器列表中，单击要配置的运行器的名称。
5. 在“Labels（标签）”部分，单击 The Gear icon。
6. 在“查找或创建标签”字段中，键入新标签的名称，然后单击“创建新标签”。 将创建自定义标签并分配给自托管运行器。 可以从自托管的运行器中删除自定义标签，但当前无法手动删除。 未分配给运行器的任何未使用标签将在 24 小时内被自动删除。

### 为组织运行器创建自定义标签

1. 导航到已注册自托管运行器组的组织的主页。
2. 单击“gear Settings”。\*\*\*\*
3. 在左侧边栏中，单击“play Actions”，然后单击“Runners”\*\*\*\*\*\*\*\*。
4. 在运行器列表中，单击要配置的运行器的名称。
5. 在“Labels（标签）”部分，单击 The Gear icon。
6. 在“查找或创建标签”字段中，键入新标签的名称，然后单击“创建新标签”。 将创建自定义标签并分配给自托管运行器。 可以从自托管的运行器中删除自定义标签，但当前无法手动删除。 未分配给运行器的任何未使用标签将在 24 小时内被自动删除。

## 分配标签给自托管的运行器

可以在存储库和组织级别将标签分配给自托管运行器。

* [为存储库运行器分配标签](#assigning-a-label-to-a-repository-runner)
* [为组织运行器分配标签](#assigning-a-label-to-an-organization-runner)

### 为存储库运行器分配标签

1. 导航到已注册自托管运行器组的存储库的主页。
2. 单击“gear Settings”\*\*\*\*。
3. 在左侧边栏中，单击“play Actions”，然后单击“Runners”\*\*\*\*\*\*\*\*。
4. 在“Labels（标签）”部分，单击 The Gear icon。
5. 要将标签分配给您的自托管运行器，在“Find or create a label（查找或创建标签）”字段中单击标签。

### 为组织运行器分配标签

1. 导航到已注册自托管运行器组的组织的主页。
2. 单击“gear Settings”。\*\*\*\*
3. 在左侧边栏中，单击“play Actions”，然后单击“Runners”\*\*\*\*\*\*\*\*。
4. 在“Labels（标签）”部分，单击 The Gear icon。
5. 要将标签分配给您的自托管运行器，在“Find or create a label（查找或创建标签）”字段中单击标签。

## 从自托管运行器中移除自定义标签

可以在存储库 和组织 级别从自承载运行程序中删除自定义标签。

* [从存储库运行器中删除自定义标签](#removing-a-custom-label-from-a-repository-runner)
* [从组织运行程序中删除自定义标签](#removing-a-custom-label-from-an-organization-runner)

### 从存储库运行器中删除自定义标签

1. 导航到已注册自托管运行器组的存储库的主页。
2. 单击“gear Settings”\*\*\*\*。
3. 在左侧边栏中，单击“play Actions”，然后单击“Runners”\*\*\*\*\*\*\*\*。
4. 在“Labels（标签）”部分，单击 The Gear icon。
5. 在“查找或创建标签”字段中，分配的标签标有 The Check icon 图标。 单击标记的标签以将其从您的自托管运行器取消分配。

### 从组织运行器中删除自定义标签

1. 导航到已注册自托管运行器组的组织的主页。
2. 单击“gear Settings”。\*\*\*\*
3. 在左侧边栏中，单击“play Actions”，然后单击“Runners”\*\*\*\*\*\*\*\*。
4. 在“Labels（标签）”部分，单击 The Gear icon。
5. 在“查找或创建标签”字段中，分配的标签标有 The Check icon 图标。 单击标记的标签以将其从您的自托管运行器取消分配。

## 以编程方式分配标签

可以在创建运行器后或其初始配置期间以编程方式将标签分配给自承载运行器。

* 若要以编程方式将标签分配给现有自承载运行器，必须使用 REST API。 有关详细信息，请参阅“[自托管运行器的 REST API 终结点](https://docs.github.com/zh/rest/actions/self-hosted-runners)”。
* 若要在初始运行器配置期间以编程方式将标签分配给自承载运行器，可以使用 `config` 参数将标签名称传递给 `labels` 脚本。

  > 注意：
  > 不能使用 `config` 脚本将标签分配给现有自托管运行器。

  例如，此命令在配置新的自承载运行器时分配名为 `gpu` 的标签：

  ```shell
  ./config.sh --url <REPOSITORY_URL> --token <REGISTRATION_TOKEN> --labels gpu
  ```

  如果标签不存在，则创建该标签。 还可使用此方法为运行器（例如 `x64` 或 `linux`）分配默认标签。 使用配置脚本分配默认标签时，GitHub Actions 会直接接受这些标签，而不会验证运行器实际使用的是否是该操作系统或架构。

  您可以使用逗号分隔来分配多个标签。 例如：

  ```shell
  ./config.sh --url <REPOSITORY_URL> --token <REGISTRATION_TOKEN> --labels gpu,x64,linux
  ```

  > 注意：
  > 如果你替换现有运行器，则必须重新分配所有自定义标签。
