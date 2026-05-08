#!/usr/bin/env python3

import os
import sys
import json
import argparse
import httpx
from datetime import datetime
from difflib import SequenceMatcher


class RAGEvaluator:
    def __init__(self, api_base_url: str):
        self.api_base_url = api_base_url.rstrip("/")
        self.client = httpx.Client(timeout=300.0)

    def load_test_dataset(self, dataset_path: str):
        with open(dataset_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []

    def query_rag_system(self, question: str, thread_id: str):
        try:
            response = self.client.post(
                f"{self.api_base_url}/chat",
                json={
                    "message": question,
                    "thread_id": thread_id,
                },
                headers={"Content-Type": "application/json"},
            )

            if response.status_code != 200:
                print(f"❌ API Error: {response.status_code} - {response.text}")
                return ""

            result = response.json()
            return result.get("final_answer", "")

        except Exception as e:
            print(f"❌ Request Error: {e}")
            return ""

    def similarity_score(self, actual: str, expected: str) -> float:
        if not actual or not expected:
            return 0.0

        actual = actual.lower().strip()
        expected = expected.lower().strip()

        return SequenceMatcher(None, actual, expected).ratio()

    def keyword_score(self, actual: str, expected: str) -> float:
        if not actual or not expected:
            return 0.0

        actual_words = set(actual.lower().split())
        expected_words = set(expected.lower().split())

        if not expected_words:
            return 0.0

        matches = actual_words.intersection(expected_words)
        return len(matches) / len(expected_words)

    def run_evaluation(self, dataset, threshold: float):
        scores = []

        for i, item in enumerate(dataset):
            question = item.get("query") or item.get("input") or item.get("question")
            expected = item.get("reference") or item.get("expected_output") or item.get("answer")

            if not question or not expected:
                print(f"⚠️ Skipping test case {i + 1}: missing question or expected answer")
                continue

            print(f"\n🧪 Test case {i + 1}")
            print(f"Question: {question}")

            actual = self.query_rag_system(question, f"ci_eval_{i}")

            if not actual:
                print("❌ No answer received")
                scores.append(0.0)
                continue

            sim = self.similarity_score(actual, expected)
            keywords = self.keyword_score(actual, expected)

            final_score = (sim + keywords) / 2
            scores.append(final_score)

            print(f"Expected: {expected}")
            print(f"Actual: {actual[:300]}")
            print(f"Similarity Score: {sim:.3f}")
            print(f"Keyword Score: {keywords:.3f}")
            print(f"Final Score: {final_score:.3f}")

        if not scores:
            return {
                "average_score": 0.0,
                "test_cases": 0,
                "passed": False,
            }

        average_score = sum(scores) / len(scores)

        return {
            "average_score": average_score,
            "test_cases": len(scores),
            "passed": average_score >= threshold,
        }


def main():
    parser = argparse.ArgumentParser(description="CI-ready RAG evaluation without OpenAI")
    parser.add_argument("--threshold", type=float, default=0.50)
    parser.add_argument("--dataset", type=str, default="test_dataset.json")
    parser.add_argument("--api-url", type=str, default=None)
    parser.add_argument("--verbose", action="store_true")

    args = parser.parse_args()

    api_base_url = args.api_url or os.getenv("API_BASE_URL", "http://localhost:8000")
    dataset_path = os.getenv("TEST_DATASET", args.dataset)

    print("=" * 80)
    print("🤖 RAG PIPELINE CI EVALUATION")
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔗 API URL: {api_base_url}")
    print(f"📁 Dataset: {dataset_path}")
    print(f"🎯 Threshold: {args.threshold}")
    print("=" * 80)

    evaluator = RAGEvaluator(api_base_url)

    try:
        dataset = evaluator.load_test_dataset(dataset_path)
    except Exception as e:
        print(f"❌ Failed to load dataset: {e}")
        sys.exit(1)

    print(f"📋 Loaded {len(dataset)} test cases")

    results = evaluator.run_evaluation(dataset, args.threshold)

    print("\n" + "=" * 80)
    print("📊 EVALUATION RESULTS")
    print("=" * 80)
    print(f"Test Cases Evaluated: {results['test_cases']}")
    print(f"Average Score: {results['average_score']:.3f}")
    print(f"Threshold: {args.threshold:.3f}")

    if results["passed"]:
        print("\n✅ CI CHECK PASSED")
        sys.exit(0)
    else:
        print("\n❌ CI CHECK FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()