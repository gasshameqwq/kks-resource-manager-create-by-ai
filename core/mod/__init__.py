"""MOD 索引与依赖关系层（Phase 2 实现）。

职责：
- 扫描 ``.zipmod`` / ``.zip``，读取内部 ``manifest.xml`` 建立 GUID 索引。
- 提取 GUID / name / author / version / description / website / game。
- 从角色卡 KKEx 块提取 ``ModID`` 依赖（含未安装的 GUID）。
- 计算「已安装 / 缺失」，并支持反向查询（MOD → 被哪些卡使用）。

复用参考：KKTools ``core/mod_index.py``（MIT）。
设计参考：KKCardModCheck —— 其 ``manifest.xml`` 可能是 UTF-16 或含多余闭合标签，
读取时需要做编码探测与容错修补。
"""

__all__: list[str] = []
