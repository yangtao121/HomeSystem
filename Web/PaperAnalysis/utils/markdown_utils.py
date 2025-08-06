"""
Markdown渲染工具模块
为ExplorePaperData应用提供统一的Markdown渲染功能
"""
import mistune
import re
from typing import Optional


class FixedMathRenderer(mistune.HTMLRenderer):
    """修复数学公式渲染问题的自定义渲染器"""
    
    def math(self, text):
        """修复的数学公式渲染方法"""
        # 对于单行数学公式，使用span标签
        return f'<span class="math">\\({text}\\)</span>'
    
    def block_math(self, text):
        """块级数学公式渲染方法"""
        # 对于多行数学公式，使用div标签
        return f'<div class="math">$$\n{text}\n$$</div>'


class MarkdownRenderer:
    """Markdown渲染器，基于mistune库，修复了数学公式渲染问题"""
    
    def __init__(self):
        """初始化渲染器"""
        # 创建自定义渲染器实例
        self.renderer = FixedMathRenderer()
        
        # 创建mistune实例，使用自定义渲染器和插件
        self.markdown = mistune.create_markdown(
            renderer=self.renderer,
            plugins=[
                'strikethrough',  # 删除线支持 ~~text~~
                'footnotes',      # 脚注支持
                'table',          # 表格支持
                'task_lists',     # 任务列表支持 - [x] item
                'def_list',       # 定义列表支持
                'abbr',           # 缩写支持
                'mark',           # 高亮支持 ==text==
                'insert',         # 插入支持 ++text++
                'superscript',    # 上标支持 ^text^
                'subscript',      # 下标支持 ~text~
                'url',            # 自动链接
                'math',           # 数学公式支持（需要客户端渲染）
            ]
        )
    
    def render(self, text: Optional[str]) -> str:
        """
        渲染Markdown文本为HTML
        
        Args:
            text: 要渲染的Markdown文本
            
        Returns:
            渲染后的HTML字符串
        """
        if not text:
            return ""
        
        # 处理字符串类型
        text = str(text).strip()
        if not text:
            return ""
        
        try:
            # 渲染Markdown
            html = self.markdown(text)
            
            # 后处理：清理mistune math插件留下的多余美元符号
            html = self._fix_math_symbols(html)
            
            return html
        except Exception as e:
            # 如果渲染失败，返回转义后的原文本
            import html
            return f'<p>{html.escape(text)}</p>'
    
    def _fix_math_symbols(self, html: str) -> str:
        """
        修复mistune math插件留下的多余美元符号
        
        问题: mistune的math插件在处理$$...$$时会产生:
        <span class="math">\($...\)</span>$
        
        应该修复为:
        <span class="math">\(...\)</span>
        
        Args:
            html: 渲染后的HTML字符串
            
        Returns:
            修复后的HTML字符串
        """
        # 简单有效的修复：
        # 1. 将 \($ 改为 \(，移除显示数学公式中多余的美元符号
        # 2. 将 \)</span>$ 改为 \)</span>，移除span后的多余美元符号
        html = html.replace('\\($', '\\(')
        html = html.replace('\\)</span>$', '\\)</span>')
        
        return html
    
    def render_safe(self, text: Optional[str]) -> str:
        """
        安全渲染Markdown文本（转义HTML特殊字符）
        
        Args:
            text: 要渲染的Markdown文本
            
        Returns:
            安全的HTML字符串
        """
        if not text:
            return ""
        
        # 先进行HTML转义，然后渲染Markdown
        import html
        escaped_text = html.escape(str(text))
        return self.render(escaped_text)


# 全局渲染器实例
_renderer = None


def get_renderer() -> MarkdownRenderer:
    """获取全局渲染器实例"""
    global _renderer
    if _renderer is None:
        _renderer = MarkdownRenderer()
    return _renderer


def render_markdown(text: Optional[str]) -> str:
    """
    便捷函数：渲染Markdown文本
    
    Args:
        text: 要渲染的Markdown文本
        
    Returns:
        渲染后的HTML字符串
    """
    renderer = get_renderer()
    return renderer.render(text)


def render_markdown_safe(text: Optional[str]) -> str:
    """
    便捷函数：安全渲染Markdown文本
    
    Args:
        text: 要渲染的Markdown文本
        
    Returns:
        安全的HTML字符串
    """
    renderer = get_renderer()
    return renderer.render_safe(text)


# 模板过滤器函数
def markdown_filter(text: Optional[str]) -> str:
    """
    Flask模板过滤器：渲染Markdown
    
    Args:
        text: 要渲染的Markdown文本
        
    Returns:
        渲染后的HTML字符串，可以直接在模板中使用|safe
    """
    return render_markdown(text)


def markdown_safe_filter(text: Optional[str]) -> str:
    """
    Flask模板过滤器：安全渲染Markdown
    
    Args:
        text: 要渲染的Markdown文本
        
    Returns:
        安全的HTML字符串，可以直接在模板中使用|safe
    """
    return render_markdown_safe(text)


if __name__ == "__main__":
    # 测试代码
    test_markdown = """
# 测试标题

这是一个**粗体**文本和*斜体*文本的例子。

## 列表测试

- 项目1
- 项目2
  - 子项目2.1
  - 子项目2.2

## 代码测试

```python
def hello_world():
    print("Hello, World!")
```

## 表格测试

| 列1 | 列2 | 列3 |
|-----|-----|-----|
| 数据1 | 数据2 | 数据3 |
| 数据4 | 数据5 | 数据6 |

## 任务列表

- [x] 已完成任务
- [ ] 待完成任务

## 其他格式

~~删除线文本~~  
==高亮文本==  
H~2~O（下标）  
x^2^（上标）  

> 这是一个引用块
> 可以包含多行内容

---

**注意**: 这只是一个测试文档。
"""
    
    renderer = MarkdownRenderer()
    html_output = renderer.render(test_markdown)
    print("渲染结果:")
    print(html_output)