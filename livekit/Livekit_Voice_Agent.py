"""Main voice agent implementation using LiveKit Agents framework (v1.3+)."""
import logging
import time
from datetime import datetime
from livekit.agents import (
    Agent,
    AgentSession,
    AutoSubscribe,
    JobContext,
    MetricsCollectedEvent,
    UserInputTranscribedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    function_tool,
    llm,
    metrics,
)
from livekit.plugins import cartesia, deepgram, groq, openai, silero

from .config import settings
from .prompts import get_system_prompt, get_greeting
from .tools.supabase_client import supabase

logger = logging.getLogger("voice-agent")
latency_logger = logging.getLogger("latency")


def create_llm(force_provider: str = None):
    """Create LLM instance with automatic fallback from Groq to OpenAI.

    Args:
        force_provider: Override the configured provider (for fallback scenarios)

    Returns:
        LLM instance (Groq or OpenAI)

    The function tries Groq first (if configured), then falls back to OpenAI
    if Groq initialization fails or if Groq API key is not available.
    """
    provider = force_provider or settings.llm_provider

    # Determine which providers are available
    groq_available = bool(settings.groq_api_key)
    openai_available = bool(settings.openai_api_key)

    if not groq_available and not openai_available:
        raise ValueError("No LLM API keys configured. Set GROQ_API_KEY or OPENAI_API_KEY.")

    # Try Groq first if configured and available
    if provider == "groq" and groq_available:
        model = settings.llm_model or "llama-3.3-70b-versatile"
        try:
            logger.info(f"🧠 Creating LLM: groq/{model}")
            llm_instance = groq.LLM(
                model=model,
                temperature=0.7,
            )
            logger.info(f"✅ LLM initialized: groq/{model}")
            return llm_instance
        except Exception as e:
            logger.warning(f"⚠️ Groq LLM initialization failed: {e}")
            if openai_available:
                logger.info("🔄 Falling back to OpenAI...")
                return create_llm(force_provider="openai")
            else:
                raise RuntimeError(f"Groq failed and OpenAI not configured: {e}")

    # Use OpenAI (either as primary or fallback)
    if openai_available:
        model = settings.llm_model if (provider == "openai" and settings.llm_model) else "gpt-4o-mini"
        try:
            logger.info(f"🧠 Creating LLM: openai/{model}")
            llm_instance = openai.LLM(
                model=model,
                temperature=0.7,
            )
            logger.info(f"✅ LLM initialized: openai/{model}")
            return llm_instance
        except Exception as e:
            logger.error(f"❌ OpenAI LLM initialization failed: {e}")
            raise RuntimeError(f"Failed to initialize OpenAI LLM: {e}")

    # Groq requested but not available, and no fallback
    raise ValueError(f"Provider '{provider}' requested but API key not configured.")


class LatencyTracker:
    """Track and log latency metrics for voice pipeline components."""

    def __init__(self):
        self.turn_count = 0
        self.metrics_history = []
        self.call_id = None
        self.region = None

        # Model configuration (set when session starts)
        self.model_config = {
            "stt_provider": "deepgram",
            "stt_model": "nova-2",
            "llm_provider": "openai",
            "llm_model": "gpt-4o-mini",
            "tts_provider": "cartesia",
            "tts_model": "sonic-2",
        }

        # Per-turn timing state
        self._reset_turn_state()

    def _reset_turn_state(self):
        """Reset timing state for a new turn."""
        self.turn_start = None
        self.user_speech_start = None
        self.user_speech_end = None
        self.stt_start = None
        self.stt_end = None
        self.llm_start = None
        self.llm_first_token = None
        self.llm_end = None
        self.tts_start = None
        self.tts_first_byte = None
        self.tts_end = None
        self.agent_speech_start = None
        self.agent_speech_end = None
        self.transcript = ""
        self.response = ""
        self.llm_tokens_in = 0
        self.llm_tokens_out = 0
        self.metric_timestamp = None  # LiveKit event timestamp (Unix float)

    def set_call_info(self, call_id: str, region: str = None):
        """Set call identification info."""
        self.call_id = call_id
        self.region = region

    def set_model_config(self, stt_provider: str, stt_model: str,
                         llm_provider: str, llm_model: str,
                         tts_provider: str, tts_model: str):
        """Set the model configuration for tracking."""
        self.model_config = {
            "stt_provider": stt_provider,
            "stt_model": stt_model,
            "llm_provider": llm_provider,
            "llm_model": llm_model,
            "tts_provider": tts_provider,
            "tts_model": tts_model,
        }

    def on_user_started_speaking(self):
        """Record when user starts speaking."""
        now = time.perf_counter()
        self.turn_start = now
        self.user_speech_start = now
        latency_logger.debug("👤 User started speaking")

    def on_user_stopped_speaking(self):
        """Record when user stops speaking."""
        now = time.perf_counter()
        self.user_speech_end = now
        self.stt_start = now
        if self.user_speech_start:
            duration = (now - self.user_speech_start) * 1000
            latency_logger.debug(f"👤 User spoke for {duration:.0f} ms")

    def on_stt_complete(self, transcript: str):
        """Record STT completion."""
        now = time.perf_counter()
        self.stt_end = now
        self.llm_start = now
        self.transcript = transcript

        if self.stt_start:
            duration = (now - self.stt_start) * 1000
            preview = transcript[:50] + "..." if len(transcript) > 50 else transcript
            latency_logger.info(f"🎤 STT:            {duration:>7.1f} ms | \"{preview}\"")

    def on_llm_first_token(self):
        """Record LLM first token."""
        now = time.perf_counter()
        self.llm_first_token = now
        if self.llm_start:
            ttfb = (now - self.llm_start) * 1000
            latency_logger.info(f"🧠 LLM TTFB:       {ttfb:>7.1f} ms")

    def on_llm_complete(self, response: str, tokens_in: int = 0, tokens_out: int = 0):
        """Record LLM completion."""
        now = time.perf_counter()
        self.llm_end = now
        self.tts_start = now
        self.response = response
        self.llm_tokens_in = tokens_in
        self.llm_tokens_out = tokens_out

        if self.llm_start:
            total = (now - self.llm_start) * 1000
            latency_logger.info(f"🧠 LLM Total:      {total:>7.1f} ms | {tokens_out} tokens")

    def on_tts_first_byte(self):
        """Record TTS first audio byte."""
        now = time.perf_counter()
        self.tts_first_byte = now
        if self.tts_start:
            ttfb = (now - self.tts_start) * 1000
            latency_logger.info(f"🔊 TTS TTFB:       {ttfb:>7.1f} ms")

    def on_agent_started_speaking(self):
        """Record when agent starts speaking."""
        now = time.perf_counter()
        self.agent_speech_start = now

        if self.turn_start:
            e2e = (now - self.turn_start) * 1000
            latency_logger.info(f"🎯 END-TO-END:     {e2e:>7.1f} ms")

    def on_agent_stopped_speaking(self):
        """Record when agent stops speaking and save metrics."""
        now = time.perf_counter()
        self.agent_speech_end = now
        latency_logger.debug("🤖 Agent finished speaking")

        # Store metrics at end of turn (agent finished speaking)
        self._store_turn_metrics()

    def _store_turn_metrics(self):
        """Store accumulated metrics for this turn to Supabase."""
        # Only store if we have a valid turn (user spoke)
        if not self.turn_start:
            latency_logger.debug("No turn data to store (turn_start is None)")
            return

        self.turn_count += 1

        # Calculate durations from our tracking
        user_speech_ms = None
        if self.user_speech_start and self.user_speech_end:
            user_speech_ms = (self.user_speech_end - self.user_speech_start) * 1000

        stt_ms = None
        if self.stt_start and self.stt_end:
            stt_ms = (self.stt_end - self.stt_start) * 1000

        llm_ttfb_ms = None
        if self.llm_start and self.llm_first_token:
            llm_ttfb_ms = (self.llm_first_token - self.llm_start) * 1000

        llm_total_ms = None
        if self.llm_start and self.llm_end:
            llm_total_ms = (self.llm_end - self.llm_start) * 1000

        tts_ttfb_ms = None
        if self.tts_start and self.tts_first_byte:
            tts_ttfb_ms = (self.tts_first_byte - self.tts_start) * 1000

        end_to_end_ms = None
        if self.turn_start and self.agent_speech_start:
            end_to_end_ms = (self.agent_speech_start - self.turn_start) * 1000

        agent_speech_ms = None
        if self.agent_speech_start and self.agent_speech_end:
            agent_speech_ms = (self.agent_speech_end - self.agent_speech_start) * 1000

        # Calculate total TTFB (user stop speaking → agent start speaking)
        ttfb_ms = None
        if self.user_speech_end and self.agent_speech_start:
            ttfb_ms = (self.agent_speech_start - self.user_speech_end) * 1000

        # Log detailed breakdown
        latency_logger.info("=" * 60)
        latency_logger.info(f"📊 TURN {self.turn_count} LATENCY METRICS")
        latency_logger.info("=" * 60)

        if ttfb_ms:
            latency_logger.info(f"⏱️  Total TTFB:     {ttfb_ms:>7.1f} ms")
        if end_to_end_ms:
            latency_logger.info(f"🎯 End-to-End:     {end_to_end_ms:>7.1f} ms")
        if stt_ms:
            latency_logger.info(f"🎤 STT Duration:   {stt_ms:>7.1f} ms")
        if llm_ttfb_ms:
            latency_logger.info(f"🧠 LLM TTFB:       {llm_ttfb_ms:>7.1f} ms")
        if llm_total_ms:
            latency_logger.info(f"🧠 LLM Total:      {llm_total_ms:>7.1f} ms")
        if tts_ttfb_ms:
            latency_logger.info(f"🔊 TTS TTFB:       {tts_ttfb_ms:>7.1f} ms")

        # Build metrics dict for history
        turn_metrics = {
            "turn": self.turn_count,
            "ttfb_ms": round(ttfb_ms, 1) if ttfb_ms else None,
            "end_to_end_ms": round(end_to_end_ms, 1) if end_to_end_ms else None,
            "stt_ms": round(stt_ms, 1) if stt_ms else None,
            "llm_ttfb_ms": round(llm_ttfb_ms, 1) if llm_ttfb_ms else None,
            "tts_ttfb_ms": round(tts_ttfb_ms, 1) if tts_ttfb_ms else None,
            "timestamp": datetime.utcnow().isoformat(),
        }
        self.metrics_history.append(turn_metrics)

        # Store in Supabase
        self._store_metrics_in_supabase(
            ttfb_ms=ttfb_ms,
            end_to_end_ms=end_to_end_ms,
            user_speech_ms=user_speech_ms,
            stt_ms=stt_ms,
            llm_ttfb_ms=llm_ttfb_ms,
            llm_total_ms=llm_total_ms,
            tts_ttfb_ms=tts_ttfb_ms,
            agent_speech_ms=agent_speech_ms,
        )

        # Log running averages every 5 turns
        if self.turn_count % 5 == 0:
            self._log_summary()

        latency_logger.info("=" * 60)

        # Reset for next turn
        self._reset_turn_state()

    def log_metrics(self, collected_metrics):
        """Log metrics from LiveKit component events (STT, LLM, TTS).

        These metrics supplement our timing data. Storage happens in _store_turn_metrics()
        when the agent stops speaking.

        Args:
            collected_metrics: Can be STTMetrics, LLMMetrics, TTSMetrics, VADMetrics, or EOUMetrics
        """
        metric_type = type(collected_metrics).__name__

        # Capture LiveKit event timestamp (available on all metric types)
        if hasattr(collected_metrics, 'timestamp') and collected_metrics.timestamp:
            # LiveKit timestamp is Unix float - capture the most recent one
            self.metric_timestamp = collected_metrics.timestamp
            latency_logger.debug(f"📅 Metric timestamp: {self.metric_timestamp}")

        # Handle different metric types from LiveKit
        if metric_type == 'STTMetrics':
            # STT metrics - capture duration if available
            if hasattr(collected_metrics, 'duration') and collected_metrics.duration:
                stt_ms = collected_metrics.duration * 1000
                latency_logger.debug(f"🎤 STT (from event): {stt_ms:.1f} ms")

        elif metric_type == 'LLMMetrics':
            # LLM metrics - time to first token
            if hasattr(collected_metrics, 'ttft') and collected_metrics.ttft:
                llm_ttfb_ms = collected_metrics.ttft * 1000
                latency_logger.debug(f"🧠 LLM TTFB (from event): {llm_ttfb_ms:.1f} ms")
                if not self.llm_first_token:
                    self.llm_first_token = time.perf_counter()
            if hasattr(collected_metrics, 'tokens_out'):
                self.llm_tokens_out = collected_metrics.tokens_out
            if hasattr(collected_metrics, 'tokens_in'):
                self.llm_tokens_in = collected_metrics.tokens_in

        elif metric_type == 'TTSMetrics':
            # TTS metrics - time to first byte
            if hasattr(collected_metrics, 'ttfb') and collected_metrics.ttfb:
                tts_ttfb_ms = collected_metrics.ttfb * 1000
                latency_logger.debug(f"🔊 TTS TTFB (from event): {tts_ttfb_ms:.1f} ms")
                if not self.tts_first_byte:
                    self.tts_first_byte = time.perf_counter()

        elif metric_type in ('VADMetrics', 'EOUMetrics'):
            # VAD/EOU metrics - just log for debugging
            latency_logger.debug(f"📊 {metric_type}: {collected_metrics}")

        else:
            # Unknown metric type - log for debugging
            latency_logger.debug(f"📊 Unknown metric type: {metric_type}")

    def _store_metrics_in_supabase(self, **kwargs):
        """Store metrics in Supabase latency_metrics table."""
        if not supabase:
            latency_logger.warning("⚠️ Supabase not configured - SUPABASE_SERVICE_ROLE_KEY not set")
            return

        try:
            record = {
                "call_id": self.call_id or "unknown",
                "turn_number": self.turn_count,
                "sequence_id": kwargs.get("sequence_id"),

                # Model configuration
                **self.model_config,

                # Core metrics
                "ttfb_ms": kwargs.get("ttfb_ms"),
                "end_to_end_ms": kwargs.get("end_to_end_ms"),

                # Component breakdown
                "stt_duration_ms": kwargs.get("stt_ms"),
                "llm_ttfb_ms": kwargs.get("llm_ttfb_ms"),
                "llm_total_ms": kwargs.get("llm_total_ms"),
                "tts_ttfb_ms": kwargs.get("tts_ttfb_ms"),

                # Additional context
                "user_speech_duration_ms": kwargs.get("user_speech_ms"),
                "agent_speech_duration_ms": kwargs.get("agent_speech_ms"),
                "llm_tokens_in": self.llm_tokens_in or None,
                "llm_tokens_out": self.llm_tokens_out or None,
                "transcript_length": len(self.transcript) if self.transcript else None,
                "response_length": len(self.response) if self.response else None,

                # Metadata
                "region": self.region,
                "agent_version": "1.0.0",

                # LiveKit event timestamp (more accurate than DB insert time)
                "metric_timestamp": datetime.fromtimestamp(self.metric_timestamp).isoformat() if self.metric_timestamp else None,
            }

            # Remove None values to let DB use defaults
            record = {k: v for k, v in record.items() if v is not None}

            latency_logger.info(f"📤 Storing metrics for call {self.call_id}, turn {self.turn_count}")
            result = supabase.table("latency_metrics").insert(record).execute()

            if result.data:
                latency_logger.info(f"✅ Metrics stored successfully: {result.data[0].get('id', 'unknown')}")
            else:
                latency_logger.warning(f"⚠️ Insert returned no data: {result}")

        except Exception as e:
            latency_logger.error(f"❌ Failed to store metrics in Supabase: {e}", exc_info=True)

    def _log_summary(self):
        """Log summary statistics."""
        if not self.metrics_history:
            return

        ttfb_values = [m["ttfb_ms"] for m in self.metrics_history if m.get("ttfb_ms")]
        if ttfb_values:
            avg_ttfb = sum(ttfb_values) / len(ttfb_values)
            min_ttfb = min(ttfb_values)
            max_ttfb = max(ttfb_values)

            latency_logger.info("-" * 60)
            latency_logger.info(f"📈 SUMMARY (last {len(ttfb_values)} turns)")
            latency_logger.info(f"   Avg TTFB: {avg_ttfb:.1f} ms")
            latency_logger.info(f"   Min TTFB: {min_ttfb:.1f} ms")
            latency_logger.info(f"   Max TTFB: {max_ttfb:.1f} ms")


# Supported languages with their display names
SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "ar": "Arabic",
    "zh": "Chinese",
}


# ============================================================================
# MENU CACHING
# ============================================================================

class MenuCache:
    """Simple in-memory cache for menu data with TTL."""

    def __init__(self, ttl_seconds: int = 300):  # 5 minute default TTL
        self.ttl_seconds = ttl_seconds
        self._cache: str = ""
        self._cached_at: float = 0
        self._lock = False  # Simple lock to prevent concurrent fetches

    def get(self) -> str | None:
        """Get cached menu if valid, None if expired or empty."""
        if not self._cache:
            return None
        if time.time() - self._cached_at > self.ttl_seconds:
            logger.debug("📋 Menu cache expired")
            return None
        return self._cache

    def set(self, menu_text: str) -> None:
        """Cache the menu text."""
        self._cache = menu_text
        self._cached_at = time.time()
        logger.debug(f"📋 Menu cached ({len(menu_text)} chars, TTL={self.ttl_seconds}s)")

    def invalidate(self) -> None:
        """Manually invalidate the cache."""
        self._cache = ""
        self._cached_at = 0
        logger.debug("📋 Menu cache invalidated")

    @property
    def is_valid(self) -> bool:
        """Check if cache is valid."""
        return bool(self._cache) and (time.time() - self._cached_at <= self.ttl_seconds)

    @property
    def age_seconds(self) -> float:
        """Get cache age in seconds."""
        if not self._cached_at:
            return float('inf')
        return time.time() - self._cached_at


