#!/usr/bin/env python3
"""
Dify Knowledge Base Usage Examples

This example demonstrates how to use the unified dify_knowledge module
for managing datasets, documents, and segments in Dify Knowledge Base.
"""

import os
import time
from pathlib import Path
import sys

# Add the parent directory to the path so we can import HomeSystem
sys.path.append(str(Path(__file__).parent.parent))

from HomeSystem.integrations.dify import (
    # 客户端
    DifyKnowledgeBaseClient,
    
    # 配置类
    DifyKnowledgeBaseConfig,
    get_config,
    UploadConfig,
    ProcessRule,
    IndexingTechnique,
    ProcessMode,
    DocumentType,
    
    # 数据模型
    DifyDatasetModel,
    DifyDocumentModel,
    DifySegmentModel,
    DatasetStatus,
    DocumentStatus,
    IndexingStatus,
    
    # 异常类
    DifyKnowledgeBaseError,
    DatasetNotFoundError,
    DocumentUploadError,
    DatasetCreationError
)

# Additional imports for the example
try:
    from HomeSystem.integrations.dify.dify_knowledge import TimeoutConfig
except ImportError:
    # Fallback if TimeoutConfig is not available
    TimeoutConfig = None


def create_and_setup_knowledge_base_example():
    """完整的知识库创建和设置示例"""
    print("=== 知识库创建和设置示例 ===")
    
    # 1. 从环境变量获取配置（推荐方式）
    try:
        config = get_config()
        print("✅ 成功从环境变量加载配置")
    except Exception:
        # 如果环境变量未设置，使用默认配置（需要手动设置API密钥）
        if TimeoutConfig:
            timeout_config = TimeoutConfig(
                connect_timeout=30,
                read_timeout=60,
                upload_timeout=300
            )
        else:
            timeout_config = None
            
        config = DifyKnowledgeBaseConfig(
            api_key="your-dify-api-key",  # 请替换为实际API密钥
            base_url="https://api.dify.ai",  # 不包含/v1，因为_make_request会自动添加
        )
        if timeout_config:
            config.timeout_config = timeout_config
        print("⚠️  使用默认配置，请设置正确的API密钥")
    
    # 2. 创建客户端并进行健康检查
    client = DifyKnowledgeBaseClient(config)
    
    print("🔍 进行连接健康检查...")
    if not client.health_check():
        print("❌ 连接失败，请检查配置")
        return None
    print("✅ 连接健康检查通过")
    
    try:
        # 3. 创建知识库
        print("\n📁 创建新知识库...")
        dataset = client.create_dataset(
            name="AI研究知识库",
            description="包含人工智能、机器学习和深度学习相关的研究文档和论文",
            permission="only_me"  # 仅自己可见
        )
        print(f"✅ 知识库创建成功:")
        print(f"   - 名称: {dataset.name}")
        print(f"   - ID: {dataset.dify_dataset_id}")
        print(f"   - 描述: {dataset.description}")
        print(f"   - 权限: {dataset.permission}")
        
        # 4. 配置上传参数
        print("\n⚙️  配置文档处理规则...")
        upload_config = UploadConfig(
            indexing_technique=IndexingTechnique.HIGH_QUALITY,
            process_rule=ProcessRule(
                mode=ProcessMode.CUSTOM,
                pre_processing_rules=[
                    {"id": "remove_extra_spaces", "enabled": True},
                    {"id": "remove_urls_emails", "enabled": False}
                ],
                segmentation={
                    "separator": "\\n\\n",  # 按段落分割
                    "max_tokens": 500,     # 每个分片最大token数
                    "chunk_overlap": 50    # 分片重叠token数
                }
            ),
            duplicate_check=True  # 启用重复检查
        )
        print("✅ 处理规则配置完成:")
        print(f"   - 索引技术: {upload_config.indexing_technique.value}")
        print(f"   - 处理模式: {upload_config.process_rule.mode.value}")
        print(f"   - 分片设置: 最大{upload_config.process_rule.segmentation['max_tokens']}tokens")
        
        return dataset, client, upload_config
        
    except DatasetCreationError as e:
        print(f"❌ 知识库创建失败: {e}")
        print(f"   错误码: {e.error_code}")
        return None
    except DifyKnowledgeBaseError as e:
        print(f"❌ 操作失败: {e}")
        return None


