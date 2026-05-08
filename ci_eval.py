#!/usr/bin/env python3
"""
CI-Ready Evaluation Script for RAG Pipeline
Measures Faithfulness and Relevancy using DeepEval
Exits with code 0 (PASS) if scores >= threshold, 1 (FAIL) if below

Usage:
    python ci_eval.py --threshold 0.85

Environment Variables:
    API_BASE_URL: Base URL for the API (default: http://localhost:8000)
    TEST_DATASET: Path to test dataset JSON file (default: test_dataset.json)
    GROQ_API_KEY: API key for LLM evaluation
"""

import os
import sys
import json
import argparse
import httpx
import asyncio
from datetime import datetime
from typing import List, Dict, Any
from deepeval import evaluate
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase

# Fix encoding for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

class RAGEvaluator:
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url.rstrip('/')
        self.client = httpx.Client(timeout=60.0)

    def query_rag_system(self, question: str, thread_id: str = "eval_test") -> str:
        """Query the RAG system and return the answer."""
        try:
            payload = {
                "message": question,
                "thread_id": thread_id
            }

            response = self.client.post(
                f"{self.api_base_url}/chat",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                result = response.json()
                return result.get("final_answer", "")
            else:
                print(f"❌ API Error: {response.status_code} - {response.text}")
                return ""

        except Exception as e:
            print(f"❌ Request Error: {str(e)}")
            return ""

    def load_test_dataset(self, dataset_path: str) -> List[Dict[str, str]]:
        """Load test dataset from JSON file."""
        try:
            with open(dataset_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
        except Exception as e:
            print(f"❌ Error loading dataset: {str(e)}")
            return []

    def create_test_cases(self, dataset: List[Dict[str, str]]) -> List[LLMTestCase]:
        """Create DeepEval test cases from dataset."""
        test_cases = []

        for i, item in enumerate(dataset):
            question = item.get("query", "")
            reference_answer = item.get("reference", "")

            if not question or not reference_answer:
                continue

            # Query the RAG system
            actual_answer = self.query_rag_system(question, f"eval_test_{i}")

            if not actual_answer:
                print(f"⚠️ Skipping test case {i+1}: No answer received")
                continue

            test_case = LLMTestCase(
                input=question,
                actual_output=actual_answer,
                expected_output=reference_answer,
                retrieval_context=[]  # Could be enhanced to include retrieved docs
            )

            test_cases.append(test_case)

        return test_cases

    def run_evaluation(self, test_cases: List[LLMTestCase], threshold: float = 0.85) -> Dict[str, Any]:
        """Run evaluation using DeepEval metrics."""
        print(f"\n🔍 Running evaluation with {len(test_cases)} test cases...")
        print(f"📊 Threshold: {threshold}")

        # Define metrics
        faithfulness_metric = FaithfulnessMetric(
            threshold=threshold,
            model="gpt-3.5-turbo",
            include_reason=True
        )

        relevancy_metric = AnswerRelevancyMetric(
            threshold=threshold,
            model="gpt-3.5-turbo",
            include_reason=True
        )

        # Run evaluation
        try:
            evaluation_results = evaluate(
                test_cases=test_cases,
                metrics=[faithfulness_metric, relevancy_metric]
            )

            # Calculate aggregate scores
            faithfulness_scores = [tc.metrics[0].score for tc in test_cases if tc.metrics]
            relevancy_scores = [tc.metrics[1].score for tc in test_cases if len(tc.metrics) > 1]

            avg_faithfulness = sum(faithfulness_scores) / len(faithfulness_scores) if faithfulness_scores else 0
            avg_relevancy = sum(relevancy_scores) / len(relevancy_scores) if relevancy_scores else 0

            results = {
                "test_cases_evaluated": len(test_cases),
                "average_faithfulness": avg_faithfulness,
                "average_relevancy": avg_relevancy,
                "threshold": threshold,
                "faithfulness_pass": avg_faithfulness >= threshold,
                "relevancy_pass": avg_relevancy >= threshold,
                "overall_pass": avg_faithfulness >= threshold and avg_relevancy >= threshold,
                "evaluation_results": evaluation_results
            }

            return results

        except Exception as e:
            print(f"❌ Evaluation Error: {str(e)}")
            return {
                "error": str(e),
                "overall_pass": False
            }

def main():
    parser = argparse.ArgumentParser(description="CI-Ready RAG Pipeline Evaluation")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.85,
        help="Minimum score threshold for PASS (default: 0.85)"
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default="test_dataset.json",
        help="Path to test dataset JSON file"
    )
    parser.add_argument(
        "--api-url",
        type=str,
        default=None,
        help="API base URL (overrides API_BASE_URL env var)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    # Environment variables
    api_base_url = args.api_url or os.getenv("API_BASE_URL", "http://localhost:8000")
    dataset_path = os.getenv("TEST_DATASET", args.dataset)

    print("=" * 80)
    print("🤖 RAG PIPELINE CI EVALUATION")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔗 API URL: {api_base_url}")
    print(f"📁 Dataset: {dataset_path}")
    print(f"🎯 Threshold: {args.threshold}")
    print("=" * 80)

    # Initialize evaluator
    evaluator = RAGEvaluator(api_base_url)

    # Load test dataset
    dataset = evaluator.load_test_dataset(dataset_path)
    if not dataset:
        print("❌ No test data found. Exiting with failure.")
        sys.exit(1)

    print(f"📋 Loaded {len(dataset)} test cases from dataset")

    # Create test cases
    test_cases = evaluator.create_test_cases(dataset)
    if not test_cases:
        print("❌ No valid test cases created. Exiting with failure.")
        sys.exit(1)

    print(f"🧪 Created {len(test_cases)} evaluation test cases")

    # Run evaluation
    results = evaluator.run_evaluation(test_cases, args.threshold)

    # Display results
    print("\n" + "=" * 80)
    print("📊 EVALUATION RESULTS")
    print("=" * 80)

    if "error" in results:
        print(f"❌ Evaluation failed: {results['error']}")
        sys.exit(1)

    print(f"Test Cases Evaluated: {results['test_cases_evaluated']}")
    print(f"Average Faithfulness: {results['average_faithfulness']:.3f}")
    print(f"Average Relevancy: {results['average_relevancy']:.3f}")
    print(f"Threshold: {results['threshold']:.3f}")

    print("\n🎯 THRESHOLD CHECKS")
    print(f"Faithfulness ≥ {args.threshold}: {'✅ PASS' if results['faithfulness_pass'] else '❌ FAIL'}")
    print(f"Relevancy ≥ {args.threshold}: {'✅ PASS' if results['relevancy_pass'] else '❌ FAIL'}")
    print(f"Overall Result: {'✅ PASS' if results['overall_pass'] else '❌ FAIL'}")

    # Exit with appropriate code
    if results['overall_pass']:
        print("\n🎉 CI CHECK PASSED - Agent quality meets standards!")
        sys.exit(0)
    else:
        print("\n💥 CI CHECK FAILED - Agent quality below threshold!")
        print("🔧 Please review and improve the RAG system before deployment.")
        sys.exit(1)

if __name__ == "__main__":
    main()