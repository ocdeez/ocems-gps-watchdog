# OCEMS GPS Monitor Service

This service monitors Peplink MAX BR1 Mini GPS data via the InControl API.

If GPS data stops updating (stale), the service automatically sends a reboot
command to the affected device.

## Features
- Polls 9+ devices from environment variables
- Detects stale GPS data
- Reboots devices via InControl REST API
- Built for Render.com deployment

## Files
- `main.py` — main service loop
- `requirements.txt` — Python packages
- `Procfile` — tells Render how to run the script
- `.env` — stored ONLY in Render (never in GitHub)

## Deployment
1. Push this repo to GitHub  
2. Connect Render → New Worker → use this repo  
3. Add all environment variables in the Render dashboard  
4. Deploy

