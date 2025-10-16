#!/usr/bin/env python3
"""
Batch Dockerfile Evaluator

Finds all dockerfiles for a given repo and evaluates them systematically,
creating two report structures:
1. reports-by-model/ - Mirrors ENVGYM-baseline structure for individual reports
2. reports-by-repo/ - Summary tables comparing all models per repository

Usage:
    python batch_evaluate.py --repo facebook_zstd
    python batch_evaluate.py --repo facebook_zstd --baseline-dir ./ENVGYM-baseline
    python batch_evaluate.py --repo facebook_zstd --skip-existing
"""

import argparse
import subprocess
import json
import os
import sys
import csv
from pathlib import Path
from typing import List, Tuple, Dict, Any


def find_dockerfiles(repo_name: str, baseline_dir: str = "ENVGYM-baseline") -> List[Tuple[str, str]]:
    """
    Find all envgym.dockerfile files for the given repo.
    
    Returns:
        List of tuples: (dockerfile_path, relative_path_from_baseline)
    """
    baseline_path = Path(baseline_dir)
    dockerfiles = []
    
    # Search for envgym.dockerfile files containing the repo name
    for dockerfile_path in baseline_path.rglob("envgym.dockerfile"):
        # Check if this dockerfile is for the target repo
        if repo_name in str(dockerfile_path):
            # Get relative path from baseline directory
            relative_path = dockerfile_path.relative_to(baseline_path)
            dockerfiles.append((str(dockerfile_path), str(relative_path)))
    
    return dockerfiles


def create_report_path(relative_dockerfile_path: str, reports_dir: str = "reports-by-model") -> str:
    """
    Create corresponding report path that mirrors the baseline structure.
    
    Args:
        relative_dockerfile_path: e.g., "claude/claude35haiku/facebook_zstd/envgym.dockerfile"
        reports_dir: Base reports directory
    
    Returns:
        Report path: e.g., "reports-by-model/claude/claude35haiku/facebook_zstd/evaluation_report.json"
    """
    # Replace envgym.dockerfile with evaluation_report.json
    path_parts = Path(relative_dockerfile_path).parts[:-1]  # Remove envgym.dockerfile
    report_path = Path(reports_dir) / Path(*path_parts) / "evaluation_report.json"
    return str(report_path)


def cleanup_docker_containers(repo_name: str) -> None:
    """Clean up any leftover Docker containers for this repo"""
    try:
        # Find and clean up any existing containers with this repo name
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", f"name=eval_{repo_name.lower()}_", "--format", "{{.Names}}"],
            capture_output=True, text=True, check=False
        )
        if result.stdout.strip():
            containers = result.stdout.strip().split('\n')
            for container in containers:
                if container.strip():
                    print(f"Cleaning up existing container: {container.strip()}")
                    subprocess.run(["docker", "stop", container.strip()], capture_output=True, check=False)
                    subprocess.run(["docker", "rm", container.strip()], capture_output=True, check=False)
    except Exception as e:
        print(f"Warning: Could not clean up containers: {e}")


def run_evaluation(dockerfile_path: str, repo_name: str, report_path: str, verbose: bool = False, skip_warnings: bool = False) -> bool:
    """
    Run DockerfileEvaluator.py on a single dockerfile.
    
    Returns:
        True if evaluation succeeded, False otherwise
    """
    # Create output directory if it doesn't exist
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    
    # Build command to run DockerfileEvaluator.py
    cmd = [
        sys.executable, "DockerfileEvaluator.py",
        "--dockerfile", dockerfile_path,
        "--repo", repo_name,
        "--output", report_path
    ]
    
    if verbose:
        cmd.append("--verbose")
    if skip_warnings:
        cmd.append("--skip-warnings")
        
    if verbose:
        print(f"Running: {' '.join(cmd)}")
    
    try:
        # Run the evaluation with UTF-8 encoding to handle Unicode characters
        # Add timeout slightly longer than DockerfileEvaluator's internal timeout (3600s + 300s buffer)
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=3900)
        
        if result.returncode == 0:
            # Check if the evaluation actually succeeded by inspecting the report
            if _validate_evaluation_success(report_path):
                print(f"SUCCESS: Successfully evaluated: {dockerfile_path}")
                print(f"  Report saved to: {report_path}")
                return True
            else:
                print(f"FAIL: Evaluation completed but failed (check report): {dockerfile_path}")
                if verbose:
                    print(f"  Report: {report_path}")
                return False
        else:
            print(f"FAIL: Failed to evaluate: {dockerfile_path}")
            if verbose:
                print(f"  STDOUT: {result.stdout}")
                print(f"  STDERR: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT: Evaluation timed out after 65 minutes: {dockerfile_path}")
        print(f"  This indicates the Docker build or evaluation process is stuck")
        return False
    except Exception as e:
        print(f"ERROR: Error evaluating {dockerfile_path}: {e}")
        return False


