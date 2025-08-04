#!/usr/bin/env python3
"""
数学公式提取工具使用示例

演示如何使用 MathFormulaExtractorTool 从 Markdown 文件或文本中提取数学公式。
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from HomeSystem.graph.tool.math_formula_extractor import MathFormulaExtractorTool
import json
import tempfile

def test_formula_extraction():
    """测试公式提取功能"""
    
    # 创建工具实例
    extractor = MathFormulaExtractorTool()
    
    # 测试用的 Markdown 文本
    test_markdown = """# 数学公式测试文档

这是一个测试文档，包含多种数学公式。

## 单行公式

爱因斯坦质能方程：
$$E = mc^2$$

## 多行公式

高斯积分：
$$
\\int_{-\\infty}^{\\infty} e^{-x^2} dx = \\sqrt{\\pi}
$$

## 复杂公式

傅里叶变换：
$$
F(\\omega) = \\int_{-\\infty}^{\\infty} f(t) e^{-i\\omega t} dt
$$

这里还有一些普通文本。

## 另一个多行公式

麦克斯韦方程组：
$$
\\begin{align}
\\nabla \\cdot \\mathbf{E} &= \\frac{\\rho}{\\epsilon_0} \\\\
\\nabla \\cdot \\mathbf{B} &= 0 \\\\
\\nabla \\times \\mathbf{E} &= -\\frac{\\partial \\mathbf{B}}{\\partial t} \\\\
\\nabla \\times \\mathbf{B} &= \\mu_0 \\mathbf{J} + \\mu_0 \\epsilon_0 \\frac{\\partial \\mathbf{E}}{\\partial t}
\\end{align}
$$

结束文本。

## 同行内多个公式（不会被提取）

这里有行内公式 $x = y + z$ 和另一个 $a = b^2$，它们不会被提取。
"""
    
    print("=" * 60)
    print("数学公式提取工具使用示例")
    print("=" * 60)
    
    # 测试文本模式
    print("\\n1. 测试文本模式：")
    result = extractor._run(markdown_text=test_markdown)
    result_data = json.loads(result)
    
    print(f"提取到 {result_data['total_count']} 个公式：")
    for i, formula in enumerate(result_data['formulas'], 1):
        print(f"\\n公式 {i}:")
        print(f"  行号: {formula['start_line']}-{formula['end_line']}")
        print(f"  内容: {formula['formula']}")
    
    # 测试文件模式
    print("\\n" + "-" * 40)
    print("2. 测试文件模式：")
    
    # 创建临时测试文件
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
        f.write(test_markdown)
        test_file_path = f.name
    
    try:
        result_file = extractor._run(file_path=test_file_path)
        result_file_data = json.loads(result_file)
        
        print(f"从文件 {test_file_path} 提取到 {result_file_data['total_count']} 个公式")
        
        # 显示前2个公式的详细信息
        for i, formula in enumerate(result_file_data['formulas'][:2], 1):
            print(f"\\n公式 {i} (来自文件):")
            print(f"  行号: {formula['start_line']}-{formula['end_line']}")
            print(f"  内容: {formula['formula'][:100]}{'...' if len(formula['formula']) > 100 else ''}")
    
    finally:
        # 清理测试文件
        os.unlink(test_file_path)
    
    # 测试错误处理
    print("\\n" + "-" * 40)
    print("3. 测试错误处理：")
    
    # 测试空输入
    result_empty = extractor._run()
    result_empty_data = json.loads(result_empty)
    print("空输入测试:", "✅ 错误处理正常" if "error" in result_empty_data else "❌ 未正确处理错误")
    
    # 测试不存在的文件
    result_not_found = extractor._run(file_path="/nonexistent/file.md")
    result_not_found_data = json.loads(result_not_found)
    print("文件不存在测试:", "✅ 错误处理正常" if "error" in result_not_found_data else "❌ 未正确处理错误")
    
    print("\\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


def demo_real_usage():
    """演示实际使用场景"""
    print("\\n" + "=" * 60)
    print("实际使用场景演示")
    print("=" * 60)
    
    extractor = MathFormulaExtractorTool()
    
    # 示例：处理包含数学公式的学术论文摘要
    academic_text = """# 深度学习中的注意力机制研究

## 摘要

注意力机制在深度学习中发挥着重要作用。

## 核心公式

自注意力机制的计算公式：
$$
\\text{Attention}(Q, K, V) = \\text{softmax}\\left(\\frac{QK^T}{\\sqrt{d_k}}\\right)V
$$

其中多头注意力定义为：
$$
\\text{MultiHead}(Q, K, V) = \\text{Concat}(\\text{head}_1, \\ldots, \\text{head}_h)W^O
$$

位置编码公式：
$$
PE(pos, 2i) = \\sin\\left(\\frac{pos}{10000^{2i/d_{model}}}\\right)
$$

## 结论

这些公式构成了Transformer架构的核心。
"""
    
    print("处理学术文本示例：")
    result = extractor._run(markdown_text=academic_text)
    result_data = json.loads(result)
    
    print(f"\\n从学术文本中提取到 {result_data['total_count']} 个公式：")
    for i, formula in enumerate(result_data['formulas'], 1):
        print(f"\\n公式 {i}:")
        print(f"  位置: 第 {formula['start_line']} 行" + 
              (f" 到第 {formula['end_line']} 行" if formula['start_line'] != formula['end_line'] else ""))
        print(f"  内容: {formula['formula']}")


if __name__ == "__main__":
    test_formula_extraction()
    demo_real_usage()