"""
配置文件更新器

负责更新llm_providers.yaml文件中的Ollama模型配置：
- 保持原有文件结构和注释
- 智能合并新发现的模型
- 创建备份文件
- 验证配置完整性
"""

import os
import re
import yaml
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

from .model_manager import ModelInfo

logger = logging.getLogger(__name__)


class ConfigUpdater:
    """配置文件更新器"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化配置更新器
        
        Args:
            config_path: 配置文件路径，默认使用项目中的llm_providers.yaml
        """
        if config_path:
            self.config_path = Path(config_path)
        else:
            # 默认使用项目配置文件路径
            current_dir = Path(__file__).parent
            self.config_path = current_dir.parent.parent / "graph" / "config" / "llm_providers.yaml"
        
        self.backup_path = self.config_path.with_suffix('.yaml.backup')
        
    def load_config(self) -> Optional[Dict[str, Any]]:
        """加载现有配置文件"""
        try:
            if not self.config_path.exists():
                logger.error(f"配置文件不存在: {self.config_path}")
                return None
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            return None
    
    def create_backup(self) -> bool:
        """创建配置文件备份"""
        try:
            if self.config_path.exists():
                # 添加时间戳的备份文件名
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_with_timestamp = self.config_path.with_suffix(f'.yaml.backup_{timestamp}')
                
                with open(self.config_path, 'r', encoding='utf-8') as src:
                    content = src.read()
                
                with open(backup_with_timestamp, 'w', encoding='utf-8') as dst:
                    dst.write(content)
                
                logger.info(f"创建备份文件: {backup_with_timestamp}")
                return True
        except Exception as e:
            logger.error(f"创建备份失败: {e}")
            return False
    
    def convert_models_to_config_format(self, models: List[ModelInfo]) -> List[Dict[str, Any]]:
        """将ModelInfo列表转换为配置文件格式"""
        config_models = []
        
        for model in models:
            config_model = {
                'name': model.name,
                'key': model.key,
                'display_name': model.display_name,
                'parameters': model.parameters,
                'max_tokens': model.max_tokens,
                'supports_functions': model.supports_functions,
                'context_length': model.context_length,
                'description': model.description
            }
            config_models.append(config_model)
        
        return config_models
    
    def merge_models(self, existing_models: List[Dict[str, Any]], 
                    new_models: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """智能合并现有模型和新发现的模型"""
        # 创建现有模型的索引（基于name）
        existing_by_name = {model.get('name', ''): model for model in existing_models}
        
        merged_models = []
        
        # 首先添加所有新模型（更新或新增）
        for new_model in new_models:
            model_name = new_model.get('name', '')
            if model_name in existing_by_name:
                # 更新现有模型，但保留手动设置的配置
                existing = existing_by_name[model_name]
                merged_model = new_model.copy()
                
                # 保留可能的手动配置
                preserve_fields = ['max_tokens', 'supports_functions', 'context_length']
                for field in preserve_fields:
                    if field in existing and existing[field] != new_model.get(field):
                        logger.info(f"保留模型 {model_name} 的手动配置 {field}: {existing[field]}")
                        merged_model[field] = existing[field]
                
                merged_models.append(merged_model)
                logger.info(f"更新模型: {model_name}")
            else:
                # 新模型
                merged_models.append(new_model)
                logger.info(f"添加新模型: {model_name}")
        
        # 添加在新模型中不存在的现有模型（可能已被删除）
        new_model_names = {model.get('name', '') for model in new_models}
        for existing_model in existing_models:
            model_name = existing_model.get('name', '')
            if model_name not in new_model_names:
                # 这个模型在Ollama中不存在了，询问是否保留
                logger.warning(f"模型 {model_name} 在Ollama中未找到，将保留在配置中（可能需要手动清理）")
                merged_models.append(existing_model)
        
        # 按name排序
        merged_models.sort(key=lambda x: x.get('name', ''))
        
        return merged_models
    
    def update_ollama_models(self, new_models: List[ModelInfo], dry_run: bool = False) -> bool:
        """更新配置文件中的Ollama模型部分"""
        # 加载现有配置
        config = self.load_config()
        if not config:
            logger.error("无法加载配置文件")
            return False
        
        # 检查配置结构
        if 'providers' not in config or 'ollama' not in config['providers']:
            logger.error("配置文件结构不正确，缺少providers.ollama部分")
            return False
        
        ollama_config = config['providers']['ollama']
        if 'models' not in ollama_config:
            logger.warning("Ollama配置中没有models部分，将创建一个新的")
            ollama_config['models'] = []
        
        # 转换新模型为配置格式
        new_config_models = self.convert_models_to_config_format(new_models)
        
        # 合并模型
        existing_models = ollama_config['models']
        merged_models = self.merge_models(existing_models, new_config_models)
        
        # 更新配置
        config['providers']['ollama']['models'] = merged_models
        
        if dry_run:
            logger.info("DRY RUN - 以下是将要更新的模型列表:")
            for model in merged_models:
                logger.info(f"  - {model.get('name', 'Unknown')} ({model.get('key', 'Unknown key')})")
            return True
        
        # 创建备份
        if not self.create_backup():
            logger.warning("备份创建失败，但继续更新配置")
        
        # 写入更新后的配置
        return self.save_config(config)
    
    def save_config(self, config: Dict[str, Any]) -> bool:
        """保存配置文件，尽量保持原有格式"""
        try:
            # 读取原文件内容以保持注释和格式
            with open(self.config_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # 使用yaml.dump生成新的配置内容
            new_yaml_content = yaml.dump(
                config, 
                default_flow_style=False, 
                allow_unicode=True, 
                indent=2,
                sort_keys=False
            )
            
            # 尝试保持文件头部的注释
            original_lines = original_content.split('\n')
            header_comments = []
            for line in original_lines:
                if line.strip().startswith('#') or line.strip() == '':
                    header_comments.append(line)
                else:
                    break
            
            # 合并头部注释和新配置
            if header_comments:
                final_content = '\n'.join(header_comments) + '\n\n' + new_yaml_content
            else:
                final_content = new_yaml_content
            
            # 写入文件
            with open(self.config_path, 'w', encoding='utf-8') as f:
                f.write(final_content)
            
            logger.info(f"配置文件已更新: {self.config_path}")
            return True
            
        except Exception as e:
            logger.error(f"保存配置文件失败: {e}")
            return False
    
    def validate_config(self) -> bool:
        """验证配置文件的完整性"""
        try:
            config = self.load_config()
            if not config:
                return False
            
            # 检查必要的结构
            required_sections = ['providers', 'embedding_providers', 'defaults']
            for section in required_sections:
                if section not in config:
                    logger.error(f"配置缺少必要部分: {section}")
                    return False
            
            # 检查Ollama配置
            if 'ollama' not in config['providers']:
                logger.error("配置缺少ollama提供商")
                return False
            
            ollama_config = config['providers']['ollama']
            required_ollama_fields = ['name', 'description', 'type', 'base_url', 'models']
            for field in required_ollama_fields:
                if field not in ollama_config:
                    logger.error(f"Ollama配置缺少必要字段: {field}")
                    return False
            
            # 检查模型配置
            models = ollama_config['models']
            if not isinstance(models, list):
                logger.error("Ollama models配置应该是列表")
                return False
            
            required_model_fields = ['name', 'key', 'display_name', 'parameters']
            for i, model in enumerate(models):
                for field in required_model_fields:
                    if field not in model:
                        logger.error(f"模型 {i} 缺少必要字段: {field}")
                        return False
            
            logger.info("配置文件验证通过")
            return True
            
        except Exception as e:
            logger.error(f"验证配置文件失败: {e}")
            return False
    
    def get_current_ollama_models(self) -> List[Dict[str, Any]]:
        """获取当前配置中的Ollama模型列表"""
        config = self.load_config()
        if not config:
            return []
        
        try:
            return config['providers']['ollama']['models']
        except KeyError:
            logger.warning("配置中没有找到Ollama模型列表")
            return []
    
    def compare_models(self, current_models: List[ModelInfo]) -> Dict[str, List[str]]:
        """比较当前发现的模型与配置文件中的模型"""
        config_models = self.get_current_ollama_models()
        
        # 创建模型名称集合
        current_names = {model.name for model in current_models}
        config_names = {model.get('name', '') for model in config_models}
        
        result = {
            'new_models': list(current_names - config_names),
            'removed_models': list(config_names - current_names),
            'existing_models': list(current_names & config_names)
        }
        
        return result