def _validate_evaluation_success(report_path: str) -> bool:
    """
    Validate that the evaluation actually succeeded by checking the report content.
    
    Returns:
        True if the evaluation was successful, False if it failed
    """
    try:
        if not os.path.exists(report_path):
            return False
            
        with open(report_path, 'r', encoding='utf-8') as f:
            report = json.load(f)
        
        # Check for build errors
        build_log = report.get('build_log', {})
        if 'error_message' in build_log:
            return False
        
        # Check total score - if it's zero or missing, consider it a failure
        summary = report.get('summary', {})
        total_score = summary.get('total_score', 0)
        
        # If total_score is 0 or not found, evaluation failed
        if total_score == 0:
            return False
        
        return True
        
    except Exception:
        # If we can't read or parse the report, consider it a failure
        return False


def _copy_model_reports(repo_reports: List[Path], reports_by_model_path: Path, models_dir: Path) -> None:
    """
    Copy individual model reports to models directory with flattened names.
    
    Args:
        repo_reports: List of report file paths
        reports_by_model_path: Base path for reports-by-model directory
        models_dir: Target models directory
    """
    for report_path in repo_reports:
        try:
            # Get relative path from reports-by-model to the report file
            relative_path = report_path.relative_to(reports_by_model_path)
            
            # Remove the filename (evaluation_report.json) and any envgym directory
            path_parts = list(relative_path.parts[:-1])  # Remove evaluation_report.json
            if path_parts and path_parts[-1] == "envgym":
                path_parts = path_parts[:-1]  # Remove envgym if present
            
            # Remove the repo name (last directory)
            if path_parts:
                path_parts = path_parts[:-1]
            
            # Join with dashes to create flattened model name
            if path_parts:
                model_name = "-".join(path_parts)
                flattened_name = f"{model_name}_report.json"
            else:
                flattened_name = "unknown_report.json"
            
            # Copy the report file
            target_path = models_dir / flattened_name
            import shutil
            shutil.copy2(report_path, target_path)
            
        except Exception as e:
            print(f"Warning: Could not copy report {report_path}: {e}")


def extract_model_info(relative_dockerfile_path: str) -> str:
    """
    Extract model identifier from dockerfile path.
    
    Args:
        relative_dockerfile_path: e.g., "claude/claude35haiku/facebook_zstd/envgym.dockerfile"
    
    Returns:
        Model identifier: e.g., "claude/claude35haiku"
    """
    path_parts = Path(relative_dockerfile_path).parts
    if len(path_parts) >= 3:
        # Handle both structures: provider/model/repo and provider/subprovider/model/repo
        if path_parts[0] == "ours" and len(path_parts) >= 4:
            # ours/claude/35haiku/repo -> "ours-claude/35haiku"
            return f"{path_parts[0]}-{path_parts[1]}/{path_parts[2]}"
        else:
            # claude/claude35haiku/repo -> "claude/claude35haiku"
            return f"{path_parts[0]}/{path_parts[1]}"
    return "unknown"


