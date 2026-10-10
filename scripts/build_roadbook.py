# -*- coding: utf-8 -*-
"""潮汕 4天3晚 路书生成器（GitHub 仓库版）

从本目录（scripts/）的检索数据生成单文件路书 HTML：
1. digest.json / d_*.json 取笔记与图片（完整模式，需先跑 xhs_call.py + batch_detail.py）
2. 下载选定图片 -> PIL 压缩 -> base64 内嵌
3. 产出 tripData.json + 单文件 HTML（Leaflet+高德免key瓦片地图、店铺卡、避雷、预算）

用法：
  python build_roadbook.py                # 完整模式（需要 scripts/digest.json 与 d_*.json）
  python build_roadbook.py --no-images    # 示例模式：无图占位、笔记链接脱敏，无需检索数据

坐标系提醒：点位数据是 [名称, 经度, 纬度]，Leaflet 一律 [纬度, 经度]（本脚本已换序）。
"""
import argparse
import base64
import subprocess
import io
import json
import os
import urllib.parse
import urllib.request

SRC = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(SRC)
THIRD_PARTY = os.path.join(REPO, "third_party")
OUT_DIR = os.path.join(REPO, "example", "generated")
IMG_CACHE = os.path.join(SRC, "assets")
os.makedirs(OUT_DIR, exist_ok=True)
os.makedirs(IMG_CACHE, exist_ok=True)

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
      "Referer": "https://www.xiaohongshu.com/"}

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

parser = argparse.ArgumentParser(description="潮汕路书生成器")
parser.add_argument("--no-images", action="store_true",
                    help="示例模式：不下载图片（占位块），笔记链接脱敏为纯文本，无需 digest.json")
# ---- intake 问卷参数（docs/PIPELINE.md 第 0 步；已回答哪项就填哪项，未填回落到默认值）----
parser.add_argument("--date-range", default=None, help="旅游时间，如 '2026-11-06 ~ 11-09'")
parser.add_argument("--budget", default=None, help="预计花费，如 '人均 3000'")
parser.add_argument("--travelers", default=None, help="人员构成，如 '2大1小(6岁)'")
parser.add_argument("--preferences", default=None, help="用户偏好，如 '不走回头路;不吃生食;节奏松弛'")
args = parser.parse_args()
NO_IMAGES = args.no_images

# ---------- 1. 笔记登记表（完整模式；--no-images 时可为空） ----------
NOTES = {}
digest_path = os.path.join(SRC, "digest.json")
if os.path.exists(digest_path):
    digest = json.load(open(digest_path, encoding="utf-8"))
    for n in digest:
        key = os.path.splitext(n["file"])[0]
        NOTES[key] = {
            "title": n["title"], "likes": n["likes"], "nickname": n["nickname"],
            "url": f"https://www.xiaohongshu.com/explore/{n['note_id']}?xsec_token={n['xsec_token']}",
        }
elif not NO_IMAGES:
    raise SystemExit("缺少 scripts/digest.json：请先按 docs/PIPELINE.md 跑检索，或加 --no-images 出示例版")

def note_ref(key):
    if key in NOTES:
        n = NOTES[key]
        return f'<a class="src" href="{n["url"]}" target="_blank">小红书原文《{n["title"]}》（{n["likes"]}赞）</a>'
    return '<span class="src">小红书高赞笔记（示例脱敏，未附链接）</span>'

def amap_link(kw, city):
    q = urllib.parse.quote(f"{kw} {city}")
    return f"https://uri.amap.com/search?keyword={q}&src=chaoshan_roadbook"

# ---------- 2. 图片清单 (asset_key, 笔记文件, 图序号) ----------
IMG_SPEC = [
    ("cz_niupai",   "d_chaozhou_food2", 0),
    ("cz_lu_e",     "d_chaozhou_food2", 1),
    ("cz_yusheng",  "d_chaozhou_food2", 4),
    ("cz_jichi",    "d_chaozhou_food2", 5),
    ("cz_zhou",     "d_chaozhou_food2", 3),
    ("cz_dabiao",   "d_chaozhou_food1", 0),
    ("na_haoli",    "d_nanao_loop", 8),
    ("na_shatamian","d_nanao_loop", 10),
    ("na_fansha",   "d_nanao_loop", 11),
    ("na_ranji",    "d_nanao_food2", 4),
    ("na_shengyan", "d_nanao_food2", 5),
    ("na_laopai",   "d_nanao_food2", 0),
    ("st_wuzhou",   "d_shantou_food1", 0),
    ("st_ruijiao",  "d_shantou_food1", 1),
    ("st_yuce",     "d_shantou_food1", 2),
    ("st_buyezhou", "d_shantou_food1", 3),
    ("st_longxiang","d_shantou_food1", 5),
    ("st_xinghua",  "d_shantou_food2", 2),
    ("st_gancao",   "d_shantou_food2", 7),
    ("st_doujiang", "d_shantou_food2", 5),
    ("st_lu_e",     "d_shantou_food2", 6),
    ("st_changfen", "d_shantou_food2", 4),
    ("st_caodadan", "d_shantou_food2", 8),
    ("sp_changshan",  "d_nanao_loop2", 1),
    ("sp_qianaowan",  "d_nanao_loop2", 2),
    ("sp_fengche",    "d_nanao_loop2", 5),
    ("sp_caihong",    "d_nanao_loop2", 6),
    ("sp_qingao",     "d_nanao_loop2", 10),
    ("sp_guangjiqiao","d_chaozhou_noback", 2),
    ("sp_kaiyuansi",  "d_chaozhou_noback", 0),
]

def load_img_url(note_file, idx):
    d = json.load(open(os.path.join(SRC, note_file + ".json"), encoding="utf-8"))
    im = (d["data"]["note"].get("imageList") or [])[idx]
    return im.get("urlDefault") or im.get("url")

def fetch_b64(asset_key, note_file, idx):
    """下载 -> 压缩 -> data uri；失败返回空串（卡片自动降级为无图）。"""
    cache = os.path.join(IMG_CACHE, asset_key + ".bin")
    if not os.path.exists(cache) or os.path.getsize(cache) < 1000:
        url = load_img_url(note_file, idx)
        req = urllib.request.Request(url, headers=UA)
        data = urllib.request.urlopen(req, timeout=60).read()
        open(cache, "wb").write(data)
    else:
        data = open(cache, "rb").read()
    if HAS_PIL:
        try:
            im = Image.open(io.BytesIO(data)).convert("RGB")
            w, h = im.size
            if w > 680:
                im = im.resize((680, int(h * 680 / w)), Image.LANCZOS)
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=74)
            data = buf.getvalue()
            mime = "image/jpeg"
        except Exception:
            mime = "image/webp"
    else:
        mime = "image/webp"
    return "data:" + mime + ";base64," + base64.b64encode(data).decode("ascii")

