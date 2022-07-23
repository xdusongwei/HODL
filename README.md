HODL
====

一种自动化交易方式，使持仓可以进行波动套利。

```
项目公开的代码以及投资策略仅供学习参考，投资需谨慎。
公开项目为代码仓库的镜像同步，不会合并提交。
```

安装
---

使用 [pdm](https://pdm.fming.dev/latest/) 管理项目，安装依赖:

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
$ pdm run bot
```


编写新broker
------------

*   继承`BrokerApiBase`
*   如果需要初始化客户端，覆盖`__post_init__`方法
*   根据需要完成`BrokerApiMixin`的部分接口
*   设定broker的种类名称`BROKER_NAME`和broker的工作描述定义`META`数组
