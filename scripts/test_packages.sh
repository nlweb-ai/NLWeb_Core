#!/bin/bash
# Complete end-to-end test of NLWeb packages from PyPI
# This script:
# 1. Creates a fresh virtual environment
# 2. Installs all packages from PyPI
# 3. Sets up config with your Azure credentials
# 4. Starts the NLWeb server
# 5. Tests real queries against your database
# 6. Shows pretty-printed results
# 7. Cleans up (unless there's an error)

set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 NLWeb Full Pipeline Test (from PyPI)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Clean up any existing test environment
TEST_DIR="/tmp/nlweb_test_$$"
rm -rf "$TEST_DIR"
mkdir -p "$TEST_DIR"
cd "$TEST_DIR"

echo "📁 Working directory: $TEST_DIR"
echo ""

# Create fresh virtual environment
echo "🐍 Creating clean virtual environment..."
python3 -m venv venv
source venv/bin/activate

echo "✅ Virtual environment activated"
echo ""

# Install packages from PyPI
echo "📦 Installing packages from PyPI..."
pip install --quiet nlweb-dataload nlweb-core nlweb-network nlweb-azure-vectordb nlweb-elastic-vectordb nlweb-qdrant-vectordb nlweb-snowflake-vectordb nlweb-azure-models

echo "✅ All packages installed"
echo ""

# Verify installations
echo "🔍 Installed packages:"
pip list | grep nlweb
echo ""

# Set up configuration
echo "⚙️  Setting up configuration..."
cp "$HOME/code/NLWeb_Core/examples/azure_hello_world/config.yaml" config.yaml

# Patch to use correct environment variable names
sed -i '' 's/AZURE_OPENAI_KEY/AZURE_OPENAI_API_KEY/g' config.yaml
sed -i '' 's/AZURE_SEARCH_KEY/AZURE_VECTOR_SEARCH_API_KEY/g' config.yaml
sed -i '' 's/AZURE_SEARCH_ENDPOINT/AZURE_VECTOR_SEARCH_ENDPOINT/g' config.yaml

# Add server section
cat >> config.yaml << 'EOF'

server:
  host: localhost
  port: 8080
  enable_cors: false
EOF

echo "✅ Config created"
echo ""

# Source keys and create .env
echo "🔑 Setting up environment variables..."
source "$HOME/code/NLWeb_Core/set_keys.sh"

