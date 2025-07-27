# ArXiv API 工具文档

## 概述

HomeSystem ArXiv 工具是一个用于搜索和获取 ArXiv 学术论文的 Python 库。该工具完全基于 ArXiv 官方 API，提供高性能、无限制的论文搜索功能，支持获取最新论文数据。

## 主要特性

- ✅ **直接 API 访问**: 使用 ArXiv 官方 API，无第三方依赖
- ✅ **无搜索限制**: 支持大量结果检索（最多 2000 条）
- ✅ **最新数据**: 获取实时更新的论文信息
- ✅ **多种排序**: 支持相关性、提交日期、更新日期排序
- ✅ **PDF 下载**: 内置 PDF 下载功能，支持进度条
- ✅ **元数据提取**: 自动提取论文 ID、发布时间等信息
- ✅ **错误处理**: 完善的异常处理和日志记录

## 安装依赖

```bash
pip install requests xml feedparser loguru tqdm
```

## 快速开始

```python
from HomeSystem.utility.arxiv.arxiv import ArxivTool

# 创建工具实例
arxiv_tool = ArxivTool()

# 基础搜索
results = arxiv_tool.arxivSearch("machine learning", num_results=20)

# 遍历结果
for paper in results:
    print(f"标题: {paper.title}")
    print(f"发布时间: {paper.published_date}")
    print(f"链接: {paper.link}")
    print("-" * 50)
```

## API 参考

### 类结构

#### ArxivData

单个论文的数据容器类。

**属性**:
- `title` (str): 论文标题
- `link` (str): ArXiv 链接
- `snippet` (str): 论文摘要
- `categories` (str): 论文分类
- `pdf_link` (str): PDF 下载链接
- `arxiv_id` (str): ArXiv ID
- `published_date` (str): 发布日期
- `tag` (list[str]): 论文标签
- `pdf` (bytes): PDF 内容（下载后）
- `pdf_path` (str): PDF 保存路径

**方法**:

##### `setTag(tag: list[str])`
设置论文标签。

```python
paper = results.results[0]
paper.setTag(["AI", "深度学习", "计算机视觉"])
```

##### `get_formatted_info() -> str`
获取格式化的论文信息。

```python
info = paper.get_formatted_info()
print(info)
```

##### `downloadPdf(save_path: str = None) -> bytes`
下载论文 PDF。

**参数**:
- `save_path` (str, optional): PDF 保存目录路径

**返回**: PDF 内容的字节数据

**异常**:
- `ValueError`: PDF 链接为空
- `Exception`: 下载或保存失败

```python
# 仅下载到内存
pdf_content = paper.downloadPdf()

# 下载并保存到文件
pdf_content = paper.downloadPdf(save_path="/path/to/save/directory")
```

##### `clearPdf()`
清空 PDF 内容，释放内存。

```python
paper.clearPdf()
```

#### ArxivResult

搜索结果容器类，提供多种结构化显示功能。

**属性**:
- `results` (list[ArxivData]): 论文数据列表
- `num_results` (int): 结果数量

**方法**:
- 支持迭代器协议，可直接遍历

```python
for paper in results:
    print(paper.title)
```

##### `display_results(display_range="all", max_display=10, show_details=True, show_summary=True)`
结构化显示搜索结果的主要方法。

**参数**:
- `display_range` (str): 显示范围，"all" 显示全部，"limited" 限制数量
- `max_display` (int): 当 display_range 为 "limited" 时的最大显示数量
- `show_details` (bool): 是否显示详细信息
- `show_summary` (bool): 是否显示摘要统计

```python
# 显示全部结果
results.display_results()

# 只显示前5个，包含摘要统计
results.display_results(display_range="limited", max_display=5, show_summary=True)

# 只显示标题，不显示摘要
results.display_results(show_details=True, show_summary=False)
```

##### `display_brief(max_display=5)`
简洁显示模式，只显示标题和基本信息。

**参数**:
- `max_display` (int): 最大显示数量

```python
# 简洁显示前5篇论文
results.display_brief(max_display=5)
```