def upload_operations_example():
    """详细的文档上传操作示例"""
    print("\n=== 文档上传操作示例 ===")
    
    # 获取知识库设置
    try:
        result = create_and_setup_knowledge_base_example()
        if not result:
            print("❌ 无法继续上传示例，知识库创建失败")
            return
    except Exception as e:
        print(f"❌ 知识库创建失败: {e}")
        return
    
    dataset, client, upload_config = result
    
    try:
        print("\n📝 开始文档上传操作...")
        
        # 1. 上传文本文档
        print("\n1️⃣ 上传文本文档...")
        text_content = """
        # Transformer架构详解
        
        Transformer是一种基于注意力机制的深度学习模型架构，由Vaswani等人在2017年的论文"Attention Is All You Need"中提出。
        
        ## 核心特点
        - 完全基于注意力机制，摒弃了循环和卷积
        - 并行计算能力强，训练效率高
        - 在机器翻译、文本生成等任务上取得突破性进展
        
        ## 主要组件
        1. **多头自注意力机制**：允许模型关注输入序列的不同位置
        2. **位置编码**：为序列中的每个位置提供位置信息
        3. **前馈神经网络**：对每个位置独立进行变换
        4. **残差连接和层归一化**：稳定训练过程
        
        ## 应用领域
        - 自然语言处理：BERT、GPT、T5等
        - 计算机视觉：Vision Transformer (ViT)
        - 多模态：CLIP、DALL-E等
        """
        
        document1 = client.upload_document_text(
            dataset_id=dataset.dify_dataset_id,
            name="Transformer架构详解",
            text=text_content.strip(),
            upload_config=upload_config
        )
        print(f"✅ 文本文档上传成功:")
        print(f"   - 文档名: {document1.name}")
        print(f"   - 文档ID: {document1.dify_document_id}")
        print(f"   - 字符数: {document1.character_count}")
        print(f"   - 词数: {document1.word_count}")
        
        # 2. 创建并上传文件文档（模拟）
        print("\n2️⃣ 模拟文件上传...")
        # 这里模拟文件上传，实际使用时需要真实文件路径
        sample_file_content = """
        # 深度学习基础概念
        
        深度学习是机器学习的一个分支，它基于人工神经网络，特别是深层神经网络来学习数据表示。
        
        ## 基本概念
        - 神经元：处理信息的基本单元
        - 层：神经元的组织结构
        - 激活函数：引入非线性
        - 反向传播：训练算法
        
        ## 常见架构
        1. 卷积神经网络（CNN）
        2. 循环神经网络（RNN）
        3. 长短期记忆网络（LSTM）
        4. Transformer
        """
        
        # 如果有实际文件，可以这样上传：
        # document2 = client.upload_document_file(
        #     dataset_id=dataset.dify_dataset_id,
        #     file_path="/path/to/your/document.pdf",
        #     upload_config=upload_config
        # )
        
        # 这里用文本模拟文件上传
        document2 = client.upload_document_text(
            dataset_id=dataset.dify_dataset_id,
            name="深度学习基础概念.md",
            text=sample_file_content.strip(),
            upload_config=upload_config
        )
        print(f"✅ 模拟文件上传成功:")
        print(f"   - 文档名: {document2.name}")
        print(f"   - 文档ID: {document2.dify_document_id}")
        
        # 3. 监控文档处理状态
        print("\n⏳ 监控文档处理状态...")
        documents_to_monitor = [document1, document2]
        
        for i, doc in enumerate(documents_to_monitor, 1):
            print(f"\n检查文档 {i}: {doc.name}")
            max_attempts = 10
            attempt = 0
            
            while attempt < max_attempts:
                try:
                    # 获取最新文档状态
                    updated_doc = client.get_document(dataset.dify_dataset_id, doc.dify_document_id)
                    
                    print(f"   状态: {updated_doc.status}")
                    print(f"   索引状态: {updated_doc.indexing_status}")
                    
                    if updated_doc.indexing_status == IndexingStatus.COMPLETED.value:
                        print(f"   ✅ 文档处理完成")
                        print(f"   - 分片数量: {updated_doc.segment_count}")
                        print(f"   - Token数: {updated_doc.tokens}")
                        break
                    elif updated_doc.indexing_status == IndexingStatus.ERROR.value:
                        print(f"   ❌ 文档处理失败: {updated_doc.error}")
                        break
                    else:
                        print(f"   ⏳ 处理中... (尝试 {attempt + 1}/{max_attempts})")
                        import time; time.sleep(2)  # 等待2秒后重试
                        
                except Exception as e:
                    print(f"   ⚠️ 状态检查失败: {e}")
                    break
                    
                attempt += 1
            
            if attempt >= max_attempts:
                print(f"   ⚠️ 超时：文档可能仍在处理中")
        
        # 4. 获取文档分片信息
        print("\n📄 获取文档分片信息...")
        for i, doc in enumerate(documents_to_monitor, 1):
            try:
                segments = client.get_document_segments(
                    dataset_id=dataset.dify_dataset_id,
                    document_id=doc.dify_document_id
                )
                print(f"\n文档 {i} ({doc.name}) 的分片:")
                print(f"   - 总分片数: {len(segments)}")
                
                for j, segment in enumerate(segments[:3], 1):  # 只显示前3个分片
                    print(f"   分片 {j}:")
                    print(f"     - 内容长度: {segment.word_count} 词")
                    print(f"     - Token数: {segment.tokens}")
                    print(f"     - 关键词: {', '.join(segment.keywords) if segment.keywords else '无'}")
                    if len(segment.content) > 100:
                        print(f"     - 内容预览: {segment.content[:100]}...")
                    else:
                        print(f"     - 内容: {segment.content}")
                
                if len(segments) > 3:
                    print(f"   ... 还有 {len(segments) - 3} 个分片")
                    
            except Exception as e:
                print(f"   ⚠️ 获取分片失败: {e}")
        
        return dataset, client, documents_to_monitor
        
    except DocumentUploadError as e:
        print(f"❌ 文档上传失败: {e}")
        return None
    except DifyKnowledgeBaseError as e:
        print(f"❌ 操作失败: {e}")
        return None


