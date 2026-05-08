import json
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langsmith import traceable

from deepeval import evaluate
from deepeval.metrics import FaithfulnessMetric, AnswerRelevancyMetric
from deepeval.test_case import LLMTestCase

from multi_agent_graph import app


load_dotenv()

os.environ.setdefault("LANGSMITH_TRACING", "true")
os.environ.setdefault("LANGSMITH_PROJECT", "rag-pipeline-audit")

DATASET_PATH = "test_dataset.json"
REPORT_PATH = "evaluation_report.md"

JUDGE_MODEL = "gpt-4o-mini"
THRESHOLD = 0.7


def clean_content(message: Any) -> str:
    """Extract and clean the final message content."""
    content = getattr(message, "content", str(message))
    content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL)
    return content.strip()


@traceable(name="Run audit query", run_type="chain")
def run_agent_query(query: str, thread_id: str) -> Dict[str, Any]:
    """Run one query through the LangGraph agent with LangSmith tracing."""

    config = {
        "configurable": {
            "thread_id": thread_id,
        },
        "metadata": {
            "lab": "rag-pipeline-audit",
            "thread_id": thread_id,
        },
        "tags": [
            "lab-audit",
            "deepeval",
            "langsmith",
        ],
    }

    return app.invoke(
        {"messages": [HumanMessage(content=query)]},
        config=config,
    )


def load_dataset(path: str) -> List[Dict[str, str]]:
    """Load the gold dataset."""

    with open(path, "r", encoding="utf-8") as file:
        dataset = json.load(file)

    if len(dataset) < 20:
        raise ValueError("Your lab requires at least 20 test cases.")

    for idx, item in enumerate(dataset, start=1):
        if "query" not in item or "reference" not in item:
            raise ValueError(
                f"Test case {idx} must contain both 'query' and 'reference'."
            )

    return dataset


def run_audit() -> None:
    print("\n📊 RAG Pipeline Audit")
    print("=" * 50)

    dataset = load_dataset(DATASET_PATH)
    print(f"Loaded {len(dataset)} test cases from {DATASET_PATH}")

    test_cases = []
    results_log = []

    for idx, entry in enumerate(dataset, start=1):
        query = entry["query"]
        reference = entry["reference"]
        thread_id = f"audit_test_{idx}"

        print(f"\n[{idx}/{len(dataset)}] {query[:70]}")

        start_time = time.time()

        try:
            result = run_agent_query(query=query, thread_id=thread_id)
            elapsed_time = round(time.time() - start_time, 2)

            messages = result.get("messages", [])

            if not messages:
                raise ValueError("Agent returned no messages.")

            actual_output = clean_content(messages[-1])

            if not actual_output:
                raise ValueError("Agent returned an empty final response.")

            test_case = LLMTestCase(
                input=query,
                actual_output=actual_output,
                expected_output=reference,
            )

            test_cases.append(test_case)

            results_log.append(
                {
                    "query": query,
                    "reference": reference,
                    "actual_output": actual_output,
                    "status": "success",
                    "elapsed_time_sec": elapsed_time,
                    "thread_id": thread_id,
                }
            )

            print(f"✅ Done in {elapsed_time}s")

        except Exception as error:
            elapsed_time = round(time.time() - start_time, 2)

            results_log.append(
                {
                    "query": query,
                    "reference": reference,
                    "status": "error",
                    "error": str(error),
                    "elapsed_time_sec": elapsed_time,
                    "thread_id": thread_id,
                }
            )

            print(f"❌ Failed: {error}")

    metrics = [
        FaithfulnessMetric(
            threshold=THRESHOLD,
            model=JUDGE_MODEL,
            include_reason=True,
        ),
        AnswerRelevancyMetric(
            threshold=THRESHOLD,
            model=JUDGE_MODEL,
            include_reason=True,
        ),
    ]

    deepeval_success = False

    print("\n🔍 Running DeepEval evaluation...")

    try:
        evaluate(
            test_cases=test_cases,
            metrics=metrics,
        )
        deepeval_success = True
        print("✅ DeepEval completed")

    except Exception as error:
        print(f"⚠️ DeepEval failed: {error}")
        print("A partial report will still be generated.")

    report = generate_report(
        results_log=results_log,
        total_cases=len(dataset),
        evaluated_cases=len(test_cases),
        deepeval_success=deepeval_success,
    )

    with open(REPORT_PATH, "w", encoding="utf-8") as file:
        file.write(report)

    print(f"\n📄 Report saved to {REPORT_PATH}")
    print("Open LangSmith and filter runs by tag: lab-audit")