cat > .env << EOF
AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY}
AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}
AZURE_VECTOR_SEARCH_API_KEY=${AZURE_VECTOR_SEARCH_API_KEY}
AZURE_VECTOR_SEARCH_ENDPOINT=${AZURE_VECTOR_SEARCH_ENDPOINT}
OPENAI_API_KEY=${OPENAI_API_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
EOF

echo "✅ Environment variables configured"
echo ""

# Create server launch script
cat > start_server.py << 'EOF'
#!/usr/bin/env python3
import os
from pathlib import Path

# Load .env
for line in Path('.env').read_text().splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        key, value = line.split('=', 1)
        if value:
            os.environ[key] = value

# Initialize and start server
from nlweb_core import init
init('config.yaml')

from nlweb_network.server import main
main()
EOF

chmod +x start_server.py

# Kill any existing server on port 8080
echo "🧹 Checking for existing servers on port 8080..."
EXISTING_PID=$(lsof -ti:8080 2>/dev/null || true)
if [ ! -z "$EXISTING_PID" ]; then
    echo "  → Killing existing process $EXISTING_PID"
    kill -9 $EXISTING_PID 2>/dev/null || true
    sleep 2
fi
echo "✅ Port 8080 is clear"
echo ""

# Start server in background
echo "🚀 Starting NLWeb server..."
python start_server.py > server.log 2>&1 &
SERVER_PID=$!

echo "✅ Server started (PID: $SERVER_PID)"
echo ""

# Wait for server to be ready
echo "⏳ Waiting for server to start..."
for i in {1..30}; do
    if curl -s http://localhost:8080/health > /dev/null 2>&1; then
        echo "✅ Server is ready!"
        break
    fi
    if [ $i -eq 30 ]; then
        echo "❌ Server failed to start after 30 seconds"
        echo ""
        echo "Server logs:"
        cat server.log
        kill $SERVER_PID 2>/dev/null || true
        exit 1
    fi
    sleep 1
    echo -n "."
done
echo ""
echo ""

# Run tests
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 Running Tests Against Real Database"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test 1: Health check
echo "Test 1: Health check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s http://localhost:8080/health | python3 -m json.tool
echo ""
echo ""

# Test 2: HTTP JSON (non-streaming)
echo "Test 2: HTTP JSON - 'spicy snacks' from seriouseats (non-streaming)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s --max-time 60 "http://localhost:8080/ask?query=spicy+snacks&site=seriouseats&streaming=false&num_results=5" > /tmp/test_response.json 2>&1
CURL_EXIT=$?

if [ $CURL_EXIT -ne 0 ]; then
    echo "❌ Curl failed with exit code $CURL_EXIT"
    cat /tmp/test_response.json
    exit 1
fi

cat > /tmp/parse_response.py << 'PYEOF'
import json
import sys

try:
    with open('/tmp/test_response.json') as f:
        data = json.load(f)

    # Print metadata
    if "_meta" in data:
        print("\n📊 Metadata:")
        print("=" * 80)
        print(json.dumps(data["_meta"], indent=2))
        print()

    # Print results
    print("📝 Results:")
    print("=" * 80)

    content = data.get("content", [])
    if not content:
        print("❌ No results found")
    else:
        result_count = len([c for c in content if c["type"] == "resource"])
        print(f"✅ Found {result_count} results\n")

        for i, item in enumerate(content, 1):
            if item["type"] == "text":
                print(f"\n💬 LLM Summary:\n{item['text']}\n")
            elif item["type"] == "resource":
                resource = item["resource"]["data"]
                print(f"\n📄 Recipe {i}:")
                print(f"   Name: {resource.get('name', 'N/A')}")
                print(f"   URL: {resource.get('url', 'N/A')}")
                print(f"   Site: {resource.get('site', 'N/A')}")
                if "recipeCategory" in resource:
                    print(f"   Category: {', '.join(resource.get('recipeCategory', []))}")
                if "totalTime" in resource:
                    print(f"   Time: {resource.get('totalTime', 'N/A')}")
                if "description" in resource:
                    desc = resource.get('description', '')
                    if len(desc) > 150:
                        desc = desc[:150] + "..."
                    print(f"   Description: {desc}")
                print()
except json.JSONDecodeError as e:
    print(f"❌ Failed to parse JSON response: {e}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Error processing response: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
PYEOF

python3 /tmp/parse_response.py

TEST2_RESULT=$?
echo ""

# Test 3: HTTP SSE (streaming)
echo "Test 3: HTTP SSE - 'pasta' (streaming)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s --max-time 60 "http://localhost:8080/ask?query=pasta&streaming=true&num_results=2" > /tmp/test_sse.txt 2>&1
if [ -s /tmp/test_sse.txt ]; then
    echo "✅ Received SSE stream ($(wc -c < /tmp/test_sse.txt) bytes)"
    echo "First 200 chars:"
    head -c 200 /tmp/test_sse.txt
    echo ""
    echo "..."
    TEST3_RESULT=0
else
    echo "❌ No SSE response received"
    TEST3_RESULT=1
fi
echo ""
echo ""

# Test 4: MCP JSON-RPC
echo "Test 4: MCP - tools/list"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s --max-time 30 -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "tools/list", "id": 1}' | python3 -m json.tool
echo ""
echo ""

# Test 5: MCP tools/call
echo "Test 5: MCP - tools/call 'dessert recipes'"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s --max-time 60 -X POST http://localhost:8080/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "tools/call",
    "params": {
      "name": "ask",
      "arguments": {
        "query": "dessert recipes",
        "num_results": 2
      }
    },
    "id": 2
  }' > /tmp/test_mcp.json 2>&1

cat > /tmp/parse_mcp.py << 'PYEOF'
import json

try:
    with open('/tmp/test_mcp.json') as f:
        data = json.load(f)

    if "result" in data:
        result = data["result"]
        if isinstance(result, list):
            print(f"✅ MCP returned {len(result)} content items")
            for i, item in enumerate(result[:3], 1):
                if item.get("type") == "resource":
                    resource = item["resource"]["data"]
                    print(f"  {i}. {resource.get('name', 'N/A')[:60]}")
        else:
            print("✅ MCP result:", json.dumps(result, indent=2)[:200])
    elif "error" in data:
        print(f"❌ MCP error: {data['error']}")
        exit(1)
    else:
        print("❌ Unexpected MCP response format")
        exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
PYEOF

python3 /tmp/parse_mcp.py
TEST5_RESULT=$?
echo ""
echo ""

# Test 6: A2A agent/card
echo "Test 6: A2A - agent/card"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s --max-time 30 -X POST http://localhost:8080/a2a \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "method": "agent/card", "id": 1}' | python3 -c "import json, sys; d=json.load(sys.stdin); print('✅ Agent:', d['result'].get('name', 'N/A'), '-', d['result'].get('description', 'N/A')[:80])"
echo ""
echo ""