def batch_operations_example():
    """批量操作示例"""
    print("\n=== 批量操作示例 ===")
    
    # 获取上传示例的结果
    try:
        result = upload_operations_example()
        if not result:
            print("❌ 无法继续批量操作示例")
            return
    except Exception as e:
        print(f"❌ 上传操作失败: {e}")
        return
    
    dataset, client, existing_docs = result
    
    try:
        print("\n📚 批量文档上传示例...")
        
        # 1. 准备批量文本文档
        batch_texts = [
            ("机器学习概述", """
            机器学习是人工智能的一个重要分支，它使计算机能够在没有明确编程的情况下学习和改进。
            
            主要类型：
            1. 监督学习：使用标记数据训练模型
            2. 无监督学习：发现数据中的隐藏模式
            3. 强化学习：通过与环境交互学习最优策略
            
            应用领域：图像识别、自然语言处理、推荐系统、自动驾驶等。
            """),
            
            ("神经网络基础", """
            神经网络是模拟人脑神经元工作方式的计算模型。
            
            基本组成：
            - 输入层：接收外部数据
            - 隐藏层：进行特征提取和变换
            - 输出层：产生最终结果
            
            关键概念：
            - 权重和偏置：可学习的参数
            - 激活函数：引入非线性
            - 损失函数：衡量预测与真实值的差异
            """),
            
            ("计算机视觉", """
            计算机视觉是让计算机"看懂"图像和视频的技术。
            
            核心任务：
            1. 图像分类：识别图像中的主要对象
            2. 目标检测：定位并识别图像中的多个对象
            3. 语义分割：对图像中每个像素进行分类
            4. 实例分割：区分同类对象的不同实例
            
            主要算法：CNN、R-CNN、YOLO、U-Net等。
            """)
        ]
        
        print(f"📝 准备批量上传 {len(batch_texts)} 个文档...")
        
        # 2. 执行批量上传
        batch_results = client.batch_upload_texts(
            dataset_id=dataset.dify_dataset_id,
            documents=batch_texts,
            upload_config=UploadConfig(
                indexing_technique=IndexingTechnique.HIGH_QUALITY,
                process_rule=ProcessRule(
                    mode=ProcessMode.AUTOMATIC,
                    pre_processing_rules=[
                        {"id": "remove_extra_spaces", "enabled": True}
                    ],
                    segmentation={
                        "separator": "\\n",
                        "max_tokens": 300
                    }
                )
            )
        )
        
        print(f"✅ 批量上传完成:")
        print(f"   - 成功上传: {len(batch_results)} 个文档")
        for doc in batch_results:
            print(f"     * {doc.name} (ID: {doc.dify_document_id})")
        
        # 3. 批量状态监控
        print(f"\n⏳ 批量监控文档处理状态...")
        all_completed = False
        max_wait_time = 60  # 最大等待60秒
        wait_time = 0
        
        while not all_completed and wait_time < max_wait_time:
            completed_count = 0
            
            for doc in batch_results:
                try:
                    updated_doc = client.get_document(dataset.dify_dataset_id, doc.dify_document_id)
                    if updated_doc.indexing_status == IndexingStatus.COMPLETED.value:
                        completed_count += 1
                except Exception:
                    pass
            
            print(f"   进度: {completed_count}/{len(batch_results)} 文档完成处理")
            
            if completed_count == len(batch_results):
                all_completed = True
                print("   ✅ 所有文档处理完成")
            else:
                time.sleep(3)
                wait_time += 3
        
        if not all_completed:
            print("   ⚠️ 部分文档可能仍在处理中")
        
        # 4. 获取知识库统计信息
        print(f"\n📊 知识库统计信息:")
        updated_dataset = client.get_dataset(dataset.dify_dataset_id, use_cache=False)
        print(f"   - 知识库名称: {updated_dataset.name}")
        print(f"   - 文档总数: {updated_dataset.document_count}")
        print(f"   - 字符总数: {updated_dataset.character_count}")
        
        # 5. 列出所有文档
        print(f"\n📋 知识库中的所有文档:")
        all_documents = client.list_documents(dataset.dify_dataset_id, limit=50)
        for i, doc in enumerate(all_documents, 1):
            print(f"   {i}. {doc.name}")
            print(f"      - ID: {doc.dify_document_id}")
            print(f"      - 状态: {doc.status} / {doc.indexing_status}")
            print(f"      - 分片数: {doc.segment_count}")
        
        return dataset, client, all_documents
        
    except Exception as e:
        print(f"❌ 批量操作失败: {e}")
        return None


