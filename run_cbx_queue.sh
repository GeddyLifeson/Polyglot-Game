#!/bin/bash
# waits for a chain to finish, then runs the next one on the GPU: keeps exactly two recorders on the card
cd /c/Users/imarl/polyglot_game
after=$1; tag=$2; shift 2
until grep -q "ALL DONE" gen_cbx_chain_$after.log 2>/dev/null; do sleep 60; done
bash run_cbx_chain.sh $tag "$@"
