#!/usr/bin/env python3
"""
holdings_io — 持仓文件唯一加载入口 (v1, 2026-09-27)

背景: 仓库里长期存在**两份** my_holdings.json, 且格式不同:

  data/my_holdings.json   version=2026-09-18, 33 只, 格式 {"groups": {...}},
                          code 带交易所后缀 (002518.SZ / 2228.HK / 100922.CSI)
                          ← App (app.py) 读这份, check_holdings.py 也读这份
                          ← **这是唯一的事实来源**

  ./my_holdings.json      version="v2.2",  27 只, 格式 {"holdings": [...]},
                          code 纯 6 位 (002518)
                          ← 孤儿陈旧文件,但 daily_report.py / daily_picks_v2.py /
                            daily_picks_dynamic.py / verify_holdings.py /
                            intel_app.py 全都在读这份

后果: 用户在 App 里看到 33 只持仓、很满意,但每晚的选股报告和持仓信号
      是拿 27 只陈旧数据算的 —— 有 6 只真实持仓的信号从来没被计算过。
      体检(check_holdings)查的是 A,实际算的是 B,监控完全失效。

本模块做三件事:
  1. resolve_path()  统一路径解析,固定指向 data/my_holdings.json,
                     同时检测并报告孤儿文件漂移
  2. load()          统一解析,兼容 3 种结构:
                     {"groups": {...}} / {"holdings": [...]} / 裸 list
  3. normalize()     统一字段: code 去后缀 + zfill(6),补 group/shares/cost_price

用法:
    from holdings_io import load_holdings, resolve_path
    holdings = load_holdings()          # 返回 list[dict], 永远不会是 None
"""
import json
import os
import sys

# 唯一事实来源。相对仓库根。
CANONICAL = os.path.join("data", "my_holdings.json")
# 已知的历史孤儿路径(只用于检测漂移,不再读取)
LEGACY_PATHS = ["my_holdings.json"]

# 需要被识别的后缀(排序:长的在前,避免 .HK 被 .HKX 之类截断)
_SUFFIXES = (".CSI", ".SH", ".SZ", ".BJ", ".HK", ".SS", ".OF")


def _repo_root():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resolve_path(root=None):
    """返回持仓文件绝对路径。

    固定用 data/my_holdings.json。根目录那份历史文件如果还在,
    打印一次漂移警告(可通过 HOLDINGS_STRICT=1 升级为抛错)。
    """
    root = root or _repo_root()
    canon = os.path.join(root, CANONICAL)
    if os.path.exists(canon):
        _warn_drift(root, canon)
        return canon
    # 事实来源缺失 —— 退回历史路径,保证功能不中断
    for rel in LEGACY_PATHS:
        legacy = os.path.join(root, rel)
        if os.path.exists(legacy):
            print(f"⚠️  [{CANONICAL}] 缺失,回退到历史文件 {rel}(数据可能陈旧)", file=sys.stderr)
            return legacy
    return canon  # 交给调用方处理"文件不存在"


