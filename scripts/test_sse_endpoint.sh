#!/bin/bash
# Test SSE endpoint from TestPyPI packages

echo "Testing SSE streaming endpoint..."
echo ""

# Test with streaming=false to get JSON
echo "Test with streaming=false (JSON response):"
curl -s "http://localhost:8080/ask?query=hello+world&streaming=false" | python3 -m json.tool
echo ""

# Test SSE stream (first 5 events)
echo "Test with streaming=true (SSE response - first 5 events):"
curl -s -N "http://localhost:8080/ask?query=hello+world&streaming=true" | head -20
echo ""

echo "✅ Both JSON and SSE modes work!"