def create_repo_csv(repo_name: str, reports_by_model_dir: str = "reports-by-model",
                    reports_by_repo_dir: str = "reports-by-repo") -> bool:
    """
    Create a CSV file comparing test performance across all models for a repository.
    
    Args:
        repo_name: Repository name
        reports_by_model_dir: Directory containing individual model reports
        reports_by_repo_dir: Directory to save repo CSV
    
    Returns:
        True if CSV created successfully, False otherwise
    """
    # Find all evaluation reports for this repo
    reports_by_model_path = Path(reports_by_model_dir)
    repo_reports = list(reports_by_model_path.rglob(f"*/{repo_name}/evaluation_report.json"))
    repo_reports += list(reports_by_model_path.rglob(f"*/{repo_name}/envgym/evaluation_report.json"))
    
    if not repo_reports:
        print(f"No reports found for repository: {repo_name}")
        return False
    
    # Load the rubric to get test metadata and params
    rubric_path = Path(f"rubrics/{repo_name}.json")
    if not rubric_path.exists():
        raise FileNotFoundError(f"Rubric file not found: {rubric_path}")
    
    try:
        with open(rubric_path, 'r') as rf:
            rubric = json.load(rf)
    except Exception as e:
        raise ValueError(f"Failed to parse rubric file {rubric_path}: {e}")
    
    # Create mapping from test_id to rubric test info
    rubric_test_info = {}
    for test in rubric.get('tests', []):
        test_id = test.get('id', f"{test.get('type', 'unknown')}_{hash(str(test.get('params', {})))}")
        rubric_test_info[test_id] = {
            'test_type': test.get('type', ''),
            'max_score': test.get('score', 1),
            'params': json.dumps(test.get('params', {}), separators=(',', ':'))  # Compact JSON string
        }
    
    # Collect all test data from reports
    models_data: Dict[str, Dict[str, float]] = {}  # model_id -> {test_id -> score}
    all_test_ids: set = set()
    test_info: Dict[str, Dict[str, Any]] = {}  # test_id -> {test_type, max_score, params}
    
    for report_path in repo_reports:
        try:
            with open(report_path, 'r') as f:
                report = json.load(f)
            
            # Extract model info from path
            relative_path = report_path.relative_to(reports_by_model_path)
            model_id = extract_model_info(str(relative_path))
            
            # Extract test results
            test_results = report.get('test_results', [])
            models_data[model_id] = {}
            
            for test_result in test_results:
                test_id = test_result.get('test_id', '')
                test_type = test_result.get('test_type', '')
                score = test_result.get('score', 0)
                
                if test_id:
                    all_test_ids.add(test_id)
                    models_data[model_id][test_id] = score
                    
                    # Store test metadata from rubric
                    if test_id not in test_info:
                        if test_id in rubric_test_info:
                            test_info[test_id] = rubric_test_info[test_id]
                        else:
                            # Fallback if test_id not found in rubric
                            test_info[test_id] = {
                                'test_type': test_type,
                                'max_score': 1,
                                'params': '{}'  # Empty params
                            }
                        
        except Exception as e:
            print(f"Warning: Could not process report {report_path}: {e}")
            continue
    
    if not models_data or not all_test_ids:
        print(f"No valid test data found for repository: {repo_name}")
        return False
    
    # Sort test IDs and model IDs for consistent ordering
    sorted_test_ids = sorted(all_test_ids)
    sorted_model_ids = sorted(models_data.keys())
    
    # Create output directory structure
    repo_output_dir = Path(reports_by_repo_dir) / repo_name
    models_dir = repo_output_dir / "models"
    os.makedirs(models_dir, exist_ok=True)
    
    # Copy individual model reports to the models directory with flattened names
    _copy_model_reports(repo_reports, reports_by_model_path, models_dir)
    
    # Create CSV file
    csv_path = repo_output_dir / f"{repo_name}_test_comparison.csv"
    
    with open(csv_path, 'w', newline='', encoding='utf-8') as csvfile:
        # Prepare header
        fieldnames = ['test_id', 'test_type', 'max_score'] + sorted_model_ids + ['params']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        # Write data rows
        for test_id in sorted_test_ids:
            row = {
                'test_id': test_id,
                'test_type': test_info.get(test_id, {}).get('test_type', ''),
                'max_score': test_info.get(test_id, {}).get('max_score', 1),
                'params': test_info.get(test_id, {}).get('params', '{}')
            }
            
            # Add scores for each model (0 if test not found for that model)
            for model_id in sorted_model_ids:
                score = models_data.get(model_id, {}).get(test_id, 0)
                row[model_id] = round(score, 2) if isinstance(score, (int, float)) else score
            
            writer.writerow(row)
    
    print(f"SUCCESS: Created test comparison CSV: {csv_path}")
    return True


