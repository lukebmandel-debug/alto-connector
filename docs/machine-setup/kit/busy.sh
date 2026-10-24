#!/bin/bash
# Shared machine-busy check for Alto sessions (one browser OR one pytest at a time).
# Exit 0 = busy (a real test runner or Playwright browser is running), 1 = free.
# Matches only real processes, never another session's waiting shell wrapper.
ps -axo comm=,args= | awk -v t="py""test" '($1 ~ /python/ && index($0, "-m " t)) || ($1 ~ /Playwright|chrome-headless|headless_shell/) || index($0, "--remote-debugging-pipe") {f=1} END {exit f?0:1}'
