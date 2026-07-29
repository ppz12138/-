# MHWilds 配装搜索器

怪物猎人荒野（Monster Hunter Wilds）自动配装搜索工具，使用向量化DFS算法实现毫秒级搜索。

## 文件结构

```
├── fast_search_v3.py      # 主搜索算法（向量化DFS + 系列优先搜索）
├── armors_cn.json         # 防具数据（简体中文）
├── charms_cn.json         # 可制作护石数据
├── decos_cn.json          # 珠子数据
├── my_charms.json         # 个人拥有护石数据
├── skills_data.json       # 技能定义数据
└── memory/                # AI记忆文件
    ├── user_profile.md        # 用户偏好
    └── project/
        ├── project_memory.md  # 项目约束和规则
        └── topics/            # 每日话题摘要
```

## 核心特性

- **系列优先搜索**：对紧凑的系列技能约束直接枚举有效组合，跳过常规DFS
- **向量化技能追踪**：用定长数组替代dict做技能累加，消除hash开销
- **精确赤字剪枝**：逐技能检查剩余部位能否提供，分数上限剪枝
- **武器孔位智能填充**：`_fill_weapon_slots_smart` 带缓存+上界预检查
- **追加技能查询**：降级线性搜索+可行性专用模式，2秒内完成全部追加技能评估

## 性能基准

| 指标 | 目标 | 实测 |
|------|------|------|
| 主搜索 | ≤20ms | 15ms（cached_ctx） |
| 追加技能 | ≤2s | 0.54s |
