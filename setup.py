from setuptools import setup, find_packages
import os

# Read README for long description
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="nlweb-core",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    python_requires=">=3.8",
    install_requires=[
        # Core dependencies
        "aiohttp>=3.8.0",
        "pyyaml>=6.0",
        "python-dotenv>=0.19.0",

        # Azure dependencies
        "azure-search-documents>=11.4.0",
        "azure-identity>=1.12.0",
        "azure-core>=1.26.0",

        # OpenAI
        "openai>=1.12.0",
    ],
    extras_require={
        # Development dependencies
        "dev": [
            "pytest>=7.0",
            "black>=22.0",
            "flake8>=4.0",
        ],

        # Optional LLM providers
        "anthropic": ["anthropic>=0.18.0"],
        "gemini": ["google-generativeai>=0.3.0"],
        "huggingface": ["huggingface_hub>=0.31.0"],

        # Optional embedding providers
        "ollama": ["ollama>=0.5.1"],

        # Optional vector databases
        "qdrant": ["qdrant-client>=1.7.0"],
        "elasticsearch": ["elasticsearch>=8.0.0"],
        "opensearch": ["opensearch-py>=2.0.0"],
        "postgres": ["psycopg2-binary>=2.9.0"],
        "milvus": ["pymilvus>=2.3.0"],

        # Optional utilities
        "snowflake": ["httpx>=0.28.1"],

        # Web server extras
        "cors": ["aiohttp-cors>=0.7.0"],

        # All optional dependencies
        "all": [
            "anthropic>=0.18.0",
            "google-generativeai>=0.3.0",
            "huggingface_hub>=0.31.0",
            "ollama>=0.5.1",
            "qdrant-client>=1.7.0",
            "elasticsearch>=8.0.0",
            "opensearch-py>=2.0.0",
            "psycopg2-binary>=2.9.0",
            "pymilvus>=2.3.0",
            "httpx>=0.28.1",
            "aiohttp-cors>=0.7.0",
        ],
    },
    author="Microsoft Corporation",
    author_email="",
    description="NLWeb Core library for building natural language web applications with vector database retrieval and LLM-based ranking",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/NLWeb_Core",
    project_urls={
        "Bug Tracker": "https://github.com/yourusername/NLWeb_Core/issues",
        "Documentation": "https://github.com/yourusername/NLWeb_Core/blob/main/README.md",
        "Source Code": "https://github.com/yourusername/NLWeb_Core",
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Internet :: WWW/HTTP :: HTTP Servers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    keywords="nlp, llm, vector-database, rag, retrieval, azure, openai, search",
    entry_points={
        "console_scripts": [
            "nlweb-server=nlweb_core.simple_server:main",
        ],
    },
)
