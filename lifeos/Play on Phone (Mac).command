#!/bin/bash
# Double-click to start LIFE OS. The first run installs what it needs (about a minute, needs internet).
cd "$(dirname "$0")"
echo ""
echo "  =============================="
echo "   LIFE OS - Living World Lab"
echo "  =============================="
echo ""
PY="$(command -v python3 || command -v python)"
if [ -z "$PY" ]; then
  echo "  Couldn't find Python. Install it from https://www.python.org/downloads/ and double-click this file again."
  read -n 1 -s -r -p "  Press any key to close."
  exit 1
fi
if [ ! -f .venv/installed.ok ]; then
  echo "  First time setup. This takes a minute or two and needs internet."
  echo ""
  rm -rf .venv
  if "$PY" -m venv .venv && .venv/bin/python -m pip install --upgrade pip --quiet && .venv/bin/python -m pip install -r requirements.txt; then
    touch .venv/installed.ok
    echo ""
    echo "  Setup finished."
  else
    echo ""
    echo "  Setup didn't finish. Check your internet connection and double-click this file again."
    rm -rf .venv
    read -n 1 -s -r -p "  Press any key to close."
    exit 1
  fi
fi
echo ""
echo "  LIFE OS is starting so your phone can connect."
echo "  A page with a QR code opens on this computer. Scan it with your phone (same Wi-Fi)."
echo "  If macOS asks to allow incoming connections for Python, click Allow."
echo "  Keep this window open while you play. Close it to stop LIFE OS."
echo ""
.venv/bin/python run.py --phone