def create_repo_summary(repo_name: str, reports_by_model_dir: str = "reports-by-model", 
                       reports_by_repo_dir: str = "reports-by-repo") -> bool:
    """
    Create a summary report for a repository comparing all models.
    
    Args:
        repo_name: Repository name
        reports_by_model_dir: Directory containing individual model reports
        reports_by_repo_dir: Directory to save repo summary
    
    Returns:
        True if summary created successfully, False otherwise
    """
    # Find all evaluation reports for this repo
    reports_by_model_path = Path(reports_by_model_dir)
    repo_reports = list(reports_by_model_path.rglob(f"*/{repo_name}/evaluation_report.json"))
    repo_reports += list(reports_by_model_path.rglob(f"*/{repo_name}/envgym/evaluation_report.json"))
    print(f"Found {len(repo_reports)} reports for repository {repo_name}: {repo_reports}")
    
    if not repo_reports:
        print(f"No reports found for repository: {repo_name}")
        return False
    
    # Collect data from all reports
    model_data = []
    
    for report_path in repo_reports:
        try:
            with open(report_path, 'r') as f:
                report = json.load(f)
            
            # Extract model info from path
            relative_path = report_path.relative_to(reports_by_model_path)
            model_id = extract_model_info(str(relative_path))
            
            # Extract key metrics
            summary = report.get('summary', {})
            model_data.append({
                'model': model_id,
                'total_score': round(summary.get('total_score', 0), 2),
                'max_score': round(summary.get('max_score', 0), 2),
                'success_rate': round(summary.get('success_rate', 0.0), 4),
                'total_time': round(summary.get('total_execution_time', 0.0), 2),
                'passed_tests': summary.get('passed_tests', 0),
                'total_tests': summary.get('total_tests', 0)
            })
            
        except Exception as e:
            print(f"Warning: Could not process report {report_path}: {e}")
            continue
    
    if not model_data:
        print(f"No valid reports found for repository: {repo_name}")
        return False
    
    # Sort by total score (descending)
    model_data.sort(key=lambda x: x['total_score'], reverse=True)
    
    # Create summary report
    from datetime import datetime
    summary_report = {
        'repository': repo_name,
        'timestamp': datetime.now().isoformat(),
        'total_models_evaluated': len(model_data),
        'best_performer': model_data[0] if model_data else None,
        'model_comparison': model_data
    }
    
    # Create output directory structure
    repo_output_dir = Path(reports_by_repo_dir) / repo_name
    os.makedirs(repo_output_dir, exist_ok=True)
    
    # Save JSON summary
    json_path = repo_output_dir / f"{repo_name}_summary.json"
    with open(json_path, 'w') as f:
        json.dump(summary_report, f, indent=2)
    
    # Create markdown comparison table
    table_path = repo_output_dir / f"{repo_name}_comparison.md"
    with open(table_path, 'w') as f:
        f.write(f"# Repository: {repo_name}\n\n")
        
        # Markdown table header
        f.write("| Model | Score | Success % | Time (s) | Tests |\n")
        f.write("|-------|-------|-----------|----------|-------|\n")
        
        # Table rows
        for data in model_data:
            score_str = f"{data['total_score']}/{data['max_score']}"
            success_pct = f"{data['success_rate']:.1%}"
            time_str = f"{data['total_time']:.1f}"
            tests_str = f"{data['passed_tests']}/{data['total_tests']}"
            
            f.write(f"| {data['model']} | {score_str} | {success_pct} | {time_str} | {tests_str} |\n")
        
        f.write("\n")
        if model_data:
            best = model_data[0]
            f.write(f"**Best Performer:** {best['model']} ")
            f.write(f"(Score: {best['total_score']}/{best['max_score']}, ")
            f.write(f"Success: {best['success_rate']:.1%})\n")
    
    # Create CSV comparison
    csv_success = create_repo_csv(repo_name, reports_by_model_dir, reports_by_repo_dir)
    
    print(f"SUCCESS: Created repo summary: {json_path}")
    print(f"SUCCESS: Created comparison table (markdown): {table_path}")
    return True and csv_success


