#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."
docker compose up -d neo4j
echo "Neo4j local reproduction service: bolt://127.0.0.1:7688"
