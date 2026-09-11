#!/bin/bash
# usage: run_cbx_chain_cpu.sh <tag> lang1 lang2 ...  — CPU recorder chain, 6 threads, resumable
cd /c/Users/imarl/polyglot_game; export PATH="$PWD/bin:$PATH" PYTHONIOENCODING=utf-8 OMP_NUM_THREADS=6 MKL_NUM_THREADS=6
tag=$1; shift
for l in "$@"; do
  mkdir -p staging_cbx_$l
  ./.venv311cbx/python.exe -u tools/gen_audio.py A1 A2 B1 B2 C1 C2 TILES --langs $l --backend chatterbox --cbx-device cpu --out staging_cbx_$l >> gen_cbx_$l.log 2>&1
  echo "$(date +%T) chain $tag finished $l" >> gen_cbx_chain_$tag.log
done
echo "$(date +%T) chain $tag ALL DONE" >> gen_cbx_chain_$tag.log
