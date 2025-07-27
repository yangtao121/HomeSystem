#!/usr/bin/env python3
"""
简单的pix2text测试脚本
"""

import os
import sys
import tempfile

# 强制设置CPU模式
os.environ['CUDA_VISIBLE_DEVICES'] = ''
os.environ['OMP_NUM_THREADS'] = '1'

# 添加项目根目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from pix2text import Pix2Text
from loguru import logger


def test_simple_pix2text():
    """简单测试pix2text"""
    try:
        logger.info("开始测试pix2text基本功能")
        
        # 尝试初始化pix2text，禁用表格识别
        logger.info("初始化pix2text...")
        try:
            # 尝试使用最简单的配置，禁用可能导致问题的组件
            config = {
                'text_ocr': {'enabled': True},
                'layout': {'enabled': False},  # 禁用布局检测
                'formula': {'enabled': False},  # 禁用公式识别
                'table': {'enabled': False},   # 禁用表格识别
                'mfd': {'enabled': False}       # 禁用数学公式检测
            }
            
            p2t = Pix2Text.from_config(config=config)
            logger.info("pix2text初始化成功")
        except Exception as e:
            logger.warning(f"配置初始化失败: {e}")
            logger.info("尝试使用最简单的初始化方式...")
            try:
                # 最简单的初始化方式，只用于文本OCR
                p2t = Pix2Text()
                logger.info("默认初始化成功")
            except Exception as e2:
                logger.error(f"初始化完全失败: {e2}")
                return False
        
        logger.info("pix2text测试完成")
        return True
        
    except Exception as e:
        logger.error(f"测试失败: {e}")
        return False


if __name__ == "__main__":
    success = test_simple_pix2text()
    if success:
        print("✅ pix2text基本测试成功")
    else:
        print("❌ pix2text基本测试失败")