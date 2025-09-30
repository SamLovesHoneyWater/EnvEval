# Batch Dockerfile Evaluator

This script systematically evaluates all Dockerfiles for a given repository across all models and providers, creating two complementary report structures.

## Overview

The batch evaluator creates **two types of reports**:

1. **reports-by-model/** - Individual detailed reports organized by model (mirrors ENVGYM-baseline structure)
2. **reports-by-repo/** - Comparative summaries organized by repository

## Directory Structure

After running evaluations, you'll have:

```
benchmark/
├── ENVGYM-baseline/           # Source dockerfiles
│   ├── claude/
│   │   ├── claude35haiku/
│   │   │   └── facebook_zstd/
│   │   │       └── envgym.dockerfile
│   │   └── claudeopus4/
│   ├── codex/
│   └── ours/
├── reports-by-model/          # Individual reports (mirrors baseline)
│   ├── claude/
│   │   ├── claude35haiku/
│   │   │   └── facebook_zstd/
│   │   │       └── evaluation_report.json
│   │   └── claudeopus4/
│   ├── codex/
│   └── ours/
└── reports-by-repo/           # Comparative summaries
    ├── facebook_zstd_summary.json
    ├── facebook_zstd_comparison.txt
    ├── nlohmann_json_summary.json
    └── nlohmann_json_comparison.txt
```

## Usage Examples

### Basic Usage
```bash
# Evaluate all dockerfiles for facebook_zstd
python batch_evaluate.py --repo facebook_zstd
```

### Skip Existing Reports
```bash
# Skip already-evaluated dockerfiles (useful for incremental runs)
python batch_evaluate.py --repo facebook_zstd --skip-existing
```

### Summary Only
```bash
# Create only the repository summary (assumes individual reports exist)
python batch_evaluate.py --repo facebook_zstd --summary-only
```

### Custom Directories
```bash
# Use custom directories
python batch_evaluate.py --repo facebook_zstd \
    --baseline-dir ./ENVGYM-baseline \
    --reports-by-model-dir ./my-model-reports \
    --reports-by-repo-dir ./my-repo-summaries
```

### Verbose Output
```bash
# Enable verbose output for debugging
python batch_evaluate.py --repo facebook_zstd --verbose
```

## Report Formats

### Individual Model Reports (reports-by-model/)

Each `evaluation_report.json` contains detailed test results (same format as DockerfileEvaluator.py):

```json
{
  "repo": "facebook_zstd",
  "dockerfile": "ENVGYM-baseline/claude/claude35haiku/facebook_zstd/envgym.dockerfile",
  "summary": {
    "total_tests": 28,
    "passed_tests": 19,
    "total_score": 39,
    "max_score": 46,
    "success_rate": 0.678,
    "total_execution_time": 92.39
  },
  "test_results": [ ... ]
}
```

### Repository Summary (reports-by-repo/)

#### JSON Summary (`{repo}_summary.json`)
```json
{
  "repository": "facebook_zstd",
  "timestamp": "2025-09-30T10:30:00",
  "total_models_evaluated": 12,
  "best_performer": {
    "model": "ours-claude/opus4",
    "total_score": 45,
    "max_score": 46,
    "success_rate": 0.98
  },
  "model_comparison": [ ... ]
}
```

#### Human-Readable Table (`{repo}_comparison.txt`)
```
Repository: facebook_zstd
================================================================================

Model                     Score        Success %  Time (s)   Tests     
--------------------------------------------------------------------------------
ours-claude/opus4         45/46        97.8%      87.2       45/46     
claude/claude35haiku      39/46        67.9%      92.4       31/46     
codex/gpt41              38/46        65.2%      78.9       30/46     
codex/gpt41mini          35/46        60.9%      82.1       28/46     
...

Best Performer: ours-claude/opus4 (Score: 45/46, Success: 97.8%)
```

## Workflow Examples

### Evaluate Multiple Repositories
```bash
# Evaluate several repositories
for repo in facebook_zstd nlohmann_json simdjson_simdjson; do
    python batch_evaluate.py --repo $repo --skip-existing
done
```

### Quick Comparison
```bash
# After evaluations, view the comparison table
cat reports-by-repo/facebook_zstd_comparison.txt
```

### Find Best Performers
```bash
# Find best performing model across all repos
grep "Best Performer" reports-by-repo/*_comparison.txt
```

## Key Features

- ✅ **Comprehensive**: Finds all dockerfiles for a repo automatically
- ✅ **Organized**: Two complementary report structures
- ✅ **Efficient**: Skip existing reports for incremental runs
- ✅ **Flexible**: Summary-only mode for quick updates
- ✅ **Readable**: Both JSON and human-readable table formats
- ✅ **Robust**: Uses existing DockerfileEvaluator.py (no code duplication)

## Integration with Existing Tools

The batch evaluator is designed to work seamlessly with the existing `DockerfileEvaluator.py`:

- Same rubric format (`rubrics/{repo}.json`)
- Same evaluation methodology
- Same detailed report format
- Adds organizational structure and comparative analysis