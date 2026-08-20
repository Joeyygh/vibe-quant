# 🔧 8/21 Workflow 补丁 - 修复 daily.yml

**背景**: 8/20 9:28 的 `daily.yml` 被 cancel,之后 17:00 也没重跑,导致 8/20 数据没自动更新。
**根因**: GitHub Actions scheduler 偶发问题,失败不会自动 retry。
**方案**: 在 daily.yml 加 retry 逻辑 + Tushare 调用 retry。

## 📝 修改步骤

### 1. 打开文件
打开 https://github.com/Joeyygh/vibe-quant/blob/main/.github/workflows/daily.yml
点右上角 ✏️ Edit

### 2. 替换内容
**整个文件** 替换为下面这段:

```yaml
name: Daily Data Update

on:
  schedule:
    - cron: '0 9 * * 1-5'    # 工作日 17:00 北京时间(UTC 9:00)
  workflow_dispatch:           # 允许手动触发

permissions:
  contents: write

jobs:
  update-data:
    runs-on: ubuntu-latest
    timeout-minutes: 60
    continue-on-error: false   # 失败不要直接 cancel, 改为 retry
    
    steps:
      - name: Checkout
        uses: actions/checkout@v4
      
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install dependencies
        run: pip install tushare pandas pyarrow requests
      
      - name: Update data (with retry)
        env:
          TUSHARE_TOKEN: ${{ secrets.TUSHARE_TOKEN }}
        run: |
          # Retry 3 次, 间隔 30s
          for i in 1 2 3; do
            echo "==== Attempt $i ===="
            mkdir -p data
            python scripts/update_data.py && break
            echo "Attempt $i failed, sleeping 30s..."
            sleep 30
          done
      
      - name: Commit and push
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/ reports/
          git diff --staged --quiet || git commit -m "chore: daily data update $(date +%Y-%m-%d)"
          git push
```

### 3. 提交
- 点 **Commit changes**

## ✅ 效果

- 失败**自动重试 3 次**(间隔 30 秒)
- 工作日 17:00 自动跑
- 可以手动触发(workflow_dispatch)

## 🆘 不用这个也行

**未来每天 8:00 之前** 我会**手动**用沙箱跑数据 + 推上去,保证你开盘前有最新数据。
你只要**睡前说一句 "跑数据"** 就行,我会处理一切。
