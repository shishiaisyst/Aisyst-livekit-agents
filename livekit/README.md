# Restaurant Voice AI Agent 🍽️🤖

A production-ready AI voice agent for restaurant order-taking via phone calls, built with LiveKit Agents framework, featuring real-time voice conversations, automated SMS notifications via Twilio, and secure payment processing through Stripe.

[![LiveKit](https://img.shields.io/badge/LiveKit-Agents-blue)](https://livekit.io)
[![Python](https://img.shields.io/badge/Python-3.11+-green)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-yellow.svg)](LICENSE)

## 📋 Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Running the Agent](#running-the-agent)
- [Deployment](#deployment)
- [Monitoring & Observability](#monitoring--observability)
- [Testing](#testing)
- [Integration Details](#integration-details)
- [Troubleshooting](#troubleshooting)
- [Contributing](#contributing)
- [License](#license)

## 🎯 Overview

This project implements a fully-featured voice AI agent that handles phone-based restaurant order-taking with the following capabilities:

- **Natural Voice Conversations**: Real-time, low-latency voice interactions using Deepgram STT, OpenAI LLM, and Cartesia TTS
- **Phone Integration**: Accept and make calls via SIP/telephony integration
- **Order Management**: Take complex orders with customizations, modifications, and special requests
- **Payment Processing**: Generate and send Stripe payment links for seamless checkout
- **SMS Notifications**: Send order confirmations and payment links via Twilio
- **Production Monitoring**: Comprehensive logging, metrics, and observability via LiveKit Insights
- **Error Handling**: Robust error recovery and fallback mechanisms

## ✨ Features

### Core Voice Agent Features
- ✅ Real-time speech-to-text with Deepgram
- ✅ Conversational intelligence with OpenAI GPT-4
- ✅ Natural text-to-speech with Cartesia
- ✅ Voice activity detection with Silero VAD
- ✅ Multilingual turn detection
- ✅ Background voice cancellation for noisy environments
- ✅ Function tools for menu lookup and order management

### Telephony Features
- ✅ Inbound call handling via SIP trunks
- ✅ Outbound calling capabilities
- ✅ DTMF support for interactive menus
- ✅ Call quality optimization for restaurant environments
- ✅ Region-specific phone number support

### Order Management
- ✅ Menu item lookup and recommendations
- ✅ Multi-item orders with quantities
- ✅ Order customizations and special requests
- ✅ Real-time order state management
- ✅ Order confirmation and summary
- ✅ Order modification support

### Payment & Notifications
- ✅ Stripe payment link generation
- ✅ SMS notifications via Twilio
- ✅ Order confirmation messages
- ✅ Payment receipt delivery
- ✅ Webhook handling for payment status

### Monitoring & Operations
- ✅ Structured logging with rotation
- ✅ Performance metrics collection
- ✅ LiveKit Agent Insights integration
- ✅ Error tracking and alerting
- ✅ Call transcription storage
- ✅ Analytics dashboard support

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Phone Network                            │
│                    (PSTN / SIP Trunk)                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ SIP Protocol
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LiveKit Cloud                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  SIP Service │  │ LiveKit Room │  │   Insights   │         │
│  │   Gateway    │──│   Manager    │──│  Monitoring  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         │ WebRTC/Agent Protocol
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Restaurant Voice Agent                         │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │               Agent Session (STT-LLM-TTS)                 │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │  │
│  │  │Deepgram │→ │ OpenAI  │→ │Cartesia │→ │ Silero  │    │  │
│  │  │   STT   │  │   LLM   │  │   TTS   │  │   VAD   │    │  │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘    │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Function Tools                         │  │
│  │  • Menu Lookup      • Add to Order                       │  │
│  │  • Get Order Total  • Complete Order                     │  │
│  │  • Send Payment     • Send SMS                           │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────┬──────────────────────────┬──────────────────────────┘
            │                          │
            │                          │
            ▼                          ▼
┌───────────────────────┐   ┌──────────────────────┐
│   Twilio SMS API      │   │   Stripe Payments    │
│  • Order Confirmations│   │  • Payment Links     │
│  • Payment Links      │   │  • Checkout Sessions │
│  • Status Updates     │   │  • Webhooks          │
└───────────────────────┘   └──────────────────────┘
```

## 📁 Project Structure

```
Aisyst-livekit-agents/
├── agents/                          # Main agent implementation
│   ├── __init__.py
│   ├── restaurant_agent.py         # Core agent logic
│   ├── tools/                       # Function tools
│   │   ├── __init__.py
│   │   ├── menu_tools.py           # Menu lookup functions
│   │   ├── order_tools.py          # Order management functions
│   │   └── payment_tools.py        # Payment & SMS functions
│   ├── models/                      # Data models
│   │   ├── __init__.py
│   │   ├── menu.py                 # Menu data structures
│   │   └── order.py                # Order data structures
│   └── config/                      # Agent configuration
│       ├── __init__.py
│       ├── prompts.py              # Agent instructions & prompts
│       └── menu_data.py            # Restaurant menu data
│
├── twilio/                          # Twilio SMS integration
│   ├── __init__.py
│   ├── sms_client.py               # SMS sending client
│   ├── templates.py                # Message templates
│   └── webhook_handler.py          # Twilio webhook handler
│
├── stripe/                          # Stripe payment integration
│   ├── __init__.py
│   ├── payment_client.py           # Payment link generation
│   ├── webhook_handler.py          # Stripe webhook handler
│   └── models.py                   # Payment data models
│
├── monitoring/                      # Monitoring & observability
│   ├── __init__.py
│   ├── logger.py                   # Structured logging setup
│   ├── metrics.py                  # Metrics collection
│   ├── health_check.py             # Health check endpoint
│   └── alerts.py                   # Alert configuration
│
├── documentation/                   # Detailed documentation
│   ├── SETUP.md                    # Detailed setup guide
│   ├── ARCHITECTURE.md             # Architecture details
│   ├── API.md                      # API documentation
│   ├── DEPLOYMENT.md               # Deployment guide
│   ├── MONITORING.md               # Monitoring guide
│   ├── TROUBLESHOOTING.md          # Common issues & solutions
│   └── CONTRIBUTING.md             # Contribution guidelines
│
├── tests/                           # Test suite
│   ├── __init__.py
│   ├── test_agent.py               # Agent behavior tests
│   ├── test_tools.py               # Function tool tests
│   ├── test_twilio.py              # Twilio integration tests
│   └── test_stripe.py              # Stripe integration tests
│
├── scripts/                         # Utility scripts
│   ├── deploy.sh                   # Deployment script
│   ├── test_call.py                # Make a test call
│   └── cleanup.sh                  # Cleanup resources
│
├── openspec/                        # OpenSpec specifications
│   ├── project.md                  # Project context
│   ├── AGENTS.md                   # OpenSpec instructions
│   └── specs/                      # Capability specifications
│
├── .env.example                     # Environment variables template
├── .env.local                       # Local development env (gitignored)
├── .gitignore                       # Git ignore rules
├── requirements.txt                 # Python dependencies
├── pyproject.toml                   # Python project configuration
├── Dockerfile                       # Container image
├── docker-compose.yml               # Local development setup
├── livekit.toml                     # LiveKit deployment config
├── README.md                        # This file
├── LICENSE                          # Apache 2.0 License
└── AGENTS.md                        # AI assistant guidelines
```

## 📋 Prerequisites

### Required Services & Accounts
1. **LiveKit Cloud Account** (Free tier available)
   - Sign up at https://cloud.livekit.io
   - Create a project and note your API credentials

2. **Twilio Account** (For SMS)
   - Sign up at https://www.twilio.com
   - Purchase a phone number
   - Get Account SID and Auth Token

3. **Stripe Account** (For payments)
   - Sign up at https://stripe.com
   - Get API keys (test & production)

4. **OpenAI Account** (For LLM)
   - Sign up at https://platform.openai.com
   - Get API key and set up billing

5. **Deepgram Account** (For STT)
   - Sign up at https://deepgram.com
   - Get API key

6. **Cartesia Account** (For TTS)
   - Sign up at https://cartesia.ai
   - Get API key

### System Requirements
- Python 3.11 or higher
- UV package manager (recommended) or pip
- Git
- 4GB+ RAM
- Stable internet connection (for real-time voice)

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/Aisyst-livekit-agents.git
cd Aisyst-livekit-agents
```

### 2. Install UV (Python Package Manager)

**macOS/Linux:**
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**Windows:**
```bash
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 3. Install Dependencies

```bash
# Using UV (recommended)
uv sync

# Or using pip
pip install -r requirements.txt
```

### 4. Download Model Files

```bash
# Download Silero VAD and other model files
uv run agents/restaurant_agent.py download-files
```

## ⚙️ Configuration

### 1. Create Environment File

Copy the example environment file and fill in your credentials:

```bash
cp .env.example .env.local
```

### 2. Configure Environment Variables

Edit `.env.local` with your credentials:

```env
# LiveKit Configuration
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

# OpenAI Configuration
OPENAI_API_KEY=sk-your-openai-api-key

# Deepgram Configuration
DEEPGRAM_API_KEY=your-deepgram-api-key

# Cartesia Configuration
CARTESIA_API_KEY=your-cartesia-api-key

# Twilio Configuration
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
TWILIO_PHONE_NUMBER=+1234567890

# Stripe Configuration
STRIPE_API_KEY=sk_test_your-stripe-key
STRIPE_WEBHOOK_SECRET=whsec_your-webhook-secret
STRIPE_SUCCESS_URL=https://yoursite.com/success
STRIPE_CANCEL_URL=https://yoursite.com/cancel

# Restaurant Configuration
RESTAURANT_NAME=Your Restaurant Name
RESTAURANT_PHONE=+1234567890
RESTAURANT_ADDRESS=123 Main St, City, State

# Monitoring Configuration
LOG_LEVEL=INFO
ENABLE_METRICS=true
SENTRY_DSN=your-sentry-dsn (optional)
```

### 3. Configure Menu Data

Edit `agents/config/menu_data.py` to customize your restaurant menu.

## 🎮 Running the Agent

### Local Development Mode

Test your agent locally in console mode (voice input/output in terminal):

```bash
uv run agents/restaurant_agent.py console
```

### Development Mode with LiveKit Cloud

Run your agent connected to LiveKit Cloud for testing with the playground:

```bash
uv run agents/restaurant_agent.py dev
```

Then open the [Agents Playground](https://cloud.livekit.io/projects/p_/agents/playground) to test your agent.

### Production Mode

Run your agent in production mode:

```bash
uv run agents/restaurant_agent.py start
```

## 🚢 Deployment

### Deploy to LiveKit Cloud

The easiest way to deploy is using the LiveKit CLI:

```bash
# Install LiveKit CLI
brew install livekit # macOS
# or download from https://github.com/livekit/livekit-cli

# Link your project
lk cloud auth

# Deploy agent
lk agent create
```

This creates a `Dockerfile`, `livekit.toml`, and deploys your agent to LiveKit Cloud.

### Deploy with Docker

```bash
# Build image
docker build -t restaurant-agent .

# Run container
docker run -d \
  --env-file .env.local \
  --name restaurant-agent \
  restaurant-agent
```

### Deploy to Other Platforms

See `documentation/DEPLOYMENT.md` for detailed guides on:
- AWS ECS/Fargate
- Google Cloud Run
- Azure Container Instances
- Kubernetes
- Self-hosted servers

## 📊 Monitoring & Observability

### LiveKit Agent Insights

View real-time agent performance in your LiveKit Cloud dashboard:
- https://cloud.livekit.io/projects/p_/sessions

Features:
- Call transcriptions
- Agent conversation traces
- Performance metrics
- Error tracking
- Cost analysis

### Application Logs

Logs are stored in `logs/` directory with rotation:
- `logs/app.log` - Application logs
- `logs/error.log` - Error logs
- `logs/metrics.log` - Metrics logs

### Metrics Collection

The monitoring module collects:
- Call duration and volume
- Order completion rate
- Payment success rate
- SMS delivery rate
- Agent response latency
- Error rates by type

Access metrics via the health check endpoint:
```bash
curl http://localhost:8080/health
```

### Alerting

Configure alerts in `monitoring/alerts.py` for:
- High error rates
- Payment failures
- SMS delivery failures
- Agent response timeouts

See `documentation/MONITORING.md` for detailed monitoring setup.

## 🧪 Testing

### Run All Tests

```bash
# Using pytest
uv run pytest

# With coverage
uv run pytest --cov=agents --cov=twilio --cov=stripe
```

### Test Individual Components

```bash
# Test agent behavior
uv run pytest tests/test_agent.py

# Test Twilio integration
uv run pytest tests/test_twilio.py

# Test Stripe integration
uv run pytest tests/test_stripe.py
```

### Make a Test Call

```bash
# Using the test script
uv run scripts/test_call.py --phone=+1234567890
```

See `documentation/TESTING.md` for comprehensive testing guide.

## 🔌 Integration Details

### Telephony Integration

The agent accepts calls via SIP trunks. Configure inbound calls in LiveKit Cloud:

1. Set up SIP trunk in LiveKit dashboard
2. Configure dispatch rules to route calls to your agent
3. Map phone number to your LiveKit project

For outbound calls, use the CreateSIPParticipant API.

See `documentation/TELEPHONY.md` for detailed setup.

### Twilio SMS Integration

Send order confirmations and payment links via SMS:

```python
from twilio.sms_client import TwilioSMSClient

client = TwilioSMSClient()
await client.send_order_confirmation(
    to="+1234567890",
    order_id="ORD-12345",
    total=45.99
)
```

### Stripe Payment Integration

Generate payment links for orders:

```python
from stripe.payment_client import StripePaymentClient

client = StripePaymentClient()
payment_link = await client.create_payment_link(
    amount=4599,  # in cents
    order_id="ORD-12345",
    customer_phone="+1234567890"
)
```

## 🐛 Troubleshooting

### Common Issues

**Agent not receiving calls:**
- Verify SIP trunk configuration
- Check dispatch rules
- Ensure agent is running in `start` or `dev` mode

**Poor audio quality:**
- Enable background voice cancellation
- Check network bandwidth
- Verify microphone/speaker settings

**Payment links not sending:**
- Verify Stripe API keys
- Check Twilio credentials
- Review webhook configuration

**Agent not responding:**
- Check OpenAI API key and quota
- Verify Deepgram connection
- Review agent logs for errors

See `documentation/TROUBLESHOOTING.md` for comprehensive troubleshooting guide.

## 📚 Additional Documentation

- **[Setup Guide](documentation/SETUP.md)** - Detailed setup instructions
- **[Architecture](documentation/ARCHITECTURE.md)** - System architecture deep dive
- **[API Documentation](documentation/API.md)** - API reference
- **[Deployment Guide](documentation/DEPLOYMENT.md)** - Production deployment
- **[Monitoring Guide](documentation/MONITORING.md)** - Observability setup
- **[Contributing](documentation/CONTRIBUTING.md)** - How to contribute

## 🤝 Contributing

We welcome contributions! Please see `documentation/CONTRIBUTING.md` for guidelines.

## 📄 License

This project is licensed under the Apache License 2.0 - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [LiveKit](https://livekit.io) - Real-time communication platform
- [OpenAI](https://openai.com) - Conversational AI
- [Deepgram](https://deepgram.com) - Speech recognition
- [Cartesia](https://cartesia.ai) - Text-to-speech
- [Twilio](https://twilio.com) - SMS delivery
- [Stripe](https://stripe.com) - Payment processing

## 📞 Support

- Documentation: `documentation/` folder
- Issues: GitHub Issues
- Discussions: GitHub Discussions
- LiveKit Docs: https://docs.livekit.io

---

**Built with ❤️ for the restaurant industry**
