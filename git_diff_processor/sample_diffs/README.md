# Sample Diffs Folder

This folder contains git diff files for testing the git diff processor.

## How to Create a Git Diff File

### Option 1: Diff between two commits
```bash
git diff commit1 commit2 > git_diff_processor/sample_diffs/diff_commit1.txt
```

### Option 2: Diff for a single commit
```bash
git show commit_hash > git_diff_processor/sample_diffs/diff_commit1.txt
```

### Option 3: Diff for uncommitted changes
```bash
git diff > git_diff_processor/sample_diffs/diff_uncommitted.txt
```

### Option 4: Diff between branches
```bash
git diff branch1 branch2 > git_diff_processor/sample_diffs/diff_branches.txt
```

## File Naming Convention

- `diff_commit1.txt` - First commit diff
- `diff_commit2.txt` - Second commit diff
- `diff_uncommitted.txt` - Uncommitted changes
- `diff_branches.txt` - Branch comparison

## Example Git Diff Format

The processor expects standard git unified diff format:

```diff
diff --git a/path/to/file.py b/path/to/file.py
index abc123..def456 100644
--- a/path/to/file.py
+++ b/path/to/file.py
@@ -10,6 +10,8 @@ def function_name():
+    # New line
     existing_code
+    return value
```

## Usage

Once you have a diff file, run:

```bash
python git_diff_processor/git_diff_processor.py sample_diffs/diff_commit1.txt
```

Or let it use the default:

```bash
python git_diff_processor/git_diff_processor.py
```
