---
name: travel-roadbook-cn
description: >
  国内旅行路书生成 Skill：小红书 MCP 检索高赞游记 + 高德 MCP 核对坐标/路线 + 免 Key 高德瓦片，
  产出单文件交互式路书 HTML（Leafet 地图、店铺卡、避雷、预算），可一键转 PDF 微信分发。
  前置问卷强制收齐旅游时间/预算/偏好（已答项跳过）。触发词：做路书、旅行计划、行程单、攻略整理、路书生成。
---

# 🧭 国内旅行路书 Skill（小红书 × 高德实战版）

把「查小红书攻略 → 整理行程 → 出可视化路书」固化为**可复现流水线**。以真实项目（潮汕 4 天 3 晚）调通全链路，全部工具免费：本地小红书 MCP 服务（无需 TikHub 付费 key）、高德官方 MCP（免费 key）、免 key 高德瓦片。

## 定位：与上游 Skill 的关系

| Skill | 定位 | 与本 Skill 关系 |
|-------|------|----------------|
| [huanyuzhilv/skills-travel-planner](https://github.com/huanyuzhilv/skills-travel-planner) | 商用交付级路书流水线（TikHub 付费 API + 飞猪） | 重型商用版；本 Skill 是其国内轻量替身——本地 MCP 免费替代 TikHub |
| [zyrobbie/travel-planner-skill](https://github.com/zyrobbie/travel-planner-skill) | 海外旅行规划 SOP（分档沟通/风险审计） | 方法论参考（问卷要素、风险核对口径与其对齐） |
| **本 Skill** | **国内实战版：小红书+高德 MCP → 单文件路书** | 零外部付费依赖，个人/小团队可直接跑 |

## 环境依赖

| 依赖 | 获取 | 坑 |
|------|------|-----|
| Python 3.10+，Pillow | `pip install pillow` | 无 PIL 也能跑（图不压缩） |
| [xiaohongshu-mcp](https://github.com/xpzouying/xiaohongshu-mcp) v2.5.5 | release 下载两个 exe 到 `~/bin/` | ⚠️ Defender 隔离 leakless.exe 必须先加排除；用前手动起服务（18060）；扫码登录 |
| 高德 MCP（可选） | `npx -y @amap/amap-maps-mcp-server` + [lbs.amap.com](https://lbs.amap.com) 免费 Web服务 Key | 用于 POI 坐标核对/驾车耗时/天气；没有也能出图（瓦片免 key） |
| Leaflet 1.9.4 | 已含于 `third_party/`（BSD-2-Clause） | 单文件内嵌，离线可用 |

完整安装步骤与注册配置见 [docs/TOOLCHAIN.md](docs/TOOLCHAIN.md)。

## 工作流（5 步，详见 docs/PIPELINE.md）

```text
第0步 问卷(INTAKE.md) → 第1步 检索 → 第2步 选品 → 第3步 生成 → 第4步 交付
```

### 第 0 步 · 问卷（强制前置）

按 [INTAKE.md](INTAKE.md) 收齐 6 要素：**旅游时间 / 出发地与大交通 / 预计花费 / 人员构成 / 路线偏好 / 饮食偏好与忌口**。
**用户提问时已给出的项直接采用，不重复追问**；未答项按默认假设走并在交付物中声明。
事实类信息（班次/票价/场次）一律标"待确认"，禁止假设。

### 第 1 步 · 检索（小红书 MCP）

```bash
python scripts/xhs_call.py login                                # 确认登录态
python scripts/xhs_call.py search "<目的地>攻略" s_trip.json    # 每方向 5-8 篇
```
关键词四类齐备：**攻略 / 美食 / 避雷 / 交通方式**（自驾加"环岛/路线"类词）。

### 第 2 步 · 选品 + 批量详情

人工挑高赞、近一年、对口的笔记 → 编辑 `batch_detail.py` 顶部清单 → `python scripts/batch_detail.py` → `digest.json + d_*.json`。
笔记结构：`data.note.desc`=正文（店铺清单在这）、`imageList[].urlDefault`=图直链（**图序≈正文店铺序**）。

### 第 3 步 · 生成

```bash
python scripts/build_roadbook.py --no-images                    # 先出无图版校对
python scripts/build_roadbook.py --date-range "…" --travelers "…" \
       --budget "…" --preferences "不走回头路;不吃生食"          # 完整版
```
产出：单文件 HTML（30 图 PIL 压缩 base64 内嵌 ≈4.8MB）+ 数据层 `tripData.json`。

### 第 4 步 · 交付

```bash
msedge --headless=new --no-pdf-header-footer --virtual-time-budget=30000 \
       --print-to-pdf="路书.pdf" "路书.html"
```
⚠️ **手机微信不渲染 html 附件，发微信一律用 PDF**（html 留电脑端用）。

## 数据与坐标规范（踩坑换来的）

1. **坐标格式**：行程点位存 `[名称, 经度, 纬度]`（GCJ-02，与高德天然对齐）；**喂 Leaflet 前必须换成 `[纬度, 经度]`**——首版潮汕路书 18 个标记全部画飞的真事故。
2. **免 key 瓦片**：`https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=8`（subdomains 1-4）。❌ `webrd0{s}`+裸 style=7 会 404；❌ OSM 瓦片国内不通。
3. **验收地图必须看标记点**，别只看瓦片是否加载（fitBounds 正常但标记全飞的症状很隐蔽）。
4. **图片下载**带 UA + Referer `https://www.xiaohongshu.com/`。
5. 换目的地只改 `build_roadbook.py` 顶部常量：`SHOPS` / `SCENIC` / `DAYS_MAP` / `TIMELINE`，不要手改 HTML 产物。

## 红线

- 笔记图片版权归原作者：**带图完整版仅限个人自用，不公开分发**；对外一律 `--no-images` 版
- `d_*.json / digest.json`（含 xsec_token、他人昵称）不进 git、不随交付物外发（.gitignore 已配）
- 小红书只读（搜索/阅读），不自动发评论发帖；同账号网页端单点登录会互踢
- 不代购代订；班次票价等动态信息标注"以官方为准"

## 安装为 Agent Skill

```bash
git clone https://gitee.com/<you>/travel-roadbook-cn.git ~/.agents/skills/travel-roadbook-cn
# 或复制本目录到 ~/.agents/skills/（ZCode 亦可用 ~/.zcode/skills/，技能名须 ASCII）
```
装完**新开会话**生效。宿主 Agent 按「工作流」章节编排，本仓库脚本即工具箱。
