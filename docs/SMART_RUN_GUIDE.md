# Vibe 智能运行指南 (smart_run)

> 解决"盘中/盘后跑 daily_report.py,数据是空的"问题
> 推送时间:2026-09-14
> 涉及文件:`scripts/daily_report.py`(已 patch)+ `scripts/smart_run.py`(新增)

## 背景

**老问题**:`daily_report.py` 的 `get_target_date()` 函数写死"17:00 前用昨天,17:00 后用今天"。

中午 12 点跑的时候,`target_date = 今天(9/14)`,但 Tushare 的 9/14 数据要 17:30 才拉回来,导致 `pro.xxx(trade_date=今天)` 全返回空,报告章节空一片。

**新方案**:让 `get_target_date()` 优先从 `data/last_update.txt` 读"最新可得的数据日期",而不是 `now.date() - 1`。

---

## 改动点

### 1. `scripts/daily_report.py` (已推送)

`get_target_date()` 函数改为:

```python
优先级:
1. 环境变量 VIBE_AS_OF_DATE 显式指定 (如 2026-09-11)
2. data/last_update.txt 记录的最近数据日期 (推荐 — 用最新可得数据)
3. 兜底: 17:00 后用今天,否则用昨天 (旧逻辑)
```

新增 `get_session_label()`:

```python
自动判断: 盘前 / 盘中(上午) / 午间 / 盘中(下午) / 盘后 / 盘后分析
```

主入口打印报告类型 + 日期,方便诊断。

### 2. `scripts/smart_run.py` (新增)

时间感知 wrapper,任何时段都能用:

```bash
# 盘前跑 (默认 9:00 前)
python scripts/smart_run.py

# 强制盘中模式
python scripts/smart_run.py --mode intraday

# 强制盘后模式
python scripts/smart_run.py --mode post

# 指定报告日期
python scripts/smart_run.py --as-of 2026-09-13

# 只打印配置不跑
python scripts/smart_run.py --dry-run
```

---

## 关键行为

| 调用时段 | 报告日期 | 报告标题后缀 | 适用场景 |
|---------|---------|------------|---------|
| 9:00 前 | last_update 的日期 | 盘前预判 | 开盘前出当日预判 |
| 9:30-11:30 | last_update 的日期 | 盘中快报(上午) | 上午盯盘快速出 |
| 11:30-13:00 | last_update 的日期 | 午间快报 | 午间总结 |
| 13:00-15:00 | last_update 的日期 | 盘中快报(下午) | 下午盯盘 |
| 15:00-17:00 | last_update 的日期 | 盘后复盘 | 收盘后分析 |
| 17:00 后 | last_update 的日期 | 盘后分析 | 深度复盘 |

**重要**:
- 永远不触发 `daily.yml`(盘中数据反正也更新不了)
- 数据陈旧度 > 1 天会在日志中警告(不阻止运行)
- `data/last_update.txt` 缺失会回退到旧逻辑(17:00 切日期)

---

## 验证步骤

推送后,到 GitHub Actions 跑一次 `daily_report.yml` 验证:

1. 看 daily_report.py 启动日志里有没有:
   ```
   ℹ️ 数据为昨日 (...), 今天数据将在 22:00 北京前自动更新
   ```
   或
   ```
   ✅ 数据为今天
   ```

2. 看报告 markdown 标题是否带"盘前预判" / "盘后复盘" 等后缀

3. 手机 GitHub App 收到 daily_report 推送后,看 `app.py` 报告章节是否齐全

---

## 回滚方案

如果新逻辑出问题,回滚 1 个 commit 即可:

```bash
git revert HEAD~1..HEAD
# 或
git push origin main --force-with-lease  # 在 main 上硬回滚 (慎用)
```

或者在 GitHub 网页:`Commits` → 找到 `feat(smart-run)` 那条 → `Revert` 按钮。

---

## 相关文件

- `scripts/daily_report.py` — 主报告生成器
- `scripts/smart_run.py` — 智能 wrapper
- `data/last_update.txt` — 数据陈旧度标记(由 `scripts/update_data.py:189` 写入)
- `scripts/update_data.py` — 数据拉取主入口
- `.github/workflows/daily.yml` — 北京 17:00 + 20:00 数据更新

---

## 后续可优化(暂不做)

1. `app.py` 报告页加时段标签(盘前/盘中/盘后)
2. 推送报告到 Telegram 时带时段后缀
3. 盘中模式单独拉取实时行情(独立于 daily.yml)
4. 持仓信号章节在盘中模式下用更短窗口(60 日线 → 20 日线)
