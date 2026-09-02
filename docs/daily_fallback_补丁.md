# 🆕 daily_fallback.yml 兜底 workflow

**创建时间**: 2026-09-02 20:18 北京时间
**目的**: 解决 daily.yml 主 cron 漏跑导致数据不更新的问题
**预计操作时间**: 1 分钟

---

## 🐛 问题背景

最近 2 周 daily.yml 调度越来越不稳定:

| 日期 | 应跑时间(北京) | 实际跑时间 | 延迟 |
|----|----|----|----|
| 8/24 | 17:00 | 17:41 | 41 分钟 |
| 8/25 | 17:00 | ❌ **cancelled** | 失败 |
| 8/28 | 17:00 | 04:38(次日) | 11 小时 |
| 8/31 | 17:00 | 00:38 + 8:38(都跑) | 跑了 2 次 |
| 9/1 | 17:00 | 21:52 | 4 小时 |
| **9/2** | **17:00** | **❌ 没跑** | **漏跑!** |

9/2 17:00 北京时间彻底没跑,导致 App 一直显示 9/1 的数据。

---

## 🎯 解决方案

加一个 **fallback workflow**,在主 workflow 失败 2 小时后(北京 19:00 = UTC 11:00)自动补救。

**核心 trick**:`git log` 检查今天是否已更新过,**是就跳过,不是才跑**,避免重复 commit。

---

## 📋 操作步骤(1 分钟)

### 1. 打开 GitHub 新建文件页面

直接点这个链接(已预填内容):
```
https://github.com/Joeyygh/vibe-quant/new/main/.github/workflows/daily_fallback.yml
```

### 2. 粘贴下面这段 YAML

把下面整段贴到 GitHub 编辑器里:

```yaml
name: Daily Data Update (Fallback)

# 🆕 2026-09-02 新增: daily.yml 主 cron 漏跑时的兜底
# 主 cron: 0 9 * * 1-5 (北京 17:00)
# 兜底 cron: 0 11 * * 1-5 (北京 19:00, 主失败 2 小时后补刀)
# 智能跳过: 如果 17:00 那个已经推过今天的 commit, 这个 workflow 直接 exit 0

on:
  schedule:
    - cron: '0 11 * * 1-5'   # 北京 19:00
  workflow_dispatch:

permissions:
  contents: write

jobs:
  update-data-fallback:
    runs-on: ubuntu-latest
    timeout-minutes: 60

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: 检查今天是否已更新
        id: check
        run: |
          TODAY=$(date +%Y-%m-%d)
          LATEST_DATE=$(git log -5 --format="%cd" --date=short | head -1)
          if [ "$LATEST_DATE" = "$TODAY" ]; then
            echo "✅ 今天 ($TODAY) 已更新过, fallback 跳过"
            echo "skip=true" >> $GITHUB_OUTPUT
          else
            echo "⚠️ 今天 ($TODAY) 未更新, fallback 启动"
            echo "skip=false" >> $GITHUB_OUTPUT
          fi

      - name: Setup Python
        if: steps.check.outputs.skip != 'true'
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        if: steps.check.outputs.skip != 'true'
        run: |
          pip install tushare pandas pyarrow

      - name: Update data
        if: steps.check.outputs.skip != 'true'
        env:
          TUSHARE_TOKEN: ${{ secrets.TUSHARE_TOKEN }}
        run: |
          mkdir -p data
          python scripts/update_data.py

      - name: Commit and push
        if: steps.check.outputs.skip != 'true'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/
          git diff --staged --quiet || git commit -m "chore: daily data update (fallback) $(date +%Y-%m-%d)"
          git push
```

### 3. 提交

- 滚到底部
- **Commit message** 写: `feat: daily_fallback.yml 兜底 workflow (主 cron 漏跑 2 小时后补刀)`
- 选 **Commit directly to the main branch**
- 点 **Commit new file**

---

## ✅ 验证

提交后 1 分钟内,去 Actions 页面看:
```
https://github.com/Joeyygh/vibe-quant/actions
```

会看到 `Daily Data Update (Fallback)` workflow 出现在列表里(虽然还没到 19:00 北京时间不跑)。

**最晚 9/3 19:00 北京时间**,fallback 第一次自动运行:
- 如果当天 17:00 已跑 → "✅ 今天已更新过, fallback 跳过"
- 如果当天 17:00 漏跑 → 自动补跑 + commit

---

## 🚀 立即生效(可选)

如果你**想现在就跑一次**让它兜底今天 9/2 的数据(我刚才手动触发的 daily.yml 还在跑中):

去 https://github.com/Joeyygh/vibe-quant/actions/workflows/daily_fallback.yml
点 **Run workflow** → 选 main → 点绿色 **Run workflow** 按钮

但**没必要**,因为我刚才触发的 daily.yml 应该 5-10 分钟内跑完,会自动推到 data/。

---

## 📅 之后每天 19:00 北京时间自动

不需要你再操作,fallback 会自动跑:
- ✅ 今天有数据 → 跳过
- ❌ 今天没数据 → 自动补跑 + commit
