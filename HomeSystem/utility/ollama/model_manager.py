"""
Ollama模型管理器

提供与Ollama服务交互的功能：
- 查询可用模型列表
- 获取模型详细信息
- 过滤符合要求的模型
"""

import os
import re
import json
import logging
import requests
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ModelInfo:
    """模型信息数据类"""
    name: str
    size: int  # 字节
    modified_at: str
    parameters: str  # 参数规模（如14B, 32B）
    context_length: int = 131072  # 默认128K上下文
    supports_functions: bool = False  # Ollama模型一般不支持函数调用
    max_tokens: int = 32768  # 默认最大输出token
    description: str = ""
    display_name: str = ""
    key: str = ""  # 用于LLM Factory的标识符


class OllamaModelManager:
    """Ollama模型管理器"""
    
    def __init__(self, base_url: Optional[str] = None):
        """
        初始化Ollama模型管理器
        
        Args:
            base_url: Ollama服务地址，默认从环境变量OLLAMA_BASE_URL读取，或使用localhost:11434
        """
        self.base_url = base_url or os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')
        self.session = requests.Session()
        self.session.timeout = 30
        
    def test_connection(self) -> bool:
        """测试与Ollama服务的连接"""
        try:
            response = self.session.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"无法连接到Ollama服务 {self.base_url}: {e}")
            return False
    
    def get_available_models(self) -> List[Dict[str, Any]]:
        """获取Ollama中的所有可用模型"""
        try:
            response = self.session.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return data.get('models', [])
        except Exception as e:
            logger.error(f"获取模型列表失败: {e}")
            return []
    
    def parse_model_info(self, model_data: Dict[str, Any]) -> Optional[ModelInfo]:
        """解析模型数据，提取关键信息"""
        try:
            name = model_data.get('name', '')
            size = model_data.get('size', 0)
            modified_at = model_data.get('modified_at', '')
            
            # 从模型名称中提取参数规模
            parameters = self._extract_parameters(name)
            if not parameters:
                logger.debug(f"无法解析模型参数: {name}")
                return None
            
            # 生成显示名称和描述
            display_name, description = self._generate_display_info(name, parameters)
            
            # 生成LLM Factory使用的key
            key = self._generate_model_key(name)
            
            return ModelInfo(
                name=name,
                size=size,
                modified_at=modified_at,
                parameters=parameters,
                display_name=display_name,
                description=description,
                key=key
            )
        except Exception as e:
            logger.error(f"解析模型信息失败: {e}")
            return None
    
    def _extract_parameters(self, model_name: str) -> Optional[str]:
        """从模型名称中提取参数规模"""
        # 匹配常见的参数格式：14b, 32b, 70b, 1.5b等
        param_patterns = [
            r'(\d+(?:\.\d+)?b)',  # 14b, 32b, 1.5b
            r'(\d+(?:\.\d+)?B)',  # 14B, 32B, 1.5B
        ]
        
        for pattern in param_patterns:
            match = re.search(pattern, model_name, re.IGNORECASE)
            if match:
                param = match.group(1).upper()
                # 转换为标准格式（如14B）
                if param.endswith('b'):
                    param = param[:-1] + 'B'
                return param
        
        return None
    
    def _parameter_to_float(self, param_str: str) -> float:
        """将参数字符串转换为数值（单位：B）"""
        try:
            # 移除B后缀并转换为浮点数
            num_str = param_str.rstrip('Bb')
            return float(num_str)
        except ValueError:
            return 0.0
    
    def _generate_display_info(self, model_name: str, parameters: str) -> tuple[str, str]:
        """生成显示名称和描述"""
        # 基于模型名称生成友好的显示名称
        name_lower = model_name.lower()
        
        if 'deepseek' in name_lower:
            if 'r1' in name_lower:
                display_name = f"DeepSeek R1 {parameters}"
                description = f"DeepSeek推理模型{parameters}版本，支持128K上下文"
            elif 'coder' in name_lower:
                display_name = f"DeepSeek Coder {parameters}"
                description = f"DeepSeek代码专用模型{parameters}版本"
            else:
                display_name = f"DeepSeek {parameters}"
                description = f"DeepSeek大语言模型{parameters}版本"
        elif 'qwen' in name_lower:
            if '3' in name_lower:
                display_name = f"通义千问3 {parameters}"
                description = f"MoE架构代码专用模型，多语言支持，支持128K上下文"
            elif '2.5' in name_lower:
                display_name = f"通义千问 2.5-{parameters}"
                description = f"通义千问2.5系列{parameters}版本"
            else:
                display_name = f"通义千问 {parameters}"
                description = f"阿里通义千问大语言模型{parameters}版本"
        elif 'llama' in name_lower:
            display_name = f"Llama {parameters}"
            description = f"Meta Llama开源模型{parameters}版本"
        elif 'mistral' in name_lower:
            display_name = f"Mistral {parameters}"
            description = f"Mistral AI开源模型{parameters}版本"
        elif 'codestral' in name_lower:
            display_name = f"Codestral {parameters}"
            description = f"Mistral AI代码专用模型{parameters}版本"
        else:
            # 通用命名
            base_name = model_name.split(':')[0].title()
            display_name = f"{base_name} {parameters}"
            description = f"{base_name}开源模型{parameters}版本"
        
        return display_name, description
    
    def _generate_model_key(self, model_name: str) -> str:
        """生成LLM Factory使用的模型key"""
        # 移除版本标签，保留主要名称
        base_name = model_name.split(':')[0]
        
        # 转换为标准格式
        name_mapping = {
            'deepseek-r1': 'DeepSeek_R1',
            'deepseek-coder': 'DeepSeek_Coder',
            'deepseek': 'DeepSeek',
            'qwen3': 'Qwen3',
            'qwen2.5': 'Qwen2_5',
            'qwen': 'Qwen',
            'llama3.3': 'Llama3_3',
            'llama3.2': 'Llama3_2',
            'llama3.1': 'Llama3_1',
            'llama3': 'Llama3',
            'llama2': 'Llama2',
            'mistral': 'Mistral',
            'codestral': 'Codestral',
        }
        
        # 查找最匹配的名称
        for pattern, mapped_name in name_mapping.items():
            if pattern in base_name.lower():
                # 提取参数信息
                params = self._extract_parameters(model_name)
                if params:
                    return f"ollama.{mapped_name}_{params}"
                else:
                    return f"ollama.{mapped_name}"
        
        # 如果没有匹配，使用通用格式
        clean_name = base_name.replace('-', '_').replace('.', '_').title()
        params = self._extract_parameters(model_name)
        if params:
            return f"ollama.{clean_name}_{params}"
        else:
            return f"ollama.{clean_name}"
    
    def filter_large_models(self, models: List[ModelInfo], min_parameters: float = 3.0) -> List[ModelInfo]:
        """过滤出参数量大于等于指定值的模型"""
        filtered = []
        for model in models:
            param_value = self._parameter_to_float(model.parameters)
            if param_value >= min_parameters:
                filtered.append(model)
            else:
                logger.debug(f"模型 {model.name} 参数量 {model.parameters} 小于 {min_parameters}B，已过滤")
        
        return filtered
    
    def get_large_models(self, min_parameters: float = 3.0) -> List[ModelInfo]:
        """获取所有符合参数要求的大模型"""
        raw_models = self.get_available_models()
        if not raw_models:
            logger.warning("未获取到任何模型")
            return []
        
        # 解析模型信息
        parsed_models = []
        for model_data in raw_models:
            model_info = self.parse_model_info(model_data)
            if model_info:
                parsed_models.append(model_info)
        
        # 过滤大模型
        large_models = self.filter_large_models(parsed_models, min_parameters)
        
        logger.info(f"发现 {len(raw_models)} 个模型，其中 {len(large_models)} 个符合 {min_parameters}B+ 参数要求")
        
        return large_models
    
    def get_model_details(self, model_name: str) -> Optional[Dict[str, Any]]:
        """获取指定模型的详细信息"""
        try:
            payload = {"name": model_name}
            response = self.session.post(f"{self.base_url}/api/show", json=payload)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"获取模型 {model_name} 详细信息失败: {e}")
            return None