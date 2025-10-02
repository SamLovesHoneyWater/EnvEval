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
            ["docker", "ps", "-a", "--filter", f"name=eval_{repo_name}_", "--format", "{{.Names}}"],
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


def run_evaluation(dockerfile_path: str, repo_name: str, report_path: str, verbose: bool = False) -> bool:
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
        print(f"Running: {' '.join(cmd)}")
    
    try:
        # Run the evaluation with UTF-8 encoding to handle Unicode characters
        result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
        
        if result.returncode == 0:
            print(f"SUCCESS: Successfully evaluated: {dockerfile_path}")
            print(f"  Report saved to: {report_path}")
            return True
        else:
            print(f"FAIL: Failed to evaluate: {dockerfile_path}")
            if verbose:
                print(f"  STDOUT: {result.stdout}")
                print(f"  STDERR: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"ERROR: Error evaluating {dockerfile_path}: {e}")
        return False


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
                'total_score': summary.get('total_score', 0),
                'max_score': summary.get('max_score', 0),
                'success_rate': summary.get('success_rate', 0.0),
                'total_time': summary.get('total_execution_time', 0.0),
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
    
    # Create output directory
    os.makedirs(reports_by_repo_dir, exist_ok=True)
    
    # Save JSON summary
    json_path = Path(reports_by_repo_dir) / f"{repo_name}_summary.json"
    with open(json_path, 'w') as f:
        json.dump(summary_report, f, indent=2)
    
    # Create human-readable table
    table_path = Path(reports_by_repo_dir) / f"{repo_name}_comparison.txt"
    with open(table_path, 'w') as f:
        f.write(f"Repository: {repo_name}\n")
        f.write("=" * 80 + "\n\n")
        
        # Table header
        f.write(f"{'Model':<25} {'Score':<12} {'Success %':<10} {'Time (s)':<10} {'Tests':<10}\n")
        f.write("-" * 80 + "\n")
        
        # Table rows
        for data in model_data:
            score_str = f"{data['total_score']}/{data['max_score']}"
            success_pct = f"{data['success_rate']:.1%}"
            time_str = f"{data['total_time']:.1f}"
            tests_str = f"{data['passed_tests']}/{data['total_tests']}"
            
            f.write(f"{data['model']:<25} {score_str:<12} {success_pct:<10} {time_str:<10} {tests_str:<10}\n")
        
        f.write("\n")
        if model_data:
            best = model_data[0]
            f.write(f"Best Performer: {best['model']} ")
            f.write(f"(Score: {best['total_score']}/{best['max_score']}, ")
            f.write(f"Success: {best['success_rate']:.1%})\n")
    
    print(f"SUCCESS: Created repo summary: {json_path}")
    print(f"SUCCESS: Created comparison table: {table_path}")
    return True


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
        if run_evaluation(dockerfile_path, args.repo, report_path, args.verbose):
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
        print(f"Repository summary: {args.reports_by_repo_dir}/{args.repo}_summary.json")
        print(f"Comparison table: {args.reports_by_repo_dir}/{args.repo}_comparison.txt")
    
    # Exit with appropriate code
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()