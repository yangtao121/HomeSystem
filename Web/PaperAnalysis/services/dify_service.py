"""
Dify 知识库服务 - 为PaperAnalysis应用提供Dify集成功能
"""
import os
import sys
import json
import tempfile
import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional
import requests

# 添加 HomeSystem 模块路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', '..'))

# 导入 Dify 和 ArXiv 模块
from HomeSystem.integrations.dify.dify_knowledge import DifyKnowledgeBaseClient, DifyKnowledgeBaseConfig
from HomeSystem.utility.arxiv.arxiv import ArxivData
from HomeSystem.integrations.database import DatabaseOperations

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str, max_length: int = 200) -> str:
    """
    清理文件名，移除或替换不安全的字符
    """
    if not filename:
        return 'document'
    
    # 确保filename是字符串并移除换行符和控制字符
    filename = str(filename).strip()
    filename = re.sub(r'[\r\n\t\v\f]', ' ', filename)
    filename = re.sub(r'\s+', ' ', filename)
    
    # 移除不安全的字符
    unsafe_chars = r'[/\\:*?"<>|\x00-\x1f\x7f-\x9f]'
    safe_filename = re.sub(unsafe_chars, '_', filename)
    
    # 移除开头和结尾的空格、点号和下划线
    safe_filename = safe_filename.strip('. _')
    safe_filename = re.sub(r'_+', '_', safe_filename)
    
    if not safe_filename or safe_filename == '_':
        safe_filename = 'document'
    
    # 限制长度
    if len(safe_filename.encode('utf-8')) > max_length:
        encoded = safe_filename.encode('utf-8')[:max_length]
        while len(encoded) > 0:
            try:
                safe_filename = encoded.decode('utf-8')
                break
            except UnicodeDecodeError:
                encoded = encoded[:-1]
        safe_filename = safe_filename.rstrip('. _')
    
    if not safe_filename:
        safe_filename = 'document'
    
    return safe_filename