def main():
    parser = argparse.ArgumentParser(description="Batch evaluate Dockerfiles for a repository")
    parser.add_argument("--repo", required=True, help="Repository name to evaluate")
    parser.add_argument("--baseline-dir", default="ENVGYM-baseline", 
                       help="Path to ENVGYM-baseline directory")
    parser.add_argument("--reports-by-model-dir", default="reports-by-model",
                       help="Directory to store individual model reports (mirrors baseline structure)")
    parser.add_argument("--reports-by-repo-dir", default="reports-by-repo",
                       help="Directory to store repository summary reports")
    parser.add_argument("--skip-existing", action="store_true",
                       help="Skip evaluation if report already exists")
    parser.add_argument("--summary-only", action="store_true",
                       help="Only create repo summary (skip individual evaluations)")
    parser.add_argument("--skip-warnings", action="store_true",
                       help="Skip user confirmation prompts for potentially destructive operations, turn on with caution!")
    parser.add_argument("--verbose", action="store_true", 
                       help="Enable verbose output")
    
    args = parser.parse_args()
    
    print(f"Batch evaluation for repository: {args.repo}")
    print(f"Baseline directory: {args.baseline_dir}")
    print(f"Reports by model: {args.reports_by_model_dir}")
    print(f"Reports by repo: {args.reports_by_repo_dir}")
    print("-" * 60)
    
    # If summary-only mode, just create the repo summary
    if args.summary_only:
        print("Creating repository summary from existing reports...")
        success = create_repo_summary(args.repo, args.reports_by_model_dir, args.reports_by_repo_dir)
        sys.exit(0 if success else 1)
    
    # Find all dockerfiles for the repo
    dockerfiles = find_dockerfiles(args.repo, args.baseline_dir)
    
    if not dockerfiles:
        print(f"No dockerfiles found for repository: {args.repo}")
        sys.exit(1)
    
    print(f"Found {len(dockerfiles)} dockerfiles for {args.repo}:")
    for dockerfile_path, relative_path in dockerfiles:
        print(f"  {relative_path}")
    print()
    
    # Clean up any existing Docker containers for this repo before starting
    print(f"Cleaning up any existing Docker containers for {args.repo}...")
    cleanup_docker_containers(args.repo)
    
    # Run evaluations
    successful = 0
    skipped = 0
    failed = 0
    
    for dockerfile_path, relative_path in dockerfiles:
        # Create corresponding report path
        report_path = create_report_path(relative_path, args.reports_by_model_dir)
        
        # Check if report already exists
        if args.skip_existing and os.path.exists(report_path):
            print(f"⏭ Skipping (report exists): {relative_path}")
            skipped += 1
            continue
        
        # Run evaluation
        print(f"🔄 Evaluating: {relative_path}")
        if run_evaluation(dockerfile_path, args.repo, report_path, args.verbose, args.skip_warnings):
            successful += 1
        else:
            failed += 1
        print()
    
    # Create repository summary
    print("Creating repository summary...")
    summary_success = create_repo_summary(args.repo, args.reports_by_model_dir, args.reports_by_repo_dir)
    
    # Print summary
    print("=" * 60)
    print("BATCH EVALUATION SUMMARY")
    print("=" * 60)
    print(f"Repository: {args.repo}")
    print(f"Total dockerfiles: {len(dockerfiles)}")
    print(f"Successful evaluations: {successful}")
    print(f"Failed evaluations: {failed}")
    print(f"Skipped evaluations: {skipped}")
    
    if successful > 0:
        print(f"\nIndividual reports: {args.reports_by_model_dir}/")
        print("(Directory structure mirrors ENVGYM-baseline)")
    
    if summary_success:
        print(f"Repository summary: {args.reports_by_repo_dir}/{args.repo}/{args.repo}_summary.json")
        print(f"Comparison table (markdown): {args.reports_by_repo_dir}/{args.repo}/{args.repo}_comparison.md")
        print(f"Test comparison CSV: {args.reports_by_repo_dir}/{args.repo}/{args.repo}_test_comparison.csv")
        print(f"Individual model reports: {args.reports_by_repo_dir}/{args.repo}/models/")
    
    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()