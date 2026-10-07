"""分类与识别层（Phase 1 起实现，Phase 3 扩展）。

识别优先级（规范 §22）：
- Level 1 格式可靠识别：KKS/KK 角色卡、服装卡、场景卡 header marker。
- Level 2 MOD metadata：``manifest.xml`` 的 GUID / name / author。
- Level 3 路径与文件名推断：**只作为候选信息，绝不当作事实**。
- Level 4 未知：``unknown``，标记 ``needs_review=1`` 交给用户确认。

约束：运行时禁止调用任何云端 AI / API 做基础分类。
"""

__all__: list[str] = []