print("下载/内嵌图片 ..." if not NO_IMAGES else "示例模式：跳过图片下载", HAS_PIL and "(PIL 压缩)" or "(原样 webp)")
IMG = {}
fail = []
for key, nf, idx in IMG_SPEC:
    if NO_IMAGES:
        IMG[key] = ""
        continue
    try:
        IMG[key] = fetch_b64(key, nf, idx)
        print("  ok", key, len(IMG[key]) // 1024, "KB(b64)")
    except Exception as e:
        IMG[key] = ""
        fail.append(key)
        print("  FAIL", key, e)

def img_html_for(name):
    img = IMG.get("", "")  # placeholder logic below
    if NO_IMAGES:
        return f'<div class="noimg">📷 占位图 · 完整模式下这里是小红书实拍<br><b>{name}</b></div>'
    return None  # 完整模式在 card 函数里按 IMG[key] 处理

# ---------- 3. 店铺卡片 ----------
SHOPS = [
    ("潮州", "府城兴潮牛坊", "人均未标", "本地人私藏清单第 1 家，牛肉火锅老店", "cz_niupai", "府城兴潮牛坊", "d_chaozhou_food2"),
    ("潮州", "官塘兄弟牛肉·总店", "人均未标", "10 点前到肉最全、鲜牛肉丸必点；两篇笔记评价「肉嫩但不惊艳」，备选：生记官塘牛肉", "cz_dabiao", "官塘兄弟牛肉", "d_zijia_route"),
    ("潮州", "府城雷记卤鹅", "人均未标", "潮州卤鹅老字号，狮头鹅香浓", "cz_lu_e", "府城雷记卤鹅", "d_chaozhou_food2"),
    ("潮州", "锋记鱼生", "人均未标", "潮州特色鱼生，配香油豉油十小碟", "cz_yusheng", "锋记鱼生", "d_chaozhou_food2"),
    ("潮州", "潮涂记腐乳鸡翅", "人均未标", "腐乳腌制现炸，古城边走边吃", "cz_jichi", "潮涂记腐乳鸡翅", "d_chaozhou_food2"),
    ("潮州", "潮之锐记砂锅粥", "人均未标", "深夜砂锅粥；同款必吃还有「阿荣砂锅粥」", "cz_zhou", "锐记砂锅粥 潮州", "d_chaozhou_food2"),
    ("南澳", "浩利食店", "人均 40+", "苍蝇馆子，千字攻略作者「南澳吃的最好吃的一顿」", "na_haoli", "浩利食店 南澳", "d_nanao_loop"),
    ("南澳", "黄记沙爹面", "人均 30+", "海鲜沙爹面入味，比厦门的好吃（笔记原话）", "na_shatamian", "黄记沙嗲面 南澳", "d_nanao_loop"),
    ("南澳", "然记糖水铺（后宅总店）", "人均 20", "岛上甜品补给，绿豆冰沙同款", "na_ranji", "然记糖水铺 南澳", "d_nanao_food2"),
    ("南澳", "然孖生腌·本港海鲜", "人均未标", "本港生腌，胆大者冲", "na_shengyan", "然孖生腌 南澳", "d_nanao_food2"),
    ("南澳", "老牌·海鲜家烧·沙嗲面", "人均未标", "后宅镇正餐备选，出岛前顺路", "na_laopai", "老牌海鲜家烧沙嗲面 南澳", "d_nanao_food2"),
    ("南澳", "兴兴反沙", "15 元/份", "反沙芋头好吃但量小价高（笔记吐槽点）", "na_fansha", "兴兴反沙 南澳", "d_nanao_loop"),
    ("汕头", "五洲牛肉馆", "人均未标", "12 顿测评第一站「二刷挚爱，11 点到店包场，现切牛肉新鲜到极致」", "st_wuzhou", "五洲牛肉馆 汕头", "d_shantou_food1"),
    ("汕头", "杏花吴记牛肉火锅", "人均 120", "20 家店清单里的必打卡牛肉火锅（要排队，错峰）", "st_xinghua", "杏花吴记牛肉火锅", "d_shantou_food2"),
    ("汕头", "瑞娇嫲嫲生腌", "人均 50", "生蚝自带海水清甜、膏蟹顶级；白粥配生腌", "st_ruijiao", "瑞娇嫲嫲 汕头", "d_shantou_food1"),
    ("汕头", "金砂阿洲鱼册店", "人均未标", "鱼册 Q 弹圈粉，芦鳗蘸酸梅酱鲜到眯眼", "st_yuce", "金砂阿洲鱼册店", "d_shantou_food1"),
    ("汕头", "双生不夜粥", "人均未标", "深夜食堂，22 点后去不用排队；酸菜东星斑「天花板」", "st_buyezhou", "双生不夜粥 汕头", "d_shantou_food1"),
    ("汕头", "龙香酒家", "人均未标", "鸽吞翅、鹅头、鱼头羹招牌", "st_longxiang", "龙香酒家 汕头", "d_shantou_food1"),
    ("汕头", "阿群甘草水果", "人均 30", "甘草梅粉腌水果，饭后解腻神器", "st_gancao", "阿群甘草水果 汕头", "d_shantou_food2"),
    ("汕头", "老牌福记加浓豆浆", "人均 15", "早餐豆浆 + 油条，加姜薯更地道", "st_doujiang", "福记加浓豆浆 汕头", "d_shantou_food2"),
    ("汕头", "陶家功夫卤鹅", "人均 30", "汕头卤鹅代表，斩盘配白饭", "st_lu_e", "陶家功夫卤鹅", "d_shantou_food2"),
    ("汕头", "小吴肠粉", "人均 10", "评价两极：一篇力荐一篇失望，人多需排队，抱着平常心", "st_changfen", "小吴肠粉 汕头", "d_shantou_food2"),
    ("汕头", "蔡大胆牛肉海鲜捞面", "人均 25", "龙眼南路夜宵街，捞面加海鲜双拼", "st_caodadan", "蔡大胆牛肉海鲜捞面", "d_shantou_food2"),
]

def card_img(img_key, name):
    if NO_IMAGES:
        return f'<div class="noimg">📷 占位图 · 完整模式嵌入小红书实拍<br><b>{name}</b></div>'
    img = IMG.get(img_key, "")
    if img:
        return f'<img src="{img}" alt="{name}">'
    return '<div class="noimg">图源失效</div>'

def shop_card(city, name, price, blurb, img_key, amap_kw, note_key):
    return (
        '<div class="card shop">'
        f'<div class="card-img">{card_img(img_key, name)}<span class="city-tag c-{city}">{city}</span></div>'
        '<div class="card-body">'
        f'<div class="shop-head"><h4>{name}</h4><span class="price">{price}</span></div>'
        f'<p>{blurb}</p>'
        f'<div class="card-foot"><a class="nav" href="{amap_link(amap_kw, city)}" target="_blank">🧭 高德导航</a>'
        f'{note_ref(note_key)}</div>'
        '</div></div>'
    )

CITY_ORDER = ["潮州", "南澳", "汕头"]
shop_sections = []
for c in CITY_ORDER:
    cards = "".join(shop_card(*s) for s in SHOPS if s[0] == c)
    shop_sections.append(f'<h3 class="city-h {c}">🍜 {c} · {sum(1 for s in SHOPS if s[0]==c)} 家</h3>'
                         f'<div class="grid">{cards}</div>')
SHOP_HTML = "".join(shop_sections)

# ---------- 4. 景点卡片 ----------
SCENIC = [
    ("广济桥 · 过河拆桥 + 灯光秀", "¥20 上桥 / 灯光秀岸边免费", "17:30 蹲「过河拆桥」，20:00 灯光秀（周五—周日加 21:30 场）；滨江长廊拍全景机位", "sp_guangjiqiao", "广济桥 潮州", "d_chaozhou_noback", "笔记配图"),
    ("开元寺", "免费", "唐代古刹，屋顶嵌瓷；避开 12:00–13:00 午休闭馆", "sp_kaiyuansi", "开元寺 潮州", "d_chaozhou_noback", "笔记配图"),
    ("长山尾灯塔", "停车 ¥10", "红塔与南澳大桥同框，日落最佳", "sp_changshan", "长山尾灯塔 南澳", "d_nanao_loop2", "图二"),
    ("钱澳湾灯塔", "路边停车", "米白灯塔立在海边栈桥上，电影感", "sp_qianaowan", "钱澳湾灯塔 南澳", "d_nanao_loop2", "图三"),
    ("蛴仔澎风车山", "导航「19 号风车」", "开车上山看海岸线全貌，日落备选地人少", "sp_fengche", "蛴仔澎 南澳", "d_nanao_loop2", "图六"),
    ("彩虹码头", "免费", "日落前海面彩色、日落时金黄", "sp_caihong", "彩虹码头 南澳", "d_nanao_loop2", "图七"),
    ("青澳湾 · 自然之门", "免费", "住岛上清晨下楼看日出，北回归线标志顺路打卡", "sp_qingao", "青澳湾 南澳", "d_nanao_loop2", "图十一"),
]

def scenic_card(name, price, blurb, img_key, amap_kw, note_key, cap):
    return (
        '<div class="card scenic">'
        f'<div class="card-img">{card_img(img_key, name)}<span class="cap">{cap}</span></div>'
        '<div class="card-body">'
        f'<div class="shop-head"><h4>{name}</h4><span class="price">{price}</span></div>'
        f'<p>{blurb}</p>'
        f'<div class="card-foot"><a class="nav" href="{amap_link(amap_kw, "")}" target="_blank">🧭 高德导航</a>'
        f'{note_ref(note_key)}</div>'
        '</div></div>'
    )

SCENIC_HTML = '<div class="grid">' + "".join(scenic_card(*s) for s in SCENIC) + "</div>"

# ---------- 5. 地图数据 ----------
# GCJ-02 大致坐标（示意图，导航以卡片高德链接为准）
DAYS_MAP = [
    {"day": "D1", "color": "#ff8c42", "pts": [
        ["潮汕站（租车）", 116.5563, 23.4657], ["潮州古城·牌坊街", 116.6335, 23.6618], ["广济桥", 116.6442, 23.6640]]},
    {"day": "D2", "color": "#2e9e6b", "pts": [
        ["官塘·牛肉火锅", 116.7230, 23.6320], ["南澳大桥 ¥96", 116.9050, 23.4280], ["长山尾灯塔", 116.9860, 23.4130],
        ["钱澳湾灯塔", 117.0270, 23.3620], ["云澳·三囱崖", 117.1300, 23.3700], ["青澳湾（住）", 117.1650, 23.3230],
        ["蛴仔澎风车山·日落", 117.1460, 23.2900]]},
    {"day": "D3", "color": "#2f6fed", "pts": [
        ["竹栖渡湾", 117.1120, 23.3780], ["深澳·总兵府", 117.0740, 23.4370], ["雄镇关", 117.0480, 23.3860],
        ["后宅镇（早午餐）", 117.0230, 23.4250], ["汕头·西堤公园停车", 116.6880, 23.3480], ["小公园", 116.6940, 23.3520],
        ["万象城·龙眼南路（住）", 116.7180, 23.3570]]},
    {"day": "D4", "color": "#9b59d0", "pts": [
        ["汕头站（还车·返程）", 116.7570, 23.3680]]},
]
chain = [[lat, lng] for d in DAYS_MAP for name, lng, lat in d["pts"]]
MAPDATA_JSON = json.dumps({"days": DAYS_MAP, "chain": chain}, ensure_ascii=False)

# ---------- 5.5 静态高清地图（仅打印/PDF 用；HTML 屏幕端仍是交互地图） ----------
MAP_ONLY_HTML = """<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8">
<link rel="stylesheet" href="leaflet.css">
<style>
html,body{margin:0;padding:0;height:100%;overflow:hidden;background:#eef}
#map{position:absolute;inset:0}
.legend{position:absolute;z-index:500;top:14px;right:14px;background:rgba(255,255,255,.94);
  border-radius:12px;padding:12px 16px;font:15px/2 "Microsoft YaHei",sans-serif;
  box-shadow:0 2px 10px rgba(0,0,0,.2)}
.legend span{display:flex;align-items:center;gap:8px}
.dot{width:15px;height:15px;border-radius:50%;display:inline-block}
</style></head><body>
<div id="map"></div>
<div class="legend">
  <span><i class="dot" style="background:#ff8c42"></i>D1 潮州古城</span>
  <span><i class="dot" style="background:#2e9e6b"></i>D2 南线进岛</span>
  <span><i class="dot" style="background:#2f6fed"></i>D3 北线出岛→汕头</span>
  <span><i class="dot" style="background:#9b59d0"></i>D4 返程</span>
</div>
<script src="leaflet.js"></script>
<script>
var DATA = __MAPDATA__;
var map = L.map('map', {zoomControl: false, scrollWheelZoom: false, attributionControl: true});
L.tileLayer('https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=8', {
  subdomains: ['1','2','3','4'], maxZoom: 18, attribution: '高德瓦片'
}).addTo(map);
var seq = 0;
DATA.days.forEach(function(d){
  var line = d.pts.map(function(p){ return [p[2], p[1]]; });
  L.polyline(line, {color: d.color, weight: 7, opacity: .9}).addTo(map);
  d.pts.forEach(function(p){
    seq++;
    L.circleMarker([p[2], p[1]], {radius: 17, color: '#fff', weight: 4, fillColor: d.color, fillOpacity: 1})
      .addTo(map).bindTooltip(String(seq), {permanent: true, direction: 'center', className: 'num-tip'});
  });
});
map.fitBounds(L.latLngBounds(DATA.chain).pad(0.07));
document.head.insertAdjacentHTML('beforeend',
  '<style>.num-tip{background:none;border:none;box-shadow:none;color:#fff;font-weight:800;font-size:16px;padding:0}'
  + '.leaflet-control-attribution{font-size:13px}</style>');
</script></body></html>
"""

STATIC_MAP_B64 = ""
MAPMODE = "no-static"
try:
    tmp_html = os.path.join(THIRD_PARTY, "_map_static.html")
    with open(tmp_html, "w", encoding="utf-8") as f:
        f.write(MAP_ONLY_HTML.replace("__MAPDATA__", MAPDATA_JSON))
    png_path = os.path.join(THIRD_PARTY, "_map_static.png")
    if os.path.exists(png_path):
        os.remove(png_path)
    subprocess.run([EDGE, "--headless=new", "--disable-gpu",
                    "--window-size=2000,1400", "--virtual-time-budget=30000",
                    f"--screenshot={png_path}", tmp_html],
                   capture_output=True, timeout=180)
    if os.path.exists(png_path) and os.path.getsize(png_path) > 50000:
        if HAS_PIL:
            im = Image.open(png_path).convert("RGB")
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=88)
            data = buf.getvalue()
        else:
            data = open(png_path, "rb").read()
        STATIC_MAP_B64 = "data:image/jpeg;base64," + base64.b64encode(data).decode("ascii")
        MAPMODE = "has-static"
        print("static map OK:", len(data) // 1024, "KB")
    else:
        print("static map FAILED: screenshot missing/too small")
    os.remove(tmp_html)
except Exception as e:
    print("static map FAILED:", e)

MAP_PRINT_DIV = (f'<div id="map-print"><img src="{STATIC_MAP_B64}" alt="路线图（高清印刷版）"></div>'
                 if STATIC_MAP_B64 else "")

# ---------- 5.6 笔记索引附录（全部信息源，HTML/PDF 双端可溯） ----------
if NOTES:
    rows = []
    for i, n in enumerate(NOTES.values(), 1):
        rows.append(
            f'<tr><td>{i}</td><td>{n["title"]}</td><td>{n["nickname"]}</td><td>{n["likes"]}</td>'
            f'<td class="mono">{n["note_id"]}</td>'
            f'<td><a href="{n["url"]}" target="_blank">打开原文</a></td></tr>')
    NOTES_APPENDIX = (
        '<h2>📎 笔记索引<span class="en">全部信息源 · 链接带 xsec_token 有时效，过期后请在小红书 App 内搜索笔记标题或 note_id</span></h2>'
        '<table class="notes-tbl"><tr><th>#</th><th>笔记标题</th><th>作者</th><th>赞</th><th>note_id</th><th>原文</th></tr>'
        + "".join(rows) + '</table>')
else:
    NOTES_APPENDIX = ""


# ---------- 6. HTML 模板 ----------
HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>潮汕 4天3晚 · 不走回头路</title>
<style>__LEAFLET_CSS__</style>
<style>
:root{
  --sea:#0e5a7a; --sea-deep:#093f57; --orange:#ff8c42; --paper:#faf6ef; --ink:#26333b;
  --card:#ffffff; --line:#e8e0d2; --green:#2e9e6b; --blue:#2f6fed; --purple:#9b59d0; --red:#d64541;
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"PingFang SC","Microsoft YaHei",system-ui,sans-serif;background:var(--paper);color:var(--ink);line-height:1.65}
.wrap{max-width:1080px;margin:0 auto;padding:0 18px 60px}
header{background:linear-gradient(135deg,var(--sea-deep) 0%,var(--sea) 60%,#1878a0 100%);color:#fff;padding:46px 18px 38px;text-align:center;position:relative;overflow:hidden}
header::after{content:"🍜 🌊 ⛩";position:absolute;right:14px;top:12px;opacity:.25;font-size:28px;letter-spacing:6px}
header h1{font-size:clamp(24px,4.5vw,40px);letter-spacing:2px}
header .sub{margin-top:10px;font-size:15px;opacity:.92}
header .route-line{margin-top:16px;display:inline-flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:14px;background:rgba(255,255,255,.12);padding:8px 16px;border-radius:99px}
header .route-line b{color:#ffd9a8}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin:22px 0}
.chip{background:#fff;border:1px solid var(--line);border-radius:12px;padding:10px 14px;font-size:13px;flex:1;min-width:150px;box-shadow:0 1px 3px rgba(38,51,59,.06)}
.chip b{display:block;font-size:15px;color:var(--sea)}
h2{font-size:22px;margin:38px 0 14px;padding-left:12px;border-left:5px solid var(--sea)}
h2 .en{font-size:12px;color:#9aa5ab;font-weight:400;margin-left:8px}
#map{height:480px;border-radius:14px;border:1px solid var(--line);z-index:1}
.map-note{font-size:12px;color:#8a949a;margin-top:8px}
#map-print{display:none}
#map-print img{width:100%;border-radius:14px;border:1px solid var(--line)}
.notes-tbl th,.notes-tbl td{font-size:12px;padding:6px 8px}
.notes-tbl .mono{font-family:Consolas,monospace;font-size:11.5px}
.legend{display:flex;flex-wrap:wrap;gap:14px;margin:12px 0 4px;font-size:13px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.dot{width:12px;height:12px;border-radius:50%;display:inline-block}
.days-strip{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.day-mini{background:#fff;border:1px solid var(--line);border-radius:12px;padding:14px}
.day-mini .tag{display:inline-block;color:#fff;font-size:12px;border-radius:6px;padding:2px 8px;margin-bottom:8px}
.day-mini h4{font-size:15px;margin-bottom:6px}
.day-mini p{font-size:12.5px;color:#5c6a72}
.timeline{background:#fff;border:1px solid var(--line);border-radius:14px;padding:20px 22px;margin-bottom:18px}
.timeline h3{font-size:17px;margin-bottom:4px}
.timeline .theme{font-size:13px;color:#7b868d;margin-bottom:12px}
.tl-item{display:flex;gap:12px;padding:9px 0;border-top:1px dashed var(--line);font-size:14px}
.tl-item:first-of-type{border-top:none}
.tl-time{flex:0 0 110px;color:var(--sea);font-weight:600;font-variant-numeric:tabular-nums}
.tl-body b{color:var(--ink)}
.tl-body .memo{display:block;font-size:12.5px;color:#75828a;margin-top:2px}
.stay{margin-top:10px;background:#f4f8f6;border-radius:8px;padding:8px 12px;font-size:13px}
.city-h{margin:26px 0 12px;font-size:18px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(255px,1fr));gap:16px}
.card{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;display:flex;flex-direction:column;box-shadow:0 1px 4px rgba(38,51,59,.07)}
.card-img{position:relative;aspect-ratio:4/3;background:#eee;overflow:hidden}
.card-img img{width:100%;height:100%;object-fit:cover;display:block}
.noimg{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;height:100%;color:#aab;font-size:13px;text-align:center;padding:8px}
.city-tag{position:absolute;left:8px;top:8px;color:#fff;font-size:12px;border-radius:6px;padding:2px 8px}
.c-潮州{background:var(--orange)}.c-南澳{background:var(--green)}.c-汕头{background:var(--blue)}
.cap{position:absolute;left:8px;bottom:8px;background:rgba(0,0,0,.55);color:#fff;font-size:11px;border-radius:5px;padding:1px 7px}
.card-body{padding:12px 14px 12px;display:flex;flex-direction:column;gap:8px;flex:1}
.shop-head{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.shop-head h4{font-size:15.5px}
.price{flex:none;font-size:12px;color:var(--sea);background:#eaf4f8;border-radius:6px;padding:1px 8px;white-space:nowrap}
.card p{font-size:13px;color:#4d5a62;flex:1}
.card-foot{display:flex;flex-direction:column;gap:5px;font-size:12px}
.card-foot .nav{color:#fff;background:var(--sea);text-align:center;border-radius:7px;padding:5px 0;text-decoration:none}
.card-foot .src{color:#8a7a63;text-decoration:none;border-bottom:1px dashed #cdbfa5}
.warn{background:#fdf1f0;border:1px solid #f2c6c2;border-radius:14px;padding:18px 22px}
.warn h3{color:var(--red);margin-bottom:10px}
.warn li{margin:7px 0 7px 18px;font-size:14px}
.warn li b{color:var(--red)}
table{width:100%;border-collapse:collapse;background:#fff;border-radius:12px;overflow:hidden;font-size:13.5px}
th,td{border:1px solid var(--line);padding:8px 10px;text-align:left}
th{background:#eef4f7;color:var(--sea)}
td.r{text-align:right;font-variant-numeric:tabular-nums}
.foot-note{margin-top:34px;font-size:12px;color:#98a2a8;border-top:1px solid var(--line);padding-top:14px}
.foot-note li{margin:4px 0 4px 16px}
@media (max-width:640px){
  #map{height:380px}
  .tl-item{flex-direction:column;gap:2px}
  .tl-time{flex:none}
}
@page{size:A4;margin:12mm 10mm}
@media print{
  header{background:var(--sea-deep)!important;-webkit-print-color-adjust:exact;print-color-adjust:exact}
  #map{height:360px}
  /* 卡片/时间线/警示块整体不可跨页切断 */
  .card,.timeline,.day-mini,.warn,.chip{break-inside:avoid;page-break-inside:avoid}
  .tl-item,tr{break-inside:avoid;page-break-inside:avoid}
  h2,h3,.city-h{break-after:avoid;page-break-after:avoid}
  body{-webkit-print-color-adjust:exact;print-color-adjust:exact}
  body.has-static #map{display:none!important}
  body.has-static #map-print{display:block}
}
</style>
</head>
<body class="__MAPMODE__">
<header>
  <h1>潮汕 4 天 3 晚 · 不走回头路</h1>
  <div class="sub">高铁进 · 落地自驾 · 单向贯穿：潮州 → 南澳（南线进岛 / 北线出岛）→ 汕头 → 返程</div>
  <div class="route-line">🚄 <b>上海虹桥</b> → 潮汕站 → 🚗 潮州古城 → 官塘 → 🌉 南澳大桥 → 青澳湾 → 🚗 深澳·后宅 → 汕头小公园 → 🚄 <b>汕头站</b></div>
  __INTAKE_LINE__
</header>
<div class="wrap">

<div class="chips">
  <div class="chip"><b>≈350 km</b>落地自驾总里程（含环岛）</div>
  <div class="chip"><b>¥96</b>南澳大桥进岛费（出岛免费）</div>
  <div class="chip"><b>2 处日落 + 1 场日出</b>风车山/彩虹码头 · 青澳湾</div>
  <div class="chip"><b>23 家店 + 7 个点位</b>全部来自小红书高赞实拍笔记</div>
  <div class="chip"><b>≈6-7.5k/2人</b>预算参考（笔记实游记口径）</div>
</div>

<h2>🗺️ 路线地图<span class="en">示意路线 · 坐标为大致位置，精确导航请点各卡片「高德导航」</span></h2>
<div class="legend">
  <span><i class="dot" style="background:#ff8c42"></i>D1 潮州古城</span>
  <span><i class="dot" style="background:#2e9e6b"></i>D2 南线进岛</span>
  <span><i class="dot" style="background:#2f6fed"></i>D3 北线出岛→汕头</span>
  <span><i class="dot" style="background:#9b59d0"></i>D4 返程</span>
</div>
<div id="map"></div>
__MAP_PRINT_DIV__
<div class="map-note">底图（高德瓦片）加载需联网；Leaflet 已内嵌本文件。__IMG_NOTE__南澳岛内「南线进、北线出」形成完整环线，桥只在进岛走一次。</div>

<h2>📅 每日节奏<span class="en">一天一个主题，跨城日主动减量</span></h2>
<div class="days-strip">
  <div class="day-mini"><span class="tag" style="background:#ff8c42">Day 1</span><h4>潮州古城 · 夜与灯</h4><p>午后抵站租车，下午 4 点后进古城：开元寺→甲第巷→广济桥过河拆桥→滨江长廊→广济楼→20:00 灯光秀→牌坊街夜市</p></div>
  <div class="day-mini"><span class="tag" style="background:#2e9e6b">Day 2</span><h4>官塘牛肉 → 南澳南线</h4><p>10 点前吃官塘牛肉火锅，过桥进岛走南线：长山尾→钱澳湾→云澳→青澳湾入住；傍晚风车山/彩虹码头看日落</p></div>
  <div class="day-mini"><span class="tag" style="background:#2f6fed">Day 3</span><h4>日出 → 北线出岛 → 汕头</h4><p>青澳湾看日出，北线竹栖渡湾→深澳→雄镇关→后宅早午餐，出岛进汕头：小公园骑楼 citywalk，夜宵双生不夜粥</p></div>
  <div class="day-mini"><span class="tag" style="background:#9b59d0">Day 4</span><h4>汕头收尾 · 返程</h4><p>福记豆浆早餐，补吃+买手信（猪肉脯/牛肉丸），午后汕头站还车，高铁返沪</p></div>
</div>

<h2>🧭 逐日详单<span class="en">时间块为建议节奏，非分钟级班表</span></h2>
__TIMELINE__

<h2>🍜 吃什么<span class="en">图与推荐均来自小红书原文笔记，点「原文」跳转</span></h2>
__SHOPS__

<h2>📸 看什么<span class="en">机位与时刻来自笔记实测</span></h2>
__SCENIC__

<h2>⚠️ 避雷清单<span class="en">13 篇笔记里被反复点名的坑</span></h2>
<div class="warn">
<h3>花钱买来的教训，直接抄</h3>
<ul>
<li><b>海泉湾「北回归线墙」</b>：人多风大、在小区里、上厕所收费——两篇笔记一致劝退；北回归线打卡去青澳湾「自然之门」即可</li>
<li><b>北回归线广场</b>：商业化严重，公交 601K 只到这里，别被「终点站」误导</li>
<li><b>岛上物价</b>：约为广州的 1.5–2 倍，后宅停车不按位停会被抄牌；北回归线广场停车 ¥23/小时，多数景点卡 15 分钟免费即走</li>
<li><b>电瓶车别租</b>：岛上严查、罚款风险，且全岛无非机动车道、陡坡多——笔记结论「四轮好」</li>
<li><b>青澳湾白天人多</b>：价值在「住旁边看日出」，白天顺路即可，不必专门打卡</li>
<li><b>孤独的树、网红打卡墙</b>：被涂改/人挤人，不值得专程去</li>
<li><b>潮州古城停车难</b>：牌坊街周边停车场常年满，停<b>凤城公园停车场</b>再步行进古城</li>
<li><b>牛肉火锅非正餐时段肉会卖完</b>：官塘一线 10 点前到最稳</li>
<li><b>揭阳古城整修中</b>：近期去潮汕不必安排揭阳</li>
<li><b>交通习惯</b>：潮汕地区没有非机动车道、电动车在路中间开——<b>租车必须买全险</b></li>
</ul>
</div>

<h2>💰 预算参考<span class="en">2 人 · 标注均为笔记/常规口径的参考值</span></h2>
<table>
<tr><th>分类</th><th>细项</th><th class="r">预估（2人）</th></tr>
<tr><td>大交通</td><td>上海⇄潮汕 高铁二等往返（约 7.5h/程；替代：飞机约 2.5h 到揭阳机场）</td><td class="r">≈2000–2400</td></tr>
<tr><td>租车</td><td>3 天 + 全险 + 潮汕站取/汕头还异地费</td><td class="r">≈900–1400</td></tr>
<tr><td>油费+过桥</td><td>≈350km + 南澳大桥 96 + 停车</td><td class="r">≈450–550</td></tr>
<tr><td>住宿</td><td>潮州古城边 1 晚 + 青澳湾海景 1 晚 + 汕头万象城/龙眼南路 1 晚</td><td class="r">≈900–1500</td></tr>
<tr><td>餐饮</td><td>按上方 23 家店人均口径放开吃</td><td class="r">≈1300–1800</td></tr>
<tr><td>门票</td><td>广济桥 20 + 广济楼 30（灯光秀免费）</td><td class="r">≈100</td></tr>
<tr><td><b>合计</b></td><td>参考笔记实游记（上海出发 2 人 6k）与本表口径</td><td class="r"><b>≈5700–7800</b></td></tr>
</table>

<h2>📌 出发前必办清单</h2>
<div class="timeline">
<div class="tl-item"><div class="tl-time">🚄 大交通</div><div class="tl-body">12306 查<b>当日</b>上海虹桥→潮汕站、汕头站→上海虹桥班次（班次时刻以 12306 为准，本攻略不锁定具体车次）；飞机替代方案：上海→揭阳潮汕机场</div></div>
<div class="tl-item"><div class="tl-time">🚗 租车</div><div class="tl-body">一嗨/神州等 App 预约<b>潮汕站或机场取车、汕头市区/汕头站还车</b>，比价异地还车费；<b>必买全险</b>；新能源车注意南澳充电桩位置（后宅/青澳湾有，出发前核实）</div></div>
<div class="tl-item"><div class="tl-time">🏨 住宿</div><div class="tl-body">D1 潮州古城内或古城边民宿（带停车）；D2 青澳湾海景公寓（看日出下楼即到，笔记实住 100–300/晚）；D3 汕头万象城/龙眼南路附近（去哪都近）</div></div>
<div class="tl-item"><div class="tl-time">🎫 门票</div><div class="tl-body">广济桥 ¥20（16:00 停止上桥，17:30 看拆桥）、广济楼登楼 ¥30；灯光秀场次：<b>工作日 20:00 一场，周五—周日 20:00 / 21:30 两场</b>（以现场公告为准）</div></div>
<div class="tl-item"><div class="tl-time">🌦️ 天气</div><div class="tl-body">出发前 3 天看台风/降雨预报——南澳大桥大风会管制，海岛行程留 Plan B（雨天改为潮州+汕头双城，跳过南澳）</div></div>
</div>

__NOTES_APPENDIX__

<div class="foot-note">
<b>数据说明</b>
<ul>
<li>全部店铺/景点/价格/避雷信息来自 2026-10-09 检索的小红书高赞笔记；__IMG_FOOT__图片为笔记实拍，版权归原作者所有，仅作个人行程参考。</li>
<li>「人均」为笔记作者口述，随季节波动；地图坐标为大致位置（GCJ-02），精确导航请使用各卡片「高德导航」链接。</li>
<li>高铁班次、灯光秀场次、营业时间、租车价格属于动态信息，出行前请在 12306 / 官方公众号 / 租车 App 二次确认。</li>
<li>本文件由 chaoshan-roadbook 生成：example/generated/tripData.json 为同源数据层，可改后重新生成。</li>
</ul>
</div>
</div>

<script>__LEAFLET_JS__</script>
<script>
var DATA = __MAPDATA__;
var map = L.map('map', {scrollWheelZoom: false}).setView([23.49, 116.85], 10);
L.tileLayer('https://wprd0{s}.is.autonavi.com/appmaptile?x={x}&y={y}&z={z}&lang=zh_cn&size=1&scl=1&style=8', {
  subdomains: ['1','2','3','4'], maxZoom: 18, attribution: '高德瓦片'
}).addTo(map);
var chain = [];
var seq = 0;
DATA.days.forEach(function(d){
  // pts 格式 [名称, 经度, 纬度]；Leaflet 一律 [纬度, 经度]
  var line = d.pts.map(function(p){ return [p[2], p[1]]; });
  chain = chain.concat(line);
  L.polyline(line, {color: d.color, weight: 4, opacity: .85, dashArray: d.day === 'D4' ? '8 8' : null}).addTo(map);
  d.pts.forEach(function(p){
    seq++;
    L.circleMarker([p[2], p[1]], {
      radius: 11, color: '#fff', weight: 2, fillColor: d.color, fillOpacity: 1
    }).addTo(map).bindPopup(
      '<b>D' + d.day.slice(1) + ' · ' + p[0] + '</b>'
    ).bindTooltip(String(seq), {permanent: true, direction: 'center', className: 'num-tip'});
  });
});
var st = L.circleMarker([31.194, 121.318], {radius: 6, color: '#fff', weight: 2, fillColor: '#666', fillOpacity: 1})
  .addTo(map).bindPopup('<b>出发 · 上海虹桥</b>（高铁进/返）');
var bounds = L.latLngBounds(chain).pad(0.18);
map.fitBounds(bounds);
document.head.insertAdjacentHTML('beforeend',
  '<style>.num-tip{background:none;border:none;box-shadow:none;color:#fff;font-weight:700;font-size:11px;padding:0}</style>');
</script>
</body>
</html>
"""

# ---------- 7. 逐日时间线 ----------
TIMELINE = """
<div class="timeline">
<h3>🟠 Day 1 · 潮州古城（夜与灯）</h3>
<div class="theme">高铁午后到 → 租车 → 「下午 4 点出发不走回头路」经典动线（笔记实测：避开暴晒和人头）</div>
<div class="tl-item"><div class="tl-time">上午</div><div class="tl-body"><b>上海虹桥 → 潮汕站</b>（高铁约 7.5h，班次以 12306 为准；或飞揭阳潮汕机场约 2.5h）<span class="memo">机场/车站取租车——记住：全险</span></div></div>
<div class="tl-item"><div class="tl-time">15:30</div><div class="tl-body"><b>进潮州古城</b>，行李寄存牌坊街口或先去民宿<span class="memo">车停凤城公园停车场，别在古城里找车位</span></div></div>
<div class="tl-item"><div class="tl-time">16:00</div><div class="tl-body"><b>开元寺</b>（免费，唐代古刹，屋顶嵌瓷；避开 12:00–13:00 午休）→ <b>甲第巷</b>（大户人家府邸，游客罕至）</div></div>
<div class="tl-item"><div class="tl-time">17:10</div><div class="tl-body"><b>广济桥</b> ¥20：每个桥亭匾额石刻慢慢看<span class="memo">⭐17:30 蹲「过河拆桥」浮桥拆解，桥上等韩江日落</span></div></div>
<div class="tl-item"><div class="tl-time">18:30</div><div class="tl-body"><b>滨江长廊</b>：拍广济桥全景最佳机位，黄昏蓝调时刻</div></div>
<div class="tl-item"><div class="tl-time">19:30</div><div class="tl-body"><b>广济楼</b>登楼 ¥30 俯瞰古城 → <b>20:00 广济桥灯光秀</b>（周五—周日加场 21:30；不用上桥，岸边免费看）</div></div>
<div class="tl-item"><div class="tl-time">20:30</div><div class="tl-body"><b>牌坊街夜市</b>收尾：23 座明清牌坊夜色最有味道<span class="memo">小吃：顺伯反沙屋 · 一杯潮茶 · 潮涂记腐乳鸡翅 · 陆彬记卤鹅；宵夜砂锅粥（阿荣/锐记）</span></div></div>
<div class="stay">🛏 住潮州古城内/古城边｜🚗 步行日，车歇着</div>
</div>

<div class="timeline">
<h3>🟢 Day 2 · 官塘牛肉 → 南澳岛南线进岛</h3>
<div class="theme">一路向东南：韩江东岸吃牛肉 → 过桥 → 南岸海景公路直奔青澳湾（下午打光面海，拍照好看）</div>
<div class="tl-item"><div class="tl-time">09:30</div><div class="tl-body"><b>官塘兄弟牛肉·总店</b>早午火锅：10 点前到肉最全、鲜牛肉丸必点<span class="memo">两篇笔记评价「肉嫩但不惊艳」，介意可换「生记官塘牛肉」；官塘在潮州东郊，顺路不绕</span></div></div>
<div class="tl-item"><div class="tl-time">11:00</div><div class="tl-body">出发过<b>南澳大桥</b>（进岛 ¥96，出岛免费），约 1h<span class="memo">节假日桥上可能堵半小时+，错峰</span></div></div>
<div class="tl-item"><div class="tl-time">12:30</div><div class="tl-body"><b>长山尾灯塔</b>（红塔+大桥同框）→ 南线：<b>田仔观海平台 → 钱澳湾灯塔</b>（海边栈桥，电影感）</div></div>
<div class="tl-item"><div class="tl-time">15:00</div><div class="tl-body"><b>云澳 · 三囱崖灯塔</b>顺路 → <b>青澳湾</b>入住海景公寓<span class="memo">笔记实住 100–300/晚；下午人多正常，价值在明早日出</span></div></div>
<div class="tl-item"><div class="tl-time">17:00</div><div class="tl-body"><b>蛴仔澎风车山</b>（导航「19 号风车」）或 <b>彩虹码头</b>看日落<span class="memo">彩虹码头：日落前海面彩色、日落时金黄（笔记原话）</span></div></div>
<div class="tl-item"><div class="tl-time">19:00</div><div class="tl-body">晚饭 <b>浩利食店</b>（人均 40+，「南澳最好吃的一顿」）或后宅 <b>黄记沙嗲面</b><span class="memo">甜品：然记糖水铺 / 兴兴反沙；胆大加然孖生腌</span></div></div>
<div class="stay">🛏 住青澳湾海景公寓｜🚗 当日约 110km</div>
</div>

<div class="timeline">
<h3>🔵 Day 3 · 青澳湾日出 → 北线出岛 → 汕头</h3>
<div class="theme">北线（竹栖渡湾—深澳—雄镇关—后宅）与昨日南线合成完整环线——岛内也零回头路</div>
<div class="tl-item"><div class="tl-time">05:40</div><div class="tl-body"><b>青澳湾日出</b>：下楼就是沙滩；顺路 <b>北回归线·自然之门</b>打卡<span class="memo">比「海泉湾墙/北回归线广场」值</span></div></div>
<div class="tl-item"><div class="tl-time">08:00</div><div class="tl-body">北线出岛：<b>竹栖渡湾</b>（避雷贴作者心中「岛上最好的地方」，人少水净）→ <b>深澳总兵府</b>（顺路可选）→ <b>雄镇关</b> → <b>后宅镇</b>早午餐<span class="memo">后宅吃老牌沙嗲面/打包谢真真糯米糍</span></div></div>
<div class="tl-item"><div class="tl-time">11:00</div><div class="tl-body">过桥出岛（免费）→ 汕头约 1h；西堤公园停车</div></div>
<div class="tl-item"><div class="tl-time">12:30</div><div class="tl-body">午餐 <b>杏花吴记牛肉火锅</b>（人均 120，错峰）或 <b>五洲牛肉馆</b>（11 点去包场）</div></div>
<div class="tl-item"><div class="tl-time">14:30</div><div class="tl-body">Citywalk：<b>汕头旅社 → 小公园 → 老妈宫戏台 → 邮政总局 → 开埠文化陈列馆</b><span class="memo">骑楼建筑群很复古，商拍摄影多</span></div></div>
<div class="tl-item"><div class="tl-time">18:00</div><div class="tl-body"><b>龙眼南路美食街</b>：蔡大胆捞面 / 如如糯米铺 / 兴欣荣鸡翅 / 叔公手作 / 阿群甘草水果</div></div>
<div class="tl-item"><div class="tl-time">22:00</div><div class="tl-body"><b>双生不夜粥</b>深夜食堂：10 点后到不用排队，酸菜东星斑</div></div>
<div class="stay">🛏 住万象城/龙眼南路附近｜🚗 当日约 110km</div>
</div>

<div class="timeline">
<h3>🟣 Day 4 · 汕头收尾 → 返沪</h3>
<div class="theme">早餐–补吃–手信–还车，午后高铁走人（汕头站出发，不用折回潮汕站）</div>
<div class="tl-item"><div class="tl-time">08:30</div><div class="tl-body"><b>老牌福记加浓豆浆</b>+油条开胃；再来份小吴肠粉（评价两极，自行验证）</div></div>
<div class="tl-item"><div class="tl-time">10:00</div><div class="tl-body">补漏任选：<b>金砂阿洲鱼册店 / 龙香酒家 / 瑞娇嫲嫲生腌 / 陶家功夫卤鹅</b>；买手信：钟福记猪肉脯 + 牛肉丸</div></div>
<div class="tl-item"><div class="tl-time">14:00</div><div class="tl-body">汕头市区/汕头站<b>还车</b>（异地还车费下单时看清）</div></div>
<div class="tl-item"><div class="tl-time">15:00+</div><div class="tl-body"><b>汕头站 → 上海虹桥</b>高铁返程<span class="memo">班次以 12306 为准；若飞返需回揭阳机场（约 1h，略回头），高铁更契合本线路</span></div></div>
</div>
"""

IMG_NOTE = "" if not NO_IMAGES else "本示例未嵌图片（--no-images 模式）。"
IMG_FOOT = ("每张卡片附原文链接。" if not NO_IMAGES
            else "本示例模式未嵌入图片与原文链接（版权与脱敏考虑）。")

# ---------- intake 注入（来自问卷参数，未填的不渲染） ----------
intake_bits = []
if args.date_range:
    intake_bits.append(f"📅 <b>{args.date_range}</b>")
if args.travelers:
    intake_bits.append(f"👥 {args.travelers}")
if args.budget:
    intake_bits.append(f"💰 {args.budget}")
INTAKE_LINE = (f'<div class="route-line" style="margin-top:8px">{" &nbsp;·&nbsp; ".join(intake_bits)}</div>'
               if intake_bits else "")
if args.preferences:
    INTAKE_LINE += f'<div class="route-line" style="margin-top:8px">🎯 偏好：{args.preferences}</div>'

leaflet_js = open(os.path.join(THIRD_PARTY, "leaflet.js"), encoding="utf-8").read()
leaflet_css = open(os.path.join(THIRD_PARTY, "leaflet.css"), encoding="utf-8").read()

html = (HTML
        .replace("__TIMELINE__", TIMELINE)
        .replace("__SHOPS__", SHOP_HTML)
        .replace("__SCENIC__", SCENIC_HTML)
        .replace("__MAPDATA__", MAPDATA_JSON)
        .replace("__IMG_NOTE__", IMG_NOTE)
        .replace("__IMG_FOOT__", IMG_FOOT)
        .replace("__INTAKE_LINE__", INTAKE_LINE)
        .replace("__MAPMODE__", MAPMODE)
        .replace("__MAP_PRINT_DIV__", MAP_PRINT_DIV)
        .replace("__NOTES_APPENDIX__", NOTES_APPENDIX)
        .replace("__LEAFLET_CSS__", leaflet_css)
        .replace("__LEAFLET_JS__", leaflet_js))

out_name = "潮汕路书-示例无图版.html" if NO_IMAGES else "潮汕4天3晚-不走回头路路书.html"
out_html = os.path.join(OUT_DIR, out_name)
with open(out_html, "w", encoding="utf-8") as f:
    f.write(html)
print("\nHTML:", out_html, round(os.path.getsize(out_html) / 1024 / 1024, 2), "MB")

# ---------- 8. tripData.json 数据层 ----------
trip = {
    "title": "潮汕 4天3晚 · 不走回头路（高铁+自驾）",
    "origin": "上海（假设，可换）",
    "dateRange": args.date_range or "待定（建议避开节假日，桥上会堵）",
    "travelers": args.travelers or "2人（假设）",
    "budget": args.budget,
    "preferences": args.preferences,
    "routeRule": "单向贯穿：潮州→官塘→南澳(南线进/北线出)→汕头；返程汕头站，不折回",
    "days": DAYS_MAP,
    "shops": [{"city": s[0], "name": s[1], "price": s[2], "blurb": s[3], "amap": amap_link(s[5], s[0]),
               "note": (NOTES[s[6]]["url"] if s[6] in NOTES else None)} for s in SHOPS],
    "scenic": [{"name": s[0], "price": s[1], "blurb": s[2], "amap": amap_link(s[4], ""),
                "note": (NOTES[s[5]]["url"] if s[5] in NOTES else None)} for s in SCENIC],
    "notes": NOTES,
    "meta": {"generated": __import__("datetime").date.today().isoformat(),
             "source": ("本机 xiaohongshu-mcp 检索，13 篇笔记见 scripts/digest.json" if not NO_IMAGES
                        else "--no-images 示例模式：未检索、未嵌图、笔记链接已脱敏"),
             "caveat": "价格/班次/场次为笔记口径，出行前 12306/官方二次确认"},
}
with open(os.path.join(OUT_DIR, "tripData.json"), "w", encoding="utf-8") as f:
    json.dump(trip, f, ensure_ascii=False, indent=1)
print("tripData.json done")
print("failed imgs:", fail if fail else "none")
