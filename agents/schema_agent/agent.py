"""模块② Schema 检索：Embedding 向量相似度召回相关表（RAG），并生成相关表 DDL 注入下游 Prompt。

优先级：
  1. 向量检索：表结构 Embedding 索引 top-k 召回（端侧 ONNX 推理）；
  2. 降级回退：fastembed 不可用时，回退为 LLM 全量 Schema 语义裁剪。
"""
from __future__ import annotations

from core.base import Agent, load_agent_config
from core.schema_vector_store import QUERY_INSTRUCTION

LLM_PRUNE_SYSTEM = """你是 Schema 检索模块。根据用户意图从完整表结构中选出相关表，并输出这些表的 DDL。
只输出相关表的建表语句（CREATE TABLE ...;），不要输出解释。"""

AGENT_DIR = __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0]

_STORE = None  # SchemaVectorStore 单例（懒加载）


def _get_vector_store():
    """懒加载向量索引；fastembed 缺失或模型不可用时返回 None，由调用方降级。"""
    global _STORE
    if _STORE is None:
        try:
            from core.schema_vector_store import SchemaVectorStore
            _STORE = SchemaVectorStore()
        except Exception as e:  # 未安装 fastembed / 模型下载失败等
            print(f"[schema-agent] Embedding 向量检索不可用，降级为 LLM 语义裁剪: {e}")
            _STORE = False
    return _STORE or None


class SchemaAgent(Agent):
    def __init__(self, llm, mcp=None):
        super().__init__(llm, mcp, load_agent_config(AGENT_DIR))
        self.top_k = int(self.config.get("top_k", 3))

    # ---------- 主流程 ----------

    def run(self, intent: dict) -> dict:
        # 1) 通过 MCP 工具检索完整 Schema
        full = self.mcp.call_tool("get_schema", {})
        if not full.get("ok"):
            return {"ok": False, "error": f"get_schema 失败: {full.get('error')}"}
        schema = full["schema"]
        question = intent.get("_question", "")

        # 2) 优先：Embedding 向量相似度检索（RAG）
        store = _get_vector_store()
        if store is not None:
            store.build_or_load(schema)
            top_tables = store.search(question, top_k=self.top_k)
            return {"ok": True, "schema": schema,
                    "relevant_ddl": self._build_ddl(schema, top_tables),
                    "retrieval": "embedding", "top_tables": top_tables}

        # 3) 降级：LLM 全量 Schema 语义裁剪
        user = (
            f"用户意图: {intent}\n\n完整表结构:\n"
            + "\n".join(f"- {t}: " + ", ".join(c["name"] for c in v["columns"]) for t, v in schema.items())
            + "\n\n请输出相关表的完整建表语句。"
        )
        return {"ok": True, "schema": schema, "relevant_ddl": self.llm.chat(LLM_PRUNE_SYSTEM, user),
                "retrieval": "llm-prune"}

    # ---------- 工具方法 ----------

    @staticmethod
    def _build_ddl(schema: dict, tables: list[str]) -> str:
        """根据检索到的相关表，确定性生成建表语句（不经 LLM，避免幻觉表结构）。"""
        stmts = []
        for t in tables:
            parts = [
                f'{c["name"]} {c["type"]}' + (" PRIMARY KEY" if c["pk"] else "")
                for c in schema[t]["columns"]
            ]
            stmts.append(f"CREATE TABLE {t} ({', '.join(parts)});")
        return "\n".join(stmts)

    @staticmethod
    def name() -> str:
        return "schema-agent"
