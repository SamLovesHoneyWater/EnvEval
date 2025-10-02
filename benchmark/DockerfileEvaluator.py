#!/usr/bin/env python3
"""
Dockerfile Evaluation Script

This script evaluates machine-generated Dockerfiles by:
1. Building the Docker container from the provided Dockerfile
2. Loading test specifications from a JSON rubric file
3. Running tests inside the container and scoring them (1 for pass, 0 for fail)

Usage:
    python DockerfileEvaluator.py --dockerfile <path> --repo <name> [--rubric <path>] [--output <path>] [--verbose]
"""

import argparse
import json
import subprocess
import sys
import tempfile
import time
import os
import re
import shutil
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestResult:
    """Represents the result of a single test"""
    test_id: str
    test_type: str
    n_passed: int
    score: float
    message: str
    execution_time: float
    n_tests: int = 1  # Default to 1 test per result


class DockerfileEvaluator:
    """Main class for evaluating Dockerfiles using JSON rubrics"""

    def __init__(self, repo_name: str, dockerfile_path: str, rubric_path: Optional[str] = None):
        self.repo_name = repo_name
        self.dockerfile_path = Path(dockerfile_path)
        self.rubric_path = Path(rubric_path) if rubric_path else Path(f"rubrics/{repo_name}.json")
        # Use more precise timestamp + random suffix to avoid conflicts
        import random
        timestamp = int(time.time() * 1000)  # milliseconds for better precision
        random_suffix = random.randint(1000, 9999)
        self.container_name = f"eval_{repo_name}_{timestamp}_{random_suffix}"
        self.image_name = f"eval_{repo_name}:latest"
        self.results: List[TestResult] = []
        self.tests: List[Dict[str, Any]] = []
        
    def load_rubric(self) -> Dict[str, Any]:
        """Load and parse the JSON rubric file"""
        try:
            with open(self.rubric_path, 'r') as f:
                rubric = json.load(f)
            print(f"Loaded rubric for repo: {rubric.get('repo', 'unknown')}")
            return rubric
        except FileNotFoundError:
            print(f"Error: Rubric file not found: {self.rubric_path}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in rubric file: {e}")
            sys.exit(1)
    
    def build_docker_image(self) -> bool:
        """Build Docker image from the provided Dockerfile"""
        print(f"Building Docker image: {self.image_name}")
        
        # Check if there's source code in data/{repo} directory
        repo_data_path = Path(f"data/{self.repo_name}")
        copied_repo_path = None
        copied_dockerfile_path = None
        
        try:
            # Get dockerfile directory
            dockerfile_dir = self.dockerfile_path.parent
            
            # Copy repo directory to dockerfile directory if it exists
            if repo_data_path.exists() and repo_data_path.is_dir():
                print(f"Found source code directory: {repo_data_path}")
                
                # Create the nested structure:
                # folder/
                # └── repo_name/
                #     ├── repo files...
                #     ├── envgym.dockerfile
                #     └── repo_name/
                #         └── repo files...
                
                # Define destination path in dockerfile directory
                copied_repo_path = dockerfile_dir / self.repo_name
                
                # Remove existing directory if it exists
                if copied_repo_path.exists():
                    shutil.rmtree(copied_repo_path)
                
                # Copy the entire repo directory to the outer repo_name folder
                shutil.copytree(repo_data_path, copied_repo_path)
                print(f"Copied {repo_data_path} to {copied_repo_path}")
                
                # Create nested repo directory inside the copied repo directory
                nested_repo_path = copied_repo_path / self.repo_name
                shutil.copytree(repo_data_path, nested_repo_path)
                print(f"Created nested repo structure at {nested_repo_path}")
                
                # Copy dockerfile into the repo directory
                copied_dockerfile_path = copied_repo_path / self.dockerfile_path.name
                shutil.copy2(self.dockerfile_path, copied_dockerfile_path)
                print(f"Copied dockerfile to {copied_dockerfile_path}")
                
            else:
                if not repo_data_path.exists():
                    raise FileNotFoundError(f"Error: Source code directory not found at {repo_data_path}. Please check that the repo parameter '{self.repo_name}' is correct.")
            
            # Use the copied dockerfile
            dockerfile_to_use = str(copied_dockerfile_path)
            
            # Set build context to the copied repo directory
            build_context = str(copied_repo_path)
            
            cmd = [
                "docker", "build", 
                "-t", self.image_name,
                "-f", dockerfile_to_use,
                build_context
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
            
            if result.returncode == 0:
                print("PASS: Docker image built successfully")
                return True
            else:
                print(f"FAIL: Failed to build Docker image:")
                print(f"STDOUT: {result.stdout}")
                print(f"STDERR: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            print("FAIL: Docker build timed out (10 minutes)")
            return False
        except Exception as e:
            print(f"FAIL: Error building Docker image: {e}")
            return False
        finally:
            # Clean up copied repo directory and dockerfile
            if copied_repo_path and copied_repo_path.exists():
                try:
                    shutil.rmtree(copied_repo_path)
                    print(f"Cleaned up copied repo directory: {copied_repo_path}")
                except Exception as e:
                    print(f"Warning: Could not clean up copied repo directory: {e}")
            
            # Note: copied_dockerfile_path cleanup is handled by removing the parent directory
    
    def run_docker_command(self, command: str, timeout: int = -1) -> tuple[bool, str, str]:
        """Run a command inside the Docker container"""
        try:
            cmd = [
                "docker", "run", "--rm",
                "--name", f"{self.container_name}_temp",
                self.image_name,
                "sh", "-c", command
            ]
            if timeout != -1:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=timeout
            )
            else:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
            )            
            success = result.returncode == 0
            return success, result.stdout, result.stderr
            
        except subprocess.TimeoutExpired:
            return False, "", f"Command timed out ({timeout}s)"
        except Exception as e:
            return False, "", str(e)
    
    def test_commands_exist(self, test: Dict[str, Any]) -> TestResult:
        """Test if commands exist in the container with proportional scoring"""
        start_time = time.time()
        params = test.get('params', {})
        command_names = params.get('names', [])
        test_id = test.get('id', f"commands_exist_{hash(tuple(command_names))}")
        
        if not command_names:
            execution_time = time.time() - start_time
            return TestResult(test_id, "commands_exist", 0, 0, 
                            "No commands specified", execution_time)
        
        found_commands = []
        missing_commands = []
        
        for command_name in command_names:
            success, stdout, stderr = self.run_docker_command(f"command -v {command_name}")
            if success and stdout.strip() != "":
                found_commands.append(command_name)
            else:
                missing_commands.append(command_name)
        
        execution_time = time.time() - start_time
        score = test.get('score', 1) * (len(found_commands) / len(command_names))
        n_passed = len(found_commands)
        
        if n_passed == len(command_names):
            message = f"All commands found: {', '.join(found_commands)}"
        elif found_commands:
            message = f"Found {len(found_commands)}/{len(command_names)} commands. Found: {', '.join(found_commands)}. Missing: {', '.join(missing_commands)}"
        else:
            message = f"No commands found. Missing: {', '.join(missing_commands)}"
        
        return TestResult(test_id, "commands_exist", n_passed, score, message, execution_time, n_tests=len(command_names))
    
    def test_output_contains(self, test: Dict[str, Any]) -> TestResult:
        """Test if command output contains specific strings"""
        start_time = time.time()
        params = test.get('params', {})
        command = params.get('command', '')
        contains_list = params.get('contains', [])
        timeout = test.get('timeout', 30)
        test_id = test.get('id', f"output_contains_{hash(command)}")
        test_score = test.get('score', 1)
        
        success, stdout, stderr = self.run_docker_command(command, timeout)
        
        execution_time = time.time() - start_time
        
        # Check if any of the required strings are in the output
        output_text = stdout + stderr
        found_matches = [item for item in contains_list if str(item) in output_text]
        n_passed = int(len(found_matches) > 0)
        score = test_score if n_passed else 0
        
        '''
        # Truncate output for logging (first 200 chars)
        output_preview = output_text.replace('\n', ' ').strip()[:200]
        if len(output_text) > 200:
            output_preview += "..."
        '''
        
        if n_passed:
            message = f"Output contains: {', '.join(map(str, found_matches))}."
        else:
            message = f"Output does not contain any of: {', '.join(map(str, contains_list))}. Command output: {output_text}"
        
        return TestResult(test_id, "output_contains", n_passed, score, message, execution_time)
    
    def test_files_exist(self, test: Dict[str, Any]) -> TestResult:
        """Test if files exist in the container"""
        start_time = time.time()
        params = test.get('params', {})
        file_paths = params.get('paths', [])
        test_id = test.get('id', f"files_exist_{hash(tuple(file_paths))}")
        test_score = test.get('score', 1)

        found_files = []
        missing_files = []
        
        for file_path in file_paths:
            success, stdout, stderr = self.run_docker_command(f"test -f '{file_path}'")
            if success:
                found_files.append(file_path)
            else:
                missing_files.append(file_path)
        
        execution_time = time.time() - start_time
        n_passed = len(found_files)
        score = test_score * (n_passed / len(file_paths)) if file_paths else 0
        
        if n_passed == len(file_paths):
            message = f"All files found: {', '.join(found_files)}"
        elif found_files:
            message = f"Found {len(found_files)}/{len(file_paths)} files. Found: {', '.join(found_files)}. Missing: {', '.join(missing_files)}"
        else:
            message = f"No files found. Missing: {', '.join(missing_files)}"

        return TestResult(test_id, "files_exist", n_passed, score, message, execution_time, n_tests=len(file_paths))

    def test_dirs_exist(self, test: Dict[str, Any]) -> TestResult:
        """Test if a directory exists in the container"""
        start_time = time.time()
        params = test.get('params', {})
        dir_paths = params.get('paths', [])
        test_id = test.get('id', f"dirs_exist_{hash(tuple(dir_paths))}")
        test_score = test.get('score', 1)

        found_dirs = []
        missing_dirs = []
        
        for dir_path in dir_paths:
            success, stdout, stderr = self.run_docker_command(f"test -d '{dir_path}'")
            if success:
                found_dirs.append(dir_path)
            else:
                missing_dirs.append(dir_path)
        
        execution_time = time.time() - start_time
        n_passed = len(found_dirs)
        score = test_score * (n_passed / len(dir_paths)) if dir_paths else 0
        
        if n_passed == len(dir_paths):
            message = f"All directories found: {', '.join(found_dirs)}"
        elif found_dirs:
            message = f"Found {len(found_dirs)}/{len(dir_paths)} directories. Found: {', '.join(found_dirs)}. Missing: {', '.join(missing_dirs)}"
        else:
            message = f"No directories found. Missing: {', '.join(missing_dirs)}"

        return TestResult(test_id, "dirs_exist", n_passed, score, message, execution_time, n_tests=len(dir_paths))

    def test_envvar_set(self, test: Dict[str, Any]) -> TestResult:
        """Test if an environment variable is set"""
        start_time = time.time()
        params = test.get('params', {})
        var_name = params.get('name', '')
        test_id = test.get('id', f"envvar_set_{var_name}")
        test_score = test.get('score', 1)
        
        success, stdout, stderr = self.run_docker_command(f"test -n \"${var_name}\"")
        
        execution_time = time.time() - start_time
        passed = success
        score = test_score if passed else 0
        message = f"Environment variable '{var_name}' {'is set' if passed else 'is not set'}"
        
        return TestResult(test_id, "envvar_set", passed, score, message, execution_time)
    
    def test_file_contains(self, test: Dict[str, Any]) -> TestResult:
        """Test if a file contains specific strings"""
        start_time = time.time()
        params = test.get('params', {})
        file_path = params.get('path', '')
        contains_list = params.get('contains', [])
        test_id = test.get('id', f"file_contains_{hash(file_path)}")
        test_score = test.get('score', 1)
        
        # First check if file exists
        success, stdout, stderr = self.run_docker_command(f"test -f '{file_path}'")
        if not success:
            execution_time = time.time() - start_time
            return TestResult(test_id, "file_contains", False, 0, 
                            f"File '{file_path}' does not exist", execution_time)
        
        # Read file content
        success, stdout, stderr = self.run_docker_command(f"cat '{file_path}'")
        execution_time = time.time() - start_time
        
        if not success:
            return TestResult(test_id, "file_contains", 0, 0, 
                            f"Could not read file '{file_path}': {stderr}", execution_time)
        
        # Check if any of the required strings are in the file
        file_content = stdout
        found_matches = [item for item in contains_list if str(item) in file_content]
        passed = len(found_matches) > 0
        score = test_score if passed else 0
        
        if passed:
            message = f"File contains: {', '.join(map(str, found_matches))}"
        else:
            message = f"File does not contain any of: {', '.join(map(str, contains_list))}"
        
        return TestResult(test_id, "file_contains", int(passed), score, message, execution_time)
    
    def test_run_command(self, test: Dict[str, Any]) -> TestResult:
        """Test if a command runs successfully"""
        start_time = time.time()
        params = test.get('params', {})
        command = params.get('command', '')
        timeout = test.get('timeout', 30)
        test_id = test.get('id', f"run_command_{hash(command)}")
        test_score = test.get('score', 1)
        
        success, stdout, stderr = self.run_docker_command(command, timeout)
        
        execution_time = time.time() - start_time
        passed = success
        score = test_score if passed else 0
        
        # Truncate output for logging (first 200 chars)
        output_text = stdout + stderr
        '''
        output_preview = output_text.replace('\n', ' ').strip()[:200]
        if len(output_text) > 200:
            output_preview += "..."
        '''
        
        if passed:
            message = f"Command executed successfully."
        else:
            message = f"Command failed. Output: {output_text}"
        
        return TestResult(test_id, "run_command", int(passed), score, message, execution_time)
    
    def can_run_test(self, test: Dict[str, Any], completed_tests: Dict[str, TestResult]) -> bool:
        """Check if a test's requirements are met"""
        requires = test.get('requires', [])
        if not requires:
            return True
        
        for req_id in requires:
            if req_id not in completed_tests or not completed_tests[req_id].n_passed:
                return False
        return True
    
    def run_single_test(self, test: Dict[str, Any]) -> TestResult:
        """Run a single test based on its type"""
        test_type = test.get('type', '')
        
        test_methods = {
            'commands_exist': self.test_commands_exist,
            'output_contains': self.test_output_contains,
            'files_exist': self.test_files_exist,
            'dirs_exist': self.test_dirs_exist,
            'envvar_set': self.test_envvar_set,
            'file_contains': self.test_file_contains,
            'run_command': self.test_run_command,
        }
        
        if test_type in test_methods:
            return test_methods[test_type](test)
        else:
            test_id = test.get('id', f"unknown_{hash(str(test))}")
            return TestResult(test_id, test_type, False, 0, 
                            f"Unknown test type: {test_type}", 0.0)
    
    def run_tests(self, tests: List[Dict[str, Any]]) -> List[TestResult]:
        """Run all tests, respecting dependencies"""
        completed_tests: Dict[str, TestResult] = {}
        remaining_tests = tests.copy()
        max_iterations = len(tests) * 2  # Prevent infinite loops
        iteration = 0
        
        while remaining_tests and iteration < max_iterations:
            iteration += 1
            tests_to_remove = []
            
            for i, test in enumerate(remaining_tests):
                if self.can_run_test(test, completed_tests):
                    print(f"Running test: {test.get('type', 'unknown')}")
                    result = self.run_single_test(test)
                    self.results.append(result)
                    completed_tests[result.test_id] = result
                    tests_to_remove.append(i)
                    
                    # Print result
                    status = "✓" if result.n_passed else "✗"
                    print(f"  {status} {result.message} ({result.execution_time:.2f}s)")
            
            # Remove completed tests (in reverse order to maintain indices)
            for i in reversed(tests_to_remove):
                remaining_tests.pop(i)
            
            # If no tests were completed in this iteration, we have unresolvable dependencies
            if not tests_to_remove and remaining_tests:
                print("Warning: Some tests have unresolvable dependencies:")
                for test in remaining_tests:
                    test_id = test.get('id', f"unknown_{hash(str(test))}")
                    requires = test.get('requires', [])
                    result = TestResult(test_id, test.get('type', 'unknown'), False, 0,
                                      f"Unresolvable dependencies: {requires}", 0.0)
                    self.results.append(result)
                break
        
        return self.results
    
    def cleanup(self):
        """Clean up Docker resources"""
        try:
            # Stop and remove any containers with our name pattern
            subprocess.run(["docker", "stop", self.container_name], 
                         capture_output=True, check=False)
            subprocess.run(["docker", "rm", self.container_name], 
                         capture_output=True, check=False)
            
            # Also clean up any leftover containers from previous runs
            result = subprocess.run(["docker", "ps", "-a", "--filter", f"name=eval_{self.repo_name}_", "--format", "{{.Names}}"], 
                                  capture_output=True, text=True, check=False)
            if result.stdout.strip():
                leftover_containers = result.stdout.strip().split('\n')
                for container in leftover_containers:
                    if container.strip():
                        subprocess.run(["docker", "stop", container.strip()], capture_output=True, check=False)
                        subprocess.run(["docker", "rm", container.strip()], capture_output=True, check=False)
                        print(f"Cleaned up leftover container: {container.strip()}")
            
            # Remove image
            subprocess.run(["docker", "rmi", self.image_name], 
                         capture_output=True, check=False)
            print(f"Cleaned up Docker resources for: {self.repo_name}")
        except Exception as e:
            print(f"Warning: Could not clean up Docker resources: {e}")
    
    def generate_report(self) -> Dict[str, Any]:
        """Generate a summary report of all test results"""
        total_tests = sum(r.n_tests for r in self.results)
        passed_tests = sum(r.n_passed for r in self.results)
        total_score = sum(r.score for r in self.results)
        max_score = sum(test.get('score', 1) for test in self.tests)
        total_time = sum(r.execution_time for r in self.results)
        
        report = {
            "repo": self.repo_name,
            "dockerfile": str(self.dockerfile_path),
            "rubric": str(self.rubric_path),
            "summary": {
                "total_tests": total_tests,
                "passed_tests": passed_tests,
                "failed_tests": total_tests - passed_tests,
                "total_score": total_score,
                "max_score": max_score,
                "success_rate": passed_tests / total_tests if total_tests > 0 else 0,
                "total_execution_time": total_time
            },
            "test_results": [
                {
                    "test_id": r.test_id,
                    "test_type": r.test_type,
                    "passed": r.n_passed,
                    "score": r.score,
                    "message": r.message,
                    "execution_time": r.execution_time
                }
                for r in self.results
            ]
        }
        
        return report
    
    def evaluate(self) -> Dict[str, Any]:
        """Main evaluation method"""
        print(f"Starting evaluation for repo: {self.repo_name}")
        print(f"Dockerfile: {self.dockerfile_path}")
        print(f"Rubric: {self.rubric_path}")
        print("-" * 50)
        
        # Load rubric
        rubric = self.load_rubric()
        tests = rubric.get('tests', [])
        self.tests = tests  # Store tests for report generation
        
        if not tests:
            print("No tests found in rubric")
            return self.generate_report()
        
        # Build Docker image
        if not self.build_docker_image():
            print("Failed to build Docker image, cannot run tests")
            return self.generate_report()
        
        try:
            # Run tests
            print(f"\nRunning {len(tests)} tests...")
            self.run_tests(tests)
            
            # Generate and return report
            return self.generate_report()
            
        finally:
            # Always cleanup
            self.cleanup()


