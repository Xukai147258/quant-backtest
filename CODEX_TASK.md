# AI 量化回测系统 - Codex 实施任务

## 上下文

你正在帮助一位有 AI/ML 背景的用户构建中长期 ETF 组合优化系统。
当前阶段：已完成概念验证（3 层系统），发现 8 个方法论文缺陷，需要从头重构。

## 工作目录

D:\桌面\

## 现有资产

- `akshare_demo.py` — AKShare 数据获取（可用）
- `akshare_stock.py` — 备选接口
- `backtest_demo.py` — Backtrader SMA/布林带回测
- `portfolio_backtest.py` — 6 种组合优化方法
- `regime_detection.py` — HMM 市场状态识别
- `sentiment_final.py` — 情绪 × HMM 双重信号
- `akshare_output/` — 基金/ETF 数据
- `portfolio_output/` — 回测结果
- `regime_output/` — HMM 状态数据
- `sentiment_output/` — 情绪分析数据

## 完整计划

见 C:\Users\Xukai\.claude\plans\majestic-soaring-karp.md

## 环境

- Python 3.13 (Anaconda: D:\ANACONDA\envs\PythonProject\)
- 已安装: akshare, pandas, numpy, scipy, backtrader, hmmlearn, snownlp, transformers
- GPU: RTX 5060 8GB (PyTorch 当前为 CPU 版)
- 数据源: AKShare (东方财富/新浪), 中文字体支持

## 你的任务

按照计划文件的 5 个 Phase 实施：

### Phase 1: 知识库（今天先做这个）
在 D:\桌面\knowledge\ 下创建 3 个文件：
1. `backtesting_checklist.md` — 每次回测前批判Agent使用的检查清单（覆盖所有 8 个陷阱 + Lopez de Prado 7 宗罪）
2. `literature_notes.md` — Purging/Embargo/CPCV/PBO/DeflatedSharpe 核心定义 + 公式
3. `framework_comparison.md` — Qlib/vnpy/Backtrader/Zipline 优缺点对比

### Phase 2-5: 核心代码（后续逐步）
按计划文件 Part E 的路线图，从数据管线 → 回测引擎 → 双Agent → 验证

## 关键约束

1. 滚动回测必须严格 Walk-Forward，使用 Expanding Window
2. 所有特征计算/标准化只依赖当前可用的历史数据
3. HMM 每次滚动重训，不用全局数据
4. Purging gap ≥ 5 个交易日
5. 成本模型包含：佣金(万2.5) + 滑点(2bp) + 冲击成本(sqrt model)
6. 评估指标必须包含 Deflated Sharpe Ratio 和 PBO
