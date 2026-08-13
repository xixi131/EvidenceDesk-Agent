# 管理缓存

可以监视、筛选和删除从工作流创建的依赖项缓存。

本文介绍如何使用 GitHub Web 界面管理缓存，但你也可以管理它们：

* 使用 REST API。 请参阅“[用于GitHub Actions缓存的 REST API 终结点](https://docs.github.com/zh/rest/actions/cache)”。
* 使用命令行中的 `gh cache` 子命令。 查看 [GitHub CLI 文档](https://cli.github.com/manual/gh_cache)。

## 查看缓存条目

可以使用 Web 界面查看存储库的缓存条目列表。 在缓存列表中，可以看到每个缓存占用的磁盘空间量、创建缓存的时间以及上次使用缓存的时间。

1. 在 GitHub 上，导航到存储库的主页面。
2. 在仓库名称下，单击“play Actions”\*\*\*\*。

   ![“github/docs”存储库的选项卡的屏幕截图。 “操作”选项卡以橙色边框突出显示。](/assets/images/help/repository/actions-tab-global-nav-update.png)
3. 在左边栏中的“Management”部分下，单击“cache Caches”\*\*\*\*。
4. 查看存储库的缓存条目列表。

   * 若要搜索用于特定分支的缓存条目，请单击“分支”下拉菜单并选择一个分支。 缓存列表将显示用于所选分支的所有缓存。
   * 若要搜索具有特定缓存键的缓存条目，请使用“筛选缓存”字段中的语法 `key: key-name`。 缓存列表将显示使用键的所有分支中的缓存。

   ![缓存条目列表的屏幕截图。](/assets/images/help/repository/actions-cache-entry-list.png)

## 删除缓存条目

有权 `write` 访问存储库的用户可以使用 GitHub Web 界面删除缓存条目。

1. 在 GitHub 上，导航到存储库的主页面。
2. 在仓库名称下，单击“play Actions”\*\*\*\*。

   ![“github/docs”存储库的选项卡的屏幕截图。 “操作”选项卡以橙色边框突出显示。](/assets/images/help/repository/actions-tab-global-nav-update.png)
3. 在左边栏中的“Management”部分下，单击“cache Caches”\*\*\*\*。
4. 在要删除的缓存项的右侧，单击 Delete cache。

   ![缓存条目列表的屏幕截图。 用于删除缓存的垃圾桶图标以深橙色轮廓突出显示。](/assets/images/help/repository/actions-cache-delete.png)

## 强制删除缓存条目

缓存具有分支范围限制，这意味着某些缓存的使用选项有限。 有关缓存范围限制的详细信息，请参阅 [依赖项缓存参考](https://docs.github.com/zh/actions/reference/workflows-and-actions/dependency-caching)。 如果限制为特定分支的缓存使用大量存储配额，则可能会导致高频率创建和删除 `default` 分支中的缓存。

例如，存储库可以打开许多新的拉取请求，每个请求都有自己的缓存，这些缓存仅限于该分支。 这些缓存可能会占用该存储库的大部分缓存存储。
仓库达到其最大缓存存储后，缓存逐出策略将按照上次访问时间的顺序，从最早到最近，依次删除缓存以释放空间。 为了在发生这种情况时防止出现缓存抖动，您可以配置工作流，以比缓存逐出策略更高的频率删除缓存。 可以使用 GitHub CLI 该命令删除特定分支的缓存。

以下示例工作流使用 `gh cache` 在拉取请求关闭后删除分支创建的多达 100 个缓存。

要对跨存储库拉取请求或来自分支的拉取请求运行以下示例，可以使用 `pull_request_target` 事件触发该工作流。 如果确实使用 `pull_request_target` 来触发该工作流，请记住一些安全注意事项。 有关详细信息，请参阅“[触发工作流的事件](https://docs.github.com/zh/actions/reference/workflows-and-actions/events-that-trigger-workflows#pull_request_target)”。

```yaml
name: Cleanup github runner caches on closed pull requests
on:
  pull_request:
    types:
      - closed

jobs:
  cleanup:
    runs-on: ubuntu-latest
    permissions:
      actions: write
    steps:
      - name: Cleanup
        run: |
          echo "Fetching list of cache keys"
          cacheKeysForPR=$(gh cache list --ref $BRANCH --limit 100 --json id --jq '.[].id')

          ## Setting this to not fail the workflow while deleting cache keys.
          set +e
          echo "Deleting caches..."
          for cacheKey in $cacheKeysForPR
          do
              gh cache delete $cacheKey
          done
          echo "Done"
        env:
          GH_TOKEN: ${{ github.token }}
          GH_REPO: ${{ github.repository }}
          BRANCH: refs/pull/${{ github.event.pull_request.number }}/merge
```

或者，可以使用 API 按照自己的节奏自动列出或删除所有缓存。 有关详细信息，请参阅“[用于GitHub Actions缓存的 REST API 终结点](https://docs.github.com/zh/rest/actions/cache#about-the-cache-in-github-actions)”。
