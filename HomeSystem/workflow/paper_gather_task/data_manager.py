"""
PaperGather任务数据管理器
提供任务结果持久化、配置版本兼容性处理、历史记录管理功能
"""
import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
import uuid
from loguru import logger
from HomeSystem.utility.arxiv.arxiv import ArxivSearchMode, ArxivData


class CustomJSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，用于处理特殊对象类型"""
    
    def default(self, obj):
        if isinstance(obj, ArxivSearchMode):
            return obj.value
        elif isinstance(obj, ArxivData):
            # 将ArxivData对象转换为可序列化的字典
            return self._arxiv_data_to_dict(obj)
        return super().default(obj)
    
    def _arxiv_data_to_dict(self, arxiv_data: ArxivData) -> dict:
        """
        将ArxivData对象转换为可JSON序列化的字典
        
        Args:
            arxiv_data: ArxivData对象
            
        Returns:
            可序列化的字典
        """
        # 获取对象的所有属性，排除不可序列化的部分
        result = {}
        
        # 基本信息字段
        basic_fields = [
            'title', 'link', 'snippet', 'categories', 'pdf_link', 'pdf_path',
            'tag', 'arxiv_id', 'published_date'
        ]
        
        # 结构化摘要字段
        abstract_fields = [
            'research_background', 'research_objectives', 'methods', 
            'key_findings', 'conclusions', 'limitations', 'future_work', 'keywords'
        ]
        
        # 分析相关字段
        analysis_fields = [
            'abstract_is_relevant', 'abstract_relevance_score', 'abstract_analysis_justification',
            'full_paper_analyzed', 'full_paper_is_relevant', 'full_paper_relevance_score',
            'full_paper_analysis_justification', 'paper_summarized', 'paper_summary',
            'final_is_relevant', 'final_relevance_score', 'search_query'
        ]
        
        # OCR结果字段（排除pdf二进制数据）
        ocr_fields = ['ocr_result']
        
        # 合并所有要序列化的字段
        all_fields = basic_fields + abstract_fields + analysis_fields + ocr_fields
        
        for field in all_fields:
            if hasattr(arxiv_data, field):
                value = getattr(arxiv_data, field)
                # 确保值是可序列化的
                if value is not None:
                    result[field] = value
        
        # 添加类型标识，便于反序列化时识别
        result['_type'] = 'ArxivData'
        
        return result


class ConfigVersionManager:
    """配置版本管理器"""
    
    CURRENT_VERSION = "1.2.0"
    
    # 版本默认值映射
    VERSION_DEFAULTS = {
        "1.0.0": {
            # 初始版本基础字段
            "interval_seconds": 3600,
            "search_query": "machine learning",
            "max_papers_per_search": 20,
            "user_requirements": "寻找机器学习和人工智能领域的最新研究论文",
            "llm_model_name": "ollama.Qwen3_30B",
            "relevance_threshold": 0.7,
            "max_papers_in_response": 50,
            "max_relevant_papers_in_response": 10,
            "enable_paper_summarization": True,
            "summarization_threshold": 0.8,
            "enable_translation": True,
            "custom_settings": {}
        },
        "1.1.0": {
            # v1.1.0 新增搜索模式
            "search_mode": "latest",
            "start_year": None,
            "end_year": None,
            "after_year": None
        },
        "1.2.0": {
            # v1.2.0 新增模型配置
            "abstract_analysis_model": None,
            "full_paper_analysis_model": None,
            "translation_model": None,
            "paper_analysis_model": None,
            "deep_analysis_model": None,
            "vision_model": None,
            # v1.2.0 新增深度分析配置
            "enable_deep_analysis": True,
            "deep_analysis_threshold": 0.8,
            "ocr_char_limit_for_analysis": 10000,
            # v1.2.0 新增视频分析配置
            "enable_video_analysis": False,
            "video_analysis_model": None
        }
    }
    
    @classmethod
    def get_upgrade_path(cls, from_version: str, to_version: str) -> List[str]:
        """获取版本升级路径"""
        versions = ["1.0.0", "1.1.0", "1.2.0"]
        
        try:
            start_idx = versions.index(from_version)
            end_idx = versions.index(to_version)
            
            if start_idx >= end_idx:
                return []
            
            return versions[start_idx + 1:end_idx + 1]
        except ValueError:
            logger.warning(f"未知版本: {from_version} 或 {to_version}")
            return [cls.CURRENT_VERSION]
    
    @classmethod
    def ensure_config_compatibility(cls, config_dict: Dict[str, Any]) -> Dict[str, Any]:
        """确保配置与当前版本兼容"""
        # 1. 检测配置版本
        version = config_dict.get('_version', '1.0.0')
        logger.info(f"检测到配置版本: {version}")
        
        # 2. 创建新的配置字典，避免修改原始数据
        new_config = config_dict.copy()
        
        # 3. 应用版本升级
        upgrade_path = cls.get_upgrade_path(version, cls.CURRENT_VERSION)
        for upgrade_version in upgrade_path:
            defaults = cls.VERSION_DEFAULTS.get(upgrade_version, {})
            for key, default_value in defaults.items():
                if key not in new_config or new_config[key] is None:
                    new_config[key] = default_value
                    logger.debug(f"配置升级: 添加字段 {key} = {default_value}")
        
        # 4. 设置当前版本标记
        new_config['_version'] = cls.CURRENT_VERSION
        
        # 5. 转换搜索模式字符串为枚举值（如果需要）
        if 'search_mode' in new_config and isinstance(new_config['search_mode'], str):
            try:
                new_config['search_mode'] = ArxivSearchMode(new_config['search_mode'])
            except ValueError:
                logger.warning(f"无效的搜索模式: {new_config['search_mode']}，使用默认值")
                new_config['search_mode'] = ArxivSearchMode.LATEST
        
        logger.info(f"配置已升级到版本: {cls.CURRENT_VERSION}")
        return new_config
    
    @classmethod
    def validate_required_fields(cls, config_dict: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """验证必需字段"""
        required_fields = ['search_query', 'user_requirements', 'llm_model_name']
        
        for field in required_fields:
            if not config_dict.get(field):
                return False, f"缺少必需参数: {field}"
        
        return True, None


class PaperGatherDataManager:
    """PaperGather任务数据管理器"""
    
    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化数据管理器
        
        Args:
            data_dir: 数据目录路径，默认为项目根目录下的 data/paper_gather
        """
        if data_dir is None:
            # 获取项目根目录
            current_file = Path(__file__)
            project_root = current_file.parent.parent.parent.parent  # 回到homesystem根目录
            data_dir = project_root / "data" / "paper_gather"
        
        self.data_dir = Path(data_dir)
        self.task_history_dir = self.data_dir / "task_history"
        self.config_presets_dir = self.data_dir / "config_presets"
        self.scheduled_tasks_file = self.data_dir / "scheduled_tasks.json"
        
        # 确保目录存在
        self._ensure_directories()
        
        logger.info(f"PaperGatherDataManager初始化完成，数据目录: {self.data_dir}")
    
    def _ensure_directories(self):
        """确保必要目录存在"""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.task_history_dir.mkdir(exist_ok=True)
        self.config_presets_dir.mkdir(exist_ok=True)
    
    def _get_task_history_file(self, date: datetime) -> Path:
        """获取指定日期的任务历史文件路径"""
        filename = f"{date.year}_{date.month:02d}_tasks.json"
        return self.task_history_dir / filename
    
    def save_task_complete(self, task_id: str, config_dict: Dict[str, Any], 
                          result_data: Dict[str, Any], start_time: datetime, 
                          end_time: datetime, status: str = "completed") -> bool:
        """
        保存完整的任务信息（配置+结果）
        
        Args:
            task_id: 任务ID
            config_dict: 任务配置字典
            result_data: 任务执行结果
            start_time: 开始时间
            end_time: 结束时间
            status: 任务状态
            
        Returns:
            保存是否成功
        """
        try:
            # 准备任务数据
            task_data = {
                "task_id": task_id,
                "config": config_dict,
                "result": result_data,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "status": status,
                "duration": (end_time - start_time).total_seconds(),
                "saved_at": datetime.now().isoformat(),
                "_version": ConfigVersionManager.CURRENT_VERSION
            }
            
            # 获取历史文件路径
            history_file = self._get_task_history_file(start_time)
            
            # 读取现有数据
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    history_data = json.load(f)
            else:
                history_data = {"tasks": []}
            
            # 添加新任务（避免重复）
            existing_task_ids = {task.get("task_id") for task in history_data.get("tasks", [])}
            if task_id not in existing_task_ids:
                history_data["tasks"].append(task_data)
                
                # 按时间排序
                history_data["tasks"].sort(key=lambda x: x.get("start_time", ""), reverse=True)
            else:
                logger.warning(f"任务 {task_id} 已存在，跳过保存")
                return False
            
            # 保存文件（使用自定义JSON编码器）
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
            
            logger.info(f"任务 {task_id} 已保存到 {history_file}")
            return True
            
        except Exception as e:
            logger.error(f"保存任务失败: {e}")
            return False
    
    def load_task_history(self, limit: int = 100, 
                         start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None,
                         status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        加载任务历史记录
        
        Args:
            limit: 最大返回数量
            start_date: 开始日期过滤
            end_date: 结束日期过滤
            status_filter: 状态过滤
            
        Returns:
            任务历史记录列表
        """
        try:
            all_tasks = []
            
            # 获取所有历史文件
            history_files = list(self.task_history_dir.glob("*_tasks.json"))
            history_files.sort(reverse=True)  # 最新的文件在前
            
            for history_file in history_files:
                try:
                    with open(history_file, 'r', encoding='utf-8') as f:
                        history_data = json.load(f)
                    
                    tasks = history_data.get("tasks", [])
                    
                    for task in tasks:
                        # 应用过滤条件
                        if start_date or end_date:
                            task_time = datetime.fromisoformat(task.get("start_time", ""))
                            if start_date and task_time < start_date:
                                continue
                            if end_date and task_time > end_date:
                                continue
                        
                        if status_filter and task.get("status") != status_filter:
                            continue
                        
                        all_tasks.append(task)
                        
                        # 达到限制数量就停止
                        if len(all_tasks) >= limit:
                            break
                    
                    if len(all_tasks) >= limit:
                        break
                        
                except Exception as e:
                    logger.error(f"读取历史文件 {history_file} 失败: {e}")
                    continue
            
            logger.info(f"加载了 {len(all_tasks)} 个历史任务")
            return all_tasks
            
        except Exception as e:
            logger.error(f"加载任务历史失败: {e}")
            return []
    
    def get_task_config_compatible(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定任务的配置（支持版本兼容性）
        
        Args:
            task_id: 任务ID
            
        Returns:
            兼容当前版本的配置字典
        """
        try:
            # 搜索所有历史文件
            history_files = list(self.task_history_dir.glob("*_tasks.json"))
            
            for history_file in history_files:
                try:
                    with open(history_file, 'r', encoding='utf-8') as f:
                        history_data = json.load(f)
                    
                    tasks = history_data.get("tasks", [])
                    for task in tasks:
                        if task.get("task_id") == task_id:
                            config = task.get("config", {})
                            
                            # 应用版本兼容性处理
                            compatible_config = ConfigVersionManager.ensure_config_compatibility(config)
                            
                            logger.info(f"找到任务 {task_id} 的配置")
                            return compatible_config
                            
                except Exception as e:
                    logger.error(f"读取历史文件 {history_file} 失败: {e}")
                    continue
            
            logger.warning(f"未找到任务 {task_id}")
            return None
            
        except Exception as e:
            logger.error(f"获取任务配置失败: {e}")
            return None
    
    def save_config_preset(self, name: str, config_dict: Dict[str, Any], 
                          description: str = "") -> bool:
        """
        保存配置预设
        
        Args:
            name: 预设名称
            config_dict: 配置字典
            description: 预设描述
            
        Returns:
            保存是否成功
        """
        try:
            presets_file = self.config_presets_dir / "user_presets.json"
            
            # 读取现有预设
            if presets_file.exists():
                with open(presets_file, 'r', encoding='utf-8') as f:
                    presets_data = json.load(f)
            else:
                presets_data = {"presets": []}
            
            # 准备预设数据
            preset_data = {
                "id": str(uuid.uuid4()),
                "name": name,
                "description": description,
                "config": config_dict,
                "created_at": datetime.now().isoformat(),
                "_version": ConfigVersionManager.CURRENT_VERSION
            }
            
            # 检查是否已存在同名预设
            existing_names = {preset.get("name") for preset in presets_data.get("presets", [])}
            if name in existing_names:
                logger.warning(f"预设 '{name}' 已存在，将覆盖")
                # 移除旧预设
                presets_data["presets"] = [p for p in presets_data["presets"] if p.get("name") != name]
            
            # 添加新预设
            presets_data["presets"].append(preset_data)
            
            # 按创建时间排序
            presets_data["presets"].sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
            # 保存文件（使用自定义JSON编码器）
            with open(presets_file, 'w', encoding='utf-8') as f:
                json.dump(presets_data, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
            
            logger.info(f"配置预设 '{name}' 已保存")
            return True
            
        except Exception as e:
            logger.error(f"保存配置预设失败: {e}")
            return False
    
    def load_config_presets(self) -> List[Dict[str, Any]]:
        """
        加载所有配置预设
        
        Returns:
            配置预设列表
        """
        try:
            presets_file = self.config_presets_dir / "user_presets.json"
            
            if not presets_file.exists():
                return []
            
            with open(presets_file, 'r', encoding='utf-8') as f:
                presets_data = json.load(f)
            
            presets = presets_data.get("presets", [])
            
            # 对每个预设应用版本兼容性处理
            compatible_presets = []
            for preset in presets:
                config = preset.get("config", {})
                compatible_config = ConfigVersionManager.ensure_config_compatibility(config)
                
                preset_copy = preset.copy()
                preset_copy["config"] = compatible_config
                compatible_presets.append(preset_copy)
            
            logger.info(f"加载了 {len(compatible_presets)} 个配置预设")
            return compatible_presets
            
        except Exception as e:
            logger.error(f"加载配置预设失败: {e}")
            return []
    
    def delete_config_preset(self, preset_id: str) -> bool:
        """
        删除配置预设
        
        Args:
            preset_id: 预设ID
            
        Returns:
            删除是否成功
        """
        try:
            presets_file = self.config_presets_dir / "user_presets.json"
            
            if not presets_file.exists():
                return False
            
            with open(presets_file, 'r', encoding='utf-8') as f:
                presets_data = json.load(f)
            
            # 过滤掉要删除的预设
            original_count = len(presets_data.get("presets", []))
            presets_data["presets"] = [p for p in presets_data["presets"] if p.get("id") != preset_id]
            
            if len(presets_data["presets"]) == original_count:
                logger.warning(f"未找到预设 {preset_id}")
                return False
            
            # 保存文件（使用自定义JSON编码器）
            with open(presets_file, 'w', encoding='utf-8') as f:
                json.dump(presets_data, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
            
            logger.info(f"配置预设 {preset_id} 已删除")
            return True
            
        except Exception as e:
            logger.error(f"删除配置预设失败: {e}")
            return False
    
    def update_task_history(self, task_id: str, updated_data: Dict[str, Any]) -> bool:
        """
        更新历史任务记录
        
        Args:
            task_id: 任务ID
            updated_data: 更新的数据（仅更新config部分）
            
        Returns:
            更新是否成功
        """
        try:
            # 搜索所有历史文件
            history_files = list(self.task_history_dir.glob("*_tasks.json"))
            
            for history_file in history_files:
                try:
                    with open(history_file, 'r', encoding='utf-8') as f:
                        history_data = json.load(f)
                    
                    # 查找并更新指定任务
                    tasks = history_data.get("tasks", [])
                    task_found = False
                    
                    for task in tasks:
                        if task.get("task_id") == task_id:
                            # 只更新config部分，保留执行结果和时间信息
                            if "config" in updated_data:
                                task["config"] = updated_data["config"]
                                # 添加更新时间戳
                                task["updated_at"] = datetime.now().isoformat()
                                task_found = True
                                break
                    
                    # 如果找到并更新了任务
                    if task_found:
                        # 保存修改后的文件
                        with open(history_file, 'w', encoding='utf-8') as f:
                            json.dump(history_data, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
                        
                        logger.info(f"历史任务 {task_id} 已在 {history_file} 中更新")
                        return True
                        
                except Exception as e:
                    logger.error(f"处理历史文件 {history_file} 失败: {e}")
                    continue
            
            logger.warning(f"未找到历史任务 {task_id}")
            return False
            
        except Exception as e:
            logger.error(f"更新历史任务失败: {e}")
            return False

    def delete_task_history(self, task_id: str) -> bool:
        """
        删除历史任务记录
        
        Args:
            task_id: 任务ID
            
        Returns:
            删除是否成功
        """
        try:
            # 搜索所有历史文件
            history_files = list(self.task_history_dir.glob("*_tasks.json"))
            
            for history_file in history_files:
                try:
                    with open(history_file, 'r', encoding='utf-8') as f:
                        history_data = json.load(f)
                    
                    # 查找并删除指定任务
                    original_count = len(history_data.get("tasks", []))
                    tasks = history_data.get("tasks", [])
                    history_data["tasks"] = [task for task in tasks if task.get("task_id") != task_id]
                    
                    # 如果找到并删除了任务
                    if len(history_data["tasks"]) < original_count:
                        # 保存修改后的文件
                        with open(history_file, 'w', encoding='utf-8') as f:
                            json.dump(history_data, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
                        
                        logger.info(f"历史任务 {task_id} 已从 {history_file} 中删除")
                        return True
                        
                except Exception as e:
                    logger.error(f"处理历史文件 {history_file} 失败: {e}")
                    continue
            
            logger.warning(f"未找到历史任务 {task_id}")
            return False
            
        except Exception as e:
            logger.error(f"删除历史任务失败: {e}")
            return False
    
    def cleanup_old_history(self, keep_months: int = 6) -> int:
        """
        清理旧的历史记录
        
        Args:
            keep_months: 保留的月数
            
        Returns:
            清理的文件数量
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=keep_months * 30)
            
            history_files = list(self.task_history_dir.glob("*_tasks.json"))
            cleaned_count = 0
            
            for history_file in history_files:
                try:
                    # 从文件名解析日期
                    name_parts = history_file.stem.split('_')
                    if len(name_parts) >= 2:
                        year = int(name_parts[0])
                        month = int(name_parts[1])
                        file_date = datetime(year, month, 1)
                        
                        if file_date < cutoff_date:
                            history_file.unlink()
                            cleaned_count += 1
                            logger.info(f"清理旧历史文件: {history_file}")
                            
                except Exception as e:
                    logger.error(f"清理文件 {history_file} 失败: {e}")
                    continue
            
            logger.info(f"清理了 {cleaned_count} 个旧历史文件")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"清理旧历史记录失败: {e}")
            return 0
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取数据统计信息
        
        Returns:
            统计信息字典
        """
        try:
            stats = {
                "total_tasks": 0,
                "completed_tasks": 0,
                "failed_tasks": 0,
                "total_presets": 0,
                "history_files": 0,
                "data_size_mb": 0.0
            }
            
            # 统计历史任务
            history_files = list(self.task_history_dir.glob("*_tasks.json"))
            stats["history_files"] = len(history_files)
            
            for history_file in history_files:
                try:
                    with open(history_file, 'r', encoding='utf-8') as f:
                        history_data = json.load(f)
                    
                    tasks = history_data.get("tasks", [])
                    stats["total_tasks"] += len(tasks)
                    
                    for task in tasks:
                        if task.get("status") == "completed":
                            stats["completed_tasks"] += 1
                        elif task.get("status") == "failed":
                            stats["failed_tasks"] += 1
                    
                    # 统计文件大小
                    stats["data_size_mb"] += history_file.stat().st_size / (1024 * 1024)
                    
                except Exception as e:
                    logger.error(f"读取统计信息失败 {history_file}: {e}")
                    continue
            
            # 统计预设数量
            presets_file = self.config_presets_dir / "user_presets.json"
            if presets_file.exists():
                try:
                    with open(presets_file, 'r', encoding='utf-8') as f:
                        presets_data = json.load(f)
                    stats["total_presets"] = len(presets_data.get("presets", []))
                    stats["data_size_mb"] += presets_file.stat().st_size / (1024 * 1024)
                except Exception:
                    pass
            
            stats["data_size_mb"] = round(stats["data_size_mb"], 2)
            
            return stats
            
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {}
    
    # === 定时任务持久化管理功能 ===
    
    def save_scheduled_task(self, task_id: str, config_dict: Dict[str, Any], 
                           status: str = "running") -> bool:
        """
        保存定时任务配置到持久化存储
        
        Args:
            task_id: 任务ID
            config_dict: 任务配置字典
            status: 任务状态 (running, paused, stopped, error)
            
        Returns:
            保存是否成功
        """
        try:
            # 确保定时任务目录存在
            scheduled_tasks_dir = self.data_dir / "scheduled_tasks"
            scheduled_tasks_dir.mkdir(exist_ok=True)
            
            # 准备任务数据
            task_data = {
                "task_id": task_id,
                "config": config_dict,
                "status": status,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "execution_count": 0,
                "last_executed_at": None,
                "next_execution_at": None,
                "error_message": None,
                "_version": ConfigVersionManager.CURRENT_VERSION
            }
            
            # 计算下次执行时间
            if "interval_seconds" in config_dict:
                next_time = datetime.now() + timedelta(seconds=config_dict["interval_seconds"])
                task_data["next_execution_at"] = next_time.isoformat()
            
            # 保存到单独的文件
            task_file = scheduled_tasks_dir / f"{task_id}.json"
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
            
            logger.info(f"定时任务 {task_id} 已保存到持久化存储")
            return True
            
        except Exception as e:
            logger.error(f"保存定时任务失败: {e}")
            return False
    
    def load_scheduled_tasks(self) -> List[Dict[str, Any]]:
        """
        加载所有定时任务配置
        
        Returns:
            定时任务配置列表
        """
        try:
            scheduled_tasks_dir = self.data_dir / "scheduled_tasks"
            if not scheduled_tasks_dir.exists():
                return []
            
            tasks = []
            task_files = list(scheduled_tasks_dir.glob("*.json"))
            
            for task_file in task_files:
                try:
                    with open(task_file, 'r', encoding='utf-8') as f:
                        task_data = json.load(f)
                    
                    # 应用配置版本兼容性
                    if "config" in task_data:
                        task_data["config"] = ConfigVersionManager.ensure_config_compatibility(
                            task_data["config"]
                        )
                    
                    tasks.append(task_data)
                    
                except Exception as e:
                    logger.error(f"读取定时任务文件 {task_file} 失败: {e}")
                    continue
            
            # 按创建时间排序
            tasks.sort(key=lambda x: x.get("created_at", ""), reverse=True)
            
            logger.info(f"加载了 {len(tasks)} 个定时任务")
            return tasks
            
        except Exception as e:
            logger.error(f"加载定时任务失败: {e}")
            return []
    
    def get_scheduled_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取指定的定时任务配置
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务配置字典
        """
        try:
            scheduled_tasks_dir = self.data_dir / "scheduled_tasks"
            task_file = scheduled_tasks_dir / f"{task_id}.json"
            
            if not task_file.exists():
                return None
            
            with open(task_file, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
            
            # 应用配置版本兼容性
            if "config" in task_data:
                task_data["config"] = ConfigVersionManager.ensure_config_compatibility(
                    task_data["config"]
                )
            
            return task_data
            
        except Exception as e:
            logger.error(f"获取定时任务 {task_id} 失败: {e}")
            return None
    
    def update_scheduled_task(self, task_id: str, updates: Dict[str, Any]) -> bool:
        """
        更新定时任务配置或状态
        
        Args:
            task_id: 任务ID
            updates: 更新的字段字典
            
        Returns:
            更新是否成功
        """
        try:
            # 获取现有任务数据
            task_data = self.get_scheduled_task(task_id)
            if not task_data:
                logger.warning(f"定时任务 {task_id} 不存在，无法更新")
                return False
            
            # 应用更新
            task_data.update(updates)
            task_data["updated_at"] = datetime.now().isoformat()
            
            # 如果更新了配置中的interval_seconds，重新计算下次执行时间
            if "config" in updates and "interval_seconds" in updates["config"]:
                if task_data.get("status") == "running":
                    next_time = datetime.now() + timedelta(seconds=updates["config"]["interval_seconds"])
                    task_data["next_execution_at"] = next_time.isoformat()
            
            # 保存更新后的数据
            scheduled_tasks_dir = self.data_dir / "scheduled_tasks"
            task_file = scheduled_tasks_dir / f"{task_id}.json"
            
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
            
            logger.info(f"定时任务 {task_id} 已更新")
            return True
            
        except Exception as e:
            logger.error(f"更新定时任务 {task_id} 失败: {e}")
            return False
    
    def delete_scheduled_task(self, task_id: str) -> bool:
        """
        删除定时任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            删除是否成功
        """
        try:
            scheduled_tasks_dir = self.data_dir / "scheduled_tasks"
            task_file = scheduled_tasks_dir / f"{task_id}.json"
            
            if task_file.exists():
                task_file.unlink()
                logger.info(f"定时任务 {task_id} 已从持久化存储删除")
                return True
            else:
                logger.warning(f"定时任务文件 {task_file} 不存在")
                return False
            
        except Exception as e:
            logger.error(f"删除定时任务 {task_id} 失败: {e}")
            return False
    
    def update_task_execution_stats(self, task_id: str, success: bool = True, 
                                   error_message: Optional[str] = None) -> bool:
        """
        更新任务执行统计信息
        
        Args:
            task_id: 任务ID
            success: 执行是否成功
            error_message: 错误信息（如果执行失败）
            
        Returns:
            更新是否成功
        """
        try:
            task_data = self.get_scheduled_task(task_id)
            if not task_data:
                return False
            
            # 更新执行统计
            task_data["execution_count"] = task_data.get("execution_count", 0) + 1
            task_data["last_executed_at"] = datetime.now().isoformat()
            task_data["updated_at"] = datetime.now().isoformat()
            
            if success:
                task_data["status"] = "running"
                task_data["error_message"] = None
                # 计算下次执行时间
                if "config" in task_data and "interval_seconds" in task_data["config"]:
                    next_time = datetime.now() + timedelta(seconds=task_data["config"]["interval_seconds"])
                    task_data["next_execution_at"] = next_time.isoformat()
            else:
                task_data["status"] = "error"
                task_data["error_message"] = error_message
                task_data["next_execution_at"] = None
            
            # 保存更新
            scheduled_tasks_dir = self.data_dir / "scheduled_tasks"
            task_file = scheduled_tasks_dir / f"{task_id}.json"
            
            with open(task_file, 'w', encoding='utf-8') as f:
                json.dump(task_data, f, ensure_ascii=False, indent=2, cls=CustomJSONEncoder)
            
            return True
            
        except Exception as e:
            logger.error(f"更新任务执行统计失败: {e}")
            return False
    
    def cleanup_old_scheduled_tasks(self, days: int = 30) -> int:
        """
        清理长时间未活动的定时任务
        
        Args:
            days: 天数阈值
            
        Returns:
            清理的任务数量
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            scheduled_tasks_dir = self.data_dir / "scheduled_tasks"
            if not scheduled_tasks_dir.exists():
                return 0
            
            task_files = list(scheduled_tasks_dir.glob("*.json"))
            cleaned_count = 0
            
            for task_file in task_files:
                try:
                    with open(task_file, 'r', encoding='utf-8') as f:
                        task_data = json.load(f)
                    
                    # 检查任务状态和最后更新时间
                    status = task_data.get("status")
                    updated_at_str = task_data.get("updated_at")
                    
                    if status in ["stopped", "error"] and updated_at_str:
                        updated_at = datetime.fromisoformat(updated_at_str)
                        if updated_at < cutoff_date:
                            task_file.unlink()
                            cleaned_count += 1
                            logger.info(f"清理过期定时任务: {task_data.get('task_id')}")
                    
                except Exception as e:
                    logger.error(f"清理任务文件 {task_file} 失败: {e}")
                    continue
            
            logger.info(f"清理了 {cleaned_count} 个过期定时任务")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"清理过期定时任务失败: {e}")
            return 0