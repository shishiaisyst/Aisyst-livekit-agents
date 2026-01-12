"""
Alert configuration and notification system.
"""

import os
from typing import Optional, Dict, Any
from enum import Enum
from monitoring.logger import get_logger

logger = get_logger(__name__)

# Try to import Sentry if available
try:
    import sentry_sdk
    SENTRY_AVAILABLE = True
except ImportError:
    SENTRY_AVAILABLE = False


class AlertLevel(str, Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertManager:
    """Manages alerts and notifications."""
    
    def __init__(self):
        """Initialize alert manager."""
        self.sentry_enabled = False
        
        # Initialize Sentry if configured
        if SENTRY_AVAILABLE:
            sentry_dsn = os.getenv("SENTRY_DSN")
            if sentry_dsn:
                sentry_sdk.init(
                    dsn=sentry_dsn,
                    environment=os.getenv("SENTRY_ENVIRONMENT", "development"),
                    traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
                )
                self.sentry_enabled = True
                logger.info("Sentry error tracking initialized")
    
    def send_alert(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Send an alert notification.
        
        Args:
            level: Alert severity level
            title: Alert title
            message: Alert message
            context: Additional context data
        """
        # Log the alert
        log_method = getattr(logger, level.value, logger.info)
        log_method(
            f"ALERT: {title}",
            extra={
                "alert_level": level.value,
                "message": message,
                **(context or {}),
            }
        )
        
        # Send to Sentry for errors and critical alerts
        if self.sentry_enabled and level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
            with sentry_sdk.push_scope() as scope:
                scope.set_level(level.value)
                scope.set_context("alert", {
                    "title": title,
                    "message": message,
                    **(context or {}),
                })
                sentry_sdk.capture_message(f"{title}: {message}")
    
    def alert_high_error_rate(self, error_count: int, time_window: int) -> None:
        """Alert on high error rate."""
        self.send_alert(
            level=AlertLevel.ERROR,
            title="High Error Rate Detected",
            message=f"{error_count} errors in the last {time_window} minutes",
            context={"error_count": error_count, "time_window": time_window},
        )
    
    def alert_payment_failure(self, order_id: str, error: str) -> None:
        """Alert on payment failure."""
        self.send_alert(
            level=AlertLevel.ERROR,
            title="Payment Processing Failed",
            message=f"Payment failed for order {order_id}",
            context={"order_id": order_id, "error": error},
        )
    
    def alert_sms_failure(self, recipient: str, error: str) -> None:
        """Alert on SMS delivery failure."""
        self.send_alert(
            level=AlertLevel.WARNING,
            title="SMS Delivery Failed",
            message=f"Failed to send SMS to {recipient}",
            context={"recipient": recipient, "error": error},
        )
    
    def alert_agent_timeout(self, session_id: str, duration: float) -> None:
        """Alert on agent response timeout."""
        self.send_alert(
            level=AlertLevel.WARNING,
            title="Agent Response Timeout",
            message=f"Agent took {duration:.2f}s to respond in session {session_id}",
            context={"session_id": session_id, "duration": duration},
        )
    
    def alert_system_resource(self, resource: str, usage_percent: float) -> None:
        """Alert on high system resource usage."""
        self.send_alert(
            level=AlertLevel.WARNING,
            title=f"High {resource.title()} Usage",
            message=f"{resource.title()} usage at {usage_percent:.1f}%",
            context={"resource": resource, "usage_percent": usage_percent},
        )


# Global alert manager instance
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """
    Get or create the global alert manager instance.
    
    Returns:
        Global AlertManager instance
    """
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager
