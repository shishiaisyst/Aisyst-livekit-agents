# Project Context

## Purpose
Building a voice AI agent specifically catered to restaurants for handling customer interactions, order taking, reservations, and customer service. The project aims to provide an intelligent, conversational interface that can understand restaurant-specific contexts and workflows.

**Current Phase**: Rapid prototyping using LiveKit Agent Builder, with plans to migrate to LiveKit Agents SDK for advanced customization and production deployment.

**Goals**:
- Create a natural, conversational voice agent for restaurant operations
- Handle order taking, menu inquiries, and reservation management
- Provide seamless customer experience with low latency and high accuracy
- Scale to production with robust error handling and monitoring

## Tech Stack

### Core Framework
- **LiveKit Agents Framework**: Python-based realtime voice AI framework
- **LiveKit Cloud**: Hosted platform for agent deployment and management
- **LiveKit Agent Builder**: Browser-based prototyping tool (current phase)

### AI Models & Services
- **STT (Speech-to-Text)**: AssemblyAI Universal Streaming, Deepgram
- **LLM (Large Language Model)**: OpenAI GPT-4.1-mini, OpenAI Realtime API
- **TTS (Text-to-Speech)**: Cartesia Sonic 3, ElevenLabs, OpenAI TTS
- **VAD (Voice Activity Detection)**: Silero VAD
- **Turn Detection**: LiveKit Multilingual Turn Detector

### Infrastructure
- **Deployment**: LiveKit Cloud (managed deployment environment)
- **Observability**: LiveKit Agent Insights (transcripts, traces, metrics)
- **Inference**: LiveKit Inference (hosted AI model serving)

### Development Tools
- **Python**: Primary programming language for SDK-based agents
- **UV**: Python package manager for dependency management
- **LiveKit CLI**: Command-line tools for project management and deployment
- **Agents Playground**: Testing environment for multimodal agent capabilities

### Future Considerations
- **Telephony Integration**: LiveKit SIP for phone call handling
- **Frontend SDKs**: React, Flutter, React Native, or Android for custom UIs
- **Database**: For order history, customer data, and menu management
- **Payment Integration**: For order processing and transactions

## Project Conventions

### Code Style
- Follow Python PEP 8 style guidelines for SDK-based agents
- Use type hints for function parameters and return values
- Prefer async/await patterns for all I/O operations
- Use descriptive variable names that reflect restaurant domain (e.g., `order_items`, `table_number`, `menu_category`)
- Keep agent instructions clear, concise, and domain-specific
- Document function tools with clear docstrings for LLM understanding

### Architecture Patterns
- **Agent Session Pattern**: Use `AgentSession` for orchestrating STT-LLM-TTS pipeline
- **Function Tools**: Implement external actions (order placement, menu lookup) as decorated function tools
- **Task-Based Workflows**: Use `AgentTask` for multi-step processes (order taking, checkout)
- **Agent Handoffs**: Consider multiple specialized agents (greeter, order taker, payment handler)
- **Event-Driven**: Leverage lifecycle events (`on_enter`, `on_exit`, `on_user_input_transcribed`)
- **Stateful Sessions**: Maintain conversation context and order state throughout interaction
- **Background Voice Cancellation**: Enable BVC for better audio quality in noisy restaurant environments

### Testing Strategy
- Use LiveKit Agents Playground for interactive testing during development
- Implement pytest-based test suites for production agents
- Test conversation flows with LLM-based validation
- Mock function tools for isolated testing
- Validate edge cases (menu item unavailability, order modifications, cancellations)
- Test telephony integration separately if using SIP
- Monitor agent performance using LiveKit Agent Insights

### Git Workflow
- Use feature branches for new capabilities
- Follow OpenSpec workflow for significant changes (new features, breaking changes)
- Commit messages should be descriptive and reference relevant specs
- Test agents locally using `console` mode before deploying
- Use `dev` mode for cloud testing before production deployment

## Domain Context

### Restaurant Operations
- **Order Taking**: Multi-item orders with customizations, quantities, and special requests
- **Menu Management**: Categories (appetizers, entrees, desserts, drinks), dietary restrictions, pricing
- **Reservations**: Date, time, party size, special occasions, seating preferences
- **Customer Service**: Hours of operation, location, parking, dietary accommodations
- **Order Modifications**: Add/remove items, change quantities, cancel orders
- **Payment Processing**: Order totals, taxes, tips, payment methods

### Conversation Patterns
- Greet customers warmly and offer assistance
- Confirm order details before finalizing
- Handle interruptions gracefully (order changes mid-conversation)
- Provide clear feedback on actions taken
- Ask clarifying questions when needed (size, preparation style, sides)
- Maintain context throughout multi-turn conversations

### Restaurant-Specific Terminology
- Menu items, ingredients, preparation methods
- Dietary terms (vegan, gluten-free, nut-free, dairy-free)
- Order modifiers (no onions, extra cheese, well-done, on the side)
- Table service terms (dine-in, takeout, delivery, curbside)

## Important Constraints

### Technical Constraints
- **Latency Requirements**: Voice responses must feel natural (<1s response time preferred)
- **Audio Quality**: Must handle noisy restaurant environments (kitchen noise, background conversations)
- **Interruption Handling**: Customers may interrupt or change their mind mid-order
- **Context Window**: LLM context limits may affect very long conversations or large menus
- **Model Availability**: Dependent on LiveKit Inference and third-party AI provider uptime

### Business Constraints
- **Accuracy Critical**: Order mistakes can lead to customer dissatisfaction and waste
- **Menu Updates**: Agent must handle menu changes, seasonal items, and out-of-stock situations
- **Multi-Language Support**: May need to support multiple languages depending on customer base
- **Compliance**: Food safety information, allergen warnings, age verification for alcohol
- **Cost Management**: AI inference costs scale with usage (STT, LLM, TTS tokens)

### Regulatory Constraints
- **Data Privacy**: Customer information (phone numbers, payment details) must be handled securely
- **Recording Consent**: May need explicit consent for call recording in certain jurisdictions
- **Accessibility**: Must provide alternative ordering methods for customers who prefer human interaction

## External Dependencies

### LiveKit Services
- **LiveKit Cloud**: Hosting, deployment, and orchestration platform
- **LiveKit Inference**: AI model serving for STT, LLM, TTS
- **LiveKit Telephony**: SIP integration for phone-based ordering (future)
- **LiveKit Agent Insights**: Observability, transcripts, and performance monitoring

### AI Model Providers
- **OpenAI**: GPT models for conversational intelligence
- **AssemblyAI**: Speech-to-text transcription
- **Cartesia**: Text-to-speech synthesis
- **Deepgram**: Alternative STT provider
- **ElevenLabs**: Alternative TTS provider with natural voices

### Future Integrations
- **Restaurant POS System**: For order submission and menu synchronization
- **Payment Gateway**: Stripe, Square, or restaurant-specific payment processor
- **Reservation System**: OpenTable, Resy, or custom booking system
- **Customer Database**: CRM for customer history and preferences
- **Delivery Platforms**: DoorDash, Uber Eats integration (if applicable)
- **Analytics Platform**: For tracking agent performance and customer satisfaction