def _warn_drift(root, canon):
    """检测孤儿历史文件是否与事实来源分叉。"""
    try:
        canon_data = _read(canon)
    except Exception:
        return

    for rel in LEGACY_PATHS:
        legacy = os.path.join(root, rel)
        if not os.path.exists(legacy) or os.path.abspath(legacy) == os.path.abspath(canon):
            continue
        try:
            legacy_data = _read(legacy)
        except Exception:
            continue

        c_codes = {n.get("code") for n in normalize(canon_data) if n.get("code")}
        l_codes = {n.get("code") for n in normalize(legacy_data) if n.get("code")}
        if c_codes == l_codes:
            continue

        only_new = c_codes - l_codes
        only_old = l_codes - c_codes
        msg = (f"🚨 持仓文件漂移!\n"
               f"    事实来源 {CANONICAL}: {len(c_codes)} 只\n"
               f"    孤儿文件 {rel}: {len(l_codes)} 只\n"
               f"    仅事实来源有: {sorted(only_new)[:10] or '无'}\n"
               f"    仅孤儿文件有: {sorted(only_old)[:10] or '无'}")
        if os.environ.get("HOLDINGS_STRICT") == "1":
            raise RuntimeError(msg)
        print(msg, file=sys.stderr)
        print(f"    → 请删除 {rel}(仓库根目录),避免脚本误读陈旧数据", file=sys.stderr)


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract(raw):
    """兼容 3 种持仓结构,返回 list[dict]。

    1) {"groups": {"深亏": [...], ...}}        ← 当前线上格式
    2) {"holdings": [...], "closed_holdings": [...]}
    3) 裸 list [...]
    """
    if isinstance(raw, list):
        return raw if all(isinstance(x, dict) for x in raw) else []
    if not isinstance(raw, dict):
        return []

    # 1) groups 格式(带 group 名回填)
    groups = raw.get("groups")
    if isinstance(groups, dict) and groups:
        out = []
        for gname, items in groups.items():
            if not isinstance(items, list):
                continue
            for it in items:
                if not isinstance(it, dict):
                    continue
                item = dict(it)
                item.setdefault("group", gname)
                out.append(item)
        if out:
            return out

    # 2) holdings 格式
    holdings = raw.get("holdings")
    if isinstance(holdings, list) and holdings:
        return [x for x in holdings if isinstance(x, dict)]

    return []


def _strip_suffix(code):
    """002518.SZ -> 002518 ; 2228.HK -> 02228 ; 100922.CSI -> 100922"""
    s = str(code).strip()
    for suf in _SUFFIXES:
        if s.upper().endswith(suf):
            return s[: -len(suf)]
    # 未识别后缀:在第一个点处切分(如 000001.00 这种老写法)
    if "." in s:
        head, tail = s.split(".", 1)
        if tail.isalpha() or tail.isdigit():
            return head
    return s


def normalize(raw):
    """统一字段,输出干净的 list[dict]。

    - code: 去交易所后缀 + zfill(6)   (港股 2228 -> 02228, 保持 6 位)
    - name / cost_price / shares / group: 存在即用,不存在给安全默认
    """
    out = []
    for h in extract(raw):
        raw_code = h.get("code") or h.get("ts_code") or h.get("symbol") or ""
        if not raw_code:
            continue
        item = {
            "code": _strip_suffix(raw_code).zfill(6),
            "raw_code": str(raw_code).strip(),
            "name": (h.get("name") or "").strip() or "-",
            "group": h.get("group") or "",
            "cost_price": _to_float(h.get("cost_price")),
            "shares": _to_float(h.get("shares")) or 0,
        }
        for k, v in h.items():
            if k not in item and k not in ("code", "ts_code", "symbol"):
                item[k] = v
        out.append(item)
    return out


def _to_float(v):
    if v is None or v == "":
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def load_holdings(root=None, quiet=False):
    """一站式:定位 + 读取 + 解析 + 归一化。失败返回 [] 而不是抛错。"""
    path = resolve_path(root)
    if not os.path.exists(path):
        if not quiet:
            print(f"⚠️  持仓文件不存在: {path}(报告将跳过持仓章节)", file=sys.stderr)
        return []
    try:
        raw = _read(path)
    except Exception as e:
        print(f"⚠️  持仓文件解析失败: {e}(报告将跳过持仓章节)", file=sys.stderr)
        return []
    holdings = normalize(raw)
    if not quiet:
        version = raw.get("version") if isinstance(raw, dict) else "list"
        print(f"  持仓: {len(holdings)} 只 (source={path}, version={version})")
    return holdings


if __name__ == "__main__":
    hs = load_holdings()
    print(f"\n共 {len(hs)} 只")
    for h in hs[:10]:
        print(f"  {h['code']}  {h['name']:<10} cost={h['cost_price']}  {h['group']}")