##### `display_titles_only(max_display=None)`
仅显示论文标题列表。

**参数**:
- `max_display` (int, optional): 最大显示数量，None 则显示全部

```python
# 仅显示所有标题
results.display_titles_only()

# 仅显示前10个标题
results.display_titles_only(max_display=10)
```

##### `get_papers_by_date_range(start_year=None, end_year=None) -> ArxivResult`
根据发布年份筛选论文。

**参数**:
- `start_year` (int, optional): 开始年份
- `end_year` (int, optional): 结束年份

**返回**: 筛选后的 ArxivResult 对象

```python
# 筛选2020年后的论文
recent_papers = results.get_papers_by_date_range(start_year=2020)

# 筛选2018-2022年的论文
period_papers = results.get_papers_by_date_range(start_year=2018, end_year=2022)
```

#### ArxivTool

主要的搜索工具类。

##### `__init__(search_host: str = None)`
构造函数。

**参数**:
- `search_host` (str, optional): 保留参数，兼容旧版本

```python
arxiv_tool = ArxivTool()
```

##### `arxivSearch(query, num_results=20, sort_by="relevance", order="desc", max_results=None, kwargs=None, use_direct_api=True) -> ArxivResult`
主要搜索方法。

**参数**:
- `query` (str): 搜索查询
- `num_results` (int, default=20): 返回结果数量
- `sort_by` (str, default="relevance"): 排序方式
  - `"relevance"`: 相关性
  - `"lastUpdatedDate"`: 最后更新日期
  - `"submittedDate"`: 提交日期
- `order` (str, default="desc"): 排序顺序
  - `"desc"`: 降序
  - `"asc"`: 升序
- `max_results` (int, optional): 保留参数，兼容旧版本
- `kwargs` (dict, optional): 保留参数，兼容旧版本
- `use_direct_api` (bool, default=True): 保留参数，总是使用直接 API

**返回**: ArxivResult 对象

```python
# 基础搜索
results = arxiv_tool.arxivSearch("deep learning")

# 获取大量结果
results = arxiv_tool.arxivSearch("neural networks", num_results=100)

# 按提交日期排序
results = arxiv_tool.arxivSearch("computer vision", 
                                sort_by="submittedDate", 
                                order="desc")
```

##### `getLatestPapers(query: str, num_results: int = 20) -> ArxivResult`
获取最新论文。

```python
latest = arxiv_tool.getLatestPapers("machine learning", num_results=30)
```

##### `getRecentlyUpdated(query: str, num_results: int = 20) -> ArxivResult`
获取最近更新的论文。

```python
updated = arxiv_tool.getRecentlyUpdated("artificial intelligence", num_results=25)
```

##### `searchWithHighLimit(query, num_results=50, sort_by="relevance", order="desc", max_single_request=20) -> ArxivResult`
高限制搜索方法。

```python
large_results = arxiv_tool.searchWithHighLimit("NLP", num_results=200)
```

##### `directArxivSearch(query, num_results=20, sort_by="relevance", order="descending") -> ArxivResult`
直接 ArXiv API 搜索。

```python
direct_results = arxiv_tool.directArxivSearch("reinforcement learning", 
                                            num_results=50,
                                            sort_by="submittedDate",
                                            order="descending")
```

##### `getLatestPapersDirectly(query: str, num_results: int = 20) -> ArxivResult`
直接获取最新论文。

```python
latest_direct = arxiv_tool.getLatestPapersDirectly("GAN", num_results=40)
```

## 使用示例

### 1. 基础搜索和结果处理

```python
from HomeSystem.utility.arxiv.arxiv import ArxivTool

# 创建工具实例
arxiv = ArxivTool()

# 搜索论文
results = arxiv.arxivSearch("transformer architecture", num_results=10)

print(f"找到 {results.num_results} 篇论文:")
for i, paper in enumerate(results, 1):
    print(f"\n{i}. {paper.title}")
    print(f"   ArXiv ID: {paper.arxiv_id}")
    print(f"   发布时间: {paper.published_date}")
    print(f"   分类: {paper.categories}")
    print(f"   链接: {paper.link}")
    print(f"   摘要: {paper.snippet[:200]}...")
```

