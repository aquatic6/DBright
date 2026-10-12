# DBright · 端侧离线数据库智能体

**DBright** = DB + Bright —— 点亮你的本地数据。基于 **MoFA 模块化框架** 与 **MCP 协议** 的端侧离线数据库问答智能体。

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/protocol-MCP-blue)](https://modelcontextprotocol.io)
[![Offline](https://img.shields.io/badge/runtime-offline%20first-green)]()

基于 **MoFA 模块化框架** 与 **MCP 协议** 的端侧离线数据库问答智能体：用户以自然语言对本地 SQLite 数据库进行查询与分析，**全程离线运行，数据不出端**。

## 项目背景与目标

云端数据库问答（Text2SQL SaaS）存在三个痛点：

| 痛点 | 说明 |
|------|------|
| 依赖联网 | 弱网/内网/涉密环境无法使用 |
| 延迟高 | 网络往返 + 云端排队，交互体验差 |
| 数据出域风险 | 库表结构与业务数据上传云端，存在泄露风险 |

**目标**：设计一个端侧离线运行的数据库智能体，用户在本地以自然语言完成对 SQLite 数据库的查询与分析，数据全程不出端。模型通过本地 Ollama 运行，工具通过 MCP 协议封装，构建「生成 — 执行 — 纠错」的调用闭环。

## 架构设计

```
用户自然语言问题
      │
      ▼
┌─────────────┐   ┌──────────────────────────────────────┐
│ ① 意图理解   │   │           MCP Server (sqlite-tools)   │
│ Intent Agent │──▶│  · get_schema      表结构检索          │
└─────────────┘   │  · execute_sql     SQL 执行(只读)      │
      │           │  · report_error    错误反馈             │
      ▼           └──────────────────────────────────────┘
┌─────────────┐              ▲            │
│ ② Schema检索 │──向量索引───┘            ▼
│Schema Agent  │ top-k召回    ┌──────────────────────────┐
└─────────────┘           │ ③ SQL 生成与执行           │
      │                   │ SQL Agent                │
      ▼                   │  生成 SQL ──执行──▶ 报错? ──┐
┌─────────────┐           │     ▲            │         │
│ ④ 结果解释   │◀──────────│     └── 纠错重试 ◀────────┘
│Result Agent  │           └──────────────────────────┘
└─────────────┘
      │
      ▼
自然语言查询结果解释（端到端链路打通）
```

### 模块划分（MoFA 模块化）

| 模块 | 职责 | MCP 工具 |
|------|------|----------|
| `agents/intent_agent` | 意图理解：解析问题为结构化意图（指标、维度、筛选、时间范围） | - |
| `agents/schema_agent` | Schema 检索（RAG）：表结构 Embedding 向量相似度召回 top-k 相关表，生成相关表 DDL 注入 Prompt | `get_schema` |
| `agents/sql_agent` | SQL 生成与执行：生成 SQL、执行、捕获错误、反馈重试（闭环） | `execute_sql` / `report_error` |
| `agents/result_agent` | 结果解释：将查询结果翻译为自然语言结论 | - |

### Schema RAG：Embedding 向量相似度检索

1. 通过 MCP `get_schema` 获取全量表结构；
2. 将「表级文本 + 列级文本」分别编码为 Embedding（BGE-small-zh，**ONNX Runtime 本地推理**，约 100MB，无需 GPU/PyTorch），并附加轻量中英词表（`core/schema_glossary.py`，约 70 个通用数据库术语）提供中文语义锚点；
3. 查询向量与所有块向量余弦相似度，表得分 = 表块得分 + β × 列块最大得分（列级信号显著抑制同域干扰表）；
4. 向量索引按 Schema 内容哈希持久化到本地，库结构变更自动重建；fastembed 不可用时自动降级为 LLM 语义裁剪。

### 「生成 — 执行 — 纠错」闭环

1. SQL Agent 生成候选 SQL（严格 JSON 输出）；
2. 通过 MCP 调用 `execute_sql` 在**只读模式**下执行；
3. 若执行报错，调用 `report_error` 格式化错误信息并回传给 LLM；
4. LLM 依据错误反馈改写 SQL，最多重试 `max_retry` 次（默认 3 次）。

## 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install -r requirements.txt

# 本地运行模型（离线推理，可选 qwen2.5 / llama3.1 等）
ollama pull qwen2.5:7b
```

> 首次运行 Schema 检索时，fastembed 会自动下载 BGE-small-zh 模型（约 100MB）到本地缓存，之后完全离线。

### 2. 初始化演示数据库

```bash
python scripts/init_demo_db.py
```

生成 `data/demo.db`：包含 `employees` / `departments` / `orders` 三张演示表。

### 3. 启动问答

```bash
python run.py
```

示例对话：

```
You > 每个部门有多少人？按人数降序
Agent > 查询结果如下：技术部 12 人，运营部 8 人，人事部 3 人。技术部人数最多。
        （执行 SQL: SELECT d.name, COUNT(*) ...，耗时 3ms，全程本地执行）
```

## 基准测试（实测）

`python scripts/bench.py [--db data/big.db] [--top-k N] [--llm]`，基于自建 15 题基准（覆盖单表/多表 JOIN/聚合/筛选/排序）：

| 指标 | demo.db（3 表） | big.db（31 表，含同域干扰表） |
|------|----------------|------------------------------|
| recall@3（严格，必需表全部召回） | **100%** | **87%** |
| recall@5（严格） | 100% | **93%** |
| 检索延迟（单次） | 3.1 ms | 3.4 ms |
| 向量索引体积 | 28 KB | 369 KB |
| 索引冷构建耗时（一次性） | 51 ms | 825 ms |

> Part B（NL→SQL 执行准确率、端到端延迟）需本地 Ollama：`python scripts/bench.py --llm`。

## 配置

`config/agent_config.yml`：

```yaml
llm:
  base_url: "http://localhost:11434/v1"   # 本地 Ollama，OpenAI 兼容接口
  model: "qwen2.5:7b"
database:
  path: "data/demo.db"                     # 本地 SQLite，只读模式打开
pipeline:
  max_retry: 3                             # SQL 纠错最大重试次数
```

## 安全设计

- **只读执行**：MCP Server 以 `mode=ro` URI 打开 SQLite，从机制上杜绝写入/删表；
- **数据不出端**：LLM 推理（Ollama）与数据库均在本地，无任何网络外传；
- **Schema 裁剪**：仅将向量检索到的相关表 DDL 注入 Prompt，避免整库结构进入上下文；
- **索引不出端**：Embedding 模型与向量索引全部本地缓存，无任何外部向量数据库服务。

## 目录结构

```
├── run.py                          # 端到端流水线入口
├── config/agent_config.yml         # LLM / 数据库 / 流水线配置
├── core/
│   ├── base.py                     # MoFA Agent 基类
│   ├── llm.py                      # 本地 LLM 客户端（Ollama / OpenAI 兼容）
│   ├── mcp_client.py               # MCP 客户端封装
│   ├── schema_vector_store.py      # Schema 向量索引（表级+列级块，ONNX 端侧推理）
│   └── schema_glossary.py          # 轻量中英词表（通用数据库术语语义锚点）
├── mcp_servers/
│   └── sqlite_tools_server.py      # MCP Server：表结构检索 / SQL 执行 / 错误反馈
├── agents/
│   ├── intent_agent/               # 模块① 意图理解
│   ├── schema_agent/               # 模块② Schema 检索
│   ├── sql_agent/                  # 模块③ SQL 生成与执行（纠错闭环）
│   └── result_agent/               # 模块④ 结果解释
└── scripts/
    ├── init_demo_db.py             # 演示数据库初始化（3 表）
    ├── init_big_db.py              # 31 表演示库（电商干扰表，压测检索）
    ├── bench.py                    # 量化基准（recall/延迟/准确率，--llm 需 Ollama）
    ├── test_schema_retrieval.py    # Schema 检索测试
    ├── debug_retrieval.py          # 检索诊断（查看 top-k 召回）
    └── test_smoke.py               # MCP 链路冒烟测试
```

## 路线图

- [ ] 多轮对话上下文管理
- [ ] 查询结果图表生成（端侧渲染）
- [ ] 接入更多本地模型后端（llama.cpp / MLX）
- [ ] 基于 MoFA dora 节点化的分布式部署
