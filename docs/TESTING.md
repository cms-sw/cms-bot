# Adding Tests to process_pr

## Quick Start

### 1. Create Test Data

Create a JSON file in `PRActionData/<test_name>/Issue_<number>.json`:

```json
{
  "id": 1,
  "number": 1,
  "title": "Test PR title",
  "body": "PR description",
  "state": "open",
  "created_at": "2024-01-01T00:00:00Z",
  "user": {"login": "author"},
  "labels": [],
  "comments": [
    {
      "id": 101,
      "body": "+1",
      "user": {"login": "l2_user"},
      "created_at": "2024-01-01T01:00:00Z"
    }
  ]
}
```

### 2. Create PR Data (if testing a PR)

Create `PRActionData/<test_name>/PullRequest_<number>.json`:

```json
{
  "number": 1,
  "state": "open",
  "draft": false,
  "mergeable": true,
  "base": {"ref": "master"},
  "head": {"sha": "abc123", "ref": "feature-branch"},
  "commits": [
    {"sha": "abc123", "message": "Initial commit"}
  ],
  "files": [
    {"filename": "src/Module/file.cc", "status": "modified"}
  ]
}
```

### 3. Write the Test

```python
class TestMyFeature:
    def test_my_scenario(self, repo_config, record_mode):
        # Setup
        init_l2_data(repo_config)
        recorder = ActionRecorder("test_my_scenario", record_mode)
        gh = MockGithub("test_my_scenario", recorder)
        repo = MockRepository("test_my_scenario", recorder=recorder)
        issue = MockIssue("test_my_scenario", number=1, recorder=recorder)
        
        # Execute
        result = process_pr(
            repo_config=repo_config,
            gh=gh,
            repo=repo,
            issue=issue,
            dry_run=True,
        )
        
        # Verify
        assert result["categories"]["my-category"] == "approved"
        
        # Save or verify recorded actions
        if record_mode:
            recorder.save()
        else:
            recorder.verify()
```

### 4. Record Expected Actions

Run once in record mode to capture expected actions:

```bash
pytest test_process_pr_v2.py::TestMyFeature::test_my_scenario --record-actions
```

This creates `PRActionData/test_my_scenario/actions.json`.

### 5. Run in Verify Mode

```bash
pytest test_process_pr_v2.py::TestMyFeature::test_my_scenario
```

## Helper Functions

### create_basic_pr_data()

Creates minimal test data files:

```python
create_basic_pr_data(
    "test_name",
    pr_number=1,
    author="author",
    files=[{"filename": "src/File.cc", "status": "modified"}],
    comments=[{"id": 101, "body": "+1", "user": "l2_user"}],
)
```

### Simple Unit Tests

For testing pure functions, use `MagicMock` directly:

```python
def test_simple_function(self):
    context = MagicMock(spec=PRContext)
    context.pr = MagicMock()
    context.pr.draft = False
    
    result = my_function(context)
    assert result == expected
```

## Test Categories

| Type | When to Use | Example |
|------|-------------|---------|
| Integration | Full process_pr flow | Approval, merge, test triggers |
| Unit | Single function | Parsing, validation |
| Mock-based | No JSON data needed | Simple logic tests |

## Common Patterns

### Testing Commands

```python
comments=[
    {"id": 101, "body": "test workflows 1,2,3", "user": "tester"}
]
```

### Testing Bot Messages

Check `result["messages"]` or verify `create_comment` actions in recorder.

### Testing Labels

Check `result["labels"]` or verify `add_to_labels` actions.

## Running Tests

```bash
# All tests
pytest test_process_pr_v2.py

# Specific test
pytest test_process_pr_v2.py::TestMyFeature::test_my_scenario

# With verbose output
pytest test_process_pr_v2.py -v

# Record mode
pytest test_process_pr_v2.py --record-actions
```