### 2. 获取最新论文

```python
# 获取最新的深度学习论文
latest_papers = arxiv.getLatestPapers("deep learning", num_results=20)

print("最新的深度学习论文:")
for paper in latest_papers:
    print(f"📄 {paper.title}")
    print(f"🕒 {paper.published_date}")
    print(f"🔗 {paper.link}")
    print("-" * 80)
```

### 3. 大量数据检索

```python
# 获取大量神经网络相关论文
large_dataset = arxiv.arxivSearch("neural network", num_results=500)

print(f"检索到 {large_dataset.num_results} 篇论文")

# 按发布时间统计
date_counts = {}
for paper in large_dataset:
    date = paper.published_date
    date_counts[date] = date_counts.get(date, 0) + 1

print("论文发布时间分布:")
for date, count in sorted(date_counts.items(), reverse=True)[:10]:
    print(f"{date}: {count} 篇")
```

### 4. PDF 下载

```python
# 搜索并下载PDF
results = arxiv.arxivSearch("attention mechanism", num_results=5)

for i, paper in enumerate(results):
    try:
        print(f"下载论文 {i+1}: {paper.title[:50]}...")
        
        # 下载PDF到指定目录
        pdf_content = paper.downloadPdf(save_path="./downloads")
        print(f"✅ 下载成功: {paper.pdf_path}")
        
        # 释放内存
        paper.clearPdf()
        
    except Exception as e:
        print(f"❌ 下载失败: {e}")
```

### 5. 按不同条件排序

```python
# 按相关性排序
relevance_results = arxiv.arxivSearch("BERT", 
                                    sort_by="relevance", 
                                    order="desc", 
                                    num_results=15)

# 按提交日期排序（最新的）
newest_results = arxiv.arxivSearch("BERT", 
                                 sort_by="submittedDate", 
                                 order="desc", 
                                 num_results=15)

# 按更新日期排序
updated_results = arxiv.getRecentlyUpdated("BERT", num_results=15)

print("按相关性排序的前3篇:")
for i, paper in enumerate(relevance_results.results[:3], 1):
    print(f"{i}. {paper.title}")

print("\n按提交日期排序的前3篇:")
for i, paper in enumerate(newest_results.results[:3], 1):
    print(f"{i}. {paper.title} ({paper.published_date})")
```

### 6. 论文标签管理

```python
results = arxiv.arxivSearch("computer vision", num_results=10)

# 为论文添加标签
for paper in results:
    # 根据标题或摘要添加相应标签
    tags = []
    
    if "CNN" in paper.title or "convolutional" in paper.snippet.lower():
        tags.append("CNN")
    if "object detection" in paper.snippet.lower():
        tags.append("目标检测")
    if "image" in paper.snippet.lower():
        tags.append("图像处理")
    
    if tags:
        paper.setTag(tags)
        print(f"论文: {paper.title[:50]}...")
        print(f"标签: {', '.join(paper.tag)}")
        print("-" * 50)
```

### 7. 结构化显示功能演示

```python
# 创建工具实例
arxiv = ArxivTool()

# 搜索机器学习相关论文
results = arxiv.arxivSearch("machine learning", num_results=20)

print("=== 结构化显示功能演示 ===")

# 1. 完整显示前5个结果
print("📋 完整显示前5个结果:")
results.display_results(display_range="limited", max_display=5)

print("\n" + "="*80 + "\n")

# 2. 简洁显示模式
print("📋 简洁显示模式:")
results.display_brief(max_display=7)

print("\n" + "="*80 + "\n")

# 3. 仅显示标题
print("📋 仅显示标题:")
results.display_titles_only(max_display=10)

print("\n" + "="*80 + "\n")

# 4. 显示全部结果（适合小数据集）
small_results = arxiv.arxivSearch("quantum computing", num_results=5)
print("📋 显示全部结果:")
small_results.display_results(display_range="all", show_summary=True)

print("\n" + "="*80 + "\n")

# 5. 年份筛选和显示
print("📋 年份筛选演示:")
recent_papers = results.get_papers_by_date_range(start_year=2020)
if recent_papers.num_results > 0:
    print(f"找到 {recent_papers.num_results} 篇2020年后的论文")
    recent_papers.display_brief(max_display=3)
else:
    print("未找到2020年后的论文")
```

