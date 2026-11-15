#!/bin/bash
# The old Claude stand-in uses context.json, not the reviewed graph or shared
# thermo functions. Fail clearly so it cannot be mistaken for the graph-backed app.
echo "This legacy Claude demo does not use the reviewed PSI graph."
echo "Run start_ai_server.command to use the integrated backend at http://localhost:8015."
exit 1
