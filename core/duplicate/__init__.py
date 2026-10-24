"""Byte-duplicate 资源分组层。

重复关系完全由既有 ``resources.sha256`` **只读派生**：同一 SHA-256
仅表示文件原始字节完全相同，不代表同角色、同 MOD 或逻辑内容等价。

安全约束：

- **永不自动删除**任何卡片或 MOD；
- 不写入 ``duplicate_groups`` / ``duplicate_members``，两张预留表保持零写入；
- 不读取或写入已废弃、未使用的 ``content_key``。
"""

__all__: list[str] = []
