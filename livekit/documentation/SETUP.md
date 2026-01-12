# Setup Guide

Complete setup instructions for the Restaurant Voice AI Agent.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Service Account Setup](#service-account-setup)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Verification](#verification)
6. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Operating System**: macOS, Linux, or Windows
- **Python**: 3.11 or higher
- **RAM**: Minimum 4GB (8GB recommended)
- **Disk Space**: Minimum 2GB free
- **Network**: Stable internet connection with low latency

### Required Accounts

You'll need accounts for the following services:

1. **LiveKit Cloud** (https://cloud.livekit.io)
2. **OpenAI** (https://platform.openai.com)
3. **Deepgram** (https://deepgram.com)
4. **Cartesia** (https://cartesia.ai)
5. **Twilio** (https://twilio.com)
6. **Stripe** (https://stripe.com)

## Service Account Setup

### 1. LiveKit Cloud

1. Sign up at https://cloud.livekit.io
2. Create a new project
3. Navigate to **Settings** → **Keys**
4. Copy your:
   - API Key
   - API Secret
   - WebSocket URL (format: `wss://your-project.livekit.cloud`)

### 2. OpenAI

1. Sign up at https://platform.openai.com
2. Navigate to **API Keys**
3. Click **Create new secret key**
4. Copy the key (starts with `sk-proj-...`)
5. Set up billing to enable API access

### 3. Deepgram

1. Sign up at https://deepgram.com
2. Navigate to **API Keys**
3. Create a new API key
4. Copy the key

### 4. Cartesia

1. Sign up at https://cartesia.ai
2. Navigate to **API Keys**
3. Create a new API key
4. Copy the key
5. (Optional) Browse voice options and note voice IDs you'd like to use

### 5. Twilio

1. Sign up at https://twilio.com
2. Navigate to **Console**
3. Copy your:
   - Account SID
   - Auth Token
4. Purchase a phone number:
   - Go to **Phone Numbers** → **Buy a Number**
   - Select a number with Voice and SMS capabilities
   - Complete purchase
   - Copy the phone number (format: `+1234567890`)

### 6. Stripe

1. Sign up at https://stripe.com
2. Navigate to **Developers** → **API Keys**
3. Copy your:
   - Publishable key (for frontend, if needed)
   - Secret key (starts with `sk_test_` for test mode)
4. Navigate to **Developers** → **Webhooks**
5. Click **Add endpoint**
6. Enter your webhook URL: `https://your-domain.com/webhooks/stripe/payment`
7. Select events to listen to:
   - `payment_intent.succeeded`
   - `payment_intent.payment_failed`
   - `charge.refunded`
8. Copy the webhook signing secret (starts with `whsec_`)

## Installation

### 1. Clone Repository

```bash
git clone https://github.com/your-org/Aisyst-livekit-agents.git
cd Aisyst-livekit-agents
```

### 2. Install UV Package Manager

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```powershell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Verify installation:
```bash
uv --version
```

### 3. Install Dependencies

```bash
uv sync
```

This will:
- Create a virtual environment
- Install all Python dependencies
- Set up development tools

### 4. Download Model Files

```bash
uv run agents/restaurant_agent.py download-files
```

This downloads:
- Silero VAD model files
- Turn detection models
- Noise cancellation models

## Configuration

### 1. Create Environment File

```bash
cp .env.example .env.local
```

### 2. Configure Environment Variables

Edit `.env.local` with your credentials:

```env
# LiveKit Configuration
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=APIxxxxxxxxxxxxxxxxx
LIVEKIT_API_SECRET=your-api-secret

# AI Model Providers
OPENAI_API_KEY=sk-proj-xxxxxxxxxxxxxxxxxx
DEEPGRAM_API_KEY=xxxxxxxxxxxxxxxxxx
CARTESIA_API_KEY=xxxxxxxxxxxxxxxxxx

# Twilio SMS
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+1234567890

# Stripe Payments
STRIPE_API_KEY=sk_test_xxxxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxxxx
STRIPE_SUCCESS_URL=https://yoursite.com/success
STRIPE_CANCEL_URL=https://yoursite.com/cancel

# Restaurant Info
RESTAURANT_NAME=Your Restaurant Name
RESTAURANT_PHONE=+1234567890
RESTAURANT_ADDRESS=123 Main St, City, State

# Optional
LOG_LEVEL=INFO
ENABLE_METRICS=true
```

### 3. Customize Menu Data

Edit `agents/config/menu_data.py` to add your restaurant's actual menu items, prices, and categories.

### 4. Customize Agent Instructions

Edit `agents/config/prompts.py` to customize the agent's personality and behavior.

## Verification

### 1. Test Console Mode

```bash
uv run agents/restaurant_agent.py console
```

This starts the agent in your terminal. You can speak to test the voice pipeline.

**Expected output:**
```
INFO: Restaurant agent initialized
INFO: Starting console mode...
```

Press `Ctrl+C` to exit.

### 2. Test Development Mode

```bash
uv run agents/restaurant_agent.py dev
```

This connects your agent to LiveKit Cloud.

**Expected output:**
```
INFO: Starting restaurant voice agent
INFO: Connected to LiveKit Cloud
INFO: Agent registered and ready
```

### 3. Test in Playground

1. Open https://cloud.livekit.io/projects/p_/agents/playground
2. Click **Connect**
3. Speak: "Hello, I'd like to order some food"
4. Verify the agent responds appropriately

### 4. Verify Integrations

**Test Twilio SMS:**
```bash
python -c "from twilio.sms_client import TwilioSMSClient; import asyncio; client = TwilioSMSClient(); asyncio.run(client.send_sms('+YOUR_PHONE', 'Test message'))"
```

**Test Stripe Payment:**
```bash
python -c "from stripe.payment_client import StripePaymentClient; import asyncio; client = StripePaymentClient(); asyncio.run(client.create_payment_link(1000, 'TEST-001'))"
```

## Troubleshooting

### Common Issues

**Issue: "Module not found" errors**
```bash
# Solution: Reinstall dependencies
uv sync --reinstall
```

**Issue: "Failed to download model files"**
```bash
# Solution: Check internet connection and retry
uv run agents/restaurant_agent.py download-files
```

**Issue: "Authentication failed" for LiveKit**
```bash
# Solution: Verify credentials
echo $LIVEKIT_API_KEY
echo $LIVEKIT_API_SECRET
# Make sure they match your LiveKit Cloud project
```

**Issue: "Twilio authentication failed"**
```bash
# Solution: Verify Twilio credentials
python -c "from twilio.rest import Client; c = Client(); print('OK')"
```

**Issue: "Stripe API error"**
```bash
# Solution: Check Stripe API key
python -c "import stripe; stripe.api_key='YOUR_KEY'; print(stripe.Account.retrieve())"
```

**Issue: Agent not responding**
- Check OpenAI API key and billing
- Verify Deepgram API key
- Check network latency
- Review logs in `logs/app.log`

**Issue: Poor audio quality**
- Enable background voice cancellation
- Check microphone settings
- Verify network bandwidth (minimum 1Mbps)
- Try a different voice model

### Getting Help

1. **Check logs**: `tail -f logs/app.log`
2. **Enable debug mode**: Set `LOG_LEVEL=DEBUG` in `.env.local`
3. **Review documentation**: See `documentation/` folder
4. **Check LiveKit docs**: https://docs.livekit.io
5. **GitHub issues**: Report bugs at repository issues page

## Next Steps

- [Deploy to Production](DEPLOYMENT.md)
- [Configure Monitoring](MONITORING.md)
- [Set up Testing](../tests/README.md)
- [Review Architecture](ARCHITECTURE.md)

---

**Need help?** Check the [Troubleshooting Guide](TROUBLESHOOTING.md) or open an issue on GitHub.
