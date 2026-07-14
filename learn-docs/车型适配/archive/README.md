# 归档文档说明

本目录存放**已过时或被取代**的早期分析文档，保留作历史参考。
当前有效文档见上级目录 `车型适配/` 及 `learn-docs/README.md` 索引。

## 归档原因

早期（2026-01）探索的是「为速腾添加专属车型定义」的移植路线：
在 opendbc `values.py` / `fingerprints.py` / `interface.py` 中新增
`VOLKSWAGEN_SAGITAR_MK8`，配合 `dashcamOnly` 与手写 CAN 补丁。

后续实践（2026-07）改用更简单可靠的路线，并经实车抓包验证：
- **代理指纹**：直接 `FINGERPRINT=VOLKSWAGEN_GOLF_MK7`（同 MQB 平台），
  无需新增车型定义。
- **进入 onroad**：`FORCE_ONROAD`（无 panda 平台），而非 dashcamOnly 补丁。
- **CAN 解析**：实测 `vw_mqb.dbc` 直接可用，车速/方向盘/档位全部可获取，
  无需生成专用 DBC（见 `../大众速腾CAN抓包解析报告.md`）。

因此早期文档的具体方案、命名（SAGITAR_MK8 实为 MK7.5）、以及靠猜测填写的
CAN 信号映射均已不适用。

## 归档清单

| 文档 | 原因 | 被取代为 |
|------|------|---------|
| 大众速腾车型适配可行性文档.md | SAGITAR_MK8 专属车型补丁路线；平台分析部分仍有参考价值 | `../第二阶段_接入CAN可行性评估.md` |
| 大众速腾车型适配总结报告.md | 描述 sagitar_adapter/patches 补丁方案；CAN 映射为未验证猜测 | `../大众速腾CAN抓包解析报告.md` |
| 大众速腾车型适配代码示例.md | SAGITAR_MK8 补丁代码模板；实际未采用此路线 | `../openpilot_车型加载逻辑分析.md`（机制参考）|
| 下一步开发路线.md | 历史过程记录：卡点已解决、方案已实施、"从抓包生成 DBC"被"直接用 vw_mqb.dbc"取代 | `../Orin_NX_部署指南.md`、`../大众速腾CAN抓包解析报告.md` |
| Orin_NX_验证任务清单.md | 2026-07-10 断网续接的临时任务清单，10 项任务已于 2026-07-14 全部完成（非因方案被取代而归档，是任务已结清）| `../../环境搭建与容器部署.md` 第十七节（软件自动曝光实机验证结论汇总）|

## 注意

关联的早期代码（若存在）`tools/vw/sagitar_adapter.py`、`sagitar_patches/`
同属此路线，未在实际部署中采用；当前 CAN 分析工具见 `tools/vw/can_analysis/`。
