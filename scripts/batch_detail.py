# -*- coding: utf-8 -*-
"""从搜索结果 JSON 里按标题选中笔记，批量拉详情（正文+图片+点赞），存 d_*.json。"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from xhs_call import connect, call_tool, extract_text

# (搜索结果文件, 标题子串, 输出名, 用途标签)
SELECT = [
    ("s_潮汕4天3晚旅游攻略.json", "上海出发", "d_shanghai_route", "路线总纲"),
    ("s_潮汕4天3晚旅游攻略.json", "四天三晚自驾逛吃攻略", "d_zijia_route", "自驾路线"),
    ("s_潮州古城一日游攻略.json", "第一次去潮州", "d_chaozhou_route", "古城路线"),
    ("s_潮州古城一日游攻略.json", "不走回头路", "d_chaozhou_noback", "古城路线"),
    ("s_chaozhou_food.json", "跟着大表哥", "d_chaozhou_food1", "潮州美食"),
    ("s_chaozhou_food.json", "跟着乌拉拉", "d_chaozhou_food2", "潮州美食"),
    ("s_南澳岛美食攻略.json", "南澳岛能有多好吃", "d_nanao_food1", "南澳美食"),
    ("s_南澳岛美食攻略.json", "纯吃一日游攻略", "d_nanao_food2", "南澳美食"),
    ("s_南澳岛自驾.json", "千字体验攻略", "d_nanao_loop", "环岛路线"),
    ("s_南澳岛自驾.json", "逆时针环岛", "d_nanao_loop2", "环岛路线"),
    ("s_南澳岛自驾.json", "避雷贴", "d_nanao_avoid", "避雷"),
    ("s_汕头美食攻略.json", "2天12顿主观评价", "d_shantou_food1", "汕头美食"),
    ("s_汕头美食攻略.json", "附人均", "d_shantou_food2", "汕头美食"),
]


def load_search(fp):
    d = json.load(open(fp, encoding="utf-8"))
    out = []
    for f in d.get("feeds", []):
        nc = f.get("noteCard") or {}
        out.append({
            "id": f.get("id"),
            "xsecToken": f.get("xsecToken"),
            "title": nc.get("displayTitle", ""),
            "type": nc.get("type"),
            "nickname": (nc.get("user") or {}).get("nickname", ""),
            "likes": (nc.get("interactInfo") or {}).get("likedCount", "0"),
            "cover": ((nc.get("cover") or {}).get("urlDefault") or ""),
        })
    return out


def main():
    sid = connect()
    digest = []
    for fp, key, out, tag in SELECT:
        try:
            feeds = load_search(fp)
        except FileNotFoundError:
            print(f"[skip] {fp} 不存在")
            continue
        hit = next((x for x in feeds if key in x["title"]), None)
        if not hit:
            print(f"[miss] {fp} 里找不到「{key}」")
            continue
        outfile = out + ".json"
        if os.path.exists(outfile) and os.path.getsize(outfile) > 2000:
            print(f"[cached] {outfile}")
            r = json.load(open(outfile, encoding="utf-8"))
        else:
            r = call_tool(sid, "get_feed_detail", {
                "feed_id": hit["id"], "xsec_token": hit["xsecToken"], "limit": 5,
            })
            text = extract_text(r)
            open(outfile, "w", encoding="utf-8").write(text)
            time.sleep(2)
        # 提取摘要
        try:
            dd = json.loads(open(outfile, encoding="utf-8").read())
        except Exception:
            dd = {}
        note = ((dd.get("data") or {}).get("note") or {})
        desc = note.get("desc") or ""
        imgs = [i.get("urlDefault") or i.get("url") or ""
                for i in (note.get("imageList") or [])]
        digest.append({
            "tag": tag, "file": outfile, "title": hit["title"], "likes": hit["likes"],
            "type": hit["type"], "nickname": hit["nickname"],
            "note_id": hit["id"], "xsec_token": hit["xsecToken"],
            "desc": desc, "images": [u for u in imgs if u],
        })
        print(f"[ok] {tag} | {hit['title'][:30]} | desc {len(desc)}字 | 图 {len(imgs)}")
    json.dump(digest, open("digest.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("digest.json written:", len(digest), "notes")


if __name__ == "__main__":
    main()
