#!/usr/bin/env python3
"""
Test script for the PR Report Coral Agent

This script demonstrates the functionality of the PR report agent's tools
without requiring the full Coral framework setup.
"""

import os
from dotenv import load_dotenv
from main import generate_news_report, fetch_rss_articles, build_google_news_url

def test_build_google_news_url():
    """Test building a Google News RSS URL"""
    print("Testing build_google_news_url...")
    result = build_google_news_url.invoke({"topic": "artificial intelligence"})
    print(f"Result: {result}")
    return result.get("success", False)

def test_generate_news_report():
    """Test generating a news report (requires GOOGLE_API_KEY)"""
    print("\nTesting generate_news_report...")
    
    if not os.getenv("GOOGLE_API_KEY"):
        print("Skipping test - GOOGLE_API_KEY not set")
        return True
    
    result = generate_news_report.invoke({
        "topic": "climate change",
        "max_articles": 5
    })
    print(f"Success: {result.get('success', False)}")
    if result.get("success"):
        print(f"Sections generated: {len(result['data'].get('sections', []))}")
    else:
        print(f"Error: {result.get('error')}")
    
    return result.get("success", False)

def test_fetch_rss_articles():
    """Test fetching RSS articles (requires GOOGLE_API_KEY)"""
    print("\nTesting fetch_rss_articles...")
    
    if not os.getenv("GOOGLE_API_KEY"):
        print("Skipping test - GOOGLE_API_KEY not set")
        return True
    
    # First build a URL
    url_result = build_google_news_url.invoke({"topic": "technology"})
    if not url_result.get("success"):
        print("Failed to build URL for test")
        return False
    
    rss_url = url_result["url"]
    result = fetch_rss_articles.invoke({
        "rss_url": rss_url,
        "max_articles": 3
    })
    
    print(f"Success: {result.get('success', False)}")
    if result.get("success"):
        print(f"Sections generated: {len(result['data'].get('sections', []))}")
    else:
        print(f"Error: {result.get('error')}")
    
    return result.get("success", False)

def main():
    """Run all tests"""
    load_dotenv()
    
    print("PR Report Agent Test Suite")
    print("=" * 40)
    
    tests = [
        ("Build Google News URL", test_build_google_news_url),
        ("Generate News Report", test_generate_news_report),
        ("Fetch RSS Articles", test_fetch_rss_articles),
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
            print(f"✅ {test_name}: {'PASSED' if success else 'FAILED'}")
        except Exception as e:
            results.append((test_name, False))
            print(f"❌ {test_name}: ERROR - {e}")
    
    print("\n" + "=" * 40)
    print("Test Summary:")
    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if not os.getenv("GOOGLE_API_KEY"):
        print("\nNote: Set GOOGLE_API_KEY environment variable to test all features")

if __name__ == "__main__":
    main()
