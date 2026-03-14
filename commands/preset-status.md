---
description: "Show config, ownership, last push info"
---

Read `.preset-toolkit/config.yaml` and show a quick summary:
1. Workspace URL, dashboard name, dashboard ID, sync folder
2. Last push fingerprint (from `.preset-toolkit/.last-push-fingerprint` if exists)
3. Whether ownership is configured (check `.preset-toolkit/ownership.yaml`)
4. Git status for uncommitted changes in the sync folder
