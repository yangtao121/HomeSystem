#!/usr/bin/env python3
"""
Home System 数据库集成测试脚本

测试数据库连接、模型操作、ArXiv集成等功能
"""

import os
import sys
import time
from pathlib import Path

# 添加项目路径到Python路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_environment():
    """测试环境配置"""
    print("🔧 测试环境配置...")
    
    # 检查环境变量
    required_vars = ['DB_HOST', 'DB_PORT', 'DB_NAME', 'DB_USER', 'DB_PASSWORD']
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}: {value}")
        else:
            missing_vars.append(var)
            print(f"  ⚠️  {var}: 未设置 (将使用默认值)")
    
    if missing_vars:
        print(f"  ℹ️  未设置的环境变量将使用默认值，建议创建 .env 文件")
    
    return True

def test_database_imports():
    """测试数据库模块导入"""
    print("\n📦 测试数据库模块导入...")
    
    try:
        from HomeSystem.integrations.database import (
            DatabaseManager, 
            get_database_manager,
            ArxivPaperModel,
            DatabaseOperations,
            CacheOperations
        )
        print("  ✅ 数据库核心模块导入成功")
        return True
    except ImportError as e:
        print(f"  ❌ 数据库模块导入失败: {e}")
        return False

def test_database_connections():
    """测试数据库连接"""
    print("\n🔗 测试数据库连接...")
    
    try:
        from HomeSystem.integrations.database import get_database_manager, check_database_health
        
        # 检查连接健康状态
        health = check_database_health()
        
        print(f"  PostgreSQL 同步连接: {'✅' if health.get('postgres_sync') else '❌'}")
        print(f"  Redis 连接: {'✅' if health.get('redis') else '❌'}")
        
        return health.get('postgres_sync', False) and health.get('redis', False)
        
    except Exception as e:
        print(f"  ❌ 数据库连接测试失败: {e}")
        return False

def test_model_operations():
    """测试数据模型操作"""
    print("\n📊 测试数据模型操作...")
    
    try:
        from HomeSystem.integrations.database import DatabaseOperations, ArxivPaperModel
        
        db_ops = DatabaseOperations()
        
        # 初始化表结构
        arxiv_model = ArxivPaperModel()
        success = db_ops.init_tables([arxiv_model])
        print(f"  表结构初始化: {'✅' if success else '❌'}")
        
        if not success:
            return False
        
        # 创建测试论文
        test_paper = ArxivPaperModel(
            arxiv_id="test.12345",
            title="Test Paper for Database Integration",
            abstract="This is a test paper for database integration testing.",
            categories="cs.LG, cs.AI",
            published_date="2024年01月",
            processing_status="pending"
        )
        
        # 测试创建
        success = db_ops.create(test_paper)
        print(f"  创建记录: {'✅' if success else '❌'}")
        
        # 测试查询
        retrieved_paper = db_ops.get_by_field(ArxivPaperModel, 'arxiv_id', 'test.12345')
        print(f"  查询记录: {'✅' if retrieved_paper else '❌'}")
        
        if retrieved_paper:
            print(f"    检索到论文: {retrieved_paper.title}")
        
        # 测试更新
        if retrieved_paper:
            success = db_ops.update(retrieved_paper, {'processing_status': 'completed'})
            print(f"  更新记录: {'✅' if success else '❌'}")
        
        # 测试删除
        if retrieved_paper:
            success = db_ops.delete(retrieved_paper)
            print(f"  删除记录: {'✅' if success else '❌'}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 数据模型操作测试失败: {e}")
        return False

def test_cache_operations():
    """测试缓存操作"""
    print("\n💾 测试缓存操作...")
    
    try:
        from HomeSystem.integrations.database import CacheOperations
        
        cache_ops = CacheOperations()
        
        # 测试基础键值操作
        success = cache_ops.set("test_key", "test_value", expire=60)
        print(f"  设置缓存: {'✅' if success else '❌'}")
        
        value = cache_ops.get("test_key")
        print(f"  获取缓存: {'✅' if value == 'test_value' else '❌'}")
        
        # 测试集合操作
        count = cache_ops.sadd("test_set", "item1", "item2", "item3")
        print(f"  集合操作: {'✅' if count > 0 else '❌'}")
        
        is_member = cache_ops.sismember("test_set", "item1")
        print(f"  集合成员检查: {'✅' if is_member else '❌'}")
        
        # 清理测试数据
        cache_ops.delete("test_key")
        cache_ops.delete("test_set")
        print("  ✅ 测试数据已清理")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 缓存操作测试失败: {e}")
        return False

def test_arxiv_integration():
    """测试ArXiv集成功能"""
    print("\n🔬 测试ArXiv集成功能...")
    
    try:
        from HomeSystem.utility.arxiv import EnhancedArxivTool
        
        # 创建增强版ArXiv工具
        arxiv_tool = EnhancedArxivTool(enable_database=True)
        print("  ✅ 增强版ArXiv工具创建成功")
        
        # 测试搜索（限制结果数量以节省时间）
        print("  🔍 执行测试搜索...")
        results = arxiv_tool.arxivSearch("quantum computing", num_results=3)
        
        if results.num_results > 0:
            print(f"  ✅ 搜索成功，找到 {results.num_results} 篇论文")
            
            # 显示第一篇论文信息
            first_paper = results.results[0]
            print(f"    示例论文: {first_paper.title[:50]}...")
            
            # 测试统计功能
            stats = arxiv_tool.get_processing_statistics()
            print(f"  📊 数据库统计: 总计 {stats.get('total', 0)} 篇论文")
            
            return True
        else:
            print("  ⚠️  搜索未返回结果")
            return False
            
    except ImportError:
        print("  ⚠️  ArXiv集成模块不可用 (可能缺少依赖)")
        return False
    except Exception as e:
        print(f"  ❌ ArXiv集成测试失败: {e}")
        return False

def main():
    """主测试函数"""
    print("🚀 Home System 数据库集成测试开始")
    print("=" * 60)
    
    test_results = []
    
    # 运行所有测试
    tests = [
        ("环境配置", test_environment),
        ("模块导入", test_database_imports),
        ("数据库连接", test_database_connections),
        ("数据模型操作", test_model_operations),
        ("缓存操作", test_cache_operations),
        ("ArXiv集成", test_arxiv_integration),
    ]
    
    for test_name, test_func in tests:
        try:
            result = test_func()
            test_results.append((test_name, result))
        except Exception as e:
            print(f"  ❌ {test_name} 测试异常: {e}")
            test_results.append((test_name, False))
    
    # 显示测试结果摘要
    print("\n" + "=" * 60)
    print("📋 测试结果摘要:")
    
    passed = 0
    total = len(test_results)
    
    for test_name, result in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"  {test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n🎯 总体结果: {passed}/{total} 测试通过")
    
    if passed == total:
        print("🎉 所有测试通过！数据库集成配置正确。")
        return 0
    else:
        print("⚠️  部分测试失败，请检查配置和依赖。")
        print("\n💡 故障排除提示:")
        print("  1. 确保Docker容器正在运行: docker-compose up -d")
        print("  2. 检查 .env 文件配置")
        print("  3. 安装所需依赖: pip install -r requirements.txt")
        return 1

if __name__ == "__main__":
    # 加载环境变量
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        print("⚠️  python-dotenv 未安装，跳过 .env 文件加载")
    
    exit_code = main()
    sys.exit(exit_code)