# 上下文

了解在 GitHub Actions 中的上下文。

## 关于上下文

上下文是一种访问工作流运行、变量、运行器环境、作业及步骤相关信息的方式。 每个上下文都是一个包含属性的对象，可以是字符串或其他对象。

在不同的工作流运行条件下，上下文、对象和属性大不相同。 例如，`matrix` 上下文仅针对 [矩阵](https://docs.github.com/zh/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idstrategymatrix)中的作业进行填充。

您可以使用表达式语法访问上下文。 有关详细信息，请参阅“[对工作流和操作中的表达式求值](https://docs.github.com/zh/actions/reference/workflows-and-actions/expressions)”。

`${{ <context> }}`

> 警告：
> 创建工作流和操作时，应始终考虑代码是否可能执行潜在攻击者的不受信任的输入。 某些上下文应被视为不受信任的输入，因为攻击者可能会插入自己的恶意内容。 有关详细信息，请参阅“[安全使用指南](https://docs.github.com/zh/actions/reference/security/secure-use#good-practices-for-mitigating-script-injection-attacks)”。

## 确定何时使用上下文

GitHub Actions 包括名为 *上下文* 的变量的集合和称为 \_默认变量\_的类似变量集合。 这些变量预期用于工作流程中的不同点：

* **默认环境变量**：这些环境变量仅存在于执行作业的运行器上。 有关详细信息，请参阅“[变量参考](https://docs.github.com/zh/actions/reference/workflows-and-actions/variables#default-environment-variables)”。
* **上下文**：你可以在工作流的任何时间点使用大多数上下文，包括当\_默认变量\_不可用时。 例如，你可以使用带表达式的上下文执行初始处理，然后将作业路由到运行器以供执行；这允许你使用带有条件 `if` 关键字的上下文来确定步骤是否应运行。 作业运行后，还可以从执行作业的运行器（如 `runner.os`）检索上下文变量。 有关可在工作流中使用不同上下文的位置的详细信息，请参阅 [上下文参考](https://docs.github.com/zh/actions/reference/workflows-and-actions/contexts#context-availability)。

下面的示例演示了这些不同类型的变量如何在一个作业中一起使用：

```yaml copy
name: CI
on: push
jobs:
  prod-check:
    if: ${{ github.ref == 'refs/heads/main' }}
    runs-on: ubuntu-latest
    steps:
      - run: echo "Deploying to production server on branch $GITHUB_REF"
```

在此示例中，`if` 语句检查 [`github.ref`](https://docs.github.com/zh/actions/reference/workflows-and-actions/contexts#github-context) 上下文以确定当前分支名称；如果名称为 `refs/heads/main`，则执行后续步骤。 `if` 检查由 GitHub Actions 处理，仅当结果为 `true` 时作业才会发送给运行器。 将作业发送到运行器后，将执行该步骤，并引用运行器中的 [`$GITHUB_REF`](https://docs.github.com/zh/actions/how-tos/write-workflows/choose-what-workflows-do/use-variables) 变量。