# Global menu cache instance (5 minute TTL)
_menu_cache = MenuCache(ttl_seconds=300)


def fetch_menu_for_prompt(force_refresh: bool = False) -> str:
    """Fetch menu items and format for system prompt.

    Uses caching to avoid repeated database queries. Menu is cached for 5 minutes.

    Args:
        force_refresh: If True, bypass cache and fetch fresh data

    Returns:
        Formatted menu text for LLM prompt
    """
    global _menu_cache

    # Check cache first (unless force refresh)
    if not force_refresh:
        cached = _menu_cache.get()
        if cached:
            logger.info(f"📋 Using cached menu ({_menu_cache.age_seconds:.0f}s old)")
            return cached

    if not supabase:
        logger.warning("📋 Supabase not configured, cannot fetch menu")
        return ""

    try:
        logger.info("📋 Fetching fresh menu from database...")
        result = supabase.table("menu_items")\
            .select("item_name, price, category")\
            .order("category")\
            .execute()

        if not result.data:
            logger.warning("📋 No menu items found in database")
            return ""

        # Format as simple list for LLM
        lines = []
        current_cat = None
        for item in result.data:
            cat = item.get("category", "Other")
            if cat != current_cat:
                if current_cat is not None:
                    lines.append("")  # blank line between categories
                lines.append(f"[{cat}]")
                current_cat = cat
            lines.append(f"- {item['item_name']}: ${item['price']:.2f}")

        menu_text = "\n".join(lines)

        # Cache the result
        _menu_cache.set(menu_text)
        logger.info(f"📋 Menu loaded: {len(result.data)} items, {len(menu_text)} chars")

        return menu_text
    except Exception as e:
        logger.warning(f"📋 Failed to fetch menu: {e}")
        # Return stale cache if available (better than nothing)
        if _menu_cache._cache:
            logger.info("📋 Returning stale cached menu due to fetch error")
            return _menu_cache._cache
        return ""


