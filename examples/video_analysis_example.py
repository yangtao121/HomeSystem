#!/usr/bin/env python3
"""
视频分析工具使用示例

演示如何使用VideoAnalysisTool分析视频内容，包括各种采样方法和分析场景。
"""

import os
import sys
from pathlib import Path

# 添加项目根目录到路径
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.insert(0, str(project_root))

from HomeSystem.graph.tool.video_analysis_tool import create_video_analysis_tool
from HomeSystem.graph.video_utils import get_supported_video_formats


def basic_video_analysis_example():
    """基本视频分析示例"""
    print("=== 基本视频分析示例 ===")
    
    # 创建视频分析工具
    tool = create_video_analysis_tool()
    
    # 显示支持的格式
    print("支持的视频格式:", get_supported_video_formats())
    
    # 示例视频路径（需要替换为实际视频）
    video_path = "sample_video.mp4"  # 替换为你的视频文件路径
    
    if not os.path.exists(video_path):
        print(f"警告: 示例视频文件不存在: {video_path}")
        print("请将示例中的video_path替换为实际存在的视频文件路径")
        return
    
    try:
        # 1. 验证视频文件
        print("\n1. 验证视频文件...")
        validation = tool.validate_video(video_path)
        print(f"验证结果: {validation['is_valid']}")
        
        if validation['is_valid']:
            video_info = validation['video_info']
            print(f"视频信息:")
            print(f"  - 文件名: {video_info['filename']}")
            print(f"  - 时长: {video_info['duration']:.1f}秒")
            print(f"  - 帧率: {video_info['fps']:.1f} FPS")
            print(f"  - 分辨率: {video_info['resolution']}")
            print(f"  - 文件大小: {video_info['file_size_mb']} MB")
        else:
            print(f"视频验证失败: {validation['error_message']}")
            return
        
        # 2. 基本视频分析
        print("\n2. 执行基本视频分析...")
        analysis_result = tool._run(
            analysis_query="请分析这个视频的主要内容，描述关键场景、人物和活动",
            video_path=video_path,
            frame_count=5,
            sampling_method="sequential"
        )
        
        print("分析结果:")
        print("-" * 60)
        print(analysis_result)
        print("-" * 60)
        
    except Exception as e:
        print(f"基本分析示例失败: {e}")


def different_sampling_methods_example():
    """不同采样方法对比示例"""
    print("\n=== 不同采样方法对比示例 ===")
    
    video_path = "sample_video.mp4"  # 替换为实际视频路径
    
    if not os.path.exists(video_path):
        print("跳过采样方法对比示例（视频文件不存在）")
        return
    
    tool = create_video_analysis_tool()
    
    # 测试不同的采样方法
    sampling_methods = ["first", "sequential", "random", "middle_random"]
    
    for method in sampling_methods:
        try:
            print(f"\n--- 采样方法: {method} ---")
            
            result = tool._run(
                analysis_query=f"使用{method}采样方法分析视频内容",
                video_path=video_path,
                frame_count=3,
                sampling_method=method
            )
            
            # 显示简化的结果（只显示前200字符）
            print(f"分析结果预览: {result[:200]}...")
            
        except Exception as e:
            print(f"采样方法 {method} 失败: {e}")


def specific_analysis_scenarios():
    """特定分析场景示例"""
    print("\n=== 特定分析场景示例 ===")
    
    video_path = "sample_video.mp4"  # 替换为实际视频路径
    
    if not os.path.exists(video_path):
        print("跳过特定场景分析示例（视频文件不存在）")
        return
    
    tool = create_video_analysis_tool()
    
    # 不同的分析查询示例
    analysis_scenarios = [
        {
            "name": "内容概述",
            "query": "简要描述这个视频的主要内容和主题",
            "frames": 3,
            "method": "sequential"
        },
        {
            "name": "人物识别",
            "query": "识别视频中出现的人物，描述他们的外观和行为",
            "frames": 5,
            "method": "random"
        },
        {
            "name": "场景分析",
            "query": "分析视频中的场景设置、环境和背景信息",
            "frames": 4,
            "method": "middle_random"
        },
        {
            "name": "技术内容",
            "query": "如果这是技术演示或教学视频，请分析技术要点和关键信息",
            "frames": 6,
            "method": "sequential"
        }
    ]
    
    for scenario in analysis_scenarios:
        try:
            print(f"\n--- {scenario['name']} ---")
            print(f"查询: {scenario['query']}")
            print(f"参数: {scenario['frames']}帧, {scenario['method']}采样")
            
            result = tool._run(
                analysis_query=scenario['query'],
                video_path=video_path,
                frame_count=scenario['frames'],
                sampling_method=scenario['method']
            )
            
            # 显示结果摘要
            lines = result.split('\n')
            summary_lines = [line for line in lines[:10] if line.strip()]
            print("分析结果摘要:")
            for line in summary_lines:
                print(f"  {line}")
            print("  ...")
            
        except Exception as e:
            print(f"场景分析失败 {scenario['name']}: {e}")


def tool_integration_example():
    """工具集成使用示例"""
    print("\n=== 工具集成使用示例 ===")
    
    # 演示如何在LangGraph中使用这个工具
    print("在LangGraph Agent中使用VideoAnalysisTool的示例:")
    
    example_code = '''
# 在Agent中集成VideoAnalysisTool
from HomeSystem.graph.tool.video_analysis_tool import create_video_analysis_tool

class VideoAnalysisAgent(BaseAgent):
    def __init__(self):
        super().__init__()
        
        # 创建视频分析工具
        self.video_tool = create_video_analysis_tool(
            base_folder_path="/path/to/video/folder",
            vision_model="ollama.Qwen2_5_VL_7B"
        )
        
        # 添加到工具列表
        self.tools.append(self.video_tool)
    
    def analyze_video_content(self, video_path: str):
        """分析视频内容的方法"""
        return self.video_tool._run(
            analysis_query="全面分析这个视频的内容",
            video_path=video_path,
            frame_count=5,
            sampling_method="sequential"
        )
'''
    
    print(example_code)


def performance_and_optimization_tips():
    """性能优化建议"""
    print("\n=== 性能优化建议 ===")
    
    tips = [
        "1. 帧数选择: 一般视频使用3-5帧，长视频可适当增加到8-10帧",
        "2. 采样策略: sequential适合分析视频流程，random适合内容丰富的视频",
        "3. 视频长度: 过长视频建议先切分或使用middle_random采样",
        "4. 内存管理: 工具会自动清理临时帧文件，无需手动管理",
        "5. 模型选择: Qwen2_5_VL_7B在准确性和速度间有良好平衡",
        "6. 并发处理: 可以并行处理多个视频文件提高效率"
    ]
    
    for tip in tips:
        print(tip)


def main():
    """主函数"""
    print("视频分析工具完整使用示例")
    print("=" * 50)
    
    # 基本使用示例
    basic_video_analysis_example()
    
    # 不同采样方法对比
    different_sampling_methods_example()
    
    # 特定分析场景
    specific_analysis_scenarios()
    
    # 工具集成示例
    tool_integration_example()
    
    # 性能优化建议
    performance_and_optimization_tips()
    
    print("\n" + "=" * 50)
    print("示例运行完成!")
    print("\n使用说明:")
    print("1. 将示例中的 'sample_video.mp4' 替换为实际存在的视频文件路径")
    print("2. 确保已安装必要的依赖: opencv-python, langchain等")
    print("3. 确保本地VL模型 (如ollama.Qwen2_5_VL_7B) 可用")
    print("4. 根据具体需求调整分析查询和参数")


if __name__ == "__main__":
    main()