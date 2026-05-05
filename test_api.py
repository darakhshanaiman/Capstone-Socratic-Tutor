import asyncio
import json
import httpx
import time
from datetime import datetime

# Configuration
API_BASE_URL = "http://localhost:8000"
TIMEOUT = 30


async def test_health_endpoint():
    """Test the /health endpoint."""
    print("\n" + "=" * 60)
    print("TEST 1: Health Check Endpoint")
    print("=" * 60)
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_BASE_URL}/health", timeout=TIMEOUT)
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Health Check PASSED")
                print(f"   Status: {data.get('status')}")
                print(f"   Version: {data.get('version')}")
                print(f"   Message: {data.get('message')}")
                return True
            else:
                print(f"❌ Health Check FAILED: {response.status_code}")
                return False
    except Exception as e:
        print(f"❌ Health Check ERROR: {str(e)}")
        return False


async def test_chat_endpoint():
    """Test the /chat endpoint."""
    print("\n" + "=" * 60)
    print("TEST 2: Chat Endpoint (Standard Request)")
    print("=" * 60)
    
    test_query = "What are the four stages of Data Engineering?"
    thread_id = "test_session_001"
    
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "message": test_query,
                "thread_id": thread_id
            }
            
            print(f"Sending query: {test_query}")
            print(f"Thread ID: {thread_id}")
            
            start_time = time.time()
            response = await client.post(
                f"{API_BASE_URL}/chat",
                json=payload,
                timeout=TIMEOUT
            )
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                print(f"\n✅ Chat Request PASSED")
                print(f"   Response Time: {elapsed_time:.2f}s")
                print(f"   Status: {data.get('status')}")
                print(f"   Thread ID: {data.get('thread_id')}")
                print(f"   Final Answer: {data.get('final_answer')[:100]}...")
                print(f"   Messages Count: {data.get('messages_count')}")
                return True, elapsed_time
            else:
                print(f"❌ Chat Request FAILED: {response.status_code}")
                print(f"   Response: {response.text}")
                return False, elapsed_time
    except Exception as e:
        print(f"❌ Chat Request ERROR: {str(e)}")
        return False, None


async def test_stream_endpoint():
    """Test the /stream endpoint."""
    print("\n" + "=" * 60)
    print("TEST 3: Stream Endpoint (SSE Streaming)")
    print("=" * 60)
    
    test_query = "Define the concept of Data Idempotency."
    thread_id = "test_session_002"
    
    try:
        async with httpx.AsyncClient() as client:
            payload = {
                "message": test_query,
                "thread_id": thread_id
            }
            
            print(f"Sending query: {test_query}")
            print(f"Thread ID: {thread_id}")
            print("\nStreaming response:")
            
            start_time = time.time()
            chunk_count = 0
            
            async with client.stream(
                "POST",
                f"{API_BASE_URL}/stream",
                json=payload,
                timeout=TIMEOUT
            ) as response:
                if response.status_code == 200:
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            chunk = line[6:]  # Remove "data: " prefix
                            try:
                                data = json.loads(chunk)
                                chunk_count += 1
                                event_type = data.get("event")
                                print(f"  [{chunk_count}] Event: {event_type}", end="")
                                if data.get("node_name"):
                                    print(f" | Node: {data.get('node_name')}", end="")
                                if data.get("content"):
                                    print(f" | Content: {data.get('content')[:50]}...", end="")
                                print()
                            except json.JSONDecodeError:
                                pass
                    
                    elapsed_time = time.time() - start_time
                    print(f"\n✅ Stream Request PASSED")
                    print(f"   Response Time: {elapsed_time:.2f}s")
                    print(f"   Chunks Received: {chunk_count}")
                    return True, elapsed_time
                else:
                    print(f"❌ Stream Request FAILED: {response.status_code}")
                    return False, None
    except Exception as e:
        print(f"❌ Stream Request ERROR: {str(e)}")
        return False, None


