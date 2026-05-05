#!/usr/bin/env python3
"""
Local CI/CD Pipeline Simulator
Runs the complete quality gate locally (without GitHub Actions)

Usage:
    python simulate_cicd.py [--threshold 0.85]
"""

import os
import sys
import time
import subprocess
from datetime import datetime
import argparse

class CICDSimulator:
    def __init__(self, threshold=0.85):
        self.threshold = threshold
        self.start_time = None
        self.steps = []
        self.passed = True

    def log_step(self, step_name, status, message=""):
        """Log a pipeline step with status."""
        timestamp = datetime.now().strftime('%H:%M:%S')
        status_icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "🔄"

        print(f"[{timestamp}] {status_icon} {step_name}")
        if message:
            print(f"         {message}")

        self.steps.append({
            "name": step_name,
            "status": status,
            "message": message,
            "timestamp": timestamp
        })

        if status == "FAIL":
            self.passed = False

    def run_command(self, command, step_name, cwd=None):
        """Run a shell command and log the result."""
        try:
            print(f"\n🔄 {step_name}...")
            result = subprocess.run(
                command,
                shell=True,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )

            if result.returncode == 0:
                self.log_step(step_name, "PASS", "Command executed successfully")
                if result.stdout.strip():
                    print(f"         Output: {result.stdout.strip()[:100]}...")
                return True
            else:
                self.log_step(step_name, "FAIL", f"Command failed: {result.stderr.strip()}")
                return False

        except subprocess.TimeoutExpired:
            self.log_step(step_name, "FAIL", "Command timed out")
            return False
        except Exception as e:
            self.log_step(step_name, "FAIL", f"Command error: {str(e)}")
            return False

    def check_prerequisites(self):
        """Check if all prerequisites are met."""
        print("🔍 Checking prerequisites...")

        # Check if Docker is available
        if not self.run_command("docker --version", "Check Docker"):
            return False

        # Check if Docker Compose is available
        if not self.run_command("docker compose version", "Check Docker Compose"):
            return False

        # Check if Python files exist
        required_files = ["ci_eval.py", "run_comprehensive_tests.py", "requirements.txt", "docker-compose.yaml"]
        for file in required_files:
            if not os.path.exists(file):
                self.log_step(f"Check {file}", "FAIL", f"File not found: {file}")
                return False

        self.log_step("Prerequisites Check", "PASS", "All requirements satisfied")
        return True

    def build_containers(self):
        """Build and start Docker containers."""
        print("\n🐳 Building Docker containers...")

        # Build containers
        if not self.run_command("docker compose build --no-cache", "Build Containers"):
            return False

        # Start containers
        if not self.run_command("docker compose up -d", "Start Containers"):
            return False

        # Wait for services to be healthy
        print("⏳ Waiting for services to be healthy...")
        time.sleep(10)  # Give containers time to start

        # Check API health
        max_retries = 12  # 2 minutes
        for i in range(max_retries):
            try:
                result = subprocess.run(
                    ["curl", "-f", "http://localhost:8000/health"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                if result.returncode == 0:
                    self.log_step("API Health Check", "PASS", "API is responding")
                    break
            except:
                pass

            if i == max_retries - 1:
                self.log_step("API Health Check", "FAIL", "API failed to respond")
                return False

            time.sleep(10)

        # Check ChromaDB health
        try:
            result = subprocess.run(
                ["curl", "-f", "http://localhost:8001/api/v1/heartbeat"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                self.log_step("ChromaDB Health Check", "PASS", "ChromaDB is responding")
            else:
                self.log_step("ChromaDB Health Check", "FAIL", "ChromaDB not responding")
                return False
        except:
            self.log_step("ChromaDB Health Check", "FAIL", "ChromaDB connection failed")
            return False

        return True

    def run_api_tests(self):
        """Run comprehensive API tests."""
        print("\n🧪 Running API functionality tests...")
        return self.run_command("python run_comprehensive_tests.py", "API Tests")

    def run_quality_evaluation(self):
        """Run the quality evaluation gate."""
        print(f"\n🤖 Running Quality Evaluation (Threshold: {self.threshold})...")

        # Set environment variables
        env = os.environ.copy()
        env["API_BASE_URL"] = "http://localhost:8000"
        env["TEST_DATASET"] = "test_dataset.json"

        # Run evaluation
        try:
            result = subprocess.run(
                [sys.executable, "ci_eval.py", "--threshold", str(self.threshold), "--verbose"],
                env=env,
                capture_output=True,
                text=True,
                timeout=600  # 10 minute timeout for evaluation
            )

            if result.returncode == 0:
                self.log_step("Quality Evaluation", "PASS", "Agent meets quality standards")
                print(f"         {result.stdout.strip()}")
                return True
            else:
                self.log_step("Quality Evaluation", "FAIL", f"Agent below quality threshold: {result.stdout.strip()}")
                return False

        except subprocess.TimeoutExpired:
            self.log_step("Quality Evaluation", "FAIL", "Evaluation timed out")
            return False
        except Exception as e:
            self.log_step("Quality Evaluation", "FAIL", f"Evaluation error: {str(e)}")
            return False

    def cleanup(self):
        """Clean up containers and resources."""
        print("\n🧹 Cleaning up...")
        self.run_command("docker compose down -v", "Cleanup Containers")
        self.run_command("docker system prune -f", "System Cleanup")

    def generate_report(self):
        """Generate a final report."""
        duration = time.time() - self.start_time if self.start_time else 0

        print("\n" + "=" * 80)
        print("📊 CI/CD PIPELINE EXECUTION REPORT")
        print("=" * 80)
        print(f"⏱️  Total Duration: {duration:.1f} seconds")
        print(f"🎯 Quality Threshold: {self.threshold}")
        print(f"📈 Overall Result: {'✅ PASSED' if self.passed else '❌ FAILED'}")
        print()

        print("📋 Pipeline Steps:")
        for step in self.steps:
            status_icon = "✅" if step["status"] == "PASS" else "❌"
            print(f"   {status_icon} {step['name']}")

        print("\n" + "=" * 80)

        if self.passed:
            print("🎉 SUCCESS: Agent passed all quality gates!")
            print("🚀 Ready for production deployment.")
        else:
            print("💥 FAILURE: Agent failed quality evaluation!")
            print("🔧 Please review and improve the RAG system.")
            print("💡 Check the logs above for specific failure reasons.")

    def run_pipeline(self):
        """Run the complete CI/CD pipeline."""
        self.start_time = time.time()

        print("=" * 80)
        print("🚀 LOCAL CI/CD PIPELINE SIMULATION")
        print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🎯 Quality Threshold: {self.threshold}")
        print("=" * 80)

        try:
            # Step 1: Prerequisites
            if not self.check_prerequisites():
                return

            # Step 2: Build containers
            if not self.build_containers():
                return

            # Step 3: API tests
            if not self.run_api_tests():
                return

            # Step 4: Quality evaluation (the main gate)
            if not self.run_quality_evaluation():
                return

        finally:
            # Always cleanup
            self.cleanup()

            # Generate report
            self.generate_report()

def main():
    parser = argparse.ArgumentParser(description="Local CI/CD Pipeline Simulator")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Quality threshold for PASS/FAIL (default: 0.85)"
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Skip cleanup (leave containers running)"
    )

    args = parser.parse_args()

    # Check if required environment variables are set
    if "GROQ_API_KEY" not in os.environ:
        print("❌ GROQ_API_KEY environment variable not set!")
        print("   Please set it with: export GROQ_API_KEY=your_key_here")
        sys.exit(1)

    # Run the pipeline
    simulator = CICDSimulator(threshold=args.threshold)

    # Override cleanup if requested
    if args.no_cleanup:
        original_cleanup = simulator.cleanup
        simulator.cleanup = lambda: None

    simulator.run_pipeline()

    # Exit with appropriate code
    sys.exit(0 if simulator.passed else 1)

if __name__ == "__main__":
    main()