def generate_report(
    results_log: List[Dict[str, Any]],
    total_cases: int,
    evaluated_cases: int,
    deepeval_success: bool,
) -> str:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    successful = [item for item in results_log if item["status"] == "success"]
    failed = [item for item in results_log if item["status"] != "success"]

    avg_time = average_time(successful)

    slowest_runs = sorted(
        results_log,
        key=lambda item: item.get("elapsed_time_sec", 0),
        reverse=True,
    )[:5]

    report = f"""# RAG Pipeline Audit Report

**Generated:** {timestamp}

## Executive Summary

- Total test cases: {total_cases}
- Agent responses collected: {evaluated_cases}
- Successful runs: {len(successful)}
- Failed runs: {len(failed)}
- Success rate: {success_rate(results_log):.1f}%
- Average response time: {avg_time:.2f}s
- DeepEval completed: {"Yes" if deepeval_success else "No"}

## Quantitative Evaluation

This audit uses DeepEval with two required lab metrics:

1. Faithfulness
   - Checks whether the answer stays grounded in the retrieved context.
   - Helps detect hallucinations.

2. Answer Relevancy
   - Checks whether the answer directly responds to the user query.

Tool call accuracy is handled through LangSmith trace inspection because this dataset only contains `query` and `reference`.

## Qualitative Trace Analysis

LangSmith tracing is enabled for each audit run.

To complete the lab writeup, open LangSmith and inspect runs tagged:

`lab-audit`

For 5 complex queries, record:

1. The slowest LangGraph node.
2. Whether retrieval returned useful context.
3. Whether the reasoning step used the context correctly.
4. Whether the correct tool was called, if the query required tool use.
5. Where the logic failed, if the response was wrong.

## Slowest Runs

| Query | Time | Thread ID |
|---|---:|---|
"""

    for item in slowest_runs:
        report += (
            f"| {item['query'][:90]} | "
            f"{item.get('elapsed_time_sec', 0):.2f}s | "
            f"{item.get('thread_id', '')} |\n"
        )

    report += """

## Detailed Execution Log

"""

    for idx, item in enumerate(results_log, start=1):
        report += f"### Test {idx}\n\n"
        report += f"- Query: {item['query']}\n"
        report += f"- Status: {item['status']}\n"
        report += f"- Time: {item.get('elapsed_time_sec', 0):.2f}s\n"
        report += f"- Thread ID: {item.get('thread_id', '')}\n"

        if item["status"] == "success":
            output = item.get("actual_output", "")
            reference = item.get("reference", "")

            report += f"- Reference: {reference[:300]}\n"
            report += f"- Output: {output[:300]}\n\n"
        else:
            report += f"- Error: {item.get('error', 'Unknown error')}\n\n"

    report += """## Lab Notes

- Task 1 is covered by `test_dataset.json`.
- Task 2 is covered by DeepEval faithfulness and answer relevancy.
- Task 3 is covered by LangSmith traces from the tagged runs.
- Tool call accuracy should be discussed manually from LangSmith traces unless the dataset is expanded with expected tool names.

"""

    return report


def average_time(successful_runs: List[Dict[str, Any]]) -> float:
    if not successful_runs:
        return 0.0

    return sum(item.get("elapsed_time_sec", 0) for item in successful_runs) / len(
        successful_runs
    )


def success_rate(results_log: List[Dict[str, Any]]) -> float:
    if not results_log:
        return 0.0

    successful_count = sum(1 for item in results_log if item["status"] == "success")
    return successful_count / len(results_log) * 100


if __name__ == "__main__":
    run_audit()