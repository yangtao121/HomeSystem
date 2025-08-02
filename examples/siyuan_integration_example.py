#!/usr/bin/env python3
"""
SiYuan 笔记集成使用示例

演示如何使用 SiYuan 笔记集成功能进行笔记管理
"""

import os
import sys
from pathlib import Path

# 添加项目路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

def example_basic_connection():
    """基础连接测试示例"""
    print("📝 基础连接测试示例")
    print("-" * 50)
    
    try:
        from HomeSystem.integrations.siyuan import SiYuanClient, SiYuanAPIError
        
        # 从环境变量创建客户端
        client = SiYuanClient.from_environment()
        print("✅ SiYuan 客户端已创建")
        
        # 测试连接
        print("🔄 测试连接...")
        connection_result = client.test_connection()
        is_connected = connection_result.get('success', False)
        print(f"连接测试: {'✅ 成功' if is_connected else '❌ 失败'}")
        
        if is_connected:
            print(f"响应时间: {connection_result.get('response_time', 0):.2f}ms")
            print(f"数据块数量: {connection_result.get('block_count', 0)}")
            
            # 获取健康状态
            health = client.health_check()
            print(f"健康状态: {'✅ 正常' if health.get('is_healthy', False) else '❌ 异常'}")
            print(f"健康检查响应时间: {health.get('response_time', 0):.2f}ms")
        else:
            print(f"错误信息: {connection_result.get('error_message', 'Unknown error')}")
            
        return is_connected
        
    except Exception as e:
        print(f"❌ 连接测试失败: {e}")
        return False

def example_notebook_operations():
    """笔记本操作示例"""
    print("\n📚 笔记本操作示例")
    print("-" * 50)
    
    try:
        from HomeSystem.integrations.siyuan import SiYuanClient
        
        client = SiYuanClient.from_environment()
        
        # 获取所有笔记本
        print("🔍 获取笔记本列表...")
        notebooks = client.get_notebooks()
        
        if notebooks:
            print(f"✅ 找到 {len(notebooks)} 个笔记本:")
            for i, notebook in enumerate(notebooks[:3], 1):  # 只显示前3个
                print(f"   {i}. {notebook['name']} (ID: {notebook['id']})")
                if 'closed' in notebook:
                    status = "已关闭" if notebook['closed'] else "已打开"
                    print(f"      状态: {status}")
            
            return notebooks[0] if notebooks else None
        else:
            print("⚠️  未找到任何笔记本")
            return None
            
    except Exception as e:
        print(f"❌ 笔记本操作失败: {e}")
        return None

def example_note_crud_operations(notebook_id: str):
    """笔记 CRUD 操作示例"""
    print("\n📄 笔记 CRUD 操作示例")
    print("-" * 50)
    
    try:
        from HomeSystem.integrations.siyuan import SiYuanClient
        
        client = SiYuanClient.from_environment()
        
        # 创建测试笔记
        print("➕ 创建测试笔记...")
        test_title = "HomeSystem 集成测试笔记"
        test_content = """# HomeSystem 集成测试

这是一个测试笔记，用于验证 SiYuan 集成功能。

## 功能测试

- [x] 连接测试
- [x] 笔记创建
- [ ] 笔记更新
- [ ] 笔记搜索

## 测试数据

| 项目 | 值 |
|------|-----|
| 创建时间 | 2024年 |
| 测试类型 | 自动化测试 |
| 状态 | 进行中 |

---

*由 HomeSystem 自动生成*
"""
        
        created_note = client.create_note(
            notebook_id=notebook_id,
            title=test_title,
            content=test_content,
            tags=["测试", "HomeSystem", "集成"]
        )
        
        print(f"✅ 笔记已创建: {created_note.title}")
        print(f"   笔记ID: {created_note.note_id}")
        print(f"   标签: {', '.join(created_note.tags)}")
        
        # 获取笔记详情
        print("\n🔍 获取笔记详情...")
        note_detail = client.get_note(created_note.note_id)
        print(f"✅ 获取成功: {note_detail.title}")
        print(f"   内容长度: {len(note_detail.content or '')} 字符")
        print(f"   创建时间: {note_detail.created_time}")
        
        # 更新笔记
        print("\n✏️  更新笔记内容...")
        updated_content = test_content + "\n\n## 更新测试\n\n笔记已成功更新！"
        updated_note = client.update_note(
            note_id=created_note.note_id,
            content=updated_content,
            title=f"{test_title} - 已更新"
        )
        
        print(f"✅ 笔记已更新: {updated_note.title}")
        
        return created_note.note_id
        
    except Exception as e:
        print(f"❌ 笔记 CRUD 操作失败: {e}")
        return None

