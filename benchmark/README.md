# SetupBench
Benchmark for Environment Setup

# Dockerfile Evaluation Script

The Python script evaluates machine-generated Dockerfiles using JSON-based rubrics. It builds Docker containers from Dockerfiles and runs tests inside them to validate the setup.

## Features

- **Multiple Test Types**: Supports 7 different types of tests
- **Dependency Management**: Tests can depend on other tests passing first
- **Flexible Scoring**: Each test can have custom scores (default 1) for different importance levels
- **Detailed Reporting**: JSON output with execution times and detailed results
- **Clean Resource Management**: Automatically cleans up Docker images after evaluation

## Supported Test Types

1. **`command_exists`**: Check if a command is available
2. **`envvar_set`**: Check if an environment variable is set
3. **`dirs_exist`**: Check if a directory exists
4. **`files_exist`**: Check if a file exists
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

#### `command_exists`
```json
{
  "type": "command_exists",
  "params": {
    "name": "java"
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
  "type": "command_exists",
  "params": {"name": "java"}
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
      "test_type": "command_exists",
      "passed": true,
      "score": 1,
      "message": "Command 'Java' found",
      "execution_time": 0.5
    }
  ]
}
```

## Requirements

- Python 3.7+
- Docker installed and accessible via command line
- Docker daemon running

## Example

See `example_usage.py` for a complete usage example and `rubrics/example.json` for a sample rubric file.

## Error Handling

- **Build Failures**: If Docker build fails, no tests are run
- **Timeout Handling**: Commands have configurable timeouts
- **Dependency Resolution**: Tests with unresolvable dependencies are marked as failed
- **Resource Cleanup**: Docker images are always cleaned up, even on failure

## Exit Codes

- `0`: All tests passed
- `1`: Some tests failed or evaluation error
- `130`: Interrupted by user (Ctrl+C)