### 8. 错误处理和重试

```python
import time

def robust_search(arxiv_tool, query, num_results=20, max_retries=3):
    """带重试机制的搜索"""
    for attempt in range(max_retries):
        try:
            results = arxiv_tool.arxivSearch(query, num_results=num_results)
            if results.num_results > 0:
                return results
            else:
                print(f"尝试 {attempt + 1}: 未找到结果")
        except Exception as e:
            print(f"尝试 {attempt + 1} 失败: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # 指数退避
    
    return None

# 使用示例
arxiv = ArxivTool()
results = robust_search(arxiv, "quantum computing", num_results=30)

if results:
    print(f"成功获取 {results.num_results} 个结果")
    # 使用结构化显示
    results.display_brief()
else:
    print("搜索失败")
```

## 最佳实践

### 1. 搜索查询优化

```python
# 使用具体的查询词
good_query = "transformer attention mechanism NLP"
bad_query = "AI"

# 使用ArXiv分类标识符
category_query = "cat:cs.LG"  # 机器学习类别

# 组合查询
complex_query = "ti:transformer AND cat:cs.CL"  # 标题包含transformer且属于计算语言学
```

### 2. 内存管理

```python
# 处理大量论文时及时清理PDF内容
results = arxiv.arxivSearch("deep learning", num_results=100)

for paper in results:
    # 处理论文信息
    process_paper_metadata(paper)
    
    # 如果需要PDF，下载后及时清理
    if need_pdf(paper):
        pdf_content = paper.downloadPdf()
        process_pdf(pdf_content)
        paper.clearPdf()  # 释放内存
```

### 3. 批量处理

```python
def batch_download_papers(queries, papers_per_query=20, save_dir="./papers"):
    """批量下载多个查询的论文"""
    arxiv = ArxivTool()
    all_papers = []
    
    for query in queries:
        print(f"搜索: {query}")
        results = arxiv.arxivSearch(query, num_results=papers_per_query)
        
        for paper in results:
            try:
                paper.downloadPdf(save_path=save_dir)
                all_papers.append(paper)
                paper.clearPdf()  # 释放内存
            except Exception as e:
                print(f"下载失败 {paper.title}: {e}")
    
    return all_papers

# 使用示例
queries = ["neural architecture search", "few-shot learning", "meta learning"]
papers = batch_download_papers(queries, papers_per_query=10)
print(f"总共下载了 {len(papers)} 篇论文")
```

## 限制说明

1. **API 限制**: ArXiv API 单次请求最多返回 2000 个结果
2. **请求频率**: 建议控制请求频率，避免过于频繁的API调用
3. **PDF 下载**: 大量PDF下载时注意网络带宽和存储空间
4. **内存使用**: 处理大量论文时注意内存管理

## 错误处理

常见错误及解决方案:

1. **网络连接错误**: 检查网络连接，重试请求
2. **ArXiv API 超时**: 增加超时设置，使用重试机制
3. **PDF 下载失败**: 检查链接有效性，重试下载
4. **内存不足**: 及时清理PDF内容，分批处理

## 更新日志

### v2.0.0 (当前版本)
- ✅ 完全移除 SearxNG 依赖
- ✅ 使用 ArXiv 官方 API
- ✅ 支持无限制搜索结果
- ✅ 优化性能和稳定性
- ✅ 保持向后兼容性

### v1.x.x (已废弃)
- ❌ 基于 SearxNG 搜索
- ❌ 搜索结果限制为 10 条
- ❌ 数据更新不及时

## 贡献和支持

如有问题或建议，请提交 Issue 或 Pull Request。

## 许可证

请遵循项目的许可证要求。