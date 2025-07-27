"""
简洁的LLM工厂 - 从YAML配置文件读取并创建langgraph直接可用的实例
"""

import os
import yaml
from typing import Optional, Dict, List
from pathlib import Path
from loguru import logger
from dotenv import load_dotenv

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_ollama import ChatOllama, OllamaEmbeddings


class LLMFactory:
    """LLM工厂 - 从YAML配置读取可用模型并创建实例"""
    
    def __init__(self, config_path: Optional[str] = None):
        load_dotenv()
        
        if config_path is None:
            config_path = Path(__file__).parent / "llm_providers.yaml"
        
        self.config = self._load_config(config_path)
        self.available_llm_models = self._detect_available_llm_models()
        self.available_embedding_models = self._detect_available_embedding_models()
        
        logger.info(f"检测到 {len(self.available_llm_models)} 个LLM模型, {len(self.available_embedding_models)} 个Embedding模型")
    
    def _load_config(self, config_path: str) -> Dict:
        """加载YAML配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"配置文件加载失败: {e}")
            raise
    
    def _is_provider_available(self, provider_config: Dict) -> bool:
        """检查提供商是否可用"""
        api_key_env = provider_config.get('api_key_env')
        
        # Ollama不需要API Key
        if not api_key_env:
            return True
        
        api_key = os.getenv(api_key_env)
        return api_key and not api_key.startswith('your_')
    
    def _detect_available_llm_models(self) -> Dict[str, Dict]:
        """检测可用的LLM模型"""
        available = {}
        
        for provider_key, provider_config in self.config.get('providers', {}).items():
            if self._is_provider_available(provider_config):
                for model in provider_config.get('models', []):
                    # 使用新的key格式（provider.model）
                    model_key = model.get('key', f"{provider_key}.{model['name'].replace(' ', '_').replace('-', '_').replace(':', '_').replace('/', '_')}")
                    available[model_key] = {
                        'provider': provider_key,
                        'model_name': model['name'],
                        'display_name': model['display_name'],
                        'type': provider_config['type'],
                        'api_key_env': provider_config.get('api_key_env'),
                        'base_url_env': provider_config.get('base_url_env'),
                        'base_url': provider_config.get('base_url'),
                        'description': model.get('description', ''),
                        'max_tokens': model.get('max_tokens'),
                        'supports_functions': model.get('supports_functions', False)
                    }
        
        return available
    
    def _detect_available_embedding_models(self) -> Dict[str, Dict]:
        """检测可用的Embedding模型"""
        available = {}
        
        for provider_key, provider_config in self.config.get('embedding_providers', {}).items():
            if self._is_provider_available(provider_config):
                for model in provider_config.get('models', []):
                    # 使用新的key格式（provider.model）
                    model_key = model.get('key', f"{provider_key}.{model['name'].replace(' ', '_').replace('-', '_').replace(':', '_').replace('/', '_')}")
                    available[model_key] = {
                        'provider': provider_key,
                        'model_name': model['name'],
                        'display_name': model['display_name'],
                        'type': provider_config['type'],
                        'api_key_env': provider_config.get('api_key_env'),
                        'base_url_env': provider_config.get('base_url_env'),
                        'base_url': provider_config.get('base_url'),
                        'description': model.get('description', ''),
                        'dimensions': model.get('dimensions'),
                        'max_input_length': model.get('max_input_length')
                    }
        
        return available
    
    def get_available_llm_models(self) -> List[str]:
        """获取所有可用LLM模型列表"""
        return list(self.available_llm_models.keys())
    
    def get_available_embedding_models(self) -> List[str]:
        """获取所有可用Embedding模型列表"""
        return list(self.available_embedding_models.keys())
    
    def create_llm(self, model_name: Optional[str] = None, **kwargs) -> BaseChatModel:
        """
        创建LLM实例，直接用于langgraph
        
        Args:
            model_name: 模型名称，如果为None则使用默认模型
            **kwargs: 传递给模型的参数
            
        Returns:
            BaseChatModel: 可直接用于langgraph的LLM实例
        """
        # 使用默认模型
        if model_name is None:
            default_config = self.config.get('defaults', {}).get('llm', {})
            model_name = default_config.get('model_key', 'deepseek.DeepSeek_V3')
        
        if model_name not in self.available_llm_models:
            available = ', '.join(self.available_llm_models.keys())
            raise ValueError(f"模型 '{model_name}' 不可用。可用模型: {available}")
        
        config = self.available_llm_models[model_name]
        logger.info(f"创建LLM: {model_name} ({config['display_name']})")
        
        # 设置默认参数
        defaults = self.config.get('defaults', {}).get('llm', {})
        params = {
            'temperature': kwargs.get('temperature', defaults.get('temperature', 0.7)),
            'max_tokens': kwargs.get('max_tokens', config.get('max_tokens', defaults.get('max_tokens', 4000))),
            **{k: v for k, v in kwargs.items() if k not in ['temperature', 'max_tokens']}
        }
        
        if config['type'] == 'ollama':
            base_url = os.getenv(config['base_url_env'], config['base_url'])
            return ChatOllama(
                model=config['model_name'],
                base_url=base_url,
                num_predict=params.pop('max_tokens'),
                **params
            )
        else:  # openai_compatible
            api_key = os.getenv(config['api_key_env'])
            base_url = os.getenv(config['base_url_env'], config['base_url'])
            return ChatOpenAI(
                model=config['model_name'],
                api_key=api_key,
                base_url=base_url,
                **params
            )
    
    def create_embedding(self, model_name: Optional[str] = None, **kwargs) -> Embeddings:
        """
        创建Embedding实例
        
        Args:
            model_name: 模型名称，如果为None则使用默认模型
            **kwargs: 传递给模型的参数
            
        Returns:
            Embeddings: Embedding实例
        """
        # 使用默认模型
        if model_name is None:
            default_config = self.config.get('defaults', {}).get('embedding', {})
            model_name = default_config.get('model_key', 'ollama.BGE_M3')
        
        if model_name not in self.available_embedding_models:
            available = ', '.join(self.available_embedding_models.keys())
            raise ValueError(f"Embedding模型 '{model_name}' 不可用。可用模型: {available}")
        
        config = self.available_embedding_models[model_name]
        logger.info(f"创建Embedding: {model_name} ({config['display_name']})")
        
        if config['type'] == 'ollama_embedding':
            base_url = os.getenv(config['base_url_env'], config['base_url'])
            return OllamaEmbeddings(
                model=config['model_name'],
                base_url=base_url,
                **kwargs
            )
        elif config['type'] == 'openai_embedding':
            api_key = os.getenv(config['api_key_env'])
            base_url = os.getenv(config['base_url_env'], config['base_url'])
            return OpenAIEmbeddings(
                model=config['model_name'],
                api_key=api_key,
                base_url=base_url,
                **kwargs
            )
        else:
            raise ValueError(f"不支持的embedding类型: {config['type']}")
    
    def list_models(self) -> None:
        """列出所有可用模型"""
        logger.info("=" * 80)
        logger.info("可用模型列表")
        logger.info("=" * 80)
        
        logger.info("\n📝 LLM模型:")
        logger.info("-" * 60)
        for model_name, config in self.available_llm_models.items():
            logger.info(f"✅ {model_name:35} | {config['display_name']}")
        
        logger.info("\n🔍 Embedding模型:")
        logger.info("-" * 60)
        for model_name, config in self.available_embedding_models.items():
            dims = f"({config['dimensions']}维)" if config.get('dimensions') else ""
            logger.info(f"✅ {model_name:35} | {config['display_name']} {dims}")
        
        logger.info("=" * 80)
        logger.info(f"总计: {len(self.available_llm_models)} 个LLM模型, {len(self.available_embedding_models)} 个Embedding模型")


# 全局工厂实例
llm_factory = LLMFactory()


def get_llm(model_name: Optional[str] = None, **kwargs) -> BaseChatModel:
    """便捷函数：创建LLM实例"""
    return llm_factory.create_llm(model_name, **kwargs)


def get_embedding(model_name: Optional[str] = None, **kwargs) -> Embeddings:
    """便捷函数：创建Embedding实例"""
    return llm_factory.create_embedding(model_name, **kwargs)


def list_available_llm_models() -> List[str]:
    """便捷函数：获取可用LLM模型列表"""
    return llm_factory.get_available_llm_models()


def list_available_embedding_models() -> List[str]:
    """便捷函数：获取可用Embedding模型列表"""
    return llm_factory.get_available_embedding_models()


if __name__ == "__main__":
    # 测试
    factory = LLMFactory()
    factory.list_models()
    
    # 测试创建模型
    try:
        llm = factory.create_llm()
        logger.info(f"✅ 默认LLM创建成功: {type(llm).__name__}")
        
        embedding = factory.create_embedding()
        logger.info(f"✅ 默认Embedding创建成功: {type(embedding).__name__}")
    except Exception as e:
        logger.error(f"❌ 模型创建失败: {e}")

    
    # 创建deepseek模型
    deepseek_llm = factory.create_llm(model_name='deepseek.DeepSeek_V3')
    logger.info(f"✅ DeepSeek LLM创建成功: {type(deepseek_llm).__name__}")

    response = deepseek_llm.invoke("你好，DeepSeek！")
    logger.info(f"✅ DeepSeek LLM响应成功: {response}")

    # 创建本地Ollama模型
    ollama_llm = factory.create_llm(model_name='ollama.Qwen3_30B')
    logger.info(f"✅ Ollama LLM创建成功: {type(ollama_llm).__name__}")
    response = ollama_llm.invoke("你好，Ollama！")
    logger.info(f"✅ Ollama LLM响应成功: {response}")