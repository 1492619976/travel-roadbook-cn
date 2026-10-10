# -*- coding: utf-8 -*-
"""调用本机 xiaohongshu-mcp (http://localhost:18060/mcp) 的轻量客户端。
只做只读操作：check_login_status / search_feeds / get_feed_detail。
用法:
  python xhs_call.py login
  python xhs_call.py search "潮州美食攻略" out.json
  python xhs_call.py detail <feed_id> <xsec_token> out.json
"""
import json
import sys
import urllib.request

BASE = "http://localhost:18060/mcp"


def post(payload, sid=None, timeout=180):
    req = urllib.request.Request(
        BASE, data=json.dumps(payload).encode("utf-8"), method="POST"
    )
    req.add_header("Content-Type", "application/json")
    req.add_header("Accept", "application/json, text/event-stream")
    if sid:
        req.add_header("Mcp-Session-Id", sid)
    resp = urllib.request.urlopen(req, timeout=timeout)
    new_sid = resp.headers.get("Mcp-Session-Id") or sid
    body = resp.read().decode("utf-8")
    result = None
    for line in body.splitlines():
        if line.startswith("data: "):
            try:
                result = json.loads(line[6:])
            except Exception:
                pass
    if result is None:
        result = json.loads(body) if body.strip() else None
    return result, new_sid


def connect():
    _, sid = post({
        "jsonrpc": "2.0", "id": 0, "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05", "capabilities": {},
            "clientInfo": {"name": "zcode-script", "version": "1.0"},
        },
    })
    post({"jsonrpc": "2.0", "method": "notifications/initialized"}, sid)
    return sid


def call_tool(sid, name, arguments, msg_id=1):
    r, _ = post({
        "jsonrpc": "2.0", "id": msg_id, "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }, sid, timeout=300)
    return r


def extract_text(result):
    """把 MCP content 里的 text 拼出来，顺带剥掉 markdown 代码围栏。"""
    parts = []
    for item in result.get("result", {}).get("content", []):
        if item.get("type") == "text":
            parts.append(item.get("text", ""))
    text = "\n".join(parts)
    return text


def main():
    cmd = sys.argv[1]
    sid = connect()
    if cmd == "login":
        r = call_tool(sid, "check_login_status", {})
        print(json.dumps(r, ensure_ascii=False, indent=2))
    elif cmd == "search":
        keyword, outfile = sys.argv[2], sys.argv[3]
        r = call_tool(sid, "search_feeds", {"keyword": keyword, "filters": {}})
        text = extract_text(r)
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(text)
        print(text[:1500])
    elif cmd == "detail":
        feed_id, xsec, outfile = sys.argv[2], sys.argv[3], sys.argv[4]
        r = call_tool(sid, "get_feed_detail", {
            "feed_id": feed_id, "xsec_token": xsec, "limit": 5,
        })
        text = extract_text(r)
        with open(outfile, "w", encoding="utf-8") as f:
            f.write(text)
        print(text[:1200])
    else:
        print("unknown cmd")


if __name__ == "__main__":
    main()
