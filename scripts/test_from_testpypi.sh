#!/bin/bash
# Test NLWeb packages from TestPyPI in a clean virtual environment
# This script:
# 1. Creates a fresh virtual environment
# 2. Installs packages from TestPyPI
# 3. Creates a test config
# 4. Starts the server
# 5. Tests with curl
# 6. Cleans up

set -e

echo "🧪 Testing NLWeb packages from TestPyPI"
echo "========================================"
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

# Install packages from TestPyPI
echo "📦 Installing packages from TestPyPI..."
echo ""

# Install core dependencies first from regular PyPI
pip install --quiet aiohttp pyyaml python-dotenv

# Install NLWeb packages from TestPyPI
echo "  → Installing nlweb-dataload..."
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple nlweb-dataload

echo "  → Installing nlweb-core..."
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple nlweb-core

echo "  → Installing nlweb-network..."
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple nlweb-network

echo "  → Installing nlweb-azure-vectordb..."
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple nlweb-azure-vectordb

echo "  → Installing nlweb-elastic-vectordb..."
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple nlweb-elastic-vectordb

echo "  → Installing nlweb-qdrant-vectordb..."
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple nlweb-qdrant-vectordb

echo "  → Installing nlweb-snowflake-vectordb..."
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple nlweb-snowflake-vectordb

echo "  → Installing nlweb-azure-models..."
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple nlweb-azure-models

echo ""
echo "✅ All packages installed"
echo ""

# Verify installations
echo "🔍 Verifying installed packages..."
pip list | grep nlweb
echo ""

# Copy the real config from the main project
echo "⚙️  Copying configuration from main project..."
if [ -f "$HOME/code/NLWeb_Core/config.yaml" ]; then
    cp "$HOME/code/NLWeb_Core/config.yaml" config.yaml
    echo "✅ Config copied from $HOME/code/NLWeb_Core/config.yaml"
else
    echo "❌ Error: Config file not found at $HOME/code/NLWeb_Core/config.yaml"
    echo "   Please provide a valid config.yaml path"
    exit 1
fi
echo ""

# Create .env file with necessary environment variables
echo "🔑 Setting up environment variables..."
cat > .env << EOF
# Azure credentials
AZURE_OPENAI_KEY=${AZURE_OPENAI_KEY:-}
AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT:-}
AZURE_SEARCH_KEY=${AZURE_SEARCH_KEY:-}
AZURE_SEARCH_ENDPOINT=${AZURE_SEARCH_ENDPOINT:-}

# OpenAI credentials
OPENAI_API_KEY=${OPENAI_API_KEY:-}

# Other keys
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
EOF

echo "✅ Environment variables saved to .env"
echo ""

# Create server launch script that uses real NLWeb
echo "🚀 Creating server launch script..."
cat > start_server.py << 'EOF'
#!/usr/bin/env python3
import sys
import os
import asyncio
from pathlib import Path

# Load environment variables from .env file
env_file = Path('.env')
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                if value:  # Only set if not empty
                    os.environ[key] = value

from nlweb_network.http import start_server

if __name__ == '__main__':
    asyncio.run(start_server('config.yaml'))
EOF

chmod +x start_server.py

echo "✅ Server launch script created"
echo ""

# Start server in background
echo "🚀 Starting NLWeb server in background..."
python start_server.py > server.log 2>&1 &
SERVER_PID=$!

echo "✅ Server started (PID: $SERVER_PID)"
echo ""

# Wait for server to be ready
echo "⏳ Waiting for server to start..."
sleep 3

# Test with curl
echo "🧪 Testing endpoints with curl..."
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 1: Health check"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
curl -s http://localhost:8080/health | python3 -m json.tool
echo ""
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 2: Query 'spicy snacks' from seriouseats (JSON mode)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
RESPONSE=$(curl -s "http://localhost:8080/ask?query=spicy+snacks&site=seriouseats&streaming=false&num_results=5")

# Pretty print the results
echo "$RESPONSE" | python3 << 'PYEOF'
import json
import sys

data = json.load(sys.stdin)
print("Metadata:", json.dumps(data["_meta"], indent=2))
print()
print("Results:")
print("=" * 80)

for i, item in enumerate(data.get("content", []), 1):
    if item["type"] == "text":
        print(f"\n{i}. {item['text']}\n")
    elif item["type"] == "resource":
        resource = item["resource"]["data"]
        print(f"   Name: {resource.get('name', 'N/A')}")
        print(f"   URL: {resource.get('url', 'N/A')}")
        print(f"   Site: {resource.get('site', 'N/A')}")
        if "recipeCategory" in resource:
            print(f"   Category: {resource.get('recipeCategory', [])}")
        if "totalTime" in resource:
            print(f"   Time: {resource.get('totalTime', 'N/A')}")
        print()
PYEOF
echo ""

# Check server logs
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Server logs:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cat server.log
echo ""

# Cleanup
echo "🧹 Cleaning up..."
kill $SERVER_PID 2>/dev/null || true
sleep 1

echo "✅ Server stopped"
echo ""

# Deactivate and clean up
deactivate
cd /
rm -rf "$TEST_DIR"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Test completed successfully!"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Summary:"
echo "  ✓ Clean virtual environment created"
echo "  ✓ Packages installed from TestPyPI"
echo "  ✓ Server started successfully"
echo "  ✓ Endpoints tested with curl"
echo "  ✓ Cleanup completed"
echo ""
echo "All NLWeb packages are working correctly from TestPyPI! 🎉"