def invalidate_menu_cache() -> None:
    """Invalidate the menu cache. Call this when menu is updated."""
    _menu_cache.invalidate()


class RestaurantAgent(Agent):
    """Restaurant order-taking voice agent."""

    def __init__(self, language: str = "en", menu_items: str = ""):
        # Use concise English-only prompt with preloaded menu
        super().__init__(
            instructions=get_system_prompt(language, multilingual=False, menu_items=menu_items),
        )
        # Order state
        self.current_order = []
        self.call_id = None
        self.caller_number = None
        # Language state
        self.current_language = language

    @function_tool()
    async def get_menu_items(self, category: str = "") -> str:
        """
        Get available menu items. Call this BEFORE adding any item to verify it exists.

        Args:
            category: Optional category filter (e.g., "pizza", "sides", "drinks")
        """
        query = supabase.table("menu_items").select("menu_item_id, item_name, price, category, description, available")

        if category:
            query = query.ilike("category", f"%{category}%")

        # Note: available column is NULL in DB, so we skip filtering
        # TODO: Update menu_items to set available=true for active items

        result = query.execute()
        items = result.data

        if not items:
            return "No menu items found." if not category else f"No items in '{category}' category."

        # Group by category for spoken response
        categories = {}
        for item in items:
            cat = item.get("category", "Other")
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(item["item_name"])

        # Format for speech (not text listing)
        parts = []
        for cat, item_names in categories.items():
            if len(item_names) <= 3:
                parts.append(f"{cat}: {', '.join(item_names)}")
            else:
                parts.append(f"{cat}: {', '.join(item_names[:3])}, and more")

        return "We have " + ". ".join(parts) + "."

    @function_tool()
    async def get_item_details(self, item_name: str) -> str:
        """
        Get details about a specific menu item including price.

        Args:
            item_name: Name of the item to look up
        """
        result = supabase.table("menu_items")\
            .select("item_name, price, description")\
            .ilike("item_name", f"%{item_name}%")\
            .execute()

        if not result.data:
            return f"Sorry, we don't have '{item_name}' on our menu."

        item = result.data[0]
        # Simple spoken format
        response = f"{item['item_name']} is ${item['price']:.2f}"
        if item.get("description"):
            response += f". {item['description']}"
        return response

    @function_tool()
    async def add_to_order(
        self,
        item_name: str,
        quantity: int = 1,
        special_instructions: str = "",
        side_choice: str = "",
        drink_choice: str = "",
        sauce_choice: str = ""
    ) -> str:
        """
        Add an item to the customer's order.

        For combo/box/meal items, you MUST collect required options BEFORE calling this:
        - side_choice: If description mentions "chips or mash" or "chips or peas", provide the choice
        - drink_choice: If description mentions "drink", provide which drink (e.g., "Coke", "Sprite")
        - sauce_choice: If description mentions "sauce", provide which sauce

        Args:
            item_name: Name of the menu item
            quantity: Number of items (default 1)
            special_instructions: Any special requests for this item
            side_choice: Required side for combos (e.g., "chips", "mash", "peas")
            drink_choice: Required drink for combos (e.g., "Coke", "Sprite", "Fanta")
            sauce_choice: Required sauce if applicable (e.g., "gravy", "aioli")
        """
        result = supabase.table("menu_items")\
            .select("menu_item_id, item_name, price, description")\
            .ilike("item_name", f"%{item_name}%")\
            .limit(1)\
            .execute()

        if not result.data:
            return f"Sorry, I couldn't find '{item_name}'. Would you like me to list our menu?"

        item = result.data[0]
        description = (item.get("description") or "").lower()
        item_name_lower = item["item_name"].lower()

        # Check if this is a combo/box/meal that requires options
        is_combo = any(kw in item_name_lower for kw in ["box", "combo", "meal", "pack", "satisfryer"])

        if is_combo:
            missing_options = []

            # Check for side choice requirement
            has_side_choice = any(phrase in description for phrase in [
                "chips or peas", "chips or mash", "mash or chips",
                "peas or chips", "our famous chips or peas"
            ])
            if has_side_choice and not side_choice:
                missing_options.append("side (chips, mash, or peas)")

            # Check for drink requirement
            has_drink = "drink" in description and "kids drink" not in description
            if has_drink and not drink_choice:
                missing_options.append("drink")

            # If missing required options, ask for them
            if missing_options:
                return f"For the {item['item_name']}, which {' and '.join(missing_options)} would you like?"

        # Build the order item with all options
        order_item = {
            "item_id": item["menu_item_id"],
            "name": item["item_name"],
            "quantity": quantity,
            "price": item["price"],
            "special_instructions": special_instructions,
        }

        # Add combo options if provided
        options_text = []
        if side_choice:
            order_item["side_choice"] = side_choice
            options_text.append(side_choice)
        if drink_choice:
            order_item["drink_choice"] = drink_choice
            options_text.append(drink_choice)
        if sauce_choice:
            order_item["sauce_choice"] = sauce_choice
            options_text.append(sauce_choice)

        self.current_order.append(order_item)

        # Build response
        if quantity == 1:
            response = f"Got it, {item['item_name']}"
        else:
            response = f"Got it, {quantity} {item['item_name']}"

        if options_text:
            response += f" with {' and '.join(options_text)}"
        response += "."

        if special_instructions:
            response += f" {special_instructions}."

        response += " Anything else?"
        return response

    @function_tool()
    async def remove_from_order(self, item_name: str) -> str:
        """
        Remove an item from the order.

        Args:
            item_name: Name of the item to remove
        """
        for i, item in enumerate(self.current_order):
            if item_name.lower() in item["name"].lower():
                removed = self.current_order.pop(i)
                total = sum(i["price"] * i["quantity"] for i in self.current_order)
                return f"Removed {removed['name']}. Current total: ${total:.2f}"
        return f"'{item_name}' is not in your current order."

    @function_tool()
    async def get_order_summary(self, confirm: bool = True) -> str:
        """
        Get a summary of the current order.

        Args:
            confirm: Confirmation to proceed (always True)
        """
        if not self.current_order:
            return "Your order is empty. What would you like to order?"

        # Build concise order list with options
        items = []
        total = 0
        for item in self.current_order:
            subtotal = item["price"] * item["quantity"]
            item_text = item['name'] if item["quantity"] == 1 else f"{item['quantity']} {item['name']}"

            # Add combo options if present
            options = []
            if item.get("side_choice"):
                options.append(item["side_choice"])
            if item.get("drink_choice"):
                options.append(item["drink_choice"])
            if item.get("sauce_choice"):
                options.append(item["sauce_choice"])
            if options:
                item_text += f" with {' and '.join(options)}"

            items.append(item_text)
            total += subtotal

        # Format as spoken sentence
        if len(items) == 1:
            order_text = items[0]
        elif len(items) == 2:
            order_text = f"{items[0]} and {items[1]}"
        else:
            order_text = ", ".join(items[:-1]) + f", and {items[-1]}"

        return f"So that's {order_text}. Total is ${total:.2f}."

    @function_tool()
    async def submit_order(self, customer_name: str, customer_phone: str) -> str:
        """
        Submit the order for pickup.

        Args:
            customer_name: Customer's name
            customer_phone: Customer's phone number
        """
        import uuid

        if not self.current_order:
            return "Your order is empty. Please add items first."

        total = sum(i["price"] * i["quantity"] for i in self.current_order)
        order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

        # Build order items text with options
        def format_order_item(i):
            text = f"{i['quantity']}x {i['name']}"
            options = []
            if i.get("side_choice"):
                options.append(i["side_choice"])
            if i.get("drink_choice"):
                options.append(i["drink_choice"])
            if i.get("sauce_choice"):
                options.append(i["sauce_choice"])
            if options:
                text += f" ({', '.join(options)})"
            if i.get("special_instructions"):
                text += f" - {i['special_instructions']}"
            return text

        order_items_text = ", ".join(format_order_item(i) for i in self.current_order)

        # Create order in database (always pickup)
        order_data = {
            "order_id": order_id,
            "owner": "e05e0713-6840-4dad-814d-61867ff72b95",
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "order_type": "pickup",
            "order_status": "pending",
            "total_order_value": total,
            "payment_status": "pending",
            "special_instructions": "Voice order: " + order_items_text,
            "item_count": sum(i["quantity"] for i in self.current_order),
            "call_id": self.call_id,  # Link order to voice call
        }

        try:
            supabase.table("orders").insert(order_data).execute()
            logger.info(f"📦 Order {order_id} created for call {self.call_id}")
        except Exception as e:
            logger.error(f"Failed to create order: {e}")
            return "Sorry, there was an issue submitting your order. Please try again."

        # Clear order
        self.current_order = []

        # Concise confirmation with fixed 20 minute pickup time
        return (
            f"Perfect {customer_name}, your order is in! "
            f"It'll be ready for pickup in about 20 minutes. "
            f"Thanks for calling, goodbye!"
        )

    @function_tool()
    async def clear_order(self, confirm: bool = True) -> str:
        """
        Clear the current order and start fresh.

        Args:
            confirm: Confirmation to clear the order (always True)
        """
        self.current_order = []
        return "Order cleared. What would you like to order?"

    @function_tool()
    async def set_language_preference(self, language: str) -> str:
        """
        Set the customer's preferred language for this conversation.

        Args:
            language: Language code (en=English, es=Spanish, fr=French, ar=Arabic, zh=Chinese)
        """
        language = language.lower().strip()

        if language not in SUPPORTED_LANGUAGES:
            available = ", ".join(f"{code}={name}" for code, name in SUPPORTED_LANGUAGES.items())
            return f"Sorry, '{language}' is not supported. Available languages: {available}"

        self.current_language = language
        lang_name = SUPPORTED_LANGUAGES[language]
        return f"Language preference set to {lang_name}. I will continue in {lang_name}."

    @function_tool()
    async def get_supported_languages(self, confirm: bool = True) -> str:
        """
        Get a list of supported languages for this conversation.

        Args:
            confirm: Confirmation to proceed (always True)
        """
        languages = [f"{name} ({code})" for code, name in SUPPORTED_LANGUAGES.items()]
        return "I support the following languages: " + ", ".join(languages)

    @function_tool()
    async def end_call(self, reason: str = "completed") -> str:
        """
        End the call with a friendly goodbye. Call this when the order is complete or customer wants to hang up.

        Args:
            reason: Why the call is ending (completed, cancelled, customer_request)
        """
        if reason == "completed":
            return "Thank you for your order! Have a great day. Goodbye!"
        elif reason == "cancelled":
            return "No problem! Feel free to call back anytime. Goodbye!"
        else:
            return "Thanks for calling! Goodbye!"


