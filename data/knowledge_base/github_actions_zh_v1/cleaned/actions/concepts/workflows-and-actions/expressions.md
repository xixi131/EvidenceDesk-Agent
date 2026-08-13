# 表达式

你可以对工作流和操作中的表达式求值。

## 关于表达式

您可以使用表达式程序化设置工作流程文件中的环境变量和访问上下文。 表达式可以是文字值、上下文引用或函数的任意组合。 您可以使用运算符组合文字、上下文引用和函数。 有关上下文的详细信息，请参阅“[上下文参考](https://docs.github.com/zh/actions/reference/workflows-and-actions/contexts)”。

表达式通常与工作流文件中的条件 `if` 关键字一起使用，以确定是否应运行步骤。 如果 `if` 条件为 `true`，该步骤将运行。

您需要使用特定语法指示 GitHub 对表达式求值，而不是将其视为字符串。

`${{ <expression> }}`

> 注意：
> 此规则的例外情况是：当你在 `if` 子句中使用表达式时，通常可以选择省略 `${{` 和 `}}`。 有关 `if` 条件的详细信息，请参阅“[GitHub Actions 的工作流语法](https://docs.github.com/zh/actions/reference/workflows-and-actions/workflow-syntax#jobsjob_idif)”。

> 警告：
> 创建工作流和操作时，应始终考虑代码是否可能执行潜在攻击者的不受信任的输入。 某些上下文应被视为不受信任的输入，因为攻击者可能会插入自己的恶意内容。 有关详细信息，请参阅“[安全使用指南](https://docs.github.com/zh/actions/reference/security/secure-use#good-practices-for-mitigating-script-injection-attacks)”。

### 设置环境变量的示例

```yaml
env:
  MY_ENV_VAR: ${{ <expression> }}
```

## 其他阅读材料

有关可在工作流和操作中使用的表达式的技术参考信息，请参阅 [对工作流和操作中的表达式求值](https://docs.github.com/zh/actions/reference/workflows-and-actions/expressions)。
