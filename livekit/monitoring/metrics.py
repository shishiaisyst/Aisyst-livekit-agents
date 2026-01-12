"""
Metrics collection for monitoring agent performance.
"""

import time
from typing import Dict, Any, Optional
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from monitoring.logger import get_logger

logger = get_logger(__name__)


@dataclass
class MetricValue:
    """Container for a metric value with timestamp."""
    value: float
    timestamp: datetime = field(default_factory=datetime.now)
    labels: Dict[str, str] = field(default_factory=dict)


class MetricsCollector:
    """Collects and stores application metrics."""
    
    def __init__(self):
        """Initialize metrics collector."""
        self.counters: Dict[str, int] = defaultdict(int)
        self.gauges: Dict[str, float] = {}
        self.histograms: Dict[str, list] = defaultdict(list)
        self.timers: Dict[str, float] = {}
        
        logger.info("Metrics collector initialized")
    
    def increment_counter(self, name: str, value: int = 1, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Increment a counter metric.
        
        Args:
            name: Metric name
            value: Amount to increment by
            labels: Optional metric labels
        """
        key = self._make_key(name, labels)
        self.counters[key] += value
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Set a gauge metric value.
        
        Args:
            name: Metric name
            value: Metric value
            labels: Optional metric labels
        """
        key = self._make_key(name, labels)
        self.gauges[key] = value
    
    def record_histogram(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """
        Record a value in a histogram.
        
        Args:
            name: Metric name
            value: Value to record
            labels: Optional metric labels
        """
        key = self._make_key(name, labels)
        self.histograms[key].append(value)
        
        # Keep only last 1000 values
        if len(self.histograms[key]) > 1000:
            self.histograms[key] = self.histograms[key][-1000:]
    
    def start_timer(self, name: str) -> None:
        """
        Start a timer for measuring duration.
        
        Args:
            name: Timer name
        """
        self.timers[name] = time.time()
    
    def stop_timer(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """
        Stop a timer and record the duration.
        
        Args:
            name: Timer name
            labels: Optional metric labels
            
        Returns:
            Duration in seconds
        """
        if name not in self.timers:
            logger.warning(f"Timer '{name}' was not started")
            return 0.0
        
        duration = time.time() - self.timers[name]
        self.record_histogram(f"{name}_duration", duration, labels)
        del self.timers[name]
        
        return duration
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get all metrics as a dictionary.
        
        Returns:
            Dictionary of all metrics
        """
        metrics = {
            "counters": dict(self.counters),
            "gauges": dict(self.gauges),
            "histograms": {},
            "timestamp": datetime.now().isoformat(),
        }
        
        # Calculate histogram statistics
        for name, values in self.histograms.items():
            if values:
                metrics["histograms"][name] = {
                    "count": len(values),
                    "sum": sum(values),
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                }
        
        return metrics
    
    def reset(self) -> None:
        """Reset all metrics."""
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()
        self.timers.clear()
        logger.info("Metrics reset")
    
    @staticmethod
    def _make_key(name: str, labels: Optional[Dict[str, str]]) -> str:
        """Create a metric key from name and labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


# Global metrics collector instance
_metrics_collector: Optional[MetricsCollector] = None


def get_metrics_collector() -> MetricsCollector:
    """
    Get or create the global metrics collector instance.
    
    Returns:
        Global MetricsCollector instance
    """
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


# Metric names as constants
class Metrics:
    """Metric name constants."""
    
    # Call metrics
    CALLS_TOTAL = "calls_total"
    CALLS_ACTIVE = "calls_active"
    CALL_DURATION = "call_duration"
    
    # Order metrics
    ORDERS_TOTAL = "orders_total"
    ORDERS_COMPLETED = "orders_completed"
    ORDERS_CANCELLED = "orders_cancelled"
    ORDER_VALUE = "order_value"
    ORDER_ITEMS = "order_items"
    
    # Payment metrics
    PAYMENTS_TOTAL = "payments_total"
    PAYMENTS_SUCCEEDED = "payments_succeeded"
    PAYMENTS_FAILED = "payments_failed"
    PAYMENT_AMOUNT = "payment_amount"
    
    # SMS metrics
    SMS_SENT = "sms_sent"
    SMS_DELIVERED = "sms_delivered"
    SMS_FAILED = "sms_failed"
    
    # Agent metrics
    AGENT_RESPONSE_TIME = "agent_response_time"
    AGENT_ERRORS = "agent_errors"
    TOOL_CALLS = "tool_calls"
    
    # System metrics
    MEMORY_USAGE = "memory_usage_bytes"
    CPU_USAGE = "cpu_usage_percent"