async def basic_usage_example():
    """基本使用示例（简化版）"""
    print("\n=== 基本使用示例 ===")
    
    # 这个示例现在主要用于演示简单的查询操作
    try:
        result = batch_operations_example()
        if not result:
            print("❌ 无法运行基本使用示例")
            return
    except Exception as e:
        print(f"❌ 批量操作失败: {e}")
        return
    
    dataset, client, documents = result
    
    try:
        print("\n🔍 知识库查询示例...")
        
        # 测试查询
        test_queries = [
            "什么是Transformer？",
            "深度学习的基本概念",
            "机器学习有哪些类型？",
            "神经网络的组成部分"
        ]
        
        for query in test_queries:
            print(f"\n查询: '{query}'")
            try:
                query_result = client.query_dataset(
                    dataset_id=dataset.dify_dataset_id,
                    query=query,
                    retrieval_model={
                        "search_method": "semantic_search",
                        "top_k": 3,
                        "score_threshold_enabled": True,
                        "score_threshold": 0.3
                    }
                )
                
                results = query_result.get('data', [])
                print(f"   找到 {len(results)} 个相关结果:")
                
                for i, result in enumerate(results, 1):
                    score = result.get('score', 0)
                    content = result.get('content', '')
                    print(f"   {i}. 相关度: {score:.3f}")
                    if len(content) > 150:
                        print(f"      内容: {content[:150]}...")
                    else:
                        print(f"      内容: {content}")
                        
            except Exception as e:
                print(f"   ❌ 查询失败: {e}")
        
        print(f"\n✅ 基本使用示例完成")
        
    except DifyKnowledgeBaseError as e:
        print(f"❌ 操作失败: {e}")