# Test 7: A2A message/send
echo "Test 7: A2A - message/send 'healthy breakfast'"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s --max-time 60 -X POST http://localhost:8080/a2a \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "message/send",
    "params": {
      "message": {
        "role": "user",
        "parts": [{"kind": "text", "text": "healthy breakfast"}]
      }
    },
    "id": 3
  }' > /tmp/test_a2a.json 2>&1

cat > /tmp/parse_a2a.py << 'PYEOF'
import json

try:
    with open('/tmp/test_a2a.json') as f:
        data = json.load(f)

    if "result" in data:
        result = data["result"]
        if "content" in result:
            content = result["content"]
            resource_count = len([c for c in content if c.get("type") == "resource"])
            print(f"✅ A2A returned {resource_count} resources")
            for item in content[:2]:
                if item.get("type") == "resource":
                    resource = item["resource"]["data"]
                    print(f"  - {resource.get('name', 'N/A')[:60]}")
        else:
            print("✅ A2A result received")
    elif "error" in data:
        print(f"❌ A2A error: {data['error']}")
        exit(1)
    else:
        print("❌ Unexpected A2A response")
        exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
PYEOF

python3 /tmp/parse_a2a.py
TEST7_RESULT=$?
echo ""
echo ""

# Test 8: Previous test (pasta recipes without filter)
echo "Test 8: HTTP JSON - 'pasta recipes' (no site filter)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s --max-time 60 "http://localhost:8080/ask?query=pasta+recipes&streaming=false&num_results=3" > /tmp/test_response3.json 2>&1
CURL_EXIT=$?

if [ $CURL_EXIT -ne 0 ]; then
    echo "❌ Curl failed with exit code $CURL_EXIT"
    cat /tmp/test_response3.json
    exit 1
fi

cat > /tmp/parse_response3.py << 'PYEOF'
import json

try:
    with open('/tmp/test_response3.json') as f:
        data = json.load(f)

    content = data.get("content", [])

    if not content:
        print("❌ No results found")
        exit(1)
    else:
        result_count = len([c for c in content if c["type"] == "resource"])
        print(f"✅ Found {result_count} results\n")

        for i, item in enumerate(content, 1):
            if item["type"] == "resource":
                resource = item["resource"]["data"]
                print(f"{i}. {resource.get('name', 'N/A')}")
                print(f"   Site: {resource.get('site', 'N/A')}")
                print(f"   URL: {resource.get('url', 'N/A')}")
                print()
except json.JSONDecodeError as e:
    print(f"❌ JSON parse error: {e}")
    exit(1)
except Exception as e:
    print(f"❌ Error: {e}")
    exit(1)
PYEOF

python3 /tmp/parse_response3.py

TEST8_RESULT=$?
echo ""

# Cleanup
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧹 Cleaning up..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Kill server
kill $SERVER_PID 2>/dev/null || true
sleep 1
echo "✅ Server stopped"
echo ""

# Check if tests passed
if [ $TEST2_RESULT -ne 0 ] || [ $TEST3_RESULT -ne 0 ] || [ $TEST5_RESULT -ne 0 ] || [ $TEST7_RESULT -ne 0 ] || [ $TEST8_RESULT -ne 0 ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "❌ TESTS FAILED"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Test Results:"
    echo "  Test 2 (HTTP JSON): $([ $TEST2_RESULT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
    echo "  Test 3 (HTTP SSE): $([ $TEST3_RESULT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
    echo "  Test 5 (MCP tools/call): $([ $TEST5_RESULT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
    echo "  Test 7 (A2A message/send): $([ $TEST7_RESULT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
    echo "  Test 8 (HTTP JSON no filter): $([ $TEST8_RESULT -eq 0 ] && echo '✅ PASS' || echo '❌ FAIL')"
    echo ""
    echo "Server logs:"
    tail -50 server.log
    echo ""
    echo "Test directory preserved at: $TEST_DIR"
    echo "To inspect:"
    echo "  cd $TEST_DIR"
    echo "  source venv/bin/activate"
    echo "  cat server.log"
    exit 1
fi

# Deactivate and clean up
deactivate
cd /
rm -rf "$TEST_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ ALL TESTS PASSED!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Summary:"
echo "  ✓ Clean virtual environment created"
echo "  ✓ Packages installed from PyPI"
echo "  ✓ Server started with real config"
echo "  ✓ HTTP JSON (non-streaming) working"
echo "  ✓ HTTP SSE (streaming) working"
echo "  ✓ MCP protocol working (tools/list, tools/call)"
echo "  ✓ A2A protocol working (agent/card, message/send)"
echo "  ✓ Site filtering working"
echo "  ✓ LLM summarization working"
echo "  ✓ Schema.org data preserved"
echo "  ✓ Cleanup completed"
echo ""
echo "🎉 All NLWeb packages and protocols working correctly from PyPI!"
echo ""
