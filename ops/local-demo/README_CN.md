# 本地 Neo4j 演示

用五个合成实体和三条关系跑通图谱工作台及 Spring API。样例包括有效成分、登记记录、作物、病害和一组共享别名。

## 启动 Neo4j

解压 Neo4j Community 4.4.x，给 Neo4j 准备 Java 11。在新建的本机测试实例中配置账号，再启动控制台。Windows 下可以使用便携 ZIP。[Neo4j 4.4 Windows 安装文档](https://neo4j.com/docs/operations-manual/4.4/installation/windows/)

~~~powershell
$neo = 'C:\path\to\neo4j-community-4.4.x'
$env:JAVA_HOME = 'C:\path\to\jdk-11'
& "$neo\bin\neo4j.bat" console
~~~

## 导入和查询

在另一个 PowerShell 中进入仓库根目录，按实际端口修改 Bolt 地址。Cypher Shell 会提示输入测试库密码。重复导入复用相同的样例节点和关系。

~~~powershell
$neo = 'C:\path\to\neo4j-community-4.4.x'
$env:JAVA_HOME = 'C:\path\to\jdk-11'
$bolt = 'bolt://127.0.0.1:7687'
& "$neo\bin\cypher-shell.bat" -a $bolt -u neo4j -f '.\ops\local-demo\seed.cypher'
~~~

将 `api/.env.local` 中的 `NEO4J_URI`、`NEO4J_USERNAME` 和 `NEO4J_PASSWORD` 填为同一测试库的连接信息。启动 API 后，下面两项分别检查实体查询和经登记记录连接的两跳路径。图谱查询可以在 DeepSeek 关闭时使用。

~~~powershell
Invoke-RestMethod 'http://127.0.0.1:4399/api/graph/search?keyword=AGRIREG-DEMO-001'
Invoke-RestMethod 'http://127.0.0.1:4399/api/graph/path?source=AgriReg%20Demo%20A&target=AgriReg%20Demo%20Crop'
~~~

如果已经有原项目的可用 Neo4j 库，可以直接把 API 配置指向该库。有原始 dump 时，在独立实例中恢复后接入。保存和重建数据的约束见 [图谱数据说明](../../DATA_NOT_INCLUDED.md)。
