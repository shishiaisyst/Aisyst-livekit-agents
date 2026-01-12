"""
Health check endpoint for monitoring agent status.
"""

import os
import psutil
from typing import Dict, Any
from fastapi import APIRouter
from datetime import datetime

from monitoring.metrics import get_metrics_collector
from monitoring.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint.
    
    Returns:
        Health status and system metrics
    """
    try:
        metrics_collector = get_metrics_collector()
        metrics = metrics_collector.get_metrics()
        
        # Get system metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        health_data = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "1.0.0",
            "environment": os.getenv("ENVIRONMENT", "development"),
            "system": {
                "cpu_percent": cpu_percent,
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "percent": memory.percent,
                },
                "disk": {
                    "total_gb": round(disk.total / (1024**3), 2),
                    "used_gb": round(disk.used / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "percent": disk.percent,
                },
            },
            "metrics": metrics,
        }
        
        # Determine overall health
        if cpu_percent > 90 or memory.percent > 90 or disk.percent > 90:
            health_data["status"] = "degraded"
            health_data["warnings"] = []
            
            if cpu_percent > 90:
                health_data["warnings"].append("High CPU usage")
            if memory.percent > 90:
                health_data["warnings"].append("High memory usage")
            if disk.percent > 90:
                health_data["warnings"].append("Low disk space")
        
        return health_data
    
    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/ready")
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness check endpoint (for Kubernetes).
    
    Returns:
        Readiness status
    """
    try:
        # Check if required services are configured
        required_env_vars = [
            "LIVEKIT_URL",
            "LIVEKIT_API_KEY",
            "OPENAI_API_KEY",
            "TWILIO_ACCOUNT_SID",
            "STRIPE_API_KEY",
        ]
        
        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        
        if missing_vars:
            return {
                "ready": False,
                "message": f"Missing required environment variables: {', '.join(missing_vars)}",
                "timestamp": datetime.now().isoformat(),
            }
        
        return {
            "ready": True,
            "message": "Service is ready to accept requests",
            "timestamp": datetime.now().isoformat(),
        }
    
    except Exception as e:
        logger.error(f"Readiness check failed: {e}", exc_info=True)
        return {
            "ready": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@router.get("/live")
async def liveness_check() -> Dict[str, str]:
    """
    Liveness check endpoint (for Kubernetes).
    
    Returns:
        Liveness status
    """
    return {
        "alive": "true",
        "timestamp": datetime.now().isoformat(),
    }