def extract_caller_number(call_id: str) -> str | None:
    """Extract phone number from call_id string.

    call_id format: call-{{call.callId}}_+61410149087_qjmjECBKb2Xb
    or: room_+61410149087_suffix
    """
    import re
    # Look for phone number pattern (+country code followed by digits)
    match = re.search(r'(\+\d{10,15})', call_id)
    if match:
        return match.group(1)
    return None


async def entrypoint(ctx: JobContext):
    """Main entrypoint for the agent worker."""

    # Get call info from room
    call_id = ctx.room.name
    caller_number = extract_caller_number(call_id)
    logger.info(f"New call: {call_id}, caller: {caller_number}")

    # Connect to room
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Preload menu for system prompt (faster responses, no hallucination)
    menu_text = fetch_menu_for_prompt()
    logger.info(f"📋 Preloaded menu: {len(menu_text)} chars")

    # Create the agent with menu context
    agent = RestaurantAgent(language="en", menu_items=menu_text)
    agent.call_id = call_id

    # Start agent session with components
    session = AgentSession(
        vad=silero.VAD.load(
            min_speech_duration=0.1,
            min_silence_duration=0.1,
        ),
        stt=deepgram.STT(
            model="nova-2",
        ),
        llm=create_llm(),
        tts=cartesia.TTS(
            model="sonic-2",
            voice="79a125e8-cd45-4c13-8a67-188112f4dd22",
        ),
        allow_interruptions=True,
    )

    # =========================================================================
    # LATENCY TRACKING - Configure and subscribe to session events
    # =========================================================================

    # Create per-call latency tracker (NOT global!)
    latency_tracker = LatencyTracker()
    latency_tracker.set_call_info(call_id=call_id, region="Australia")
    latency_tracker.set_model_config(
        stt_provider="deepgram",
        stt_model="nova-2",
        llm_provider=settings.llm_provider,
        llm_model=settings.effective_llm_model,
        tts_provider="cartesia",
        tts_model="sonic-2",
    )

    # Accumulate metrics across events for each turn
    turn_metrics = {
        "user_speech_duration_ms": None,  # How long user spoke (metadata, not part of TTFB)
        "llm_ttfb_ms": None,              # LLM time to first token
        "llm_total_ms": None,             # LLM total generation time
        "llm_tokens_in": None,            # Input tokens
        "llm_tokens_out": None,           # Output tokens
        "tts_ttfb_ms": None,              # TTS time to first byte
    }

    @session.on("metrics_collected")
    def on_metrics_collected(ev: MetricsCollectedEvent):
        """Collect all metrics from STT, LLM, TTS events and store on TTS completion."""
        nonlocal turn_metrics
        metric_type = type(ev.metrics).__name__
        m = ev.metrics

        try:

            # STT Metrics - user speech duration (NOT processing latency)
            # NOTE: audio_duration = how long user spoke, NOT STT processing time
            # This is useful metadata but should NOT be included in TTFB calculation
            if metric_type == 'STTMetrics':
                audio_duration = getattr(m, 'audio_duration', None)
                if audio_duration and audio_duration > 0:
                    # Store as user speech duration (metadata only, not part of TTFB)
                    turn_metrics["user_speech_duration_ms"] = audio_duration * 1000
                    logger.info(f"🎤 User speech: {turn_metrics['user_speech_duration_ms']:.1f} ms")

            # LLM Metrics - time to first token and total time
            elif metric_type == 'LLMMetrics':
                # Time to first token
                ttft = getattr(m, 'ttft', None)
                if ttft is not None and ttft > 0:
                    turn_metrics["llm_ttfb_ms"] = ttft * 1000
                    logger.info(f"🧠 LLM TTFB: {turn_metrics['llm_ttfb_ms']:.1f} ms")

                # Total duration
                duration = getattr(m, 'duration', None)
                if duration is not None and duration > 0:
                    turn_metrics["llm_total_ms"] = duration * 1000

                # Token counts (LiveKit 1.3 uses prompt_tokens/completion_tokens)
                tokens_in = getattr(m, 'prompt_tokens', None)
                tokens_out = getattr(m, 'completion_tokens', None)

                if tokens_in is not None:
                    turn_metrics["llm_tokens_in"] = tokens_in
                if tokens_out is not None:
                    turn_metrics["llm_tokens_out"] = tokens_out

                if tokens_in is not None or tokens_out is not None:
                    logger.info(f"🧠 LLM Tokens: {tokens_in} in, {tokens_out} out")

            # TTS Metrics - time to first byte (this is last in pipeline, so store everything)
            elif metric_type == 'TTSMetrics':
                if hasattr(m, 'ttfb') and m.ttfb:
                    turn_metrics["tts_ttfb_ms"] = m.ttfb * 1000
                    logger.info(f"🔊 TTS TTFB: {turn_metrics['tts_ttfb_ms']:.1f} ms")

                # Calculate total TTFB = LLM TTFB + TTS TTFB
                # (time from user stops speaking to agent starts speaking)
                # NOTE: Does NOT include user speech duration - that's not latency
                total_ttfb = sum(filter(None, [
                    turn_metrics.get("llm_ttfb_ms"),
                    turn_metrics.get("tts_ttfb_ms"),
                ]))

                logger.info(f"⏱️  TOTAL TTFB: {total_ttfb:.1f} ms - STORING ALL METRICS")

                # Store all accumulated metrics to Supabase
                if supabase:
                    try:
                        record = {
                            "call_id": call_id,
                            "turn_number": latency_tracker.turn_count + 1,
                            # Model configuration (from settings)
                            "stt_provider": "deepgram",
                            "stt_model": "nova-2",
                            "llm_provider": settings.llm_provider,
                            "llm_model": settings.effective_llm_model,
                            "tts_provider": "cartesia",
                            "tts_model": "sonic-2",
                            # Core metrics (TTFB = LLM TTFB + TTS TTFB)
                            "ttfb_ms": total_ttfb if total_ttfb > 0 else None,
                            # Component breakdown
                            "user_speech_duration_ms": turn_metrics.get("user_speech_duration_ms"),
                            "llm_ttfb_ms": turn_metrics.get("llm_ttfb_ms"),
                            "llm_total_ms": turn_metrics.get("llm_total_ms"),
                            "tts_ttfb_ms": turn_metrics.get("tts_ttfb_ms"),
                            # Token usage
                            "llm_tokens_in": turn_metrics.get("llm_tokens_in"),
                            "llm_tokens_out": turn_metrics.get("llm_tokens_out"),
                            # Metadata
                            "region": "Australia",
                            "agent_version": "1.0.0",
                        }
                        # Remove None values
                        record = {k: v for k, v in record.items() if v is not None}

                        result = supabase.table("latency_metrics").insert(record).execute()
                        latency_tracker.turn_count += 1

                        if result.data:
                            logger.info(f"✅ METRICS STORED: {result.data[0].get('id', 'ok')}")
                        else:
                            logger.warning(f"⚠️ Insert returned: {result}")
                    except Exception as e:
                        logger.error(f"❌ Failed to store: {e}")
                else:
                    logger.warning("⚠️ Supabase not configured")

                # Reset for next turn
                turn_metrics = {
                    "user_speech_duration_ms": None,
                    "llm_ttfb_ms": None,
                    "llm_total_ms": None,
                    "llm_tokens_in": None,
                    "llm_tokens_out": None,
                    "tts_ttfb_ms": None,
                }

        except Exception as e:
            logger.error(f"Failed in metrics handler: {e}", exc_info=True)

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev: UserInputTranscribedEvent):
        """User speech transcribed."""
        transcript = ev.transcript if hasattr(ev, 'transcript') else str(ev)
        preview = transcript[:50] + "..." if len(transcript) > 50 else transcript
        logger.info(f"📝 Transcribed: {preview}")

    # Log call start with metadata
    call_start_time = datetime.utcnow()
    try:
        supabase.table("voice_calls").insert({
            "call_id": call_id,
            "caller_number": caller_number,
            "status": "in_progress",
            "language": "en",  # Default, could be detected later
            "started_at": call_start_time.isoformat(),
        }).execute()
        logger.info(f"📞 Call logged: {call_id} from {caller_number}")
    except Exception as e:
        logger.warning(f"Failed to log call start: {e}")

    # Register shutdown callback to log call end with duration
    @ctx.add_shutdown_callback
    async def on_shutdown():
        try:
            call_end_time = datetime.utcnow()
            duration_seconds = int((call_end_time - call_start_time).total_seconds())
            supabase.table("voice_calls").update({
                "status": "completed",
                "ended_at": call_end_time.isoformat(),
                "duration_seconds": duration_seconds,
            }).eq("call_id", call_id).execute()
            logger.info(f"📞 Call ended: {call_id}, duration: {duration_seconds}s")
        except Exception as e:
            logger.warning(f"Failed to log call end: {e}")

    # Start the session
    await session.start(
        room=ctx.room,
        agent=agent,
    )

    # Initial greeting with model info
    model_name = f"{settings.llm_provider}/{settings.effective_llm_model}"
    logger.info(f"🤖 Using LLM: {model_name}")
    await session.say(
        get_greeting("en", model=model_name),
        allow_interruptions=True,
    )


def main():
    """Run the voice agent worker."""
    import os
    from .health import start_health_server
    start_health_server(port=int(os.environ.get("PORT", 8080)))

    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
            ws_url=settings.livekit_url,
        ),
    )


if __name__ == "__main__":
    main()