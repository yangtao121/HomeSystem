#!/usr/bin/env python3
"""
auto_generate_example.py

用途:
  为新增公开符号(<symbol>)生成最小示例骨架与 usage 文档模板。

特性:
  - 验证模块与符号可导入
  - 解析函数/类签名并生成参数占位注释
  - 在 examples/ 下按模块路径创建 <symbol>_example.py (若不存在)
  - 在 docs/examples/ 下创建 <symbol>-usage-v<date>.md (若不存在)
  - 避免覆盖已有文件

用法:
  python scripts/auto_generate_example.py HomeSystem.graph.chat_agent ChatAgent
  python scripts/auto_generate_example.py HomeSystem.graph.llm_factory build_llm

限制:
  - 不执行复杂 AST 推理，仅基于 inspect
  - 仅支持可直接 import 的符号
"""
from __future__ import annotations
import argparse
import importlib
import inspect
import sys
from datetime import date
from pathlib import Path
from textwrap import indent

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "examples"
DOCS_EXAMPLES_DIR = REPO_ROOT / "docs" / "examples"

USAGE_TEMPLATE = """# {symbol} Usage\n\n用途: {summary}\n\n核心能力:\n- <补充1>\n- <补充2 可删>\n- <补充3 可删>\n\n最小示例: `{example_rel}`\n\n输入参数:\n{params}\n返回:\n{returns}\n\n注意: <可选风险 / 依赖 / 性能关注点>\n版本: v{today}\n"""

def parse_args():
    p = argparse.ArgumentParser(description="Generate example + usage doc for a symbol")
    p.add_argument("module", help="Full module import path, e.g. HomeSystem.graph.chat_agent")
    p.add_argument("symbol", help="Public symbol name (function or class)")
    p.add_argument("--summary", default="<一句话说明>")
    return p.parse_args()


def import_symbol(module_path: str, symbol: str):
    try:
        mod = importlib.import_module(module_path)
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] 无法导入模块 {module_path}: {e}")
        sys.exit(1)
    if not hasattr(mod, symbol):
        print(f"[ERROR] 模块 {module_path} 不包含符号 {symbol}")
        sys.exit(1)
    obj = getattr(mod, symbol)
    return obj


def build_param_lines(obj) -> str:
    if inspect.isclass(obj):
        target = getattr(obj, "__init__", None)
        if target is None:
            return "(无参数)"
    else:
        target = obj
    try:
        sig = inspect.signature(target)
    except Exception:  # noqa: BLE001
        return "(签名不可解析)"
    lines = []
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        annotation = param.annotation if param.annotation is not inspect._empty else "Any"  # type: ignore[attr-defined]
        default = (
            f"= {param.default!r}" if param.default is not inspect._empty else ""
        )
        lines.append(f"- {name}: {annotation}{default}")
    return "\n".join(lines) if lines else "(无参数)"


def infer_returns(obj) -> str:
    if inspect.isclass(obj):
        return "实例化对象"
    try:
        sig = inspect.signature(obj)
        if sig.return_annotation is not inspect._empty:
            return str(sig.return_annotation)
    except Exception:  # noqa: BLE001
        pass
    return "<返回值说明占位>"


def module_to_example_subdir(module_path: str) -> Path:
    # Remove leading root package if present
    parts = module_path.split(".")
    # skip top-level 'HomeSystem' to keep shorter example paths
    if parts and parts[0] == "HomeSystem":
        parts = parts[1:]
    return EXAMPLES_DIR.joinpath(*parts)


def write_example(module_path: str, symbol: str, summary: str, params_text: str):
    subdir = module_to_example_subdir(module_path)
    subdir.mkdir(parents=True, exist_ok=True)
    example_file = subdir / f"{symbol.lower()}_example.py"
    if example_file.exists():
        print(f"[SKIP] 示例已存在: {example_file}")
        return example_file
    rel_import = module_path
    param_comment = indent(
        "\n".join(
            [
                "# 参数占位 (根据需要替换)",
                *[f"# {line}" for line in params_text.splitlines() if line],
            ]
        ),
        "    ",
    )
    code = f'''#!/usr/bin/env python3\n"""{symbol}: {summary}\n运行: python {example_file.relative_to(REPO_ROOT)}\n"""\nfrom {rel_import} import {symbol}\n\n\ndef main():\n{param_comment}\n    # TODO: 构造最小输入并调用\n    # result = {symbol}(...) if callable; or instance = {symbol}(...)\n    # print(result)\n    pass\n\n\nif __name__ == "__main__":\n    main()\n'''
    example_file.write_text(code, encoding="utf-8")
    print(f"[OK] 示例已创建: {example_file}")
    return example_file


def write_usage(symbol: str, summary: str, example_path: Path, params_text: str, returns: str):
    DOCS_EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    usage_file = DOCS_EXAMPLES_DIR / f"{symbol.lower()}-usage-v{today}.md"
    if usage_file.exists():
        print(f"[SKIP] usage 文档已存在: {usage_file}")
        return usage_file
    params_block = params_text if params_text else "(无参数)"
    content = USAGE_TEMPLATE.format(
        symbol=symbol,
        summary=summary,
        example_rel=example_path.relative_to(REPO_ROOT),
        params=params_block,
        returns=returns,
        today=today,
    )
    usage_file.write_text(content, encoding="utf-8")
    print(f"[OK] usage 文档已创建: {usage_file}")
    return usage_file


def main():
    args = parse_args()
    obj = import_symbol(args.module, args.symbol)
    params_text = build_param_lines(obj)
    returns = infer_returns(obj)
    example_path = write_example(args.module, args.symbol, args.summary, params_text)
    write_usage(args.symbol, args.summary, example_path, params_text, returns)
    print("[DONE] 生成完成。请补充示例的实际调用与参数说明，并在 docs/README.md 索引登记。")


if __name__ == "__main__":  # pragma: no cover
    main()
