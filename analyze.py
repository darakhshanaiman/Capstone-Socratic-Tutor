import json
from collections import Counter

def analyze_feedback(file_path="feedback_log.json"):
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("No feedback data found.")
        return
    except json.JSONDecodeError:
        print("Invalid JSON data in feedback log.")
        return

    total_responses = len(data)
    negative_feedback = sum(1 for entry in data if entry.get("feedback") == "Bad")

    print(f"Total responses: {total_responses}")
    print(f"Negative feedback: {negative_feedback}")

    failed_queries = [entry["user_input"] for entry in data if entry.get("feedback") == "Bad"]
    query_counts = Counter(failed_queries)

    print("\nTop 3 failed queries:")
    for query, count in query_counts.most_common(3):
        print(f"- {query} (Failed {count} times)")

if __name__ == "__main__":
    analyze_feedback()
