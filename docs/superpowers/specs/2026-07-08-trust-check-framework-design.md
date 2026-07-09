# 量化回测系统 — 检查框架设计文档

> 四阶段串行审批制。共29项检查，全部通过才能进入历史盘回测。

---

## 一、框架概述

阶段一A: 前视偏差防线 (6项)
阶段一B: 结构性过拟合防线 (5项)
阶段二: 工程实现精确性 (6项)
阶段三: 策略筛选与合理性 (8项)

核心规则: 每阶段全部通过才能进入下一阶段，任何一项不通过则停止并报告。

---

## 二、阶段一A: 前视偏差防线 (6项)

### A1 - Purging gap 合规
遍历每步计算 train_end 到 test_start 的实际交易日数，min_gap >= 3 则 PASS。

### A2 - Embargo 语义正确
在 walkforward 中记录 embargo 日志，验证排除区间为 [prev_test_end, prev_test_end + embargo_days]。

### A3 - HMM 无前视拟合
记录 fit_predict 和 select_optimal_n_states 的日期范围，验证均 <= train_end。

### A4 - 标准化仅基于历史
Scaler 每步新建，fit 数据范围 <= train_end。

### A5 - 测试集仅用一次
遍历区间对检查重叠。

### A6 - 信号计算无 T+0 偏差
权重计算和应用之间至少隔 1 个交易日。

---

## 三、阶段一B: 结构性过拟合防线 (5项)

### B1 - 成本模型 >= 真实下限
stamp_duty > 0, commission_rate >= 0.00025, slippage_bps >= 2.0

### B2 - Walk-Forward 步数 >= 3
n_steps >= 3

### B3 - 策略池多样性 >= 2
策略数 >= 2 且权重相关系数 < 0.7

### B4 - 随机种子敏感性
3 个种子重跑，Sharpe 标准差 < 0.3

### B5 - 参数敏感性初步扫描
purge_days/step_months 网格，Sharpe 波动 < 0.5

---

## 四、阶段二: 工程实现精确性 (6项)

### C1 - 单元测试通过
### C2 - 数据清洗对齐
### C3 - 数据清洗质量
### C4 - 运行时干净
### C5 - 数据源完整性
### C6 - 边缘情况覆盖

---

## 五、阶段三: 策略筛选与合理性 (8项)

### D1 - DSR p < 0.05
### D2 - PBO < 0.3
### D3 - 参数敏感性深化
### D4 - CPCV 正收益 > 50%
### D5 - Sharpe < 2.5
### D6 - Builder 决策合理
### D7 - Critic 无系统性误判
### D8 - Meta-Learner 合理

---

## 六、模式与成本

| 模式 | 成本 | 场景 |
|------|------|------|
| dev | 10-15s | 日常开发 |
| full | 40-50s | 提交前 |
| final | 90-120s | 历史盘前 |

---

## 七、依赖清单

- WalkForwardBacktester: 已有
- walkforward.py 修改: 需要
- RollingHMMDetector 修改: 需要
- main.py 修改: 需要
- tests/test_edge_cases.py: 需要创建
