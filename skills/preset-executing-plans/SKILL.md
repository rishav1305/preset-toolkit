---
name: preset-executing-plans
description: "Execute dashboard change plans with validation checkpoints at each step"
---

# Executing Plans

Execute a dashboard change plan step by step, running validation checkpoints at each stage. Stop and report at the first failure.

## Conversation Principles (MANDATORY)

**NEVER ask about:**
- Config formats, file paths, YAML structure, directory layout
- Which scripts to run, CLI flags, sync modes, technical parameters
- Auth methods, tokens, API endpoints, CSRF handling
- Git branches, merge strategies, commit messages
- Infrastructure, server details, environment setup

**ONLY ask about:**
- Business intent: "What change do you want to make?"
- Logic validation: "Revenue = Ads + Subs. Is that correct?"
- Data correctness: "The current value is $3M. Does that look right?"
- Visual specifics: "Should the label say 'X' or 'Y'?"
- Ownership clarity: "This tile is in Bob's section. Notify him?"
- Approval gates: "Here's what changes. Push it?"

## Prerequisites

```python
from scripts.config import ToolkitConfig
config = ToolkitConfig.discover()
```

A plan should exist from `preset-writing-plans` or the user's direct instructions. If no plan exists, suggest creating one first.

## Execution Protocol

### Before Starting

1. **Verify clean state:**
   ```bash
   git status --short -- <sync_folder>
   ```
   If there are uncommitted changes, ask: "There are uncommitted changes. Should I stash them before proceeding?"

2. **Record baseline fingerprint:**
   ```python
   from scripts.fingerprint import compute_fingerprint
   baseline_fp = compute_fingerprint(primary_dataset_yaml)
   ```

### For Each Step

Execute the planned change, then immediately run the checkpoint:

1. **Apply the change.** Use the safe YAML edit pattern for dataset SQL edits. Use direct file editing for chart YAMLs and dashboard CSS.

2. **YAML validity check:**
   ```python
   import yaml
   with open(edited_file) as f:
       yaml.safe_load(f)  # Must not raise
   ```
   If this fails, the edit broke the YAML structure. Revert and retry.

3. **Marker check:**
   ```python
   from scripts.fingerprint import check_markers
   result = check_markers(primary_dataset_yaml, markers_file)
   if not result.all_present:
       # STOP -- the edit removed required content
       print(f"Checkpoint FAILED: Missing markers: {result.missing}")
       # Revert the change
   ```

4. **Report step status:**
   ```
   Step X: <description>
     Status: PASS
     Markers: All present
     File: <which file was edited>
   ```

### If a Checkpoint Fails

Stop execution immediately. Report:

```
Execution stopped at Step X.

  Reason: <what failed>
  Last good state: Step X-1

  Options:
    1. Fix the issue and retry Step X
    2. Revert all changes and start over
    3. Abort the plan
```

Never silently continue past a failed checkpoint.

### Final Steps (After All Edits)

After all planned edits are applied and their checkpoints pass:

1. **Full validate:**
   ```bash
   sup sync validate <sync_folder>
   ```

2. **Complete marker check** across all dataset YAMLs (not just the primary one).

3. **Dry-run:**
   ```bash
   sup sync run <sync_folder> --push-only --dry-run --force
   ```

4. **Show summary and ask for push approval:**
   ```
   All steps completed successfully.

     Steps executed: X/X
     Markers: All present
     Validation: PASSED
     Dry-run: <output summary>

   Push these changes? (yes/no)
   ```

5. **If approved, push** -- invoke `preset-sync-push` with the appropriate mode.

6. **Post-push verification:**
   - Pull back and check markers
   - Capture screenshot
   - Compare against baseline screenshot
   - Report visual changes

7. **Git commit:**
   ```bash
   git add <sync_folder>/
   git commit -m "Sync: <plan description>"
   ```

## Rollback Protocol

If anything goes wrong during execution or after push:

1. **Before push (local changes only):**
   ```bash
   git stash  # Save current state just in case
   git checkout -- <sync_folder>/  # Restore from last commit
   ```

2. **After push (changes are on Preset):**
   - Restore local files from the last git commit
   - Re-push the restored state
   - Verify with pull-back

Never use `git checkout --` or `git restore` without first confirming with the user that uncommitted work can be discarded. Prefer `git stash` when in doubt.

## Progress Tracking

For multi-step plans, show progress after each step:

```
Progress: [====----] 4/8 steps

  Step 1: Update card title ............. PASS
  Step 2: Update formula ................ PASS
  Step 3: Add asterisk annotation ....... PASS
  Step 4: Update notes section .......... PASS
  Step 5: CSS spacing adjustment ........ (next)
  Step 6: Validate all .................. (pending)
  Step 7: Push .......................... (pending)
  Step 8: Verify + commit ............... (pending)
```
