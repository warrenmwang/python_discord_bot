#!/bin/bash
cd alpaca.cpp
# ./chat -p '$($1)' | tee alpaca_response.txt
./chat -p "$1" > alpaca_response.txt