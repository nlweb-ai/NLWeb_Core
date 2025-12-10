#!/usr/bin/env python3
"""
A/B test script to compare hybrid search vs pure vector search
"""
import asyncio
import json
import sys
from typing import List, Dict, Any

# Test queries that should benefit from hybrid search
TEST_QUERIES = [
    "paneer recipe",           # Specific ingredient name
    "Tom Hanks movies",        # Specific actor name
    "chocolate cake",          # Exact product term
    "romantic comedy",         # Genre + type
    "Italian cuisine",         # Cuisine type
    "quick breakfast ideas",   # General semantic query
]


async def run_search_test(query: str, hybrid_enabled: bool) -> Dict[str, Any]:
    """Run a single search query with specified hybrid mode"""
    import os
    os.chdir('/Users/prashjai/Documents/NLWeb_Core')
    
    # Import after changing directory
    import nlweb_core
    from nlweb_core.config import CONFIG
    
    # Temporarily modify config
    original_hybrid = getattr(CONFIG.retrieval_endpoints.get(CONFIG.write_endpoint), 'hybrid_search', False)
    CONFIG.retrieval_endpoints[CONFIG.write_endpoint].hybrid_search = hybrid_enabled
    
    try:
        # Import retriever
        from nlweb_core.retriever import search
        
        # Run search
        results = await search(query, site="all", num_results=10)
        
        # Extract URLs and types
        parsed_results = []
        for result in results:
            parsed_results.append({
                "url": result[0],
                "type": result[2],
                "site": result[3],
                "content_preview": result[1][:150] if len(result[1]) > 150 else result[1]
            })
        
        return {
            "query": query,
            "mode": "hybrid" if hybrid_enabled else "vector-only",
            "count": len(parsed_results),
            "results": parsed_results
        }
    finally:
        # Restore original config
        CONFIG.retrieval_endpoints[CONFIG.write_endpoint].hybrid_search = original_hybrid


async def compare_results(query: str) -> Dict[str, Any]:
    """Compare hybrid vs vector-only search for a query"""
    print(f"\n{'='*80}")
    print(f"Testing: {query}")
    print(f"{'='*80}")
    
    # Run both modes
    vector_results = await run_search_test(query, hybrid_enabled=False)
    hybrid_results = await run_search_test(query, hybrid_enabled=True)
    
    # Find differences
    vector_urls = set(r["url"] for r in vector_results["results"])
    hybrid_urls = set(r["url"] for r in hybrid_results["results"])
    
    only_in_vector = vector_urls - hybrid_urls
    only_in_hybrid = hybrid_urls - vector_urls
    common = vector_urls & hybrid_urls
    
    # Analyze ranking changes for common results
    rank_changes = []
    for url in common:
        vector_rank = next(i for i, r in enumerate(vector_results["results"]) if r["url"] == url)
        hybrid_rank = next(i for i, r in enumerate(hybrid_results["results"]) if r["url"] == url)
        if vector_rank != hybrid_rank:
            rank_changes.append({
                "url": url,
                "vector_rank": vector_rank + 1,
                "hybrid_rank": hybrid_rank + 1,
                "improvement": vector_rank - hybrid_rank
            })
    
    # Sort by improvement
    rank_changes.sort(key=lambda x: abs(x["improvement"]), reverse=True)
    
    # Print comparison
    print(f"\n📊 Results Summary:")
    print(f"  Vector-only: {vector_results['count']} results")
    print(f"  Hybrid:      {hybrid_results['count']} results")
    print(f"  Common:      {len(common)} results")
    print(f"  Different:   {len(only_in_vector) + len(only_in_hybrid)} results")
    
    if only_in_hybrid:
        print(f"\n✨ NEW in Hybrid (likely keyword matches):")
        for i, result in enumerate(hybrid_results["results"]):
            if result["url"] in only_in_hybrid:
                print(f"  #{i+1}. {result['url']}")
                print(f"       Type: {result['type']}")
    
    if only_in_vector:
        print(f"\n❌ REMOVED in Hybrid (pushed out by keyword matches):")
        for i, result in enumerate(vector_results["results"]):
            if result["url"] in only_in_vector:
                print(f"  #{i+1}. {result['url']}")
                print(f"       Type: {result['type']}")
    
    if rank_changes:
        print(f"\n📈 Ranking Changes (common results):")
        for change in rank_changes[:5]:  # Top 5 changes
            direction = "↑" if change["improvement"] > 0 else "↓"
            print(f"  {direction} {change['url']}")
            print(f"     Vector: #{change['vector_rank']} → Hybrid: #{change['hybrid_rank']} ({change['improvement']:+d})")
    
    # Top 3 comparison
    print(f"\n🏆 Top 3 Comparison:")
    print(f"\n  Vector-only:")
    for i, result in enumerate(vector_results["results"][:3]):
        print(f"    {i+1}. {result['url']}")
        print(f"       {result['type']} | {result['site']}")
    
    print(f"\n  Hybrid:")
    for i, result in enumerate(hybrid_results["results"][:3]):
        marker = "🆕" if result["url"] in only_in_hybrid else ""
        print(f"    {i+1}. {result['url']} {marker}")
        print(f"       {result['type']} | {result['site']}")
    
    return {
        "query": query,
        "vector_count": vector_results['count'],
        "hybrid_count": hybrid_results['count'],
        "new_results": len(only_in_hybrid),
        "removed_results": len(only_in_vector),
        "rank_changes": len(rank_changes)
    }


