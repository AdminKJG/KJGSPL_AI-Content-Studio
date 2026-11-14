#!/bin/sh
set -eu
# Render's free filesystem is ephemeral. This is an evaluation service only.
mkdir -p /app/data /app/workspace /app/outputs /app/agent_workspace /app/videofx_outputs /tmp/nginx/client_body /tmp/nginx/proxy /tmp/nginx/fastcgi /tmp/nginx/uwsgi /tmp/nginx/scgi
test -n "${STUDIO_API_TOKEN:-}" || { echo 'STUDIO_API_TOKEN is required'; exit 1; }
test -n "${STUDIO_PUBLIC_ORIGIN:-}" || { echo 'STUDIO_PUBLIC_ORIGIN is required'; exit 1; }
export CORS_ORIGINS="$STUDIO_PUBLIC_ORIGIN"
export STUDIO_SECURE_COOKIES=true
(cd /app && python -m uvicorn server.main:app --host 127.0.0.1 --port 8008 --workers 1 --no-proxy-headers) &
BACKEND=$!
(cd /app/frontend && HOSTNAME=127.0.0.1 PORT=3000 node server.js) &
FRONTEND=$!
nginx -g 'daemon off;' &
PROXY=$!
trap 'kill $BACKEND $FRONTEND $PROXY 2>/dev/null || true' INT TERM EXIT
while kill -0 "$BACKEND" 2>/dev/null && kill -0 "$FRONTEND" 2>/dev/null && kill -0 "$PROXY" 2>/dev/null; do sleep 3; done
echo 'A Studio process exited; shutting down for restart'
exit 1
