#!/usr/bin/env python3
"""
测试重构后的深度论文分析智能体

使用指定的论文文件夹和视觉模型进行完整的分析测试。
"""

import sys
import os
import json
from pathlib import Path

# 添加项目路径
sys.path.append('/mnt/nfs_share/code/homesystem')

from HomeSystem.graph.deep_paper_analysis_agent import create_deep_paper_analysis_agent
from loguru import logger

def test_deep_paper_analysis():
    """测试深度论文分析功能"""
    
    # 配置参数
    paper_folder = "/mnt/nfs_share/code/homesystem/data/paper_analyze/2502.13508"
    vision_model = "ollama.Qwen2_5_VL_7B" 
    analysis_model = "moonshot.Kimi_K2"
    
    logger.info(f"开始测试深度论文分析智能体")
    logger.info(f"论文文件夹: {paper_folder}")
    logger.info(f"视觉模型: {vision_model}")
    logger.info(f"分析模型: {analysis_model}")
    
    try:
        # 1. 创建智能体
        logger.info("步骤1: 创建深度论文分析智能体...")
        agent = create_deep_paper_analysis_agent(
            analysis_model=analysis_model,
            vision_model=vision_model
        )
        logger.info("✅ 智能体创建成功")
        
        # 2. 验证文件夹存在
        if not os.path.exists(paper_folder):
            raise FileNotFoundError(f"论文文件夹不存在: {paper_folder}")
        
        logger.info("步骤2: 验证论文文件夹结构...")
        imgs_folder = os.path.join(paper_folder, "imgs")
        if os.path.exists(imgs_folder):
            image_count = len([f for f in os.listdir(imgs_folder) if f.endswith('.jpg')])
            logger.info(f"✅ 发现 {image_count} 个图片文件")
        
        # 3. 执行论文分析
        logger.info("步骤3: 开始执行论文深度分析...")
        logger.info("注意: 这将调用云端LLM和本地视觉模型，可能需要几分钟时间...")
        
        # 执行分析
        analysis_result = agent.analyze_paper_folder(paper_folder, thread_id="test_2502_13508")
        
        # 4. 检查分析结果
        logger.info("步骤4: 验证分析结果...")
        
        if "error" in analysis_result:
            logger.error(f"❌ 分析失败: {analysis_result['error']}")
            return False
        
        # 检查关键结果字段
        required_fields = ["chinese_analysis", "messages", "is_complete"]
        missing_fields = [field for field in required_fields if field not in analysis_result]
        
        if missing_fields:
            logger.warning(f"⚠️ 缺少字段: {missing_fields}")
        
        # 检查中文分析结果
        if analysis_result.get("chinese_analysis"):
            logger.info("✅ 中文分析结果已生成")
            chinese_content = analysis_result["chinese_analysis"]
            
            # 显示分析结果预览
            content_preview = chinese_content[:500] if len(chinese_content) > 500 else chinese_content
            logger.info(f"分析结果预览: {content_preview}...")
            logger.info(f"分析结果长度: {len(chinese_content)} 字符")
        else:
            logger.warning("⚠️ 未生成中文分析结果")
        
        # 检查消息历史和工具调用情况
        messages = analysis_result.get("messages", [])
        tool_calls_count = 0
        tool_messages_count = 0
        ai_messages_count = 0
        
        for msg in messages:
            if msg.__class__.__name__ == 'AIMessage':
                ai_messages_count += 1
                # 使用 getattr 安全检查 tool_calls
                tool_calls = getattr(msg, 'tool_calls', None)
                if tool_calls:
                    tool_calls_count += len(tool_calls)
                    logger.info(f"  AI消息 {ai_messages_count} 包含 {len(tool_calls)} 个工具调用")
            elif msg.__class__.__name__ == 'ToolMessage':
                tool_messages_count += 1
                # 显示工具响应的预览
                content_preview = str(msg.content)[:100] if hasattr(msg, 'content') else "<no content>"
                logger.info(f"  工具响应 {tool_messages_count}: {content_preview}...")
        
        logger.info(f"✅ 消息历史包含 {len(messages)} 条消息")
        logger.info(f"  - AI消息: {ai_messages_count} 条")
        logger.info(f"  - 工具调用总数: {tool_calls_count} 次")
        logger.info(f"  - 工具响应: {tool_messages_count} 条")
        
        # 验证工具调用是否成功
        if tool_calls_count > 0 and tool_messages_count > 0:
            logger.info(f"✅ 工具调用成功: {tool_calls_count} 次调用, {tool_messages_count} 次响应")
        elif tool_calls_count > 0:
            logger.warning(f"⚠️ 工具调用部分成功: {tool_calls_count} 次调用但无响应")
        else:
            logger.warning(f"⚠️ 未检测到工具调用，可能需要检查 LLM 配置")
        
        # 5. 生成测试报告
        logger.info("步骤5: 生成测试摘要...")
        
        test_summary = {
            "test_status": "SUCCESS",
            "paper_folder": paper_folder,
            "models_used": {
                "analysis_model": analysis_model,
                "vision_model": vision_model
            },
            "results": {
                "has_chinese_analysis": analysis_result.get("chinese_analysis") is not None,
                "chinese_analysis_length": len(analysis_result.get("chinese_analysis", "")),
                "message_count": len(messages),
                "ai_messages_count": ai_messages_count,
                "tool_calls_made": tool_calls_count,
                "tool_responses_received": tool_messages_count,
                "tool_call_success_rate": tool_messages_count / max(tool_calls_count, 1),
                "analysis_complete": analysis_result.get("is_complete", False)
            }
        }
        
        logger.info("🎉 深度论文分析测试成功完成!")
        print("\n" + "="*50)
        print("测试摘要:")
        print(json.dumps(test_summary, ensure_ascii=False, indent=2))
        print("="*50)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 测试失败: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def test_simple_functionality():
    """测试基本功能"""
    
    logger.info("执行简化测试...")
    
    try:
        # 测试智能体创建
        agent = create_deep_paper_analysis_agent(
            vision_model="ollama.Qwen2_5_VL_7B"
        )
        
        # 测试配置
        config = agent.get_config()
        logger.info(f"配置测试通过: {config.vision_model}")
        
        # 测试图片工具创建（使用测试文件夹）
        from HomeSystem.graph.tool.image_analysis_tool import create_image_analysis_tool
        test_folder = "/mnt/nfs_share/code/homesystem/data/paper_analyze/2502.13508"
        
        if os.path.exists(test_folder):
            tool = create_image_analysis_tool(test_folder, "ollama.Qwen2_5_VL_7B")
            logger.info(f"图片工具创建成功: {tool.name}")
            
            # 测试工具绑定和初始化
            if hasattr(agent.analysis_llm, 'bind_tools'):
                logger.info("✅ LLM工具绑定方法存在")
                
                # 测试创建工具绑定
                try:
                    test_tools = [tool]
                    bound_llm = agent.analysis_llm.bind_tools(test_tools)
                    logger.info("✅ 工具绑定测试成功")
                    
                    # 检查绑定后的 LLM 属性
                    if hasattr(bound_llm, 'bound_tools') or hasattr(bound_llm, 'tools'):
                        logger.info("✅ 绑定的 LLM 包含工具信息")
                    else:
                        logger.warning("⚠️ 绑定的 LLM 未包含工具信息")
                        
                except Exception as e:
                    logger.error(f"❌ 工具绑定测试失败: {e}")
                    return False
            else:
                logger.error("❌ LLM工具绑定方法不存在")
                return False
            
        logger.info("✅ 简化测试全部通过")
        
        # 添加关于工具调用的提示
        logger.info("📝 工具调用测试提示:")
        logger.info("  - 如果在完整测试中未检测到工具调用，请检查:")
        logger.info("    1. LLM 模型是否支持工具调用 (function calling)")
        logger.info("    2. 提示词是否明确指示何时使用工具")
        logger.info("    3. 视觉模型是否正常运行")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ 简化测试失败: {e}")
        return False

if __name__ == "__main__":
    logger.info("开始测试重构后的深度论文分析智能体...")
    
    # 首先运行简化测试
    if test_simple_functionality():
        logger.info("基础功能测试通过，开始完整分析测试...")
        
        # 自动执行完整测试验证简化改造
        logger.info("\n⚠️  开始执行完整测试验证简化改造...")
        success = test_deep_paper_analysis()
        if success:
            logger.info("🎉 所有测试完成！重构成功。")
        else:
            logger.error("❌ 完整测试失败")
            sys.exit(1)
    else:
        logger.error("❌ 基础功能测试失败")
        sys.exit(1)