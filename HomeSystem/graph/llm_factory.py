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
from langchain_deepseek import ChatDeepSeek
# from langchain_community.chat_models import ChatZhipuAI
from pydantic import SecretStr


class LLMFactory:
    """LLM工厂 - 从YAML配置读取可用模型并创建实例"""
    
    def __init__(self, config_path: Optional[str] = None):
        load_dotenv()
        
        if config_path is None:
            config_path = str(Path(__file__).parent / "config" / "llm_providers.yaml")
        
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
                        'context_length': model.get('context_length'),
                        'supports_functions': model.get('supports_functions', False),
                        'supports_vision': model.get('supports_vision', False),
                        'supports_thinking': model.get('supports_thinking', False),
                        'thinking_max_length': model.get('thinking_max_length')
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
    
    def get_available_vision_models(self) -> List[str]:
        """获取所有支持视觉的模型列表"""
        return [model_key for model_key, config in self.available_llm_models.items() 
                if config.get('supports_vision', False)]
    
    def supports_vision(self, model_name: str) -> bool:
        """检查指定模型是否支持视觉功能"""
        if model_name not in self.available_llm_models:
            return False
        return self.available_llm_models[model_name].get('supports_vision', False)
    
    def is_local_model(self, model_name: str) -> bool:
        """检查是否为本地模型"""
        if model_name not in self.available_llm_models:
            return False
        return self.available_llm_models[model_name]['type'] == 'ollama'
    
    def supports_thinking(self, model_name: str) -> bool:
        """检查指定模型是否支持思考模式"""
        if model_name not in self.available_llm_models:
            return False
        return self.available_llm_models[model_name].get('supports_thinking', False)
    
    def get_available_thinking_models(self) -> List[str]:
        """获取所有支持思考模式的模型列表"""
        return [model_key for model_key, config in self.available_llm_models.items() 
                if config.get('supports_thinking', False)]
    
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
        
        # 分离思考模式参数和普通参数
        thinking_params = {}
        if 'enable_thinking' in kwargs:
            thinking_params['enable_thinking'] = kwargs.pop('enable_thinking')
        if 'thinking_budget' in kwargs:
            thinking_params['thinking_budget'] = kwargs.pop('thinking_budget')
        
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
        elif config['provider'] == 'deepseek':  # Use native ChatDeepSeek for DeepSeek models
            api_key = os.getenv(config['api_key_env'])
            # DeepSeek has max_tokens limit of 8192
            if 'max_tokens' in params and params['max_tokens'] > 8192:
                params['max_tokens'] = 8192
            return ChatDeepSeek(
                model=config['model_name'],
                api_key=SecretStr(api_key) if api_key else None,
                **params
            )
        elif config['provider'] == 'zhipuai':  # Use OpenAI compatible for ZhipuAI models
            api_key = os.getenv(config['api_key_env'])
            base_url = os.getenv(config['base_url_env'], config['base_url'])
            return ChatOpenAI(
                model=config['model_name'],
                api_key=SecretStr(api_key) if api_key else None,
                base_url=base_url,
                **params
            )
        else:  # openai_compatible
            api_key = os.getenv(config['api_key_env'])
            base_url = os.getenv(config['base_url_env'], config['base_url'])
            
            # 处理阿里云思考模式模型的特殊参数
            if config.get('provider') == 'alibaba' and config.get('supports_thinking', False) and thinking_params:
                return ChatOpenAI(
                    model=config['model_name'],
                    api_key=SecretStr(api_key) if api_key else None,
                    base_url=base_url,
                    model_kwargs=thinking_params,
                    **params
                )
            else:
                return ChatOpenAI(
                    model=config['model_name'],
                    api_key=SecretStr(api_key) if api_key else None,
                    base_url=base_url,
                    **params
                )
    
    def create_vision_llm(self, model_name: Optional[str] = None, **kwargs) -> BaseChatModel:
        """
        创建支持视觉的LLM实例
        
        Args:
            model_name: 模型名称，如果为None则自动选择支持视觉的模型
            **kwargs: 传递给模型的参数
            
        Returns:
            BaseChatModel: 支持视觉的LLM实例
            
        Raises:
            ValueError: 如果指定的模型不支持视觉功能或为云端模型
        """
        # 如果未指定模型，选择默认的视觉模型
        if model_name is None:
            vision_models = self.get_available_vision_models()
            if not vision_models:
                raise ValueError("没有可用的视觉模型")
            model_name = vision_models[0]  # 选择第一个可用的视觉模型
        
        # 检查模型是否支持视觉
        if not self.supports_vision(model_name):
            raise ValueError(f"模型 '{model_name}' 不支持视觉功能")
        
        # 检查是否为本地模型（只有本地模型支持视觉）
        if not self.is_local_model(model_name):
            available_vision = ', '.join(self.get_available_vision_models())
            raise ValueError(f"云端模型 '{model_name}' 不支持视觉功能。请使用本地视觉模型: {available_vision}")
        
        # 创建支持视觉的LLM实例
        logger.info(f"创建视觉LLM: {model_name}")
        return self.create_llm(model_name, **kwargs)
    
    def create_thinking_llm(self, model_name: Optional[str] = None, **kwargs) -> BaseChatModel:
        """
        创建支持思考模式的LLM实例
        
        Args:
            model_name: 模型名称，如果为None则自动选择支持思考模式的模型
            **kwargs: 传递给模型的参数，可包含enable_thinking和thinking_budget
            
        Returns:
            BaseChatModel: 支持思考模式的LLM实例
            
        Raises:
            ValueError: 如果指定的模型不支持思考模式
        """
        # 如果未指定模型，选择默认的思考模式模型
        if model_name is None:
            thinking_models = self.get_available_thinking_models()
            if not thinking_models:
                raise ValueError("没有可用的思考模式模型")
            model_name = thinking_models[0]  # 选择第一个可用的思考模式模型
        
        # 检查模型是否支持思考模式
        if not self.supports_thinking(model_name):
            raise ValueError(f"模型 '{model_name}' 不支持思考模式")
        
        # 设置默认的思考模式参数
        if 'enable_thinking' not in kwargs:
            kwargs['enable_thinking'] = True
        if 'thinking_budget' not in kwargs:
            kwargs['thinking_budget'] = 1  # 默认思考预算
        
        # 创建支持思考模式的LLM实例
        logger.info(f"创建思考模式LLM: {model_name}")
        return self.create_llm(model_name, **kwargs)
    
    def validate_vision_input(self, model_name: str) -> None:
        """
        验证模型是否可以接受视觉输入
        
        Args:
            model_name: 模型名称
            
        Raises:
            ValueError: 如果模型不支持视觉或为云端模型
        """
        if not self.supports_vision(model_name):
            if self.is_local_model(model_name):
                available_vision = ', '.join(self.get_available_vision_models())
                raise ValueError(f"本地模型 '{model_name}' 不支持视觉功能。请使用: {available_vision}")
            else:
                raise ValueError(f"云端模型 '{model_name}' 仅支持纯文本输入，不支持图片处理")
    
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
                api_key=SecretStr(api_key) if api_key else None,
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
            vision_mark = "👁️" if config.get('supports_vision', False) else "📝"
            thinking_mark = "🧠" if config.get('supports_thinking', False) else ""
            local_mark = "🏠" if config['type'] == 'ollama' else "☁️"
            logger.info(f"✅ {model_name:35} | {vision_mark}{thinking_mark}{local_mark} {config['display_name']}")
        
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


