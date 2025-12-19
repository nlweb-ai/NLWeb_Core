#!/usr/bin/env python3
"""
Script to dump conversations from PostgreSQL database.

Usage:
    python dump_conversations.py [--limit N] [--user USER_ID] [--conversation CONV_ID]
"""

import asyncio
import asyncpg
import json
import argparse
import os
from datetime import datetime


async def dump_conversations(limit=10, user_id=None, conversation_id=None):
    """Dump conversations from PostgreSQL."""

    # Get connection string from environment
    conn_str = os.getenv('POSTGRES_CONNECTION_STRING')
    if not conn_str:
        print("Error: POSTGRES_CONNECTION_STRING environment variable not set")
        print("Please run: source set_keys.sh")
        return

    try:
        # Connect to database
        conn = await asyncpg.connect(conn_str)
        print(f"Connected to PostgreSQL database\n")

        # Build query based on filters
        query = """
            SELECT message_id, conversation_id, user_id, site, timestamp,
                   request, results, metadata
            FROM conversations
        """
        params = []
        where_clauses = []

        if user_id:
            where_clauses.append(f"user_id = ${len(params) + 1}")
            params.append(user_id)

        if conversation_id:
            where_clauses.append(f"conversation_id = ${len(params) + 1}")
            params.append(conversation_id)

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        query += f" ORDER BY timestamp DESC LIMIT ${len(params) + 1}"
        params.append(limit)

        # Execute query
        rows = await conn.fetch(query, *params)

        print(f"Found {len(rows)} conversation message(s)\n")
        print("=" * 80)

        # Display results
        for idx, row in enumerate(rows, 1):
            print(f"\n--- Message {idx} ---")
            print(f"Message ID:      {row['message_id']}")
            print(f"Conversation ID: {row['conversation_id']}")
            print(f"User ID:         {row['user_id']}")
            print(f"Site:            {row['site']}")
            print(f"Timestamp:       {row['timestamp']}")

            # Display request (parse JSON if string)
            request = row['request']
            if isinstance(request, str):
                request = json.loads(request)
            print(f"\nRequest (full):")
            print(json.dumps(request, indent=2))
            print(f"\nRequest summary:")
            print(f"  Query: {request.get('query', {}).get('text', 'N/A')}")
            print(f"  Site:  {request.get('query', {}).get('site', 'N/A')}")
            if request.get('context'):
                print(f"  Context: {request.get('context')}")
            if request.get('prefer'):
                print(f"  Prefer: {request.get('prefer')}")
            if request.get('meta'):
                print(f"  Meta: {request.get('meta')}")

            # Display results count (parse JSON if string)
            results = row['results']
            if isinstance(results, str):
                results = json.loads(results) if results else None
            if results:
                print(f"\nResults: {len(results)} item(s)")
                for i, result in enumerate(results[:3], 1):  # Show first 3 results
                    print(f"  {i}. {result.get('name', 'N/A')} - {result.get('url', 'N/A')}")
                if len(results) > 3:
                    print(f"  ... and {len(results) - 3} more")
            else:
                print(f"\nResults: None")

            # Display metadata (parse JSON if string)
            metadata = row['metadata']
            if isinstance(metadata, str):
                metadata = json.loads(metadata) if metadata else None
            if metadata:
                print(f"\nMetadata: {json.dumps(metadata, indent=2)}")

            print("=" * 80)

        # Close connection
        await conn.close()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    parser = argparse.ArgumentParser(
        description='Dump conversations from PostgreSQL database'
    )
    parser.add_argument(
        '--limit', '-n',
        type=int,
        default=10,
        help='Number of messages to retrieve (default: 10)'
    )
    parser.add_argument(
        '--user', '-u',
        type=str,
        help='Filter by user ID'
    )
    parser.add_argument(
        '--conversation', '-c',
        type=str,
        help='Filter by conversation ID'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output as JSON'
    )

    args = parser.parse_args()

    asyncio.run(dump_conversations(
        limit=args.limit,
        user_id=args.user,
        conversation_id=args.conversation
    ))


if __name__ == '__main__':
    main()
