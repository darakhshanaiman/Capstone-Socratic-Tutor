import asyncio
import httpx
import json
import time
import sys
from datetime import datetime

# Fix encoding for Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

async def run_all_tests():
    print("=" * 70)
    print("RAG PIPELINE API - COMPREHENSIVE TEST SUITE")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    
    client = httpx.AsyncClient(timeout=30)
    tests_passed = 0
    tests_total = 4
    
    # TEST 1: Health Check
    print("\n[TEST 1/4] Health Check Endpoint")
    print("-" * 70)
    try:
        response = await client.get("http://localhost:8000/health")
        if response.status_code == 200:
            print("[PASS] Health Check")
            print(f"   Response: {response.json()}")
            tests_passed += 1
        else:
            print(f"[FAIL] Health Check - Status Code: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Health Check: {str(e)}")
    
    # TEST 2: Chat Endpoint
    print("\n[TEST 2/4] Chat Endpoint (Standard Request)")
    print("-" * 70)
    try:
        payload = {
            "message": "What are the four stages of Data Engineering?",
            "thread_id": "test_session_001"
        }
        start = time.time()
        response = await client.post("http://localhost:8000/chat", json=payload)
        elapsed = time.time() - start
        
        if response.status_code == 200:
            result = response.json()
            print("[PASS] Chat Endpoint")
            print(f"   Response Time: {elapsed:.2f}s")
            print(f"   Final Answer (first 100 chars): {result['final_answer'][:100]}...")
            print(f"   Message Count: {result['messages_count']}")
            tests_passed += 1
        else:
            print(f"[FAIL] Chat Endpoint - Status Code: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Chat Endpoint: {str(e)}")
    
    # TEST 3: Stream Endpoint
    print("\n[TEST 3/4] Stream Endpoint (Server-Sent Events)")
    print("-" * 70)
    try:
        payload = {
            "message": "Explain hybrid search in information retrieval",
            "thread_id": "stream_test_001"
        }
        start = time.time()
        event_count = 0
        async with client.stream("POST", "http://localhost:8000/stream", json=payload) as response:
            if response.status_code == 200:
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        event_count += 1
                elapsed = time.time() - start
                
                print("[PASS] Stream Endpoint")
                print(f"   Events Received: {event_count}")
                print(f"   Response Time: {elapsed:.2f}s")
                tests_passed += 1
            else:
                print(f"[FAIL] Stream Endpoint - Status Code: {response.status_code}")
    except Exception as e:
        print(f"[ERROR] Stream Endpoint: {str(e)}")
    
    # TEST 4: Multi-Turn Persistence
    print("\n[TEST 4/4] Multi-Turn Conversation (Persistence)")
    print("-" * 70)
    try:
        thread_id = "persistence_test_001"
        
        # Turn 1
        response1 = await client.post(
            "http://localhost:8000/chat",
            json={"message": "What is Data Ingestion?", "thread_id": thread_id}
        )
        messages1 = response1.json()["messages_count"]
        
        # Turn 2
        response2 = await client.post(
            "http://localhost:8000/chat",
            json={"message": "How is that different from Transformation?", "thread_id": thread_id}
        )
        messages2 = response2.json()["messages_count"]
        
        if messages2 > messages1:
            print("[PASS] Multi-Turn Conversation (Persistence)")
            print(f"   Turn 1 Message Count: {messages1}")
            print(f"   Turn 2 Message Count: {messages2}")
            tests_passed += 1
        else:
            print(f"[FAIL] Conversation History not preserved")
            print(f"   Turn 1: {messages1}, Turn 2: {messages2}")
    except Exception as e:
        print(f"[ERROR] Persistence Test: {str(e)}")
    
    # SUMMARY
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Tests Passed: {tests_passed}/{tests_total}")
    
    if tests_passed == tests_total:
        print("SUCCESS - ALL TESTS PASSED - API IS READY FOR DEPLOYMENT")
    else:
        print(f"WARNING - {tests_total - tests_passed} test(s) failed - review errors above")
    
    print("=" * 70)

if __name__ == "__main__":
    asyncio.run(run_all_tests())