async def main():
    """Run A/B tests for all queries"""
    print("🔬 Hybrid Search A/B Testing")
    print("=" * 80)
    print("Comparing: Vector-only vs Hybrid (keyword + vector) search")
    print(f"Testing {len(TEST_QUERIES)} queries...\n")
    
    # Set up environment
    import os
    os.environ['AZURE_SEARCH_ENDPOINT'] = os.getenv('AZURE_SEARCH_ENDPOINT', 'https://yoast-vector-db.search.windows.net')
    os.environ['AZURE_SEARCH_KEY'] = os.getenv('AZURE_SEARCH_KEY', '')
    os.environ['AZURE_OPENAI_ENDPOINT'] = os.getenv('AZURE_OPENAI_ENDPOINT', 'https://nlweboaiinstance1.openai.azure.com/')
    os.environ['AZURE_OPENAI_API_KEY'] = os.getenv('AZURE_OPENAI_API_KEY', '')
    
    # Initialize NLWeb
    import nlweb_core
    nlweb_core.init('config.yaml')
    
    # Run tests
    summaries = []
    for query in TEST_QUERIES:
        try:
            summary = await compare_results(query)
            summaries.append(summary)
        except Exception as e:
            print(f"❌ Error testing '{query}': {e}")
            import traceback
            traceback.print_exc()
    
    # Overall summary
    print(f"\n\n{'='*80}")
    print("📋 Overall Summary")
    print(f"{'='*80}")
    
    total_new = sum(s['new_results'] for s in summaries)
    total_removed = sum(s['removed_results'] for s in summaries)
    total_rank_changes = sum(s['rank_changes'] for s in summaries)
    
    print(f"\nAcross {len(summaries)} queries:")
    print(f"  • {total_new} new results found with hybrid search")
    print(f"  • {total_removed} results removed/pushed out")
    print(f"  • {total_rank_changes} results changed ranking")
    
    print(f"\n💡 Recommendations:")
    if total_new > total_removed:
        print(f"  ✅ Hybrid search finds {total_new - total_removed} MORE relevant results")
        print(f"     Consider keeping hybrid_search: true")
    elif total_new < total_removed:
        print(f"  ⚠️  Hybrid search may be too aggressive with keyword matching")
        print(f"     Review if keyword matches are more relevant than semantic ones")
    else:
        print(f"  ⚖️  Hybrid search provides different but not necessarily more results")
        print(f"     Depends on your use case: exact matches vs semantic similarity")
    
    if total_rank_changes > 0:
        print(f"  📊 {total_rank_changes} ranking changes suggest hybrid reorders results")
        print(f"     Manually review if keyword-matched results rank higher appropriately")


if __name__ == "__main__":
    asyncio.run(main())
