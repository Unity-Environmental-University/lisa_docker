#!/bin/bash
set -euo pipefail

cd /home/mvirgin/lisa_docker
source .venv/bin/activate

until pg_isready -h localhost -p 5433; do
    sleep 10
done

echo "===== $(date -Is) starting run =====" >> logs/run.log
python3.12 dbupdate.py sync all >> logs/run.log 2>&1
echo "===== $(date -Is) finished run =====" >> logs/run.log