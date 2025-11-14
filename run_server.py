#!/usr/bin/env python
"""
Wrapper script to run the NLWeb server with better error handling.
This helps diagnose startup issues in containerized environments.
"""
import sys
import traceback

def main():
    try:
        print("Starting NLWeb server...")
        print(f"Python version: {sys.version}")
        print(f"Python path: {sys.path}")

        # Import and run the server
        from nlweb_network.server import main as server_main
        print("Server module imported successfully")

        server_main()

    except Exception as e:
        print(f"\n{'='*60}")
        print(f"FATAL ERROR: Server failed to start")
        print(f"{'='*60}")
        print(f"Error type: {type(e).__name__}")
        print(f"Error message: {str(e)}")
        print(f"\nFull traceback:")
        traceback.print_exc()
        print(f"{'='*60}\n")
        sys.exit(1)

if __name__ == '__main__':
    main()
