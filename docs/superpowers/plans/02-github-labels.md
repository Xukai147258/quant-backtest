# Task: GitHub Labels Setup

> **For agentic workers:** This is a standalone project management task. Create GitHub labels for the quant-backtest repository via API.

**Goal:** Create a standard set of GitHub labels on https://github.com/Xukai147258/quant-backtest for issue triage and prioritization.

**Authentication:** Use the GitHub Personal Access Token (classic) stored in git config:
`ash
git config --global --get github.token
`
Or passed directly. Token has epo scope.

**Labels to create:**

Priority labels (color: #e99695 for P0/P1, #fef2c0 for P2, #bfdadc for P3):
| Name | Color | Description |
|------|-------|-------------|
| P0 | e99695 | Blocker: must fix immediately |
| P1 | e99695 | Critical: should fix this iteration |
| P2 | fef2c0 | Important: should fix this quarter |
| P3 | bfdadc | Nice to have: when time permits |

Category labels:
| Name | Color | Description |
|------|-------|-------------|
| bug | d73a4a | Something isn't working |
| enhancement | a2eeef | New feature or request |
| tech-debt | 7057ff | Code quality improvement |
| testing | 0075ca | Test coverage or test infra |
| documentation | 0075ca | Docs or comments |

---

**API endpoint:** POST https://api.github.com/repos/Xukai147258/quant-backtest/labels

**Example:**
`ash
curl -H \"Authorization: Bearer \\" \
  -H \"Accept: application/vnd.github.v3+json\" \
  https://api.github.com/repos/Xukai147258/quant-backtest/labels \
  -d '{\"name\":\"P0\",\"color\":\"e99695\",\"description\":\"Blocker: must fix immediately\"}'
`

**Steps:**
- [ ] Create all 8 labels via GitHub API
- [ ] Verify labels appear on the repository Issues page
- [ ] Commit nothing (this is a GitHub settings change, not a code change)

**Verification:** GET https://api.github.com/repos/Xukai147258/quant-backtest/labels returns all 8 labels.
