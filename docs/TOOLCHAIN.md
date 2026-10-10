# 🧰 旅行路书工具链清单（skill + MCP + 脚本）

> 2026-10-10 盘点。用于换机重装与 GitHub 仓库 README 素材。所有下载地址均已核实（GitHub API / 官方 README），标注 ❓ 的表示待核实。

## 一、组件总览

| 组件 | 类型 | 作用 | 下载来源（已核实） | 本机位置 |
|------|------|------|-------------------|---------|
| xiaohongshu-mcp v2.5.5 | MCP 服务 | 小红书笔记搜索/详情/图片（search_feeds → get_feed_detail），内置浏览器自动登录 | **https://github.com/xpzouying/xiaohongshu-mcp**（16.2k⭐，Go+go-rod，Apache-2.0） | `~/bin/xiaohongshu-mcp.exe`（服务，监听 18060）+ `~/bin/xiaohongshu-login.exe`（扫码登录） |
| travel-planner | Agent Skill | 海外旅行规划 SOP（驴半半）：分档沟通、路线骨架、风险核对、H5+Excel 交付方法论 | **https://github.com/zyrobbie/travel-planner-skill**（v3.2.8，MIT） | `~/.agents/skills/travel-planner/` |
| travel-roadbook（skills-travel-planner） | Agent Skill | 商用路书生成流水线：行程 brief → tripData.json → HTML/PDF，小红书配图/文案 enrich，一键 deliver 脚本 | **https://github.com/huanyuzhilv/skills-travel-planner**（MIT，文档站 huanyuzhilv.github.io/skills-travel-planner） | `~/.agents/skills/travel-roadbook/` |
| 高德地图 MCP（官方） | MCP（stdio） | POI 搜索 / 驾车路线 / 地理编码 / 行政区 / 天气 / 测距 | npm 官方包 `@amap/amap-maps-mcp-server`（`npx -y` 拉起，无需下载安装）；**需先到 lbs.amap.com 申请免费 Web服务 Key** | 注册于 `~/.zcode/cli/config.json` → `mcp.servers.amap` |
| Leaflet 1.9.4 | 前端库（内嵌用） | 路书 HTML 的地图引擎（js+css 已下载内嵌进单文件 HTML） | https://unpkg.com/leaflet@1.9.4/dist/leaflet.js（或官网 leafletjs.com） | `sources/assets/leaflet.js` / `leaflet.css` |
| 潮汕三脚本 | Python 脚本（自研） | xhs_call.py（MCP 轻量客户端）/ batch_detail.py（批量拉详情）/ build_roadbook.py（出图解路书 HTML） | 本仓库 `scripts/`（自研可改造） | `sources/` |

> ⚠️ 勘误记录：备份包 README 曾把小红书 MCP 来源记为 `xiaochenchenhe/xiaohongshu-mcp`，经 GitHub API 核实该 repo 不存在，**正确出处为 xpzouying/xiaohongshu-mcp**（star 数与时间线吻合）。

## 二、MCP 注册配置（ZCode / 兼容 MCP 客户端）

合并进 `~/.zcode/cli/config.json` 的 `mcp.servers`（schema 严格，未知字段会被静默丢弃；注册后新会话生效）：

```json
{
  "xiaohongshu": {
    "type": "http",
    "url": "http://localhost:18060/mcp",
    "enabled": true,
    "timeoutMs": 60000
  },
  "amap": {
    "type": "stdio",
    "command": "npx",
    "args": ["-y", "@amap/amap-maps-mcp-server"],
    "env": { "AMAP_MAPS_API_KEY": "<lbs.amap.com 申请的 Web服务 Key>" },
    "enabled": true,
    "timeoutMs": 60000
  }
}
```

注册后工具名：`mcp__xiaohongshu__*`（search_feeds / get_feed_detail…）、`mcp__amap__*`（maps_text_search / maps_geo / maps_direction_driving / maps_weather…）。

## 三、安装与使用要点（按坑排序）

1. **Defender 排除（最大的坑）**：go-rod 的 leakless.exe 每次解压到 `%TEMP%\leakless-amd64-*\` 被 Defender 静默隔离 → login/mcp 双 panic "file contains a virus"。解法=管理员 PowerShell 加排除（ExclusionProcess `leakless.exe` + ExclusionPath 两个 exe、xiaohongshu-mcp 目录、整个 Temp），ps1 脚本在备份包 `01-服务端-xiaohongshu-mcp/`。
2. **小红书 MCP 不自启**：用前先后台运行 `~/bin/xiaohongshu-mcp.exe`；首次自动下载 150MB 内置浏览器到 `AppData\Local\xiaohongshu-mcp\browser\`；登录用 `xiaohongshu-login.exe` 扫码。
3. **账号红线**：同账号网页端单点登录（MCP 登了别处网页会互踢，手机 App 不受影响）；cookies 过期重跑 login；只搜索/阅读，勿自动发评论发帖。
4. **高德 MCP 要 Key**：lbs.amap.com 开放平台 → 控制台 → 创建应用 → 添加 Key(Web服务) → 填入 env。免 Key 的替代只有"静态瓦片"（见第 6 条）。
5. **Skill 安装**：复制到 `~/.agents/skills/`，新会话生效；ZCode 启动时扫描，中途装的当会话看不到。
6. **免 Key 地图瓦片**（build_roadbook.py 方案）：`https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=8`（subdomains 1-4，GCJ-02 坐标天然对齐）；❌ `webrd0{s}`+裸 `style=7` 会 404；❌ tile.openstreetmap.org 国内不通。
7. **Leaflet 坐标顺序**：一律 `[纬度, 经度]`；自存点位若是 `[名称, 经度, 纬度]` 必须换序再喂（潮汕路书首版标记全飞的真实事故）。
8. **Python 侧**：Git Bash `/tmp` 对 Python 不可见，输出用显式 Windows 路径；图片下载带 UA+Referer（`https://www.xiaohongshu.com/`）；search_feeds 偶发超时换短词重试。

## 四、检索数据结构速查

笔记详情 JSON 在 `data.note`：
- `desc`：正文（店铺清单/图注就在这里，"P1/P2" 可对应 imageList 下标）
- `imageList[].urlDefault`：webp 直链（带签名，配 UA+Referer 可直接下载；**图序≈正文店铺序**）

## 五、离线备份包

`02-学习/99-网盘中转/小红书工具链-2026-10-09.zip`（11.6MB / 117 文件）：两个 exe + Defender 排除 ps1 + 两个 skill 完整目录 + 潮汕三脚本 + 注册片段 + 换机安装 README。换机重装优先用它，不必重走 GitHub 下载。（⚠️ 本清单已勘误其 repo 名错误）

## 六、生成链全景

```
小红书 MCP (search_feeds → 笔记短list)
   → batch_detail.py (get_feed_detail → 13篇详情 JSON)
   → 人工选品（高赞/对口）
   → build_roadbook.py (店铺/景点卡片 + Leaflet 地图 + 避雷 + 预算 → 单文件 HTML，图片 PIL 压缩 base64 内嵌)
   → [可选] Edge headless --print-to-pdf 出 PDF（手机微信可看；html 附件微信不预览）
```
