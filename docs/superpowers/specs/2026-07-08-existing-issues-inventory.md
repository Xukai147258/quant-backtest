# 现有自动化框架问题清单

> 基于对当前代码库、GitHub 配置和 CI/CD 状态的全面审查。
> 共 12 个问题，按 P0-P3 排列。

---

## P0: 阻塞性问题（必须优先修复）

### P0-1: CI 持续 failure 无人响应

**ID**: CI-001
**文件**: .github/workflows/test.yml
**影响**: 所有分支、所有提交

**现象**:
- GitHub Actions 最近 5 次运行全部 failure（master 和 task 分支均如此）
- 本地 49 个测试全部通过，CI 却失败 — CI 环境与本地环境不一致
- 没有人发现或处理 CI 失败

**原因分析**（需确认）:
1. CI 运行在 ubuntu-latest，本地是 Windows — 路径、编码差异
2. requirements.txt 中缺少某个依赖
3. CI 中 pip install 后版本与本地不一致

**修复建议**:
1. 在 CI workflow 中加入 python -c 验证关键依赖安装
2. 添加 pytest.ini 或 setup.cfg 锁定测试行为
3. 将 pip install 改为 pip install -r requirements.txt --upgrade

---

### P0-2: Embargo 实现语义错误

**ID**: WKF-001
**文件**: engine/walkforward.py:92-96
**影响**: 所有回测结果

**现象**:
- 注释写: "T1: Embargo exclusion - exclude [prev_test_end, prev_test_end + embargo]"
- 代码实现:
  embargo_start = train_end_date - timedelta(days=self.embargo_days)
  embargo_end = train_end_date - timedelta(days=1)
- 排除的是 [train_end - embargo, train_end - 1]，不是 [prev_test_end, prev_test_end + embargo]
- 注释和代码矛盾，Embargo 实际未生效

**影响分析**:
- 实际效果: 在 train_end 附近又做了一次 Purging
- 预期效果: 排除上一轮测试期之后的一段时间（防序列相关污染）
- Embargo 完全没有生效

**修复建议**:
- 将排除区间改为基于 prev_test_end:
  embargo_start = prev_test_end_date
  embargo_end = prev_test_end_date + timedelta(days=self.embargo_days)

---

## P1: 高优先级

### P1-1: CI 触发条件有漏洞

**ID**: CI-002
**文件**: .github/workflows/test.yml

**现象**:
on:
  push: [ '**' ]
  pull_request: [ master, main ]
- 远程分支是 origin/master 和 origin/task/*，没有 main 分支
- PR 到 task 分支不会触发 CI

**影响**: task 分支之间的 PR 不会被 CI 检查

**修复建议**: 将 pull_request 改为 [master] 或 [ '**' ]

---

### P1-2: 分支命名与规范不一致

**ID**: GIT-001
**文件**: CONTRIBUTING.md

**现象**:
- 规范规定 feat/fix/refactor/docs/chore 前缀
- 实际使用 task/ 前缀
- 当前分支: task/10-fix-data-pipeline

**修复建议**: 统一规范与实际使用

---

### P1-3: master 与 origin/master 分叉

**ID**: GIT-002

**现象**:
- master: 0d482ab
- origin/master: 3b5d769
- master 领先 origin/master 2 个 commit

**修复建议**: git push origin master

---

### P1-4: 成本模型 stamp_duty = 0

**ID**: COST-001
**文件**: core/cost.py

**现象**:
- stamp_duty 默认值为 0.0
- A 股卖出印花税实际为万分之五（减半征收后）

**影响**: 每次卖出交易成本被低估 0.05%，收益被系统性高估

**修复建议**: 默认值改为 0.0005，或在 main.py 传入

---

## P2: 中优先级

### P2-1: 测试空文件

**ID**: TEST-001
**文件**: tests/test_critic.py, tests/test_meta_learner.py

**现象**: 两个文件只有一行注释，pytest 不会报错但 coverage 显示为 0

**修复建议**: 删除这两个空文件

---

### P2-2: 无边缘情况测试

**ID**: TEST-002
**文件**: tests/

**现象**: 没有 test_edge_cases.py，49 个测试全部针对正常路径

**修复建议**: 创建 test_edge_cases.py，覆盖 >= 3 种边缘场景

---

### P2-3: 无代码覆盖率

**ID**: CI-003
**文件**: .github/workflows/test.yml

**现象**: 没有集成 coverage

**修复建议**: 加入 coverage run -m pytest 和 coverage report

---

### P2-4: .gitignore 有遗漏

**ID**: GIT-003
**文件**: .gitignore

**现象**: 工作区有 _patch_main.py 等 untracked 文件

**修复建议**: 加入 _patch_*.py trust_check_report/

---

## P3: 低优先级

### P3-1: CHANGELOG 已知问题过时

**ID**: DOC-001
**文件**: CHANGELOG.md

**现象**:
- Embargo 标记为 P2 实际是 P0 bug
- sentiment.py 已有真实数据，不再为 stub

**修复建议**: 更新 CHANGELOG.md

---

### P3-2: 工作区有临时调试文件

**ID**: GIT-004

**现象**: 根目录有 _patch_main.py, _patch_wf.py 等 untracked 文件

**修复建议**: 清理不需要的文件，保留的 commit

---

## 汇总

| 优先级 | 数量 | 问题 ID |
|--------|------|---------|
| P0 | 2 | CI-001, WKF-001 |
| P1 | 4 | CI-002, GIT-001, GIT-002, COST-001 |
| P2 | 4 | TEST-001, TEST-002, CI-003, GIT-003 |
| P3 | 2 | DOC-001, GIT-004 |
| 总计 | 12 | |
