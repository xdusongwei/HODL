HODL
====

一种自动化交易方式，使持仓可以进行波动套利。

对于长期持(被)仓(套)股份，以特定价格作为基准价格，分段按不同涨幅高价卖出再一次性低价全部买回，可以利用股价波动得到一些切实的利润。

这个策略比较简单，只关心每日股价波动数据，没有技术分析，不需要量化信息，因此不会发生分析偏差导致额外的损失，而人只对SH入场建仓行为负责。

```
项目公开的代码以及其投资策略仅供学习参考，不为任何盈亏事实负有责任。
因此，利用此项目参与投资请意识其风险，包括技术上的。
```

```
公开项目为代码仓库的镜像同步，不会合并提交。
```

策略概述
------

对于无有效订单(不存在非当日已成交订单且不存在当日订单)的持仓(Store)，会首先设定执行计划的`基准价格`(base_price)。
基准价格可以参考下面的参数取最小值:
* 昨收价，默认必须
* 上一次买回的价格
* 当日的最低价

有了基准价格之后，根据买卖因子表，计算出每一档(level)需要设定的实际卖出价格，和对应的卖出股数，
并连同历史订单记录，以及其他设定，形成`执行计划`(plan)。
这个执行计划，在下出有效订单后，将会一直有效保存，直到某个交易日买回平仓完毕后，或者无历史有效的订单，被新计划重置。

每一个交易日结束后，执行计划中的无效订单(成交量为0)会从历史记录中去除。


安装
---

使用 [pdm](https://pdm-project.org/latest/) 管理项目，安装依赖:

```bash
$ pdm install
```


配置
----

在项目根目录创建`config.toml`或者使用环境变量`TRADE_BOT_CONFIG`指定配置文件位置。
配置文件根结构定义位于`VariableTools`，主要设置broker节定义交易券商服务的设置，以及store节定义持仓的关键信息和行为设定。


命令
----

启动服务:
```bash
$ pdm bot
```
