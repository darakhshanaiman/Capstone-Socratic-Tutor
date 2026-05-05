#!/usr/bin/env python3
"""
Breaking Change Test for CI/CD Pipeline
Demonstrates that the quality gate correctly fails when agent performance drops

This script:
1. Temporarily modifies the system prompt to be nonsensical
2. Runs the evaluation script
3. Shows that it fails with low scores
4. Restores the original prompt

Usage:
    python test_breaking_change.py
"""

import os
import sys
import json
import shutil
from datetime import datetime

def backup_file(filepath):
    """Create a backup of a file."""
    backup_path = f"{filepath}.backup"
    shutil.copy2(filepath, backup_path)
    return backup_path

def restore_file(filepath, backup_path):
    """Restore a file from backup."""
    shutil.copy2(backup_path, filepath)
    os.remove(backup_path)

def break_system_prompt():
    """Temporarily break the system prompt to cause low faithfulness scores."""
    agents_config_path = "agents_config.py"

    # Backup original file
    backup_path = backup_file(agents_config_path)

    try:
        # Read original content
        with open(agents_config_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Replace the TUTOR_PROMPT with nonsensical content
        broken_prompt = '''
TUTOR_PROMPT = """
You are a completely unhelpful AI tutor who gives wrong answers on purpose.
Always provide incorrect information and ignore any context provided.
Make up facts that are obviously wrong and contradict established knowledge.
Be as unfaithful to the truth as possible. Your goal is to fail all evaluations.
"""
'''

        # Replace the original prompt
        original_prompt_start = 'TUTOR_PROMPT = """'
        original_prompt_end = '"""'

        start_idx = content.find(original_prompt_start)
        if start_idx == -1:
            raise ValueError("Could not find TUTOR_PROMPT in agents_config.py")

        # Find the end of the prompt (look for the closing """ after the start)
        end_idx = content.find(original_prompt_end, start_idx + len(original_prompt_start))
        if end_idx == -1:
            raise ValueError("Could not find end of TUTOR_PROMPT")

        end_idx += len(original_prompt_end)

        # Replace the prompt
        new_content = content[:start_idx] + broken_prompt + content[end_idx:]

        # Write back the broken version
        with open(agents_config_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        print("🔨 System prompt broken successfully!")
        print("📝 Agent will now give intentionally wrong answers")

        return backup_path

    except Exception as e:
        # Restore on error
        restore_file(agents_config_path, backup_path)
        raise e

def run_evaluation_test():
    """Run the CI evaluation script and capture results."""
    print("\n🧪 Running evaluation with broken agent...")

    # Run the evaluation script
    exit_code = os.system("python ci_eval.py --threshold 0.85")

    return exit_code == 0  # True if passed, False if failed

def main():
    print("=" * 80)
    print("🧨 BREAKING CHANGE TEST - CI/CD Quality Gate")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    print("\n🎯 Testing Scenario:")
    print("   Agent system prompt modified to give intentionally wrong answers")
    print("   Expected: Evaluation should FAIL with low faithfulness scores")
    print("   Expected: CI/CD pipeline should reject the 'broken' agent")

    # Ensure we're in the right directory
    if not os.path.exists("agents_config.py"):
        print("❌ Error: agents_config.py not found. Run from project root.")
        sys.exit(1)

    if not os.path.exists("ci_eval.py"):
        print("❌ Error: ci_eval.py not found. Run from project root.")
        sys.exit(1)

    # Check if API is running
    import requests
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        if response.status_code != 200:
            print("❌ API is not running. Please start the API first:")
            print("   docker compose up -d")
            sys.exit(1)
    except:
        print("❌ Cannot connect to API. Please start the API first:")
        print("   docker compose up -d")
        sys.exit(1)

    print("\n✅ API is running. Proceeding with breaking change test...")

    # Break the system prompt
    backup_path = None
    try:
        backup_path = break_system_prompt()

        # Run evaluation
        passed = run_evaluation_test()

        print("\n" + "=" * 80)
        print("📊 TEST RESULTS")
        print("=" * 80)

        if not passed:
            print("✅ SUCCESS: Breaking change test PASSED!")
            print("   - Agent gave wrong answers (as intended)")
            print("   - Evaluation correctly detected low faithfulness")
            print("   - CI/CD pipeline would FAIL this build")
            print("   - Quality gate is working correctly!")
        else:
            print("❌ FAILURE: Breaking change test did NOT work as expected")
            print("   - Evaluation unexpectedly PASSED")
            print("   - Quality gate may not be working correctly")
            print("   - Check the evaluation script and thresholds")

        print("\n🔄 Restoring original system prompt...")

    except Exception as e:
        print(f"❌ Error during test: {str(e)}")

    finally:
        # Always restore the original file
        if backup_path and os.path.exists(backup_path):
            restore_file("agents_config.py", backup_path)
            print("✅ Original system prompt restored")

    print("\n🎯 Test completed!")
    print("💡 This demonstrates how the CI/CD pipeline prevents")
    print("   broken or low-quality agents from reaching production.")

if __name__ == "__main__":
    main()