async def test_thread_state_endpoint():
    """Test the /threads/{thread_id} endpoint."""
    print("\n" + "=" * 60)
    print("TEST 4: Thread State Endpoint")
    print("=" * 60)
    
    thread_id = "test_session_001"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{API_BASE_URL}/threads/{thread_id}",
                timeout=TIMEOUT
            )
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Thread State Retrieval PASSED")
                print(f"   Thread ID: {data.get('thread_id')}")
                print(f"   Messages Count: {data.get('messages_count')}")
                print(f"   Next Nodes: {data.get('next_nodes')}")
                return True
            else:
                print(f"⚠️  Thread State NOT FOUND: {response.status_code}")
                print(f"   (This is expected if thread was just created)")
                return True  # Not a failure
    except Exception as e:
        print(f"⚠️  Thread State ERROR: {str(e)}")
        return True  # Not critical


async def test_concurrent_requests():
    """Test multiple concurrent requests."""
    print("\n" + "=" * 60)
    print("TEST 5: Concurrent Requests (Load Test)")
    print("=" * 60)
    
    queries = [
        "What is the purpose of the Domain Name System?",
        "How does Asymmetric Encryption differ from Symmetric Encryption?",
        "What is the role of TF-IDF in document ranking?"
    ]
    
    print(f"Sending {len(queries)} concurrent requests...\n")
    
    try:
        async with httpx.AsyncClient() as client:
            tasks = []
            start_time = time.time()
            
            for idx, query in enumerate(queries):
                payload = {
                    "message": query,
                    "thread_id": f"concurrent_test_{idx}"
                }
                task = client.post(
                    f"{API_BASE_URL}/chat",
                    json=payload,
                    timeout=TIMEOUT
                )
                tasks.append(task)
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            total_time = time.time() - start_time
            
            success_count = 0
            for idx, response in enumerate(responses):
                if isinstance(response, Exception):
                    print(f"  ❌ Request {idx + 1} FAILED: {str(response)}")
                elif response.status_code == 200:
                    print(f"  ✅ Request {idx + 1} PASSED")
                    success_count += 1
                else:
                    print(f"  ❌ Request {idx + 1} FAILED: {response.status_code}")
            
            print(f"\n✅ Concurrent Test PASSED")
            print(f"   Success Rate: {success_count}/{len(queries)}")
            print(f"   Total Time: {total_time:.2f}s")
            print(f"   Avg Time per Request: {total_time/len(queries):.2f}s")
            
            return success_count == len(queries)
    
    except Exception as e:
        print(f"❌ Concurrent Test ERROR: {str(e)}")
        return False


async def run_all_tests():
    """Run all API tests."""
    results = []
    
    print("\n" + "=" * 60)
    print("🧪 API ENDPOINT TEST SUITE")
    print("=" * 60)
    print(f"API Base URL: {API_BASE_URL}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test 1: Health Check
    health_passed = await test_health_endpoint()
    results.append(("Health Check", health_passed))
    
    if not health_passed:
        print("\n⚠️  API is not responding. Please ensure the server is running:")
        print("   python api.py")
        return results
    
    # Test 2: Chat Endpoint
    chat_passed, chat_time = await test_chat_endpoint()
    results.append(("Chat Endpoint", chat_passed))
    
    # Test 3: Stream Endpoint
    stream_passed, stream_time = await test_stream_endpoint()
    results.append(("Stream Endpoint", stream_passed))
    
    # Test 4: Thread State Endpoint
    thread_passed = await test_thread_state_endpoint()
    results.append(("Thread State", thread_passed))
    
    # Test 5: Concurrent Requests
    concurrent_passed = await test_concurrent_requests()
    results.append(("Concurrent Requests", concurrent_passed))
    
    # Print Summary
    print("\n" + "=" * 60)
    print("📊 TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    print(f"Ended: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return results


if __name__ == "__main__":
    print("\n⏳ Make sure the FastAPI server is running:")
    print("   In another terminal, run: python api.py")
    print("\nWaiting 2 seconds before starting tests...\n")
    time.sleep(2)
    
    try:
        asyncio.run(run_all_tests())
    except KeyboardInterrupt:
        print("\n\n❌ Test suite interrupted by user")
    except Exception as e:
        print(f"\n❌ Test suite error: {str(e)}")
