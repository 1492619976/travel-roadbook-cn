# travel-roadbook-c · 国内旅行路书 Skill

> **小红书 MCP 检索 × 高德地图免 Key 瓦片 × 单文件交互式路书**——面向国内自由行的 Agent Skill。
> 把「查小红书攻略 → 问卷收需求 → 整理行程 → 出路书 HTML/PDF」固化成可复现流水线，零付费 API 依赖。
> 附真实实战示例：[潮汕 4 天 3 晚 · 不走回头路](example/潮汕路书-示例无图版.html)。

[English](#english)

## ✨ 这个 Skill 干什么

1. **问卷前置**（[INTAKE.md](INTAKE.md)）：旅游时间 / 预算 / 人员 / 路线偏好（如"不走回头路"）/ 饮食忌口（如"不吃生食"）——已答项跳过，未答项按声明的默认假设走
2. **小红书检索**：本地 [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) 服务拉高赞游记（攻略/美食/避雷/交通四类关键词）
3. **结构化选品**：批量详情 → 店铺/景点/避雷/价格口径落成 `tripData.json` 数据层
4. **生成交付**：单文件路书 HTML（Leaflet 路线地图 + 店铺卡 + 高德导航链接 + 预算表），一键转 PDF 微信分发

```text
问卷 → 检索 → 选品 → 生成 → PDF
```

## 📦 安装

```bash
# 作为 Agent Skill（ZCode / Claude Code / Cursor 等支持 skills 目录的宿主）
git clone https://gitee.com/paul-sun/travel-roadbook-c.git ~/.agents/skills/travel-roadbook-c

# 依赖
pip install pillow
# 小红书 MCP + 高德 MCP 安装与坑清单（Defender 排除！）：docs/TOOLCHAIN.md
```

装完新开会话生效；宿主按 [SKILL.md](SKILL.md) 的工作流编排。

## 🧰 工具链（全部免费）

| 组件 | 作用 | 来源 |
|------|------|------|
| xiaohongshu-mcp | 小红书笔记搜索/详情/图片 | [xpzouying/xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp)（16k+⭐，Apache-2.0） |
| 高德 MCP | POI 坐标核对 / 驾车路线 / 天气 | 官方 `@amap/amap-maps-mcp-server` + [lbs.amap.com](https://lbs.amap.com) 免费 Key |
| 高德瓦片 | 路书地图底图 | **免 Key**：`wprd0{s}...style=8`（GCJ-02） |
| Leaflet 1.9.4 | 地图引擎（内嵌） | [third_party/](third_party/)，BSD-2-Clause |

> 上游同类型 Skill：[huanyuzhilv/skills-travel-planner](https://github.com/huanyuzhilv/skills-travel-planner)（商用级，走付费 TikHub）、[zyrobbie/travel-planner-skill](https://github.com/zyrobbie/travel-planner-skill)（海外 SOP）。本 Skill = 国内免费轻量实战版。

## 📁 目录

```
travel-roadbook-c/
├── SKILL.md                # ← Skill 主体：工作流/规范/红线（宿主 Agent 读这个）
├── INTAKE.md               # 前置问卷模板（6 要素）
├── scripts/
│   ├── xhs_call.py         # 小红书 MCP 轻量客户端（login/search/detail）
│   ├── batch_detail.py     # 批量笔记详情 → digest.json
│   └── build_roadbook.py   # 路书生成器（--no-images / --date-range 等参数）
├── example/                # 实战示例：潮汕 4 天 3 晚（无图版 + 脱敏数据层）
├── docs/
│   ├── TOOLCHAIN.md        # 工具链清单：下载地址/安装坑/注册配置（均已实测核实）
│   └── PIPELINE.md         # 生成链全景 + 踩坑速查
└── third_party/            # Leaflet 1.9.4
```

## 🚀 快速开始

```bash
# 零依赖体验：无图示例（验证环境）
python scripts/build_roadbook.py --no-images

# 完整流程（小红书 MCP 服务已启动，见 docs/TOOLCHAIN.md）
python scripts/xhs_call.py search "潮州美食攻略" s_cz.json
python scripts/batch_detail.py                       # 选品后批量拉详情
python scripts/build_roadbook.py \
  --date-range "2026-11-11 ~ 11-14" --travelers "2大1小" \
  --budget "人均3000" --preferences "不走回头路;不吃生食"

# 转 PDF（发微信用 PDF，手机微信不渲染 html 附件）
msedge --headless=new --no-pdf-header-footer --virtual-time-budget=30000 \
       --print-to-pdf="路书.pdf" "路书.html"
```

**换目的地**：改 `scripts/build_roadbook.py` 顶部常量（`SHOPS`/`SCENIC`/`DAYS_MAP`/`TIMELINE`），流程不变。

## 🔍 实战示例：潮汕 4 天 3 晚

- 打开 [example/潮汕路书-示例无图版.html](example/潮汕路书-示例无图版.html)：四色路线地图（18 编号点）、23 家店卡片、避雷清单、预算表
- 真实数据源：13 篇小红书高赞笔记（2026-10 检索）；完整版含 30 张实拍图内嵌（版权原因本仓库只放无图版）
- 数据层：[example/tripData.example.json](example/tripData.example.json)（已脱敏）

## ⚠️ 版权与合规

- 笔记内容整理自小红书公开笔记，图片与原文版权归原作者；**带图完整版仅限个人自用，不公开分发**
- 检索产物（`d_*.json`/`digest.json`，含 xsec_token）不进 git 不外发（.gitignore 已配）
- 小红书只读使用；请勿自动评论/发帖
- 本仓库 MIT（[LICENSE](LICENSE)）；`third_party/` Leaflet 遵循 BSD-2-Clause

---

# English

**travel-roadbook-c** — an agent skill for domestic-China travel roadbooks. Pipeline: intake questionnaire (dates/budget/preferences) → Xiaohongshu notes retrieval via a local [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) service → structured `tripData.json` → single-file interactive HTML roadbook (Leaflet + keyless AMap tiles, shop cards, navigation links, budget table) → PDF for WeChat sharing. Zero paid-API dependencies. Ships a real 4-day Chaoshan trip as the worked example (image-free version for copyright reasons). See [SKILL.md](SKILL.md), [docs/TOOLCHAIN.md](docs/TOOLCHAIN.md), [docs/PIPELINE.md](docs/PIPELINE.md).
