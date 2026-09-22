"""
Performance Monitoring Utility
System performance metrics, including CPU, memory, disk, network, etc.
"""

import psutil
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import threading
from enum import Enum

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Metric type"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    PROCESS = "process"
    CUSTOM = "custom"


@dataclass
class PerformanceMetric:
    """Performance metric"""
    name: str
    value: float
    unit: str
    timestamp: datetime
    metric_type: MetricType
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class SystemStats:
    """System statistics"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used: int
    memory_total: int
    disk_usage_percent: float
    disk_used: int
    disk_total: int
    network_bytes_sent: int
    network_bytes_recv: int
    active_processes: int


class PerformanceMonitor:
    """Performance monitor"""
    
    def __init__(self, max_history_size: int = 1000, collection_interval: int = 60):
        self.max_history_size = max_history_size
        self.collection_interval = collection_interval
        self.metrics_history: deque = deque(maxlen=max_history_size)
        self.system_stats_history: deque = deque(maxlen=max_history_size)
        self.is_monitoring = False
        self.monitor_task: Optional[asyncio.Task] = None
        self.lock = threading.Lock()
        
        # Network statistics baseline
        self._network_baseline = None
        self._last_network_check = None
    
    def _get_system_stats(self) -> SystemStats:
        """Get system status information"""
        
        # CPU utilization
        cpu_percent = psutil.cpu_percent(interval=1)
        
        # Memory utilization
        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_used = memory.used
        memory_total = memory.total
        
        # Disk utilization
        disk = psutil.disk_usage('/')
        disk_usage_percent = (disk.used / disk.total) * 100
        disk_used = disk.used
        disk_total = disk.total
        
        # Network statistics
        network = psutil.net_io_counters()
        network_bytes_sent = network.bytes_sent
        network_bytes_recv = network.bytes_recv
        
        # Active process count
        active_processes = len(psutil.pids())
        
        return SystemStats(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            memory_used=memory_used,
            memory_total=memory_total,
            disk_usage_percent=disk_usage_percent,
            disk_used=disk_used,
            disk_total=disk_total,
            network_bytes_sent=network_bytes_sent,
            network_bytes_recv=network_bytes_recv,
            active_processes=active_processes
        )
    
    def _get_process_stats(self, process_name: str = None) -> List[Dict[str, Any]]:
        """Get process statistics"""
        
        processes = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'memory_info']):
            try:
                if process_name and process_name not in proc.info['name']:
                    continue
                
                processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cpu_percent': proc.info['cpu_percent'],
                    'memory_percent': proc.info['memory_percent'],
                    'memory_rss': proc.info['memory_info'].rss if proc.info['memory_info'] else 0,
                    'memory_vms': proc.info['memory_info'].vms if proc.info['memory_info'] else 0
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        
        return processes
    
    def _calculate_network_delta(self, current_stats: SystemStats) -> Dict[str, int]:
        """Calculate network traffic increment"""
        
        if self._network_baseline is None:
            self._network_baseline = current_stats
            self._last_network_check = current_stats.timestamp
            return {'bytes_sent_delta': 0, 'bytes_recv_delta': 0}
        
        time_delta = (current_stats.timestamp - self._last_network_check).total_seconds()
        if time_delta <= 0:
            return {'bytes_sent_delta': 0, 'bytes_recv_delta': 0}
        
        bytes_sent_delta = current_stats.network_bytes_sent - self._network_baseline.network_bytes_sent
        bytes_recv_delta = current_stats.network_bytes_recv - self._network_baseline.network_bytes_recv
        
        # Calculate throughput per second
        bytes_sent_per_sec = bytes_sent_delta / time_delta
        bytes_recv_per_sec = bytes_recv_delta / time_delta
        
        self._network_baseline = current_stats
        self._last_network_check = current_stats.timestamp
        
        return {
            'bytes_sent_delta': bytes_sent_delta,
            'bytes_recv_delta': bytes_recv_delta,
            'bytes_sent_per_sec': bytes_sent_per_sec,
            'bytes_recv_per_sec': bytes_recv_per_sec
        }
    
    async def collect_metrics(self):
        """Collect performance metrics"""
        
        try:
            # Get system status information
            system_stats = self._get_system_stats()
            
            with self.lock:
                self.system_stats_history.append(system_stats)
            
            # Calculate network traffic increment
            network_delta = self._calculate_network_delta(system_stats)
            
            # Create performance metrics
            metrics = [
                PerformanceMetric(
                    name="cpu_usage",
                    value=system_stats.cpu_percent,
                    unit="percent",
                    timestamp=system_stats.timestamp,
                    metric_type=MetricType.CPU
                ),
                PerformanceMetric(
                    name="memory_usage",
                    value=system_stats.memory_percent,
                    unit="percent",
                    timestamp=system_stats.timestamp,
                    metric_type=MetricType.MEMORY
                ),
                PerformanceMetric(
                    name="memory_used",
                    value=system_stats.memory_used,
                    unit="bytes",
                    timestamp=system_stats.timestamp,
                    metric_type=MetricType.MEMORY
                ),
                PerformanceMetric(
                    name="disk_usage",
                    value=system_stats.disk_usage_percent,
                    unit="percent",
                    timestamp=system_stats.timestamp,
                    metric_type=MetricType.DISK
                ),
                PerformanceMetric(
                    name="disk_used",
                    value=system_stats.disk_used,
                    unit="bytes",
                    timestamp=system_stats.timestamp,
                    metric_type=MetricType.DISK
                ),
                PerformanceMetric(
                    name="network_sent_per_sec",
                    value=network_delta.get('bytes_sent_per_sec', 0),
                    unit="bytes_per_second",
                    timestamp=system_stats.timestamp,
                    metric_type=MetricType.NETWORK
                ),
                PerformanceMetric(
                    name="network_recv_per_sec",
                    value=network_delta.get('bytes_recv_per_sec', 0),
                    unit="bytes_per_second",
                    timestamp=system_stats.timestamp,
                    metric_type=MetricType.NETWORK
                ),
                PerformanceMetric(
                    name="active_processes",
                    value=system_stats.active_processes,
                    unit="count",
                    timestamp=system_stats.timestamp,
                    metric_type=MetricType.PROCESS
                )
            ]
            
            with self.lock:
                self.metrics_history.extend(metrics)
            
            logger.debug(f"Collected performance metrics: {len(metrics)} metrics")
            
        except Exception as e:
            logger.error(f"Failed to collect performance indicators: {e}")
    
    async def start_monitoring(self):
        """Start monitoring"""
        
        if self.is_monitoring:
            logger.warning("Performance monitoring is already running")
            return
        
        self.is_monitoring = True
        self.monitor_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info(f"Start performance monitoring, collection interval: {self.collection_interval} seconds")
    
    async def stop_monitoring(self):
        """Stop monitoring"""
        
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Stop performance monitoring")
    
    async def _monitoring_loop(self):
        """Monitoring loop"""
        
        while self.is_monitoring:
            try:
                await self.collect_metrics()
                await asyncio.sleep(self.collection_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(self.collection_interval)
    
    def get_current_stats(self) -> SystemStats:
        """Get current system statistics"""
        
        with self.lock:
            if self.system_stats_history:
                return self.system_stats_history[-1]
            else:
                return self._get_system_stats()
    
    def get_metrics_summary(self, time_range_minutes: int = 60) -> Dict[str, Any]:
        """Get metrics summary"""
        
        cutoff_time = datetime.now() - timedelta(minutes=time_range_minutes)
        
        with self.lock:
            # Filter indicators within the specified time range
            recent_metrics = [
                metric for metric in self.metrics_history
                if metric.timestamp >= cutoff_time
            ]
            
            # Group by metric name
            metrics_by_name = {}
            for metric in recent_metrics:
                if metric.name not in metrics_by_name:
                    metrics_by_name[metric.name] = []
                metrics_by_name[metric.name].append(metric.value)
            
            # Calculate statistics
            summary = {}
            for name, values in metrics_by_name.items():
                if values:
                    summary[name] = {
                        'count': len(values),
                        'min': min(values),
                        'max': max(values),
                        'avg': sum(values) / len(values),
                        'latest': values[-1]
                    }
            
            return summary
    
    def get_system_health(self) -> Dict[str, Any]:
        """Get system health status"""
        
        current_stats = self.get_current_stats()
        
        # Health status assessment
        health_status = "healthy"
        warnings = []
        
        if current_stats.cpu_percent > 80:
            health_status = "warning"
            warnings.append(f"CPU utilization too high: {current_stats.cpu_percent:.1f}%")
        
        if current_stats.memory_percent > 85:
            health_status = "warning"
            warnings.append(f"High memory usage: {current_stats.memory_percent:.1f}%")
        
        if current_stats.disk_usage_percent > 90:
            health_status = "critical"
            warnings.append(f"High disk usage: {current_stats.disk_usage_percent:.1f}%")
        
        return {
            "status": health_status,
            "warnings": warnings,
            "current_stats": {
                "cpu_percent": current_stats.cpu_percent,
                "memory_percent": current_stats.memory_percent,
                "disk_usage_percent": current_stats.disk_usage_percent,
                "active_processes": current_stats.active_processes
            },
            "timestamp": current_stats.timestamp.isoformat()
        }
    
    def get_top_processes(self, limit: int = 10, sort_by: str = "cpu") -> List[Dict[str, Any]]:
        """Get the process with the highest resource consumption"""
        
        processes = self._get_process_stats()
        
        # Sort by specified field
        if sort_by == "cpu":
            processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
        elif sort_by == "memory":
            processes.sort(key=lambda x: x['memory_percent'], reverse=True)
        
        return processes[:limit]
    
    def add_custom_metric(self, name: str, value: float, unit: str = "", tags: Dict[str, str] = None):
        """Add custom indicator"""
        
        metric = PerformanceMetric(
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.now(),
            metric_type=MetricType.CUSTOM,
            tags=tags or {}
        )
        
        with self.lock:
            self.metrics_history.append(metric)
    
    def clear_history(self):
        """Clear historical data"""
        
        with self.lock:
            self.metrics_history.clear()
            self.system_stats_history.clear()
        
        logger.info("Clear performance monitoring historical data")


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


# Performance monitoring decorator
def monitor_performance(metric_name: str, unit: str = ""):
    """Performance monitoring decorator"""
    
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                performance_monitor.add_custom_metric(
                    f"{metric_name}_execution_time",
                    execution_time,
                    unit or "seconds"
                )
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                performance_monitor.add_custom_metric(
                    f"{metric_name}_error_time",
                    execution_time,
                    unit or "seconds",
                    {"error": str(e)}
                )
                raise
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                performance_monitor.add_custom_metric(
                    f"{metric_name}_execution_time",
                    execution_time,
                    unit or "seconds"
                )
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                performance_monitor.add_custom_metric(
                    f"{metric_name}_error_time",
                    execution_time,
                    unit or "seconds",
                    {"error": str(e)}
                )
                raise
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator
