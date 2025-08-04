"""
高质量文本分块索引工具

基于LangGraph和LangChain的最佳实践，提供多策略文本分块和语义搜索功能。
支持递归分块、语义分块、固定大小分块等策略，集成向量存储和语义检索。
"""

import json
import re
import numpy as np
from typing import Dict, Any, List, Type, Optional
from abc import ABC, abstractmethod
from langchain_core.tools import BaseTool
from langchain_core.documents import Document
try:
    from langchain_text_splitters import RecursiveCharacterTextSplitter
except ImportError:
    # Fallback for older langchain versions
    from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)


class TextChunkIndexerInput(BaseModel):
    """文本分块索引工具输入模型"""
    text_content: str = Field(description="要分块索引的文本内容")
    query: Optional[str] = Field(default=None, description="检索查询，如果提供则返回最相关内容")


class BaseChunker(ABC):
    """分块器基类"""
    
    @abstractmethod
    def chunk_text(self, text: str, chunk_size: int, chunk_overlap: int) -> List[Dict[str, Any]]:
        """分块文本"""
        pass


class RecursiveChunker(BaseChunker):
    """递归字符分块器
    
    基于LangChain的RecursiveCharacterTextSplitter实现，
    按照层次化分隔符进行智能分割，保持语义完整性。
    """
    
    def __init__(self):
        self.separators = ["\n\n", "\n", " ", ""]
    
    def chunk_text(self, text: str, chunk_size: int, chunk_overlap: int) -> List[Dict[str, Any]]:
        """使用递归字符分割器分块文本"""
        try:
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=self.separators,
                length_function=len
            )
            
            chunks = splitter.split_text(text)
            result = []
            
            current_pos = 0
            for i, chunk in enumerate(chunks):
                # 找到当前块在原文中的位置
                start_pos = text.find(chunk, current_pos)
                if start_pos == -1:
                    start_pos = current_pos
                
                end_pos = start_pos + len(chunk)
                current_pos = start_pos + len(chunk) - chunk_overlap
                
                result.append({
                    "content": chunk.strip(),
                    "chunk_id": f"recursive_chunk_{i}",
                    "start_pos": start_pos,
                    "end_pos": end_pos,
                    "chunk_size": len(chunk),
                    "metadata": {
                        "strategy": "recursive",
                        "separators_used": self.separators
                    }
                })
            
            return result
            
        except Exception as e:
            logger.error(f"递归分块过程中发生错误: {str(e)}")
            return []


class SemanticChunker(BaseChunker):
    """语义分块器
    
    基于句子embedding相似度进行动态分块，
    在语义变化点分割文本，保持语义连贯性。
    """
    
    def __init__(self, embeddings_model=None):
        self.embeddings_model = embeddings_model
        self.sentence_pattern = re.compile(r'[.!?]+\s+')
    
    def chunk_text(self, text: str, chunk_size: int, chunk_overlap: int) -> List[Dict[str, Any]]:
        """使用语义相似度分块文本"""
        try:
            # 如果没有embedding模型，退化为句子级分块
            if not self.embeddings_model:
                return self._sentence_based_chunking(text, chunk_size, chunk_overlap)
            
            # 分割成句子
            sentences = self._split_sentences(text)
            if len(sentences) <= 1:
                return [{
                    "content": text,
                    "chunk_id": "semantic_chunk_0",
                    "start_pos": 0,
                    "end_pos": len(text),
                    "chunk_size": len(text),
                    "metadata": {"strategy": "semantic", "sentence_count": len(sentences)}
                }]
            
            # 计算句子embeddings
            embeddings = self._compute_embeddings(sentences)
            
            # 基于相似度变化找到分割点
            split_points = self._find_split_points(embeddings, sentences, chunk_size)
            
            # 生成分块
            chunks = self._create_chunks_from_splits(text, sentences, split_points, chunk_overlap)
            
            return chunks
            
        except Exception as e:
            logger.error(f"语义分块过程中发生错误: {str(e)}")
            return self._sentence_based_chunking(text, chunk_size, chunk_overlap)
    
    def _split_sentences(self, text: str) -> List[str]:
        """分割文本为句子"""
        sentences = self.sentence_pattern.split(text)
        return [s.strip() for s in sentences if s.strip()]
    
    def _sentence_based_chunking(self, text: str, chunk_size: int, chunk_overlap: int) -> List[Dict[str, Any]]:
        """基于句子的简单分块（fallback方法）"""
        sentences = self._split_sentences(text)
        chunks = []
        current_chunk = ""
        chunk_id = 0
        start_pos = 0
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= chunk_size or not current_chunk:
                current_chunk += sentence + " "
            else:
                # 保存当前块
                chunk_content = current_chunk.strip()
                chunks.append({
                    "content": chunk_content,
                    "chunk_id": f"semantic_chunk_{chunk_id}",
                    "start_pos": start_pos,
                    "end_pos": start_pos + len(chunk_content),
                    "chunk_size": len(chunk_content),
                    "metadata": {"strategy": "semantic_fallback"}
                })
                
                # 开始新块（考虑重叠）
                overlap_text = current_chunk[-chunk_overlap:] if chunk_overlap > 0 else ""
                current_chunk = overlap_text + sentence + " "
                start_pos = start_pos + len(chunk_content) - len(overlap_text)
                chunk_id += 1
        
        # 添加最后一块
        if current_chunk.strip():
            chunk_content = current_chunk.strip()
            chunks.append({
                "content": chunk_content,
                "chunk_id": f"semantic_chunk_{chunk_id}",
                "start_pos": start_pos,
                "end_pos": start_pos + len(chunk_content),
                "chunk_size": len(chunk_content),
                "metadata": {"strategy": "semantic_fallback"}
            })
        
        return chunks
    
    def _compute_embeddings(self, sentences: List[str]) -> List[List[float]]:
        """计算句子embeddings"""
        try:
            embeddings = self.embeddings_model.embed_documents(sentences)
            return embeddings
        except Exception as e:
            logger.error(f"计算embeddings时发生错误: {str(e)}")
            return []
    
    def _find_split_points(self, embeddings: List[List[float]], sentences: List[str], chunk_size: int) -> List[int]:
        """基于相似度变化找到分割点"""
        if len(embeddings) <= 1:
            return []
        
        # 计算相邻句子间的相似度差异
        similarities = []
        for i in range(len(embeddings) - 1):
            sim = self._cosine_similarity(embeddings[i], embeddings[i + 1])
            similarities.append(sim)
        
        # 找到相似度显著下降的点作为分割点
        split_points = []
        current_size = 0
        
        for i, sentence in enumerate(sentences):
            current_size += len(sentence)
            
            # 如果当前大小超过chunk_size，或者相似度显著下降，则分割
            if (current_size >= chunk_size and i < len(similarities) and 
                similarities[i] < np.percentile(similarities, 25)):
                split_points.append(i + 1)
                current_size = 0
        
        return split_points
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """计算余弦相似度"""
        try:
            vec1_arr = np.array(vec1)
            vec2_arr = np.array(vec2)
            return float(np.dot(vec1_arr, vec2_arr) / (np.linalg.norm(vec1_arr) * np.linalg.norm(vec2_arr)))
        except:
            return 0.0
    
    def _create_chunks_from_splits(self, text: str, sentences: List[str], 
                                 split_points: List[int], chunk_overlap: int) -> List[Dict[str, Any]]:
        """根据分割点创建分块"""
        chunks = []
        start_idx = 0
        
        for i, split_idx in enumerate(split_points + [len(sentences)]):
            chunk_sentences = sentences[start_idx:split_idx]
            chunk_content = " ".join(chunk_sentences).strip()
            
            if chunk_content:
                # 计算在原文中的位置
                start_pos = text.find(chunk_sentences[0]) if chunk_sentences else 0
                end_pos = start_pos + len(chunk_content)
                
                chunks.append({
                    "content": chunk_content,
                    "chunk_id": f"semantic_chunk_{i}",
                    "start_pos": start_pos,
                    "end_pos": end_pos,
                    "chunk_size": len(chunk_content),
                    "metadata": {
                        "strategy": "semantic",
                        "sentence_count": len(chunk_sentences)
                    }
                })
            
            # 考虑重叠
            if chunk_overlap > 0 and split_idx < len(sentences):
                overlap_sentences = min(chunk_overlap // 50, len(chunk_sentences))  # 假设平均句子长度50字符
                start_idx = max(0, split_idx - overlap_sentences)
            else:
                start_idx = split_idx
        
        return chunks


class FixedChunker(BaseChunker):
    """固定大小分块器
    
    简单的固定大小分块，计算效率最高，
    适合对语义完整性要求不高的场景。
    """
    
    def chunk_text(self, text: str, chunk_size: int, chunk_overlap: int) -> List[Dict[str, Any]]:
        """固定大小分块文本"""
        try:
            chunks = []
            start = 0
            chunk_id = 0
            
            while start < len(text):
                end = min(start + chunk_size, len(text))
                chunk_content = text[start:end].strip()
                
                if chunk_content:
                    chunks.append({
                        "content": chunk_content,
                        "chunk_id": f"fixed_chunk_{chunk_id}",
                        "start_pos": start,
                        "end_pos": end,
                        "chunk_size": len(chunk_content),
                        "metadata": {"strategy": "fixed"}
                    })
                    chunk_id += 1
                
                # 移动到下一个位置，考虑重叠
                start = end - chunk_overlap if chunk_overlap > 0 else end
                
                # 避免无限循环
                if start >= end:
                    break
            
            return chunks
            
        except Exception as e:
            logger.error(f"固定大小分块过程中发生错误: {str(e)}")
            return []


class TextChunkIndexerTool(BaseTool):
    """高质量文本分块索引工具
    
    支持多种分块策略和语义搜索功能。
    集成向量存储，支持基于embedding的相似度检索。
    """
    
    name: str = "text_chunk_indexer"
    description: str = "高质量文本分块和语义搜索工具，支持多种分块策略和向量检索"
    args_schema: Type[BaseModel] = TextChunkIndexerInput
    embeddings_model: Any = Field(default=None, exclude=True)
    
    def __init__(self, embeddings_model=None, auto_embedding=True, **kwargs):
        super().__init__(**kwargs)
        
        # 如果没有提供embedding模型且启用自动模式，尝试获取默认模型
        if embeddings_model is None and auto_embedding:
            try:
                from HomeSystem.graph.llm_factory import LLMFactory
                factory = LLMFactory()
                embeddings_model = factory.create_embedding()  # 使用默认的ollama.BGE_M3
                logger.info("✅ 自动加载embedding模型: ollama.BGE_M3")
            except Exception as e:
                logger.warning(f"⚠️ 无法自动加载embedding模型: {e}")
                embeddings_model = None
        
        object.__setattr__(self, 'embeddings_model', embeddings_model)
        object.__setattr__(self, 'vector_store', None)
        object.__setattr__(self, 'chunks_cache', [])
        
        # 初始化分块器
        chunkers = {
            "recursive": RecursiveChunker(),
            "semantic": SemanticChunker(embeddings_model),
            "fixed": FixedChunker()
        }
        object.__setattr__(self, 'chunkers', chunkers)
    
    def _run(self, text_content: str, query: Optional[str] = None) -> str:
        """执行文本分块和索引"""
        try:
            # 使用默认参数
            chunk_strategy = "recursive"
            chunk_size = 1000
            chunk_overlap = 200
            top_k = 5
            similarity_threshold = 0.0
            
            # 验证输入
            if not text_content or not text_content.strip():
                return json.dumps({
                    "error": "文本内容不能为空",
                    "chunks": [],
                    "search_results": [],
                    "total_chunks": 0
                }, ensure_ascii=False)
            
            chunkers = getattr(self, 'chunkers', {})
            # 选择分块策略
            if chunk_strategy not in chunkers:
                chunk_strategy = "recursive"
                logger.warning(f"未知的分块策略，使用默认的递归分块策略")
            
            # 执行分块
            chunker = chunkers[chunk_strategy]
            chunks = chunker.chunk_text(text_content, chunk_size, chunk_overlap)
            
            if not chunks:
                return json.dumps({
                    "error": "分块失败，未生成任何分块",
                    "chunks": [],
                    "search_results": [],
                    "total_chunks": 0
                }, ensure_ascii=False)
            
            # 缓存分块结果
            object.__setattr__(self, 'chunks_cache', chunks)
            
            # 如果提供了查询，执行语义搜索
            search_results = []
            if query:
                search_results = self._perform_search(query, top_k, similarity_threshold)
            
            # 构建结果
            result = {
                "chunks": chunks,
                "search_results": search_results,
                "total_chunks": len(chunks),
                "chunk_strategy": chunk_strategy,
                "chunk_stats": self._calculate_chunk_stats(chunks)
            }
            
            if query:
                result["query"] = query
                result["search_performed"] = True
            
            return json.dumps(result, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"文本分块索引过程中发生错误: {str(e)}")
            return json.dumps({
                "error": f"处理过程中发生错误: {str(e)}",
                "chunks": [],
                "search_results": [],
                "total_chunks": 0
            }, ensure_ascii=False)
    
    def _perform_search(self, query: str, top_k: int, similarity_threshold: float) -> List[Dict[str, Any]]:
        """执行语义搜索"""
        try:
            embeddings_model = getattr(self, 'embeddings_model', None)
            chunks_cache = getattr(self, 'chunks_cache', []) 
            vector_store = getattr(self, 'vector_store', None)
            
            if not embeddings_model or not chunks_cache:
                return []
            
            # 创建向量存储
            if not vector_store:
                documents = [
                    Document(
                        page_content=chunk["content"],
                        metadata={
                            "chunk_id": chunk["chunk_id"],
                            "start_pos": chunk["start_pos"],
                            "end_pos": chunk["end_pos"],
                            **chunk["metadata"]
                        }
                    )
                    for chunk in chunks_cache
                ]
                
                vector_store = FAISS.from_documents(documents, embeddings_model)
                object.__setattr__(self, 'vector_store', vector_store)
            
            # 执行相似度搜索
            results = vector_store.similarity_search_with_score(query, k=top_k)
            
            # 处理搜索结果
            search_results = []
            for doc, score in results:
                # 确保score是Python原生数值类型
                score_value = float(score) if hasattr(score, 'item') else float(score)
                similarity_score = 1 - score_value  # FAISS返回的是距离，需要转换为相似度
                
                if similarity_score >= similarity_threshold:
                    search_results.append({
                        "content": doc.page_content,
                        "similarity_score": round(similarity_score, 4),
                        "chunk_id": doc.metadata.get("chunk_id", "unknown"),
                        "start_pos": int(doc.metadata.get("start_pos", 0)),
                        "end_pos": int(doc.metadata.get("end_pos", 0)),
                        "metadata": {k: v for k, v in doc.metadata.items() 
                                   if k not in ["chunk_id", "start_pos", "end_pos"]}
                    })
            
            return search_results
            
        except Exception as e:
            logger.error(f"语义搜索过程中发生错误: {str(e)}")
            return []
    
    def _calculate_chunk_stats(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """计算分块统计信息"""
        try:
            if not chunks:
                return {}
            
            chunk_sizes = [chunk["chunk_size"] for chunk in chunks]
            
            return {
                "avg_chunk_size": round(np.mean(chunk_sizes), 2),
                "min_chunk_size": min(chunk_sizes),
                "max_chunk_size": max(chunk_sizes),
                "total_characters": sum(chunk_sizes),
                "size_std": round(np.std(chunk_sizes), 2)
            }
            
        except Exception as e:
            logger.error(f"计算统计信息时发生错误: {str(e)}")
            return {}
    
    def clear_cache(self):
        """清除缓存"""
        object.__setattr__(self, 'chunks_cache', [])
        object.__setattr__(self, 'vector_store', None)


def create_text_chunk_indexer_tool(embeddings_model=None, auto_embedding=True):
    """创建文本分块索引工具实例
    
    Args:
        embeddings_model: 手动指定的embedding模型，如果提供则忽略auto_embedding
        auto_embedding: 是否自动加载默认embedding模型(ollama.BGE_M3)
        
    Returns:
        TextChunkIndexerTool: 配置好的文本分块索引工具实例
    """
    return TextChunkIndexerTool(
        embeddings_model=embeddings_model, 
        auto_embedding=auto_embedding
    )