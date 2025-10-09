# EnvEval Benchmark

Evaluation framework for machine-generated Dockerfiles that validates environment setup through automated testing.

## Overview

EnvEval consists of two main tools:
1. **DockerfileEvaluator.py** - Evaluates individual Dockerfiles using JSON-based rubrics
2. **batch_evaluate.py** - Batch evaluates multiple Dockerfiles and generates comparison reports

The evaluation process builds Docker containers from provided Dockerfiles and runs comprehensive tests inside them to validate the environment setup.

## Features

- **Multiple Test Types**: Supports 7 different types of tests
- **Dependency Management**: Tests can depend on other tests passing first
- **Flexible Scoring**: Each test can have custom scores (default 1) for different importance levels
- **Detailed Reporting**: JSON output with execution times and detailed results
- **Clean Resource Management**: Automatically cleans up Docker images after evaluation

## Supported Test Types

1. **`commands_exist`**: Check if commands are available
2. **`envvar_set`**: Check if an environment variable is set
3. **`dirs_exist`**: Check if directories exist
4. **`files_exist`**: Check if files exist
5. **`file_contains`**: Check if a file contains specific strings
6. **`run_command`**: Run a command and check if it succeeds
7. **`output_contains`**: Run a command and check if output contains specific strings

## Usage

```bash
python DockerfileEvaluator.py --dockerfile artifacts/example.dockerfile --repo example --output reports/example_report.json --verbose
```

## Command Line Arguments

- `--dockerfile` (required): Path to the Dockerfile to evaluate
- `--repo` (required): Repository name (used to find rubric file)
- `--rubric` (optional): Path to custom rubric JSON file (default: `rubrics/<repo>.json`)
- `--output` (optional): Path to save evaluation report JSON
- `--skip-warnings` (optional): Skip user confirmation prompts for potentially destructive operations
- `--verbose` (optional): Enable detailed output

## Rubric JSON Format

The rubric file should follow this structure:

```json
{
  "repo": "project_name",
  "tests": [
    {
      "id": "unique_test_id",
      "type": "test_type",
      "params": {
        "parameter": "value"
      },
      "timeout": 30,
      "score": 2,
      "requires": ["dependency_test_id"]
    }
  ]
}
```

### Common Test Properties

- **`id`** (optional): Unique identifier for the test, used for dependencies
- **`type`** (required): The type of test to run
- **`params`** (required): Test-specific parameters
- **`timeout`** (optional): Maximum execution time in seconds (default: 30)
- **`score`** (optional): Points awarded for passing this test (default: 1)
- **`requires`** (optional): Array of test IDs that must pass before this test runs

### Test Parameters by Type

#### `commands_exist`
```json
{
  "type": "commands_exist",
  "params": {
    "names": ["java", "javac"]
  },
  "score": 2
}
```

#### `output_contains`
```json
{
  "type": "output_contains",
  "params": {
    "command": "java -version",
    "contains": ["11", "17", "21"]
  },
  "timeout": 10,
  "score": 1
}
```

#### `files_exist`
```json
{
  "type": "files_exist",
  "params": {
    "paths": [
      "/path/to/file"
    ]
  }
}
```

#### `dirs_exist`
```json
{
  "type": "dirs_exist",
  "params": {
    "paths": [
      "/path/to/directory"
    ]
  }
}
```

#### `envvar_set`
```json
{
  "type": "envvar_set",
  "params": {
    "name": "JAVA_HOME"
  }
}
```

#### `file_contains`
```json
{
  "type": "file_contains",
  "params": {
    "path": "/path/to/file",
    "contains": ["text1", "text2"]
  }
}
```

#### `run_command`
```json
{
  "type": "run_command",
  "params": {
    "command": "npm --version"
  },
  "timeout": 60
}
```

## Test Dependencies

Tests can depend on other tests using the `requires` field:

```json
{
  "id": "check_java",
  "type": "commands_exist",
  "params": {"names": ["java"]}
},
{
  "type": "output_contains",
  "params": {
    "command": "java -version",
    "contains": ["11"]
  },
  "requires": ["check_java"]
}
```

## Output Format

The script generates a comprehensive JSON report:

```json
{
  "repo": "project_name",
  "dockerfile": "/path/to/Dockerfile",
  "rubric": "/path/to/rubric.json",
  "build_log": {
    "command": "docker build -t eval_project:latest -f /path/to/Dockerfile /build/context",
    "dockerfile_path": "/path/to/Dockerfile",
    "build_context": "/build/context",
    "scenario": "scenario_1",
    "repo_data_exists": true,
    "build_success": true,
    "build_stdout": "...",
    "build_stderr": "...",
    "build_returncode": 0,
    "build_timeout": false,
    "error_message": null
  },
  "summary": {
    "total_tests": 5,
    "passed_tests": 4,
    "failed_tests": 1,
    "total_score": 4,
    "max_score": 5,
    "success_rate": 0.8,
    "total_execution_time": 15.3
  },
  "test_results": [
    {
      "test_id": "check_java",
      "test_type": "commands_exist",
      "passed": 1,
      "score": 1,
      "message": "All commands found: java",
      "execution_time": 0.5
    }
  ]
}
```

## Batch Evaluation

The `batch_evaluate.py` script automates the evaluation of multiple Dockerfiles for a given repository, creating organized reports for comparison across different models.

### Usage

```bash
# Evaluate all dockerfiles for a repository
python batch_evaluate.py --repo facebook_zstd

# Skip existing reports to avoid re-evaluation
python batch_evaluate.py --repo facebook_zstd --skip-existing

# Only generate repository summary from existing reports
python batch_evaluate.py --repo facebook_zstd --summary-only

# Use custom directories
python batch_evaluate.py --repo facebook_zstd --baseline-dir ./ENVGYM-baseline --reports-by-model-dir ./my-reports
```

### Command Line Arguments

- `--repo` (required): Repository name to evaluate
- `--baseline-dir` (optional): Path to ENVGYM-baseline directory (default: "ENVGYM-baseline")
- `--reports-by-model-dir` (optional): Directory for individual model reports (default: "reports-by-model")
- `--reports-by-repo-dir` (optional): Directory for repository summary reports (default: "reports-by-repo")
- `--skip-existing` (optional): Skip evaluation if report already exists
- `--summary-only` (optional): Only create repo summary, skip individual evaluations
- `--skip-warnings` (optional): Skip user confirmation prompts for potentially destructive operations
- `--verbose` (optional): Enable verbose output

### Output Structure

The batch evaluator creates two types of reports:

#### 1. Individual Model Reports (`reports-by-model/`)
Mirrors the ENVGYM-baseline directory structure:
```
reports-by-model/
├── claude/
│   └── claude35haiku/
│       └── facebook_zstd/
│           └── evaluation_report.json
├── codex/
│   └── gpt4.1/
│       └── facebook_zstd/
│           └── evaluation_report.json
└── ours/
    └── claude/
        └── 35haiku/
            └── facebook_zstd/
                └── evaluation_report.json
```

#### 2. Repository Summary Reports (`reports-by-repo/`)
Comparative analysis across all models for a repository:
```
reports-by-repo/
├── facebook_zstd_summary.json       # Detailed JSON comparison
└── facebook_zstd_comparison.txt     # Human-readable table
```


## Requirements

- Python 3.7+
- Docker installed and accessible via command line
- Docker daemon running

## Example

See `rubrics/example.json` for a sample rubric file and `artifacts/example.dockerfile` for a sample Dockerfile.

### Quick Start

1. Create a rubric file for your repository in `rubrics/<repo_name>.json`
2. Place your source code in `data/<repo_name>/`
3. Run the evaluator:
   ```bash
   python DockerfileEvaluator.py --dockerfile artifacts/example.dockerfile --repo example --output reports/example_report.json --verbose
   ```
4. For batch evaluation:
   ```bash
   python batch_evaluate.py --repo example --verbose
   ```

## Error Handling

- **Build Failures**: If Docker build fails, no tests are run
- **Build Timeout**: Docker builds timeout after 60 minutes (3600 seconds)
- **Command Timeout**: Individual test commands have configurable timeouts (default: 30 seconds)
- **Dependency Resolution**: Tests with unresolvable dependencies are marked as failed
- **Resource Cleanup**: Docker images and containers are always cleaned up, even on failure

## Exit Codes

- `0`: All tests passed
- `1`: Some tests failed or evaluation error
- `130`: Interrupted by user (Ctrl+C)
