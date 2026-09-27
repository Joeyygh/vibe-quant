#!/usr/bin/env python3
"""
lint_workflows.py — 零依赖的 GitHub Actions YAML 静态体检 (v1, 2026-09-27)

为什么需要它
------------
本仓库有两个 workflow 因为 YAML 语法问题被 GitHub 标记为"无效",
而且**失效是完全静默的**:

  - 定时任务被 GitHub 直接跳过,不会报错、不会通知
  - actions 注册表里 name 字段从 "Daily Report" 退化成文件路径
  - workflow_dispatch 返回 422 "does not have 'workflow_dispatch' trigger"
  - 只有去翻 actions 列表才会发现

真实踩过的两个坑:
  1) step 名里写裸 ": "   -> - name: Health check: my_holdings.json
     ": " 是 YAML 键值分隔符,plain scalar 里出现即解析失败。
  2) 块标量里续行落到第 0 列 -> run: | 内部某行顶格,
     提前结束块标量,后面那行被当成 YAML 内容 → 解析失败。

本脚本不依赖 pyyaml(沙箱/GitHub runner 未必装了),用行级规则覆盖这两类
以及若干相邻的常见坑。真要完整校验,还是建议 `python -c "import yaml,sys;
yaml.safe_load(open(sys.argv[1]))"`。

用法:
    python scripts/lint_workflows.py            # 检查 .github/workflows/*.yml
    python scripts/lint_workflows.py path.yml   # 检查指定文件
退出码: 0 = 全过, 1 = 有 ERROR
"""
import glob
import os
import re
import sys

WF_DIR = ".github/workflows"

# key: 行内未加引号的 ": "  → plain scalar 里非法
UNQUOTED_COLON = re.compile(
    r'^\s*(?:-\s+)?[A-Za-z_][A-Za-z0-9_.-]*:\s+'      # key:
    r'(?!["\']|[\[{&*!|>@`#])'                          # 值不是引号/流/块起始
    r'([^#]*?:\s.*)$'                                   # 但值里又出现了 ": "
)

BLOCK_SCALAR = re.compile(r':\s*[|>][-+0-9]*\s*(#.*)?$')  # run: | / |-

ERR, WARN, OK = "ERROR", "WARN ", "  ok"


def lint(path):
    issues = []  # (level, lineno, msg)
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")

    in_block = False          # 是否在 run: | / | 块标量里
    block_indent = None       # 块标量的基准缩进
    block_key_indent = None   # 所属 key 的缩进

    for i, raw in enumerate(lines, 1):
        line = raw.rstrip()
        stripped = line.strip()

        # ---- 块标量跟踪 ----
        if in_block:
            if not stripped:
                continue
            indent = len(line) - len(line.lstrip())
            if indent > block_indent:
                continue                       # 正常块内容
            # 顶格或缩进回退 → 块结束
            in_block = False
            if indent == 0 and stripped:
                issues.append((ERR, i,
                               f"块标量外的第 0 列内容 {stripped!r} —— "
                               f"很可能是上一段 run: | 的续行顶格了,"
                               f"会导致 YAML 解析失败"))
            continue

        if not stripped or stripped.startswith("#"):
            continue

        m = BLOCK_SCALAR.search(line)
        if m:
            in_block = True
            block_key_indent = len(line) - len(line.lstrip())
            block_indent = block_key_indent + 2
            continue

        # ---- 裸 ": " ----
        m = UNQUOTED_COLON.match(line)
        if m:
            issues.append((ERR, i,
                           f"未加引号的值里含 \": \" → {m.group(1).strip()!r}。"
                           f'把整个值用单引号包起来,或去掉冒号'))

        # ---- Tab 缩进 ----
        if line.startswith("\t") or (line[:len(line) - len(line.lstrip())].count("\t")):
            issues.append((ERR, i, "YAML 不允许 Tab 缩进"))

        # ---- 明显未闭合的引号 ----
        for q in ("'", '"'):
            if line.count(q) % 2 == 1 and "${{" not in line and not stripped.startswith("#"):
                issues.append((WARN, i, f"{q} 引号数为奇数,可能未闭合"))

    return issues


def main():
    if len(sys.argv) > 1:
        files = sys.argv[1:]
    else:
        files = sorted(glob.glob(os.path.join(WF_DIR, "*.yml")) +
                       glob.glob(os.path.join(WF_DIR, "*.yaml")))

    if not files:
        print(f"ℹ️  {WF_DIR}/ 下没有找到 workflow 文件")
        return 0

    bad = 0
    for f in files:
        issues = lint(f)
        errs = [x for x in issues if x[0] == ERR]
        warns = [x for x in issues if x[0] == WARN]
        if errs or warns:
            print(f"\n❌ {f}")
            for lvl, ln, msg in sorted(issues, key=lambda x: x[1]):
                print(f"   {lvl} L{ln}: {msg}")
            bad += len(errs)
        else:
            print(f"✅ {f}")

    print()
    if bad:
        print(f"🔴 {bad} 个 ERROR —— GitHub 会把该 workflow 判为无效并**静默跳过**它的定时任务。")
        return 1
    print("🟢 全部 workflow 语法体检通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
