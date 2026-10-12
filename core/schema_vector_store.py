"""Schema 向量检索：表结构 Embedding 相似度召回（端侧离线，ONNX 推理）。

工作原理：
  1. 将「表级文本 + 列级文本」分别编码为 Embedding（BGE-small-zh，本地 ONNX 推理）：
     - 表级：数据表 X，字段：col1、col2、...
     - 列级：X 表的 col 字段
  2. 查询向量与所有块向量做余弦相似度；表得分 = 表块得分 + β × 该表列块得分之和，
     取 top-k 相关表（列级信号可显著抑制同域干扰表，见 scripts/bench.py）；
  3. 向量索引按 Schema 内容哈希持久化到本地，库结构变更时自动重建。

全程本地运行，无需 GPU / PyTorch / 外部向量数据库服务。
"""
from __future__ import annotations

import hashlib
import pickle
from pathlib import Path

import numpy as np

from core.schema_glossary import gloss

# BGE 官方推荐的中文检索查询指令（fastembed 的 query_embed 不会自动添加）
QUERY_INSTRUCTION = "为这个句子生成表示以用于检索相关文章："

COL_WEIGHT = 0.3  # 列级信号聚合权重 β


class SchemaVectorStore:
    """Schema 向量索引：build_or_load() 建/载索引，search() 相似度召回表名。"""

    MODEL = "BAAI/bge-small-zh-v1.5"  # 约 100MB，端侧友好

    def __init__(self, cache_dir: str | Path = "data/schema_vec_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        from fastembed import TextEmbedding  # 延迟导入，未安装时由上层降级处理
        self._model = TextEmbedding(self.MODEL)
        self._names: list[str] = []        # 表名列表
        self._table_of: list[int] = []     # 每个向量块所属的表下标
        self._embs: np.ndarray | None = None

    # ---------- 索引构建 ----------

    @staticmethod
    def _chunks(name: str, info: dict) -> list[str]:
        """返回 [表级文本, 列1文本, 列2文本, ...]，并附加轻量词表的中文语义锚点。"""
        cols = [c["name"] for c in info["columns"]]
        cols_disp = "、".join(f"{c}({gloss(c)})" if gloss(c) else c for c in cols)
        g = gloss(name)
        head = f"数据表 {name}（{g}）" if g else f"数据表 {name}"
        texts = [f"{head}，字段：{cols_disp}"]
        texts += [f"{g or name} 表的 {c}({gloss(c)}) 字段" if gloss(c) else f"{name} 表的 {c} 字段" for c in cols]
        return texts

    @staticmethod
    def _schema_hash(schema: dict) -> str:
        return hashlib.md5(repr(sorted(schema.items())).encode("utf-8")).hexdigest()

    def build_or_load(self, schema: dict) -> None:
        """Schema 未变更则加载本地缓存的向量索引，否则重建并持久化。"""
        cache = self.cache_dir / f"{self._schema_hash(schema)}.pkl"
        if cache.exists():
            with open(cache, "rb") as f:
                self._names, self._table_of, self._embs = pickle.load(f)
            return
        names = list(schema.keys())
        table_of, texts = [], []
        for i, n in enumerate(names):
            chunks = self._chunks(n, schema[n])
            table_of += [i] * len(chunks)
            texts += chunks
        embs = np.asarray(list(self._model.embed(texts)), dtype=np.float32)
        embs /= np.linalg.norm(embs, axis=1, keepdims=True)  # 归一化，点积即余弦
        self._names, self._table_of, self._embs = names, table_of, embs
        with open(cache, "wb") as f:
            pickle.dump((names, table_of, embs), f)

    # ---------- 相似度检索 ----------

    def search(self, query: str, top_k: int = 3) -> list[str]:
        """返回与查询最相关的 top_k 个表名（表得分降序）。"""
        q = np.asarray(
            list(self._model.query_embed(QUERY_INSTRUCTION + query)), dtype=np.float32
        )[0]
        q /= np.linalg.norm(q)
        chunk_scores = self._embs @ q
        # 聚合到表级：表块 1 倍 + 列块 β 倍
        first = np.zeros(len(chunk_scores), dtype=bool)
        seen = set()
        for pos, t in enumerate(self._table_of):
            if t not in seen:
                first[pos] = True
                seen.add(t)
        # 聚合到表级：表块得分 + β × 列块最大得分（用 max 而非 sum，避免宽表被列数加权）
        table_scores = np.zeros(len(self._names), dtype=np.float32)
        np.add.at(table_scores, self._table_of, np.where(first, chunk_scores, 0.0))
        col_scores = np.where(first, -np.inf, chunk_scores)
        col_max = np.full(len(self._names), -np.inf, dtype=np.float32)
        np.maximum.at(col_max, self._table_of, col_scores)
        table_scores += COL_WEIGHT * np.where(np.isfinite(col_max), col_max, 0.0)
        idx = np.argsort(-table_scores)[:top_k]
        return [self._names[i] for i in idx]