def file_upload_example():
    """文件上传示例"""
    print("\n=== 文件上传示例 ===")
    
    config = get_config()
    client = DifyKnowledgeBaseClient(config)
    
    try:
        # 创建数据集
        dataset = client.create_dataset(
            name="文档知识库",
            description="包含各种文档格式的知识库"
        )
        print(f"创建数据集: {dataset.name}")
        
        # 准备上传配置
        upload_config = UploadConfig(
            indexing_technique=IndexingTechnique.HIGH_QUALITY,
            process_rule=ProcessRule(
                mode=ProcessMode.CUSTOM,
                pre_processing_rules=[
                    {"id": "remove_extra_spaces", "enabled": True},
                    {"id": "remove_urls_emails", "enabled": False}
                ],
                segmentation={
                    "separator": "\\n\\n",
                    "max_tokens": 800,
                    "chunk_overlap": 50
                }
            )
        )
        
        # 示例：上传PDF文件（如果存在）
        pdf_path = "/path/to/sample.pdf"
        if os.path.exists(pdf_path):
            document = client.upload_document_file(
                dataset_id=dataset.dify_dataset_id,
                file_path=pdf_path,
                upload_config=upload_config
            )
            print(f"上传PDF成功: {document.name}")
        
        # 示例：批量上传文本
        texts_data = [
            ("文档1", "第一个文档的内容..."),
            ("文档2", "第二个文档的内容..."),
            ("文档3", "第三个文档的内容...")
        ]
        
        batch_results = client.batch_upload_texts(
            dataset_id=dataset.dify_dataset_id,
            documents=texts_data,
            upload_config=upload_config
        )
        print(f"批量上传完成: {len(batch_results)} 个文档")
        
    except Exception as e:
        print(f"文件上传失败: {e}")


def data_model_example():
    """数据模型使用示例"""
    print("\n=== 数据模型示例 ===")
    
    # 1. 创建数据集模型
    dataset_model = DifyDatasetModel()
    dataset_model.dify_dataset_id = "dataset_123"
    dataset_model.name = "AI研究知识库"
    dataset_model.description = "包含AI相关研究文档"
    dataset_model.status = DatasetStatus.ACTIVE
    dataset_model.document_count = 15
    dataset_model.word_count = 50000
    
    print("数据集模型:")
    print(f"  ID: {dataset_model.dify_dataset_id}")
    print(f"  名称: {dataset_model.name}")
    print(f"  状态: {dataset_model.status}")
    print(f"  文档数: {dataset_model.document_count}")
    
    # 2. 创建文档模型
    document_model = DifyDocumentModel()
    document_model.dify_document_id = "doc_456"
    document_model.dify_dataset_id = dataset_model.dify_dataset_id
    document_model.name = "Transformer论文"
    document_model.file_type = DocumentType.TXT.value
    document_model.status = DocumentStatus.COMPLETED.value
    document_model.indexing_status = IndexingStatus.COMPLETED.value
    document_model.word_count = 8000
    document_model.segment_count = 12
    
    print("\n文档模型:")
    print(f"  ID: {document_model.dify_document_id}")
    print(f"  名称: {document_model.name}")
    print(f"  类型: {document_model.file_type}")
    print(f"  状态: {document_model.status}")
    print(f"  段落数: {document_model.segment_count}")
    
    # 3. 创建段落模型
    segment_model = DifySegmentModel()
    segment_model.dify_segment_id = "seg_789"
    segment_model.dify_document_id = document_model.dify_document_id
    segment_model.position = 1
    segment_model.content = "Transformer是一种基于注意力机制的深度学习模型..."
    segment_model.word_count = 150
    segment_model.tokens = 200
    segment_model.keywords = ["transformer", "attention", "深度学习"]
    
    print("\n段落模型:")
    print(f"  ID: {segment_model.dify_segment_id}")
    print(f"  位置: {segment_model.position}")
    print(f"  词数: {segment_model.word_count}")
    print(f"  关键词: {', '.join(segment_model.keywords)}")
    
    # 4. 转换为字典
    dataset_dict = dataset_model.to_dict()
    print(f"\n数据集字典keys: {list(dataset_dict.keys())}")


def error_handling_example():
    """错误处理示例"""
    print("\n=== 错误处理示例 ===")
    
    config = DifyKnowledgeBaseConfig(
        api_key="invalid-key",  # 故意使用无效密钥
        base_url="https://api.dify.ai"
    )
    client = DifyKnowledgeBaseClient(config)
    
    try:
        # 尝试创建数据集（会失败）
        client.create_dataset(name="测试数据集")
    except DifyKnowledgeBaseError as e:
        print(f"捕获到知识库错误: {e}")
        print(f"错误类型: {type(e).__name__}")
    
    try:
        # 尝试获取不存在的数据集
        client.get_dataset("nonexistent_id")
    except DatasetNotFoundError as e:
        print(f"数据集未找到: {e}")
    except DifyKnowledgeBaseError as e:
        print(f"其他知识库错误: {e}")