def example_search_operations():
    """搜索操作示例"""
    print("\n🔍 搜索操作示例")
    print("-" * 50)
    
    try:
        from HomeSystem.integrations.siyuan import SiYuanClient
        
        client = SiYuanClient.from_environment()
        
        # 搜索笔记
        search_queries = ["测试", "HomeSystem", "集成"]
        
        for query in search_queries:
            print(f"🔍 搜索关键词: '{query}'...")
            
            search_result = client.search_notes(
                query=query,
                limit=5
            )
            
            print(f"✅ 找到 {search_result.total_count} 条结果")
            print(f"   搜索耗时: {search_result.search_time:.2f}ms")
            
            # 显示前3个结果
            for i, result in enumerate(search_result.results[:3], 1):
                title = result.get('title', '无标题')[:40]
                note_id = result.get('id', '')[:8]
                print(f"   {i}. {title}... (ID: {note_id}...)")
            
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ 搜索操作失败: {e}")
        return False

def example_sql_query_operations():
    """SQL 查询操作示例"""
    print("\n🗄️  SQL 查询操作示例")
    print("-" * 50)
    
    try:
        from HomeSystem.integrations.siyuan import SiYuanClient
        
        client = SiYuanClient.from_environment()
        
        # 基础统计查询
        queries = [
            ("总文档数", "SELECT COUNT(*) as count FROM blocks WHERE type = 'd'"),
            ("最近创建", "SELECT id, content FROM blocks WHERE type = 'd' ORDER BY created DESC LIMIT 3"),
            ("标签统计", "SELECT tag, COUNT(*) as count FROM blocks WHERE tag IS NOT NULL AND tag != '' GROUP BY tag LIMIT 5")
        ]
        
        for name, sql in queries:
            print(f"📊 {name}查询...")
            try:
                result = client.execute_sql(sql)
                print(f"✅ 查询成功，返回 {len(result)} 条记录")
                
                # 显示部分结果
                for i, row in enumerate(result[:2], 1):
                    # 格式化显示
                    row_data = []
                    for key, value in row.items():
                        if isinstance(value, str) and len(value) > 30:
                            value = value[:30] + "..."
                        row_data.append(f"{key}: {value}")
                    print(f"   {i}. {', '.join(row_data)}")
                
                print()
                
            except Exception as e:
                print(f"⚠️  {name}查询失败: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ SQL 查询操作失败: {e}")
        return False

def example_export_operations(note_id: str):
    """导出操作示例"""
    print("\n📤 导出操作示例")
    print("-" * 50)
    
    try:
        from HomeSystem.integrations.siyuan import SiYuanClient
        
        client = SiYuanClient.from_environment()
        
        # 导出笔记为 Markdown
        print(f"📄 导出笔记 (ID: {note_id[:8]}...)...")
        
        exported_content = client.export_note(note_id, format='md')
        
        if exported_content:
            print(f"✅ 导出成功，内容长度: {len(exported_content)} 字符")
            
            # 显示前几行内容
            lines = exported_content.split('\n')[:5]
            print("   内容预览:")
            for line in lines:
                preview = line[:60] + "..." if len(line) > 60 else line
                print(f"     {preview}")
            
            # 可选：保存到文件
            export_file = Path("/tmp/siyuan_export_test.md")
            export_file.write_text(exported_content, encoding='utf-8')
            print(f"📁 内容已保存到: {export_file}")
            
        return True
        
    except Exception as e:
        print(f"❌ 导出操作失败: {e}")
        return False

def example_sync_operations():
    """同步操作示例"""
    print("\n🔄 同步操作示例")
    print("-" * 50)
    
    try:
        from HomeSystem.integrations.siyuan import SiYuanClient
        
        client = SiYuanClient.from_environment()
        
        print("🔄 开始同步数据...")
        sync_result = client.sync_data(
            notebook_ids=None,  # None 表示所有笔记本
            sync_type='incremental',  # 增量同步
            last_sync_time=None  # None 表示获取所有数据
        )
        
        print(f"同步状态: {sync_result.get('status', 'unknown')}")
        print(f"处理项目: {sync_result.get('items_processed', 0)}")
        print(f"创建项目: {sync_result.get('items_created', 0)}")
        print(f"失败项目: {sync_result.get('items_failed', 0)}")
        
        # 显示同步的笔记
        details = sync_result.get('details', {})
        notes = details.get('notes', [])
        if notes:
            print(f"\n📝 同步的笔记 (显示前3篇):")
            for i, note_dict in enumerate(notes[:3], 1):
                title = note_dict.get('title', '无标题')[:40]
                notebook_name = note_dict.get('notebook_name', '未知')
                tags = note_dict.get('tags', [])
                print(f"   {i}. {title}...")
                print(f"      笔记本: {notebook_name}")
                print(f"      标签: {', '.join(tags) if tags else '无'}")
        
        return True
        
    except Exception as e:
        print(f"❌ 同步操作失败: {e}")
        return False

def example_advanced_usage():
    """高级用法示例"""
    print("\n🚀 高级用法示例")
    print("-" * 50)
    
    try:
        from HomeSystem.integrations.siyuan import SiYuanClient
        
        # 使用自定义配置创建客户端
        client = SiYuanClient(
            base_url=os.getenv('SIYUAN_API_URL', 'http://127.0.0.1:6806'),
            api_token=os.getenv('SIYUAN_API_TOKEN', ''),
            timeout=30
        )
        
        # 复杂 SQL 查询示例
        complex_queries = [
            {
                'name': '最活跃的笔记本',
                'sql': '''
                SELECT 
                    box as notebook_id,
                    COUNT(*) as note_count,
                    MAX(updated) as last_updated
                FROM blocks 
                WHERE type = 'd' 
                GROUP BY box 
                ORDER BY note_count DESC 
                LIMIT 5
                '''
            },
            {
                'name': '最近更新的笔记',
                'sql': '''
                SELECT 
                    id,
                    content,
                    updated
                FROM blocks 
                WHERE type = 'd' 
                ORDER BY updated DESC 
                LIMIT 5
                '''
            }
        ]
        
        for query_info in complex_queries:
            print(f"📊 执行查询: {query_info['name']}")
            try:
                results = client.execute_sql(query_info['sql'])
                print(f"✅ 找到 {len(results)} 条记录")
                
                for i, row in enumerate(results[:2], 1):
                    print(f"   {i}. {dict(list(row.items())[:3])}...")  # 只显示前3个字段
                print()
                
            except Exception as e:
                print(f"⚠️  查询失败: {e}")
        
        # 批量操作示例
        print("🔄 批量操作示例...")
        
        # 获取所有笔记本
        notebooks = client.get_notebooks()
        if notebooks:
            print(f"✅ 获取到 {len(notebooks)} 个笔记本")
            
            # 为每个笔记本获取笔记数量
            for notebook in notebooks[:3]:  # 只处理前3个
                notebook_id = notebook['id']
                notebook_name = notebook['name']
                
                count_sql = f"SELECT COUNT(*) as count FROM blocks WHERE box = '{notebook_id}' AND type = 'd'"
                count_result = client.execute_sql(count_sql)
                
                if count_result:
                    note_count = count_result[0].get('count', 0)
                    print(f"   📚 {notebook_name}: {note_count} 篇笔记")
        
        return True
        
    except Exception as e:
        print(f"❌ 高级用法示例失败: {e}")
        return False

def main():
    """主函数"""
    print("🎯 SiYuan 笔记集成使用示例")
    print("=" * 60)
    
    # 检查环境变量
    required_vars = ['SIYUAN_API_URL', 'SIYUAN_API_TOKEN']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print("⚠️  缺少必要的环境变量:")
        for var in missing_vars:
            print(f"   - {var}")
        print("\n💡 请设置环境变量或在 .env 文件中配置:")
        print("   SIYUAN_API_URL=http://127.0.0.1:6806")
        print("   SIYUAN_API_TOKEN=your_api_token")
        return
    
    # 加载环境变量
    try:
        from dotenv import load_dotenv
        load_dotenv()
        print("✅ 环境变量已加载")
    except ImportError:
        print("⚠️  python-dotenv 未安装，使用系统环境变量")
    
    # 基础连接测试
    is_connected = example_basic_connection()
    if not is_connected:
        print("❌ 连接失败，无法继续后续示例")
        return
    
    # 获取笔记本信息
    notebook = example_notebook_operations()
    
    # 运行示例
    examples = [
        ("搜索操作", example_search_operations, []),
        ("SQL 查询操作", example_sql_query_operations, []),
        ("同步操作", example_sync_operations, []),
        ("高级用法", example_advanced_usage, []),
    ]
    
    # 如果有可用的笔记本，添加需要笔记本ID的示例
    if notebook:
        examples.insert(1, ("笔记 CRUD 操作", example_note_crud_operations, [notebook['id']]))
    
    created_note_id = None
    
    for name, func, args in examples:
        try:
            print(f"\n{'='*20} {name} {'='*20}")
            
            # 特殊处理 CRUD 操作的返回值
            if name == "笔记 CRUD 操作":
                created_note_id = func(*args)
                success = created_note_id is not None
            else:
                success = func(*args)
            
            if not success:
                print(f"⚠️  {name} 示例未完全成功")
                
        except Exception as e:
            print(f"❌ {name} 示例执行失败: {e}")
        
        print()  # 添加空行分隔
    
    # 如果创建了测试笔记，演示导出功能
    if created_note_id:
        try:
            print(f"{'='*20} 导出操作 {'='*20}")
            example_export_operations(created_note_id)
        except Exception as e:
            print(f"❌ 导出操作示例执行失败: {e}")
    
    print("🎉 所有示例执行完成！")
    print("\n💡 提示:")
    print("- 确保 SiYuan 笔记软件正在运行")
    print("- 在 SiYuan 设置中启用 API 并配置访问令牌")
    print("- 查看 docs/local-services-api.md 了解详细配置")
    print("- 运行前请备份重要数据")

if __name__ == "__main__":
    # 运行主函数
    main()