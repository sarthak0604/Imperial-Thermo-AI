#!/bin/bash
# Double-click on a Mac to run the site with the stand-in AI at http://localhost:8000 (Ctrl+C to stop).
cd "$(dirname "$0")"
PORT=8000
if [ ! -f .env.local ]; then echo "No .env.local yet — copy .env.local.example to .env.local and paste your key. Starting with mock answers."; fi
# An earlier copy of the server may still be running (that's the "Address already in use" error).
# Stop it so this run uses the latest code and prompt.
OLD=$(lsof -ti tcp:$PORT -sTCP:LISTEN 2>/dev/null)
if [ -n "$OLD" ]; then
  if curl -s -m 2 "http://localhost:$PORT/api/health" | grep -q '"ok"'; then
    echo "Stopping the stand-in server that was already running on port $PORT..."
    kill $OLD 2>/dev/null; sleep 1
  else
    echo "Port $PORT is used by something else. Close it, or set PORT=8001 in .env.local and run again."; exit 1
  fi
fi
( sleep 1.5; open "http://localhost:$PORT" ) &
python3 standin/server.py