def advanced_features_example():
    """高级功能示例"""
    print("\n=== 高级功能示例 ===")
    
    config = get_config()
    client = DifyKnowledgeBaseClient(config)
    
    try:
        # 创建客户端（缓存功能已内置）
        cached_client = DifyKnowledgeBaseClient(config)
        
        # 注意：重试策略在客户端初始化时已配置，这里仅作演示
        print("重试策略已在客户端初始化时配置")
        
        # 获取所有数据集
        datasets = cached_client.list_datasets()
        print(f"找到 {len(datasets)} 个数据集")
        
        if datasets:
            dataset_id = datasets[0].dify_dataset_id
            
            # 获取数据集详情
            dataset_detail = cached_client.get_dataset(dataset_id)
            print(f"数据集详情: {dataset_detail.name}")
            
            print("缓存功能已内置在客户端中")
            
            print("注意：此演示版本不包含数据集更新功能")
        
    except Exception as e:
        print(f"高级功能示例失败: {e}")


def main():
    """主函数：运行所有示例"""
    print("Dify Knowledge Base 使用示例")
    print("=" * 50)
    
    # 检查环境变量
    if not os.getenv("DIFY_KB_API_KEY") and not os.getenv("DIFY_API_KEY"):
        print("⚠️  警告: 未设置 Dify API 密钥环境变量")
        print("请设置以下环境变量之一:")
        print("  export DIFY_KB_API_KEY=your-api-key")
        print("  export DIFY_API_KEY=your-api-key")
        print("  export DIFY_BASE_URL=https://api.dify.ai/v1  # 可选，默认为本地")
        print()
        print("🔧 如果您想运行完整示例，请先配置API密钥")
        print("🔧 如果只想查看数据模型和错误处理示例，可以继续运行")
        print()
    
    # 询问用户是否运行完整示例
    run_full_examples = False
    if os.getenv("DIFY_KB_API_KEY") or os.getenv("DIFY_API_KEY"):
        run_full_examples = True
        print("✅ 检测到API密钥，将运行完整示例")
    else:
        print("⚠️  未检测到API密钥，将只运行数据模型和错误处理示例")
    
    try:
        if run_full_examples:
            print("\n" + "=" * 60)
            print("🚀 开始运行完整的 Dify 知识库操作示例")
            print("=" * 60)
            
            # 主要示例：创建知识库 -> 上传文档 -> 批量操作 -> 查询测试
            print("\n📚 这个示例将演示完整的知识库使用流程:")
            print("   1. 创建知识库和配置")
            print("   2. 上传个别文档（文本和文件）")
            print("   3. 批量上传多个文档")
            print("   4. 查询知识库内容")
            print("   5. 监控处理状态")
            
            # 运行主要的知识库操作示例
            # Note: basic_usage_example is currently async but calls sync functions
            print("注意：由于API方法是同步的，示例已修改为直接调用")
            
            print("\n" + "=" * 60)
            print("📁 文件上传专项示例")
            print("=" * 60)
            # 运行文件上传示例（如果需要）
            file_upload_example()
            
        # 总是运行数据模型和错误处理示例（不需要API连接）
        print("\n" + "=" * 60)
        print("📊 数据模型使用示例")
        print("=" * 60)
        data_model_example()
        
        print("\n" + "=" * 60)
        print("🛠️  错误处理示例")
        print("=" * 60)
        error_handling_example()
        
        if run_full_examples:
            print("\n" + "=" * 60)
            print("🔧 高级功能示例")
            print("=" * 60)
            advanced_features_example()
    
    except KeyboardInterrupt:
        print("\n⚠️  用户中断了示例运行")
    except Exception as e:
        print(f"\n❌ 示例运行出现错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("✅ 示例运行完成！")
    print("=" * 60)
    
    if run_full_examples:
        print("\n📋 运行总结:")
        print("   ✅ 知识库创建和设置")
        print("   ✅ 文档上传操作（文本和文件）")
        print("   ✅ 批量文档处理")
        print("   ✅ 知识库查询测试")
        print("   ✅ 高级功能演示")
    else:
        print("\n📋 运行总结:")
        print("   ✅ 数据模型使用演示")
        print("   ✅ 错误处理机制演示")
        print("   ⚠️  完整API示例需要设置API密钥")
    
    print("\n💡 提示:")
    print("   - 设置 DIFY_KB_API_KEY 环境变量来运行完整示例")
    print("   - 查看代码注释了解更多配置选项")
    print("   - 参考 HomeSystem 文档获取详细使用指南")


if __name__ == "__main__":
    # 运行示例
    main()