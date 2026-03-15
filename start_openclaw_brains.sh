#!/bin/bash
source /home/openclaw/chief_env/bin/activate

pkill -f chief_album_brain.py
pkill -f chief_billing_brain.py

setsid -f python /home/openclaw/chief_album_brain.py </dev/null >/tmp/chief_album_brain.log 2>&1
setsid -f python /home/openclaw/chief_billing_brain.py </dev/null >/tmp/chief_billing_brain.log 2>&1
