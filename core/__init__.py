"""KKS Resource Manager 核心逻辑包。

设计约束（见 docs/ARCHITECTURE.md）：
- 本包与界面完全解耦，不 import PyQt6，可单独测试。
- 默认只读：扫描与解析绝不修改、移动、删除用户原始文件。
- 运行时零网络、零云 AI 依赖。
"""

__version__ = "0.15.0"
__phase__ = "Phase 1.5-B (Scan GUI)"
