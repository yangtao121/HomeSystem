import os
import json
import requests
import time
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone
from requests import Session, Response
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from loguru import logger


class SiYuanAPIError(Exception):
    """Base exception for SiYuan API errors"""

    def __init__(self, message: str, error_code: Optional[str] = None, response: Optional[Response] = None):
        super().__init__(message)
        self.error_code = error_code
        self.response = response
        self.timestamp = datetime.now(timezone.utc)


@dataclass
class NoteInfo:
    """笔记信息数据结构"""
    note_id: str
    title: str
    content: Optional[str] = None
    notebook_id: Optional[str] = None
    notebook_name: Optional[str] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    tags: List[str] = field(default_factory=list)
    path: Optional[str] = None
    parent_id: Optional[str] = None
    note_type: str = "doc"  # doc, heading, list, etc.
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """搜索结果数据结构"""
    query: str
    results: List[Dict[str, Any]]
    total_count: int
    search_time: float  # ms
    filters_applied: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SiYuanClient:
    """
    SiYuan Notes API 客户端
    支持笔记 CRUD 操作、搜索、SQL 查询等功能
    """

    def __init__(
        self,
        base_url: str,
        api_token: Optional[str] = None,
        timeout: int = 30,
        max_retries: int = 3
    ):
        """
        初始化 SiYuan API 客户端

        :param base_url: SiYuan 服务器地址 (e.g., "http://localhost:6806")
        :param api_token: API 认证令牌
        :param timeout: 请求超时时间（秒）
        :param max_retries: 最大重试次数
        """
        self.base_url = base_url.rstrip('/')
        self.api_token = api_token
        self.timeout = timeout

        # 配置会话和重试策略
        self.session = Session()
        retry = Retry(
            total=max_retries,
            backoff_factor=0.3,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=['GET', 'POST', 'PUT', 'DELETE']
        )
        self.session.mount('https://', HTTPAdapter(max_retries=retry))
        self.session.mount('http://', HTTPAdapter(max_retries=retry))

        # 设置认证头
        self._setup_auth()

    def _setup_auth(self):
        """设置认证头"""
        if self.api_token:
            self.session.headers.update({
                'Authorization': f'token {self.api_token}',
                'Content-Type': 'application/json'
            })

    @classmethod
    def from_environment(cls) -> 'SiYuanClient':
        """Create SiYuan client using environment variables"""
        return cls(
            base_url=os.getenv('SIYUAN_API_URL', 'http://127.0.0.1:6806'),
            api_token=os.getenv('SIYUAN_API_TOKEN', ''),
            timeout=int(os.getenv('SIYUAN_TIMEOUT', '30'))
        )

    def test_connection(self) -> Dict[str, Any]:
        """
        测试 SiYuan 连接
        :return: 连接测试结果
        """
        try:
            start_time = time.time()
            # 使用最简单的 SQL 查询来测试连接
            test_query = "SELECT COUNT(*) as count FROM blocks LIMIT 1"
            response = self._api_request('/api/query/sql', {'stmt': test_query})
            response_time = (time.time() - start_time) * 1000  # ms

            if response.get('code') == 0:
                data = response.get('data', [])
                block_count = data[0].get('count', 0) if data else 0

                return {
                    'success': True,
                    'response_time': response_time,
                    'version': 'SiYuan',
                    'capabilities': ['note_create', 'note_search', 'note_update', 'block_operations', 'sql_query'],
                    'block_count': block_count,
                    'api_accessible': True
                }
            else:
                raise SiYuanAPIError(f"API returned error code: {response.get('code')}")

        except Exception as e:
            logger.error(f"SiYuan connection test failed: {str(e)}")
            return {
                'success': False,
                'error_message': str(e),
                'response_time': 0
            }

    def check_health(self) -> Dict[str, Any]:
        """
        检查 SiYuan 健康状态
        :return: 健康检查结果
        """
        try:
            start_time = time.time()
            # 使用简单的 SQL 查询检查系统状态
            health_query = "SELECT COUNT(*) as total_blocks FROM blocks"
            response = self._api_request('/api/query/sql', {'stmt': health_query})
            response_time = (time.time() - start_time) * 1000  # ms

            if response.get('code') == 0:
                data = response.get('data', [])
                total_blocks = data[0].get('total_blocks', 0) if data else 0

                return {
                    'status': 'healthy',
                    'response_time': response_time,
                    'total_blocks': total_blocks,
                    'api_accessible': True,
                    'last_check': datetime.now(timezone.utc).isoformat()
                }
            else:
                raise SiYuanAPIError(f"Health check failed: API error {response.get('code')}")

        except Exception as e:
            logger.error(f"SiYuan health check failed: {str(e)}")
            return {
                'status': 'unhealthy',
                'error_message': str(e),
                'response_time': 0,
                'last_check': datetime.now(timezone.utc).isoformat()
            }

    def get_notebooks(self) -> List[Dict[str, Any]]:
        """
        获取所有笔记本
        :return: 笔记本列表
        """
        try:
            response = self._api_request('/api/notebook/lsNotebooks', {})
            return response.get('data', {}).get('notebooks', [])
        except Exception as e:
            logger.error(f"Failed to get notebooks: {str(e)}")
            raise SiYuanAPIError(f"Get notebooks failed: {str(e)}")

    def search_notes(
        self,
        query: str,
        notebook_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> SearchResult:
        """
        搜索笔记
        :param query: 搜索关键词
        :param notebook_id: 指定笔记本 ID（可选）
        :param limit: 返回结果数量限制
        :param offset: 结果偏移量
        :return: 搜索结果
        """
        start_time = time.time()

        try:
            # 构建搜索 SQL
            sql_query = f"""
            SELECT * FROM blocks 
            WHERE type = 'd' AND (content LIKE '%{query}%' OR name LIKE '%{query}%')
            """

            if notebook_id:
                sql_query += f" AND box = '{notebook_id}'"

            sql_query += f" ORDER BY updated DESC LIMIT {limit} OFFSET {offset}"

            # 执行搜索
            search_result = self._api_request('/api/query/sql', {
                'stmt': sql_query
            })

            blocks = search_result.get('data', [])

            # 转换搜索结果
            notes = []
            for block in blocks:
                note = self._convert_note(block)
                notes.append({
                    'id': note.note_id,
                    'title': note.title,
                    'content': note.content,
                    'notebook': note.notebook_name,
                    'tags': note.tags,
                    'created_time': note.created_time.isoformat() if note.created_time else None,
                    'updated_time': note.updated_time.isoformat() if note.updated_time else None,
                    'path': note.path,
                    'relevance_score': 1.0  # SiYuan 不提供相关性评分
                })

            # 获取总数（需要单独查询）
            count_query = sql_query.replace('SELECT *', 'SELECT COUNT(*) as count')
            count_query = count_query.split('ORDER BY')[0]  # 移除 ORDER BY 和 LIMIT
            count_result = self._api_request('/api/query/sql', {
                'stmt': count_query
            })
            total_count = count_result.get('data', [{}])[0].get('count', 0)

            search_time = (time.time() - start_time) * 1000

            return SearchResult(
                query=query,
                results=notes,
                total_count=total_count,
                search_time=search_time,
                filters_applied={'notebook_id': notebook_id} if notebook_id else {},
                metadata={
                    'sql_query': sql_query
                }
            )

        except Exception as e:
            logger.error(f"SiYuan note search failed: {str(e)}")
            raise SiYuanAPIError(f"Note search failed: {str(e)}")

    def execute_sql(self, sql: str) -> List[Dict[str, Any]]:
        """
        执行 SQL 查询
        :param sql: SQL 查询语句
        :return: 查询结果列表
        """
        try:
            response = self._api_request('/api/query/sql', {'stmt': sql})
            return response.get('data', [])
        except Exception as e:
            logger.error(f"SQL query failed: {str(e)}")
            raise SiYuanAPIError(f"SQL query failed: {str(e)}")

    def health_check(self) -> Dict[str, Any]:
        """
        健康检查
        :return: 健康状态信息
        """
        try:
            start_time = time.time()
            # 使用简单查询检查健康状态
            response = self._api_request('/api/query/sql', {'stmt': 'SELECT 1 as health'})
            response_time = (time.time() - start_time) * 1000
            
            if response.get('code') == 0:
                return {
                    'is_healthy': True,
                    'response_time': response_time,
                    'details': {
                        'api_accessible': True,
                        'database_accessible': True
                    }
                }
            else:
                return {
                    'is_healthy': False,
                    'response_time': response_time,
                    'details': {
                        'error': response.get('msg', 'Unknown error')
                    }
                }
        except Exception as e:
            return {
                'is_healthy': False,
                'response_time': 0,
                'details': {
                    'error': str(e)
                }
            }

    def create_note(
        self,
        notebook_id: str,
        title: str,
        content: str,
        parent_id: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> NoteInfo:
        """
        创建笔记
        :param notebook_id: 笔记本 ID
        :param title: 笔记标题
        :param content: 笔记内容（Markdown 格式）
        :param parent_id: 父笔记 ID（可选）
        :param tags: 标签列表（可选）
        :return: 创建的笔记信息
        """
        try:
            # 创建文档
            create_data = {
                'notebook': notebook_id,
                'path': f"/{title}",
                'md': content
            }

            if parent_id:
                create_data['parentID'] = parent_id

            response = self._api_request('/api/filetree/createDoc', create_data)
            note_id = response.get('data')

            if not note_id:
                raise SiYuanAPIError("Failed to create note: no ID returned")

            # 如果有标签，添加标签
            if tags:
                for tag in tags:
                    self._api_request('/api/attr/setBlockAttrs', {
                        'id': note_id,
                        'attrs': {'custom-tag': tag}
                    })

            # 获取创建的笔记详情
            return self.get_note(note_id)

        except Exception as e:
            logger.error(f"Failed to create note: {str(e)}")
            raise SiYuanAPIError(f"Note creation failed: {str(e)}")

    def update_note(
        self,
        note_id: str,
        content: Optional[str] = None,
        title: Optional[str] = None
    ) -> NoteInfo:
        """
        更新笔记
        :param note_id: 笔记 ID
        :param content: 新内容（可选）
        :param title: 新标题（可选）
        :return: 更新后的笔记信息
        """
        try:
            # 更新内容
            if content is not None:
                self._api_request('/api/block/updateBlock', {
                    'id': note_id,
                    'data': content,
                    'dataType': 'markdown'
                })

            # 更新标题
            if title is not None:
                self._api_request('/api/attr/setBlockAttrs', {
                    'id': note_id,
                    'attrs': {'name': title}
                })

            # 返回更新后的笔记
            return self.get_note(note_id)

        except Exception as e:
            logger.error(f"Failed to update note {note_id}: {str(e)}")
            raise SiYuanAPIError(f"Note update failed: {str(e)}")

    def get_note(self, note_id: str) -> NoteInfo:
        """
        获取笔记详情
        :param note_id: 笔记 ID
        :return: 笔记信息
        """
        try:
            # 获取块信息
            block_info = self._api_request('/api/block/getBlockInfo', {
                'id': note_id
            })

            block = block_info.get('data')
            if not block:
                raise SiYuanAPIError(f"Note {note_id} not found")

            return self._convert_note(block)

        except Exception as e:
            logger.error(f"Failed to get note {note_id}: {str(e)}")
            raise SiYuanAPIError(f"Get note failed: {str(e)}")

    def export_note(self, note_id: str, format_type: str = 'md') -> str:
        """
        导出笔记
        :param note_id: 笔记 ID
        :param format_type: 导出格式（默认：md）
        :return: 导出的内容
        """
        try:
            response = self._api_request('/api/export/exportMd', {
                'id': note_id
            })

            if format_type == 'md':
                return response.get('data', {}).get('content', '')
            else:
                # 其他格式的导出可以在这里扩展
                raise SiYuanAPIError(f"Unsupported export format: {format_type}")

        except Exception as e:
            logger.error(f"Failed to export note {note_id}: {str(e)}")
            raise SiYuanAPIError(f"Note export failed: {str(e)}")

    def sql_query(self, sql: str) -> List[Dict[str, Any]]:
        """
        执行 SQL 查询
        :param sql: SQL 查询语句
        :return: 查询结果
        """
        try:
            response = self._api_request('/api/query/sql', {'stmt': sql})
            return response.get('data', [])
        except Exception as e:
            logger.error(f"SQL query failed: {str(e)}")
            raise SiYuanAPIError(f"SQL query failed: {str(e)}")

    def sync_data(
        self,
        notebook_ids: Optional[List[str]] = None,
        sync_type: str = 'incremental',
        last_sync_time: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        同步 SiYuan 笔记数据
        :param notebook_ids: 指定笔记本 ID 列表（可选）
        :param sync_type: 同步类型（full 或 incremental）
        :param last_sync_time: 上次同步时间（增量同步时使用）
        :return: 同步结果
        """
        start_time = datetime.now(timezone.utc)
        result = {
            'status': 'pending',
            'items_processed': 0,
            'items_created': 0,
            'items_failed': 0,
            'start_time': start_time.isoformat(),
            'sync_type': sync_type
        }

        try:
            all_notes = []

            # 获取所有笔记本
            notebooks = self.get_notebooks()

            # 过滤笔记本
            if notebook_ids:
                notebooks = [nb for nb in notebooks if nb['id'] in notebook_ids]

            for notebook in notebooks:
                notebook_id = notebook['id']
                notebook_name = notebook['name']

                try:
                    # 构建 SQL 查询获取笔记
                    sql_query = f"""
                    SELECT * FROM blocks 
                    WHERE root_id IN (
                        SELECT root_id FROM blocks 
                        WHERE box = '{notebook_id}' AND type = 'd'
                    ) AND type = 'd'
                    """

                    # 增量同步：添加时间过滤
                    if sync_type == 'incremental' and last_sync_time:
                        # SiYuan 使用时间戳，需要转换
                        timestamp = int(datetime.fromisoformat(last_sync_time.replace('Z', '+00:00')).timestamp())
                        sql_query += f" AND updated >= '{timestamp}'"

                    sql_query += " ORDER BY updated DESC"

                    # 执行 SQL 查询
                    blocks = self.sql_query(sql_query)

                    for block in blocks:
                        try:
                            note = self._convert_note(block, notebook_name)
                            all_notes.append(note)
                            result['items_processed'] += 1
                        except Exception as e:
                            logger.error(f"Failed to convert note {block.get('id')}: {str(e)}")
                            result['items_failed'] += 1

                except Exception as e:
                    logger.error(f"Failed to sync notebook {notebook_name}: {str(e)}")
                    result['items_failed'] += len(notebooks)  # 假设每个笔记本有一些笔记

            result['items_created'] = len(all_notes)
            result['status'] = 'success' if result['items_failed'] == 0 else 'partial'
            result['details'] = {
                'notes': [note.__dict__ for note in all_notes],
                'notebooks_processed': len(notebooks)
            }

            logger.info(f"SiYuan sync completed: {result['items_processed']} processed, {result['items_failed']} failed")

        except Exception as e:
            logger.error(f"SiYuan sync failed: {str(e)}")
            result['status'] = 'failed'
            result['error_message'] = str(e)

        finally:
            result['end_time'] = datetime.now(timezone.utc).isoformat()

        return result

    def _api_request(self, endpoint: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        发送 SiYuan API 请求
        :param endpoint: API 端点
        :param data: 请求数据
        :return: API 响应
        """
        url = f"{self.base_url}{endpoint}"

        try:
            if data is not None:
                response = self.session.post(url, json=data, timeout=self.timeout)
            else:
                response = self.session.get(url, timeout=self.timeout)

            response.raise_for_status()

            # 检查 SiYuan API 响应格式
            result = response.json()
            if result.get('code') != 0:
                error_msg = result.get('msg', 'Unknown API error')
                raise SiYuanAPIError(f"SiYuan API error: {error_msg}", error_code=str(result.get('code')))

            return result

        except requests.exceptions.RequestException as e:
            error_msg = f"API request failed: {str(e)}"
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg += f" | Details: {error_detail}"
                except json.JSONDecodeError:
                    error_msg += f" | Response: {e.response.text[:200]}"
            raise SiYuanAPIError(error_msg, response=getattr(e, 'response', None)) from e

    def _convert_note(self, block_data: Dict[str, Any], notebook_name: Optional[str] = None) -> NoteInfo:
        """
        将 SiYuan 块数据转换为统一格式
        :param block_data: SiYuan 块数据
        :param notebook_name: 笔记本名称（可选）
        :return: 笔记信息对象
        """
        try:
            # 获取笔记内容
            content = None
            if block_data.get('content'):
                content = self._extract_text_content(block_data['content'])

            # 解析时间戳
            created_time = None
            updated_time = None

            if block_data.get('created'):
                try:
                    # SiYuan 时间戳格式：YYYYMMDDHHmmss
                    created_str = block_data['created']
                    if len(created_str) == 14:
                        created_time = datetime.strptime(created_str, '%Y%m%d%H%M%S')
                        created_time = created_time.replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            if block_data.get('updated'):
                try:
                    updated_str = block_data['updated']
                    if len(updated_str) == 14:
                        updated_time = datetime.strptime(updated_str, '%Y%m%d%H%M%S')
                        updated_time = updated_time.replace(tzinfo=timezone.utc)
                except Exception:
                    pass

            # 提取标签
            tags = []
            if block_data.get('tag'):
                tags = [tag.strip() for tag in block_data['tag'].split(',') if tag.strip()]

            return NoteInfo(
                note_id=block_data['id'],
                title=block_data.get('name', block_data.get('content', '')[:50]),
                content=content,
                notebook_id=block_data.get('box'),
                notebook_name=notebook_name,
                created_time=created_time,
                updated_time=updated_time,
                tags=tags,
                path=block_data.get('path'),
                parent_id=block_data.get('parent_id'),
                note_type=block_data.get('type', 'doc'),
                metadata={
                    'siyuan_id': block_data['id'],
                    'root_id': block_data.get('root_id'),
                    'hash': block_data.get('hash'),
                    'length': block_data.get('length'),
                    'subtype': block_data.get('subtype'),
                    'ial': block_data.get('ial'),  # Inline Attribute List
                    'sort': block_data.get('sort', 0)
                }
            )

        except Exception as e:
            logger.error(f"Failed to convert note data: {str(e)}")
            raise SiYuanAPIError(f"Note conversion failed: {str(e)}")

    def _extract_text_content(self, content: str, max_length: int = 10000) -> str:
        """
        提取和清理文本内容
        :param content: 原始内容
        :param max_length: 最大长度
        :return: 清理后的文本内容
        """
        if not content:
            return ""

        # 基础清理
        # 移除 HTML 标签
        clean_content = re.sub(r'<[^>]+>', '', content)
        # 移除多余空白
        clean_content = re.sub(r'\s+', ' ', clean_content).strip()

        # 截断过长内容
        if len(clean_content) > max_length:
            clean_content = clean_content[:max_length] + '...'

        return clean_content


# Helper function for environment-based configuration
def from_environment() -> SiYuanClient:
    """使用环境变量创建客户端"""
    return SiYuanClient(
        base_url=os.environ['SIYUAN_URL'],
        api_token=os.environ.get('SIYUAN_API_TOKEN'),
        timeout=int(os.environ.get('SIYUAN_TIMEOUT', 30))
    )


# Example usage
if __name__ == "__main__":
    # Example 1: 环境变量配置的客户端
    # client = from_environment()
    
    # Example 2: 直接配置的客户端
    client = SiYuanClient(
        base_url="http://localhost:6806",
        api_token="your-api-token-here"
    )

    # Example 3: 测试连接
    try:
        connection_result = client.test_connection()
        if connection_result['success']:
            print(f"连接成功！响应时间: {connection_result['response_time']:.2f}ms")
            print(f"系统支持的功能: {connection_result['capabilities']}")
        else:
            print(f"连接失败: {connection_result['error_message']}")
    except SiYuanAPIError as e:
        print(f"连接测试失败: {str(e)}")

    # Example 4: 搜索笔记
    try:
        search_result = client.search_notes("深度学习", limit=10)
        print(f"搜索到 {search_result.total_count} 个结果")
        for note in search_result.results:
            print(f"- {note['title']} ({note['notebook']})")
    except SiYuanAPIError as e:
        print(f"搜索失败: {str(e)}")