def get_vision_llm(model_name: Optional[str] = None, **kwargs) -> BaseChatModel:
    """便捷函数：创建支持视觉的LLM实例"""
    return llm_factory.create_vision_llm(model_name, **kwargs)


def list_available_vision_models() -> List[str]:
    """便捷函数：获取可用视觉模型列表"""
    return llm_factory.get_available_vision_models()


def check_vision_support(model_name: str) -> bool:
    """便捷函数：检查模型是否支持视觉"""
    return llm_factory.supports_vision(model_name)


def validate_vision_input(model_name: str) -> None:
    """便捷函数：验证模型视觉输入能力"""
    return llm_factory.validate_vision_input(model_name)


def get_thinking_llm(model_name: Optional[str] = None, **kwargs) -> BaseChatModel:
    """便捷函数：创建支持思考模式的LLM实例"""
    return llm_factory.create_thinking_llm(model_name, **kwargs)


def list_available_thinking_models() -> List[str]:
    """便捷函数：获取可用思考模式模型列表"""
    return llm_factory.get_available_thinking_models()


def check_thinking_support(model_name: str) -> bool:
    """便捷函数：检查模型是否支持思考模式"""
    return llm_factory.supports_thinking(model_name)


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

    # 创建kimi模型
    # kimi_llm = factory.create_llm(model_name='moonshot.Kimi_K2')
    # logger.info(f"✅ Kimi LLM创建成功: {type(kimi_llm).__name__}")
    # response = kimi_llm.invoke("你好，Kimi！")

    # 创建硅基流动模型
    siliconflow_llm = factory.create_llm(model_name='siliconflow.DeepSeek_V3')
    logger.info(f"✅ SiliconFlow LLM创建成功: {type(siliconflow_llm).__name__}")
    response = siliconflow_llm.invoke("你好，SiliconFlow！")
    logger.info(f"✅ SiliconFlow LLM响应成功: {response}")

    # 创建智谱AI模型（如果API Key可用）
    try:
        zhipuai_llm = factory.create_llm(model_name='zhipuai.GLM_4_5')
        logger.info(f"✅ ZhipuAI LLM创建成功: {type(zhipuai_llm).__name__}")
        response = zhipuai_llm.invoke("你好，智谱AI！")
        logger.info(f"✅ ZhipuAI LLM响应成功: {response}")
    except Exception as e:
        logger.warning(f"⚠️  ZhipuAI模型创建失败（可能缺少API Key）: {e}")
