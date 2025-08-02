"""
Markdown渲染工具模块
为ExplorePaperData应用提供统一的Markdown渲染功能
"""
import mistune
from typing import Optional


class MarkdownRenderer:
    """Markdown渲染器，基于mistune库"""
    
    def __init__(self):
        """初始化渲染器"""
        # 创建mistune实例，启用常用插件
        self.markdown = mistune.create_markdown(
            renderer='html',
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
            return html
        except Exception as e:
            # 如果渲染失败，返回转义后的原文本
            import html
            return f'<p>{html.escape(text)}</p>'
    
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