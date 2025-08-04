#!/usr/bin/env python3
"""
文本分块索引工具使用示例

简化版演示，展示 TextChunkIndexerTool 的核心功能：
- 智能文本分块
- 语义搜索（如果有embedding模型）
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from HomeSystem.graph.tool.text_chunk_indexer import TextChunkIndexerTool
import json


def main():
    print("文本分块索引工具使用示例")
    print("=" * 50)
    
    # 创建工具实例（自动加载本地embedding模型）
    print("🚀 初始化工具...")
    indexer = TextChunkIndexerTool()
    
    # 检查embedding模型状态
    embedding_model = getattr(indexer, 'embeddings_model', None)
    if embedding_model:
        print("✅ 自动加载了embedding模型，支持语义搜索")
    else:
        print("⚠️ 未加载embedding模型，仅支持文本分块")
    
    # 示例文档：技术说明
    document = """
# API接口文档

## 用户认证
用户认证采用JWT令牌机制。客户端需要在请求头中包含Authorization字段，
格式为 "Bearer <token>"。令牌有效期为24小时。

## 数据查询API
GET /api/data - 获取数据列表
支持分页参数：page（页码）和limit（每页大小）
返回格式为JSON，包含data数组和pagination信息。

## 数据创建API  
POST /api/data - 创建新数据
请求体需要包含name、type、value等必填字段。
创建成功返回201状态码和新创建的数据对象。

## 错误处理
API使用标准HTTP状态码表示结果：
- 200: 成功
- 400: 请求参数错误
- 401: 认证失败
- 403: 权限不足
- 500: 服务器错误

所有错误响应都包含error字段，提供详细的错误信息。

## 限流策略
API采用令牌桶算法进行限流，每个用户每分钟最多100次请求。
超出限制将返回429状态码，需要等待一分钟后重试。
"""
    
    print("📄 处理文档并生成分块...")
    
    # 1. 基本分块
    result = indexer._run(text_content=document)
    data = json.loads(result)
    
    print(f"✅ 生成了 {data.get('total_chunks', 0)} 个分块")
    print(f"分块策略: {data.get('chunk_strategy', 'unknown')}")
    
    # 显示分块信息
    chunks = data.get('chunks', [])
    for i, chunk in enumerate(chunks):
        content_preview = chunk.get('content', '')[:80].replace('\n', '\\n')
        print(f"  分块 {i+1}: {content_preview}...")
    
    # 2. 语义搜索演示
    print(f"\n🔍 语义搜索演示:")
    
    search_queries = [
        "如何进行用户认证？",
        "API限流是怎么实现的？",
        "创建数据需要什么参数？"
    ]
    
    for query in search_queries:
        print(f"\n查询: {query}")
        
        search_result = indexer._run(
            text_content=document,
            query=query
        )
        
        search_data = json.loads(search_result)
        results = search_data.get('search_results', [])
        
        if results:
            best_match = results[0]
            similarity = best_match.get('similarity_score', 0)
            content = best_match.get('content', '')[:120]
            print(f"  📄 匹配内容 (相似度: {similarity:.3f}): {content}...")
        else:
            if embedding_model:
                print(f"  ❌ 未找到相关内容")
            else:
                print(f"  ⚠️ 无法进行语义搜索（embedding模型未加载）")
    
    print(f"\n{'=' * 50}")
    print("✅ 示例完成！")
    
    # 3. 工具集成提示
    print(f"\n💡 LangGraph集成使用方法:")
    print(f"```python")
    print(f"from HomeSystem.graph.tool import TextChunkIndexerTool")
    print(f"")
    print(f"# 方式1: 自动模式（推荐）- 自动加载ollama.BGE_M3")
    print(f"tool = TextChunkIndexerTool()")
    print(f"")
    print(f"# 方式2: 手动指定embedding模型")
    print(f"from HomeSystem.graph.llm_factory import LLMFactory")
    print(f"factory = LLMFactory()")
    print(f"embedding_model = factory.create_embedding('ollama.BGE_M3')")
    print(f"tool = TextChunkIndexerTool(embeddings_model=embedding_model)")
    print(f"")
    print(f"# 方式3: 禁用自动embedding（仅分块功能）")
    print(f"tool = TextChunkIndexerTool(auto_embedding=False)")
    print(f"")
    print(f"# 在LangGraph节点中使用")
    print(f"result = tool._run(")
    print(f"    text_content='您的文档内容',")
    print(f"    query='搜索查询'  # 可选，需要embedding支持")
    print(f")")
    print(f"```")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n❌ 运行出错: {str(e)}")
        import traceback
        traceback.print_exc()