class DifyService:
    """Dify 知识库服务"""
    
    def __init__(self):
        self.db_ops = DatabaseOperations()
        self.dify_client = None
        self._init_dify_client()
    
    def _init_dify_client(self):
        """初始化 Dify 客户端"""
        try:
            config = DifyKnowledgeBaseConfig.from_environment()
            config.validate()
            self.dify_client = DifyKnowledgeBaseClient(config)
            logger.info("Dify 客户端初始化成功")
        except Exception as e:
            logger.error(f"Dify 客户端初始化失败: {e}")
            self.dify_client = None
    
    def is_available(self) -> bool:
        """检查 Dify 服务是否可用"""
        if not self.dify_client:
            logger.error("Dify 客户端未初始化，请检查环境变量配置")
            return False
        
        try:
            health_status = self.dify_client.health_check()
            if not health_status:
                logger.error("Dify 服务健康检查失败，请检查服务状态和网络连接")
            return health_status
        except Exception as e:
            logger.error(f"Dify 服务连接测试失败: {e}")
            return False
    
    def get_or_create_dataset(self, task_name: str) -> Optional[str]:
        """获取或创建以 task_name 命名的知识库"""
        if not self.dify_client:
            logger.error("Dify 客户端未初始化")
            return None
        
        try:
            logger.info(f"正在查找或创建知识库: {task_name}")
            
            # 查找现有知识库
            datasets = self.dify_client.list_datasets(limit=100)
            logger.info(f"找到 {len(datasets)} 个现有知识库")
            
            for dataset in datasets:
                logger.debug(f"检查知识库: {dataset.name} (ID: {dataset.dify_dataset_id})")
                if dataset.name == task_name:
                    logger.info(f"找到现有知识库: {task_name} (ID: {dataset.dify_dataset_id})")
                    return dataset.dify_dataset_id
            
            # 创建新知识库
            logger.info(f"创建新知识库: {task_name}")
            dataset = self.dify_client.create_dataset(
                name=task_name,
                description=f"论文知识库 - {task_name}",
                permission="only_me"
            )
            logger.info(f"成功创建知识库: {task_name} (ID: {dataset.dify_dataset_id})")
            return dataset.dify_dataset_id
            
        except Exception as e:
            logger.error(f"获取或创建知识库失败: {e}")
            return None
    
    def validate_upload_preconditions(self, arxiv_id: str) -> Dict[str, Any]:
        """验证上传前置条件"""
        validation_result = {
            "success": True,
            "errors": [],
            "warnings": []
        }
        
        try:
            # 检查 Dify 客户端状态
            if not self.dify_client:
                validation_result["errors"].append("Dify 客户端未初始化")
                validation_result["success"] = False
                return validation_result
            
            # 检查 Dify 服务连接
            if not self.is_available():
                validation_result["errors"].append("无法连接到 Dify 服务，请检查网络连接和服务状态")
                validation_result["success"] = False
            
            # 从数据库获取论文信息并验证
            paper = self.db_ops.get_by_id(arxiv_id)
            if not paper:
                validation_result["errors"].append("论文不存在")
                validation_result["success"] = False
                return validation_result
            
            # 检查论文是否已上传
            if paper.dify_document_id:
                validation_result["errors"].append("论文已上传到 Dify")
                validation_result["success"] = False
            
            # 检查任务名称
            if not paper.task_name:
                validation_result["errors"].append("论文未分配任务名称，无法确定目标知识库")
                validation_result["success"] = False
            elif len(paper.task_name.strip()) < 2:
                validation_result["errors"].append("任务名称过短，无法创建有效的知识库")
                validation_result["success"] = False
            
            # 检查论文基本信息完整性
            if not paper.title:
                validation_result["errors"].append("论文标题缺失")
                validation_result["success"] = False
            elif len(paper.title.strip()) < 10:
                validation_result["warnings"].append("论文标题过短，可能影响上传质量")
            
            if not paper.abstract:
                validation_result["warnings"].append("论文摘要缺失，可能影响知识库检索效果")
            elif len(paper.abstract.strip()) < 100:
                validation_result["warnings"].append("论文摘要过短，可能影响知识库检索效果")
            
            if not paper.authors:
                validation_result["warnings"].append("论文作者信息缺失")
            
            # 检查PDF下载可能性
            if paper.pdf_url:
                if not paper.pdf_url.startswith('http'):
                    validation_result["warnings"].append("PDF链接格式异常，可能无法下载")
            else:
                validation_result["warnings"].append("缺少PDF链接，系统将尝试从ArXiv下载")
            
        except Exception as e:
            validation_result["errors"].append(f"验证过程中发生错误: {str(e)}")
            validation_result["success"] = False
        
        return validation_result
    
    def upload_paper_to_dify(self, arxiv_id: str) -> Dict[str, Any]:
        """上传论文到 Dify 知识库"""
        # 首先进行预上传验证
        validation = self.validate_upload_preconditions(arxiv_id)
        if not validation["success"]:
            return {
                "success": False,
                "error": "; ".join(validation["errors"]),
                "validation_errors": validation["errors"],
                "validation_warnings": validation["warnings"]
            }
        
        # 如果有警告，记录到日志
        if validation["warnings"]:
            logger.warning(f"论文 {arxiv_id} 上传前警告: {'; '.join(validation['warnings'])}")
        
        if not self.dify_client:
            return {"success": False, "error": "Dify 客户端未初始化"}
        
        try:
            # 从数据库获取论文信息
            paper = self.db_ops.get_by_id(arxiv_id)
            if not paper:
                return {"success": False, "error": "论文不存在"}
            
            # 检查是否已上传
            if paper.dify_document_id:
                return {"success": False, "error": "论文已上传到 Dify"}
            
            # 获取或创建知识库
            dataset_id = self.get_or_create_dataset(paper.task_name)
            logger.info(f"获取到的知识库ID: {dataset_id}")
            
            if not dataset_id:
                return {"success": False, "error": "无法创建或获取知识库"}
            
            # 创建 ArxivData 对象并下载 PDF
            arxiv_data = ArxivData({
                'title': paper.title,
                'link': f"http://arxiv.org/abs/{arxiv_id}",
                'snippet': paper.abstract,
                'categories': paper.categories or ''
            })
            
            try:
                # 下载 PDF
                logger.info(f"开始下载论文 PDF: {arxiv_id}")
                pdf_content = arxiv_data.downloadPdf()
                
                if not pdf_content:
                    return {"success": False, "error": "PDF 下载失败"}
                
                # 临时保存 PDF 文件
                safe_title = sanitize_filename(paper.title, max_length=150)
                temp_filename = f"{arxiv_id}_{safe_title}.pdf"
                
                temp_dir = tempfile.gettempdir()
                temp_pdf_path = os.path.join(temp_dir, temp_filename)
                
                with open(temp_pdf_path, 'wb') as temp_file:
                    temp_file.write(pdf_content)
                
                try:
                    # 上传到 Dify
                    logger.info(f"开始上传论文到 Dify: {arxiv_id}, 使用知识库ID: {dataset_id}")
                    
                    # 重试机制
                    import time
                    for attempt in range(3):
                        try:
                            logger.info(f"第 {attempt + 1} 次尝试上传: dataset_id={dataset_id}")
                            document = self.dify_client.upload_document_file(
                                dataset_id=dataset_id,
                                file_path=temp_pdf_path,
                                name=f"{arxiv_id} - {paper.title}"
                            )
                            break
                        except Exception as upload_error:
                            logger.warning(f"第 {attempt + 1} 次上传尝试失败: {upload_error}")
                            if attempt < 2:
                                time.sleep(2)
                            else:
                                raise
                    
                    # 更新数据库记录
                    paper.dify_dataset_id = dataset_id
                    paper.dify_document_id = document.dify_document_id
                    paper.dify_upload_time = datetime.now()
                    paper.dify_document_name = document.name
                    paper.dify_character_count = document.character_count or 0
                    paper.dify_metadata = json.dumps({
                        "upload_source": "paper_analysis",
                        "task_name": paper.task_name,
                        "upload_method": "pdf_file"
                    })
                    
                    success = self.db_ops.update(paper)
                    if not success:
                        logger.warning(f"数据库更新失败: {arxiv_id}")
                    
                    return {
                        "success": True,
                        "dataset_id": dataset_id,
                        "document_id": document.dify_document_id,
                        "document_name": document.name
                    }
                
                finally:
                    # 清理临时文件
                    try:
                        os.unlink(temp_pdf_path)
                    except:
                        pass
                
            except Exception as e:
                logger.error(f"论文 {arxiv_id} 下载或上传失败: {e}")
                return {"success": False, "error": f"下载或上传失败: {str(e)}"}
            
        except Exception as e:
            logger.error(f"上传论文 {arxiv_id} 时发生错误: {e}")
            return {"success": False, "error": str(e)}
    
    def get_eligible_papers_for_upload(self, filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """获取符合上传条件的论文"""
        try:
            # 查询条件：有任务名称且未上传到Dify的论文
            papers = self.db_ops.search({
                'task_name_not_null': True,
                'dify_document_id_null': True
            })
            
            eligible_papers = []
            for paper in papers:
                eligible_papers.append({
                    'arxiv_id': paper.arxiv_id,
                    'title': paper.title,
                    'task_name': paper.task_name
                })
            
            return eligible_papers
        except Exception as e:
            logger.error(f"获取符合条件的论文失败: {e}")
            return []
    
    def _classify_error_type(self, error: str) -> str:
        """分类错误类型"""
        error_lower = error.lower()
        if 'pdf' in error_lower and ('下载' in error_lower or 'download' in error_lower):
            return 'pdf_download_error'
        elif '客户端' in error_lower or 'client' in error_lower:
            return 'client_error'
        elif '知识库' in error_lower or 'dataset' in error_lower:
            return 'dataset_error'
        elif '网络' in error_lower or 'network' in error_lower or 'connection' in error_lower:
            return 'network_error'
        elif '任务名称' in error_lower or 'task' in error_lower:
            return 'task_error'
        elif '已上传' in error_lower:
            return 'already_uploaded'
        else:
            return 'unknown_error'
    
    def _generate_upload_suggestions(self, failed_papers: List[Dict], failure_summary: Dict) -> List[str]:
        """生成上传建议"""
        suggestions = []
        
        if failure_summary.get('pdf_download_error', 0) > 0:
            suggestions.append("部分论文PDF下载失败，请检查网络连接或ArXiv服务状态")
        
        if failure_summary.get('task_error', 0) > 0:
            suggestions.append("部分论文缺少任务名称，请先为论文分配任务")
        
        if failure_summary.get('client_error', 0) > 0:
            suggestions.append("Dify客户端配置有问题，请检查API密钥和服务器配置")
        
        if failure_summary.get('network_error', 0) > 0:
            suggestions.append("网络连接问题，请检查网络连接和防火墙设置")
        
        if failure_summary.get('already_uploaded', 0) > 0:
            suggestions.append("部分论文已经上传，可以忽略这些错误")
        
        return suggestions
    
    def upload_all_eligible_papers_with_summary(self, filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """上传所有符合条件的论文并生成详细总结"""
        if not self.dify_client:
            return {
                "success": False,
                "error": "Dify 客户端未初始化",
                "total_eligible": 0,
                "total_attempted": 0,
                "success_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "progress": 0,
                "successful_papers": [],
                "failed_papers": [],
                "skipped_papers": [],
                "failure_summary": {},
                "suggestions": []
            }
        
        try:
            # 获取符合条件的论文
            eligible_papers = self.get_eligible_papers_for_upload(filters)
            total_eligible = len(eligible_papers)
            
            if total_eligible == 0:
                return {
                    "success": True,
                    "total_eligible": 0,
                    "total_attempted": 0,
                    "success_count": 0,
                    "failed_count": 0,
                    "skipped_count": 0,
                    "progress": 100,
                    "message": "没有找到符合条件的论文",
                    "successful_papers": [],
                    "failed_papers": [],
                    "skipped_papers": [],
                    "failure_summary": {},
                    "suggestions": []
                }
            
            # 初始化结果统计
            successful_papers = []
            failed_papers = []
            skipped_papers = []
            failure_summary = {}
            
            logger.info(f"开始批量上传 {total_eligible} 篇符合条件的论文")
            
            # 批量上传
            for i, paper in enumerate(eligible_papers):
                arxiv_id = paper['arxiv_id']
                title = paper.get('title', 'Unknown Title')
                
                try:
                    # 上传单个论文
                    upload_result = self.upload_paper_to_dify(arxiv_id)
                    
                    if upload_result['success']:
                        successful_papers.append({
                            'arxiv_id': arxiv_id,
                            'title': title,
                            'task_name': paper.get('task_name'),
                            'dataset_id': upload_result.get('dataset_id'),
                            'document_id': upload_result.get('document_id')
                        })
                        logger.info(f"上传成功: {arxiv_id} - {title}")
                    else:
                        error = upload_result.get('error', '未知错误')
                        failed_papers.append({
                            'arxiv_id': arxiv_id,
                            'title': title,
                            'task_name': paper.get('task_name'),
                            'error': error,
                            'error_type': self._classify_error_type(error)
                        })
                        
                        # 统计失败原因
                        error_type = self._classify_error_type(error)
                        failure_summary[error_type] = failure_summary.get(error_type, 0) + 1
                        
                        logger.warning(f"上传失败: {arxiv_id} - {error}")
                
                except Exception as e:
                    error_msg = str(e)
                    failed_papers.append({
                        'arxiv_id': arxiv_id,
                        'title': title,
                        'task_name': paper.get('task_name'),
                        'error': f'上传异常: {error_msg}',
                        'error_type': 'system_error'
                    })
                    
                    failure_summary['system_error'] = failure_summary.get('system_error', 0) + 1
                    logger.error(f"上传异常: {arxiv_id} - {error_msg}")
                
                # 进度更新
                progress = int((i + 1) / total_eligible * 100)
                if (i + 1) % 5 == 0 or i == total_eligible - 1:
                    logger.info(f"上传进度: {i + 1}/{total_eligible} ({progress}%)")
            
            # 生成建议
            suggestions = self._generate_upload_suggestions(failed_papers, failure_summary)
            
            # 汇总结果
            result = {
                "success": True,
                "total_eligible": total_eligible,
                "total_attempted": total_eligible,
                "success_count": len(successful_papers),
                "failed_count": len(failed_papers),
                "skipped_count": len(skipped_papers),
                "progress": 100,
                "message": f"批量上传完成：成功 {len(successful_papers)} 篇，失败 {len(failed_papers)} 篇",
                "successful_papers": successful_papers,
                "failed_papers": failed_papers,
                "skipped_papers": skipped_papers,
                "failure_summary": failure_summary,
                "suggestions": suggestions
            }
            
            logger.info(f"批量上传完成: {result['message']}")
            return result
            
        except Exception as e:
            logger.error(f"批量上传失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "total_eligible": 0,
                "total_attempted": 0,
                "success_count": 0,
                "failed_count": 0,
                "skipped_count": 0,
                "progress": 0,
                "message": f"批量上传过程中发生错误: {e}",
                "successful_papers": [],
                "failed_papers": [],
                "skipped_papers": [],
                "failure_summary": {},
                "suggestions": []
            }
    
    def verify_dify_document(self, arxiv_id: str) -> Dict[str, Any]:
        """验证单个文档在Dify中的状态"""
        if not self.dify_client:
            return {"success": False, "error": "Dify 客户端未初始化"}
        
        try:
            paper = self.db_ops.get_by_id(arxiv_id)
            if not paper:
                return {"success": False, "error": "论文不存在"}
            
            if not paper.dify_document_id or not paper.dify_dataset_id:
                return {"success": False, "error": "论文未上传到Dify"}
            
            # 尝试获取文档信息
            try:
                document = self.dify_client.get_document(paper.dify_dataset_id, paper.dify_document_id)
                if document:
                    return {
                        "success": True,
                        "verified": True,
                        "status": "exists",
                        "document": {
                            "id": document.dify_document_id,
                            "name": document.name,
                            "character_count": document.character_count
                        }
                    }
                else:
                    return {
                        "success": True,
                        "verified": False,
                        "status": "missing",
                        "error": "文档在Dify服务器上不存在"
                    }
            except Exception as e:
                return {"success": False, "error": f"验证失败: {str(e)}"}
                
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def batch_verify_all_documents(self) -> Dict[str, Any]:
        """批量验证所有已上传文档的状态"""
        try:
            # 获取所有已上传的论文
            papers_to_verify = []
            all_papers = self.db_ops.get_all()
            
            for paper in all_papers:
                if paper.dify_document_id:
                    papers_to_verify.append({
                        'arxiv_id': paper.arxiv_id,
                        'title': paper.title,
                        'dify_document_id': paper.dify_document_id,
                        'dify_dataset_id': paper.dify_dataset_id
                    })
            
            if not papers_to_verify:
                return {
                    "success": True,
                    "total": 0,
                    "verified": 0,
                    "failed": 0,
                    "missing": 0,
                    "progress": 100,
                    "message": "没有需要验证的论文",
                    "failed_papers": [],
                    "missing_papers": []
                }
            
            total = len(papers_to_verify)
            verified_count = 0
            failed_count = 0
            missing_count = 0
            failed_papers = []
            missing_papers = []
            
            logger.info(f"开始批量验证 {total} 篇论文的 Dify 文档状态")
            
            # 逐个验证每篇论文
            for i, paper in enumerate(papers_to_verify):
                arxiv_id = paper['arxiv_id']
                title = paper['title']
                
                try:
                    # 调用单篇验证方法
                    verify_result = self.verify_dify_document(arxiv_id)
                    
                    if verify_result.get('success'):
                        if verify_result.get('verified'):
                            verified_count += 1
                            logger.debug(f"验证成功: {arxiv_id}")
                        elif verify_result.get('status') == 'missing':
                            missing_count += 1
                            missing_papers.append({
                                'arxiv_id': arxiv_id,
                                'title': title,
                                'error': '文档在 Dify 服务器上不存在'
                            })
                            logger.warning(f"文档丢失: {arxiv_id}")
                        else:
                            failed_count += 1
                            failed_papers.append({
                                'arxiv_id': arxiv_id,
                                'title': title,
                                'error': verify_result.get('error', '验证失败')
                            })
                            logger.warning(f"验证失败: {arxiv_id}")
                    else:
                        failed_count += 1
                        failed_papers.append({
                            'arxiv_id': arxiv_id,
                            'title': title,
                            'error': verify_result.get('error', '验证过程出错')
                        })
                        logger.error(f"验证出错: {arxiv_id}")
                        
                except Exception as e:
                    failed_count += 1
                    error_msg = str(e)
                    failed_papers.append({
                        'arxiv_id': arxiv_id,
                        'title': title,
                        'error': f'验证异常: {error_msg}'
                    })
                    logger.error(f"验证异常: {arxiv_id} - {error_msg}")
                
                # 进度更新
                progress = int((i + 1) / total * 100)
                if (i + 1) % 10 == 0 or i == total - 1:
                    logger.info(f"验证进度: {i + 1}/{total} ({progress}%)")
            
            # 汇总结果
            result = {
                "success": True,
                "total": total,
                "verified": verified_count,
                "failed": failed_count,
                "missing": missing_count,
                "progress": 100,
                "message": f"验证完成: 验证通过 {verified_count} 篇, 失败 {failed_count} 篇, 丢失 {missing_count} 篇",
                "failed_papers": failed_papers,
                "missing_papers": missing_papers
            }
            
            logger.info(f"批量验证完成: {result['message']}")
            return result
            
        except Exception as e:
            logger.error(f"批量验证失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "total": 0,
                "verified": 0,
                "failed": 0,
                "missing": 0,
                "progress": 0,
                "message": f"批量验证过程中发生错误: {e}",
                "failed_papers": [],
                "missing_papers": []
            }