#!/bin/bash
# Double-click on a Mac to run the site with Claude Haiku through YOUR Claude Code login (Pro/Max plan), at http://localhost:8000.
# Needs Claude Code installed and signed in once: open Terminal, run `claude`, log in with your Claude account. Ctrl+C to stop.
# Uses your plan's usage limits, not API billing. For running on your own computer only.
cd "$(dirname "$0")"
export AI_PROVIDER=claude
export AI_MODEL="${AI_MODEL:-haiku}"     # or sonnet
export AI_CONTEXT_K=6                    # Claude has room for more NASA investigations per question than Groq's free plan
PORT=8000
OLD=$(lsof -ti tcp:$PORT -sTCP:LISTEN 2>/dev/null)
if [ -n "$OLD" ]; then
  if curl -s -m 2 "http://localhost:$PORT/api/health" | grep -q '"ok"'; then
    echo "Stopping the stand-in server that was already running on port $PORT..."
    kill $OLD 2>/dev/null; sleep 1
  else
    echo "Port $PORT is used by something else. Close it and run again."; exit 1
  fi
fi
if ! command -v claude >/dev/null 2>&1 && [ ! -x "$HOME/.local/bin/claude" ] && [ ! -x "$HOME/.claude/local/claude" ] && [ ! -x /opt/homebrew/bin/claude ] && [ ! -x /usr/local/bin/claude ]; then
  echo "Claude Code isn't installed (or not on PATH). Install it from https://code.claude.com, run 'claude' once to sign in, then try again."
fi
( sleep 1.5; open "http://localhost:$PORT" ) &
python3 standin/server.py
