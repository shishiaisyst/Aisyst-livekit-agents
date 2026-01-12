# Quick Start Guide

Get your restaurant voice agent running in under 10 minutes!

## Prerequisites

- Python 3.11+
- Accounts for: LiveKit Cloud, OpenAI, Deepgram, Cartesia, Twilio, Stripe

## Installation

```bash
# 1. Clone and navigate to project
git clone <repository-url>
cd Aisyst-livekit-agents

# 2. Install UV package manager
curl -LsSf https://astral.sh/uv/install.sh | sh

# 3. Install dependencies
uv sync

# 4. Download model files
uv run agents/restaurant_agent.py download-files
```

## Configuration

```bash
# 1. Copy environment template
cp .env.example .env.local

# 2. Edit .env.local with your credentials
# - LiveKit: URL, API Key, API Secret
# - OpenAI: API Key
# - Deepgram: API Key
# - Cartesia: API Key
# - Twilio: Account SID, Auth Token, Phone Number
# - Stripe: API Key, Webhook Secret

# 3. Customize menu (optional)
# Edit agents/config/menu_data.py
```

## Run

```bash
# Console mode (local testing with voice I/O)
uv run agents/restaurant_agent.py console

# Development mode (connect to LiveKit Cloud)
uv run agents/restaurant_agent.py dev

# Then test in: https://cloud.livekit.io/projects/p_/agents/playground
```

## Deploy

```bash
# Install LiveKit CLI
brew install livekit

# Authenticate
lk cloud auth

# Deploy
lk agent create
```

## Test

```bash
# Run tests
uv run pytest

# Make a test call (requires SIP trunk setup)
uv run scripts/test_call.py --phone=+1234567890
```

## Next Steps

- **Customize Menu**: Edit `agents/config/menu_data.py`
- **Adjust Prompts**: Edit `agents/config/prompts.py`
- **Monitor Performance**: Check LiveKit Cloud dashboard
- **Set up Telephony**: Configure SIP trunk for phone calls
- **Review Full Setup**: See [SETUP.md](SETUP.md)

## Troubleshooting

**Agent not responding?**
- Check API keys in `.env.local`
- Verify billing is set up for OpenAI
- Check logs: `tail -f logs/app.log`

**Audio quality issues?**
- Enable noise cancellation in agent code
- Check network bandwidth
- Try a different TTS voice

**Need Help?**
- Full documentation: `documentation/` folder
- LiveKit docs: https://docs.livekit.io
- Open an issue on GitHub

---

**That's it!** Your voice agent should now be running. 🎉