def main():
    parser = argparse.ArgumentParser(description="Evaluate Dockerfiles using JSON rubrics")
    parser.add_argument("--dockerfile", required=True, help="Path to the Dockerfile to evaluate")
    parser.add_argument("--repo", required=True, help="Repository name")
    parser.add_argument("--rubric", help="Path to the rubric JSON file (default: rubrics/<repo>.json)")
    parser.add_argument("--output", help="Path to save the evaluation report JSON")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose output")
    
    args = parser.parse_args()
    
    # Create evaluator
    evaluator = DockerfileEvaluator(args.repo, args.dockerfile, args.rubric)

    try:
        # Run evaluation
        report = evaluator.evaluate()
        
        # Print summary
        print("\n" + "=" * 50)
        print("EVALUATION SUMMARY")
        print("=" * 50)
        summary = report["summary"]
        print(f"Repository: {report['repo']}")
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Passed: {summary['passed_tests']}")
        print(f"Failed: {summary['failed_tests']}")
        print(f"Score: {summary['total_score']}/{summary['max_score']}")
        print(f"Success Rate: {summary['success_rate']:.2%}")
        print(f"Total Time: {summary['total_execution_time']:.2f}s")
        
        # Save report if requested
        if args.output:
            with open(args.output, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\nReport saved to: {args.output}")
        
        # Print detailed results if verbose
        if args.verbose:
            print("\nDETAILED RESULTS:")
            print("-" * 50)
            for result in report["test_results"]:
                status = "PASS" if result["passed"] else "FAIL"
                print(f"{status} [{result['test_type']}] {result['message']} ({result['execution_time']:.2f}s)")
        
        # Exit with appropriate code
        sys.exit(0 if summary['failed_tests'] == 0 else 1)
        
    except KeyboardInterrupt:
        print("\nEvaluation interrupted by user")
        evaluator.cleanup()
        sys.exit(130)
    except Exception as e:
        print(f"Evaluation failed: {e}")
        evaluator.cleanup()
        sys.exit(1)


if __name__ == "__main__":
    main()
