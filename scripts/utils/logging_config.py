#!/usr/bin/env python3
"""
Centralized logging configuration for NCAA lacrosse statistics scraper.

This module provides consistent logging setup and utilities for all scripts
in the lacrosse stats pipeline. It creates timestamped log files and provides
structured logging with both file and console output.

Usage (typically imported by other scripts):
    from scripts.utils.logging_config import setup_logging, log_script_start, log_script_end
    logger = setup_logging(__name__, 'script_name')
    log_script_start(logger, 'My Script', args)
    # ... script logic ...
    log_script_end(logger, 'My Script', success=True, summary={'processed': 100})

Output:
    - outputs/logs/{script}_{timestamp}.log: Detailed log files with timestamps
    - Console: Real-time logging output during script execution
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


def setup_logging(module_name, script_name=None, log_level=logging.INFO):
    """
    Set up structured logging with outputs/logs directory.
    
    Args:
        module_name: Name of the calling module (use __name__)
        script_name: Optional script identifier for log filename
        log_level: Logging level (default: INFO)
    
    Returns:
        Logger instance configured for the module
    """
    # Create logs directory
    log_dir = Path("outputs/logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    script_prefix = f"{script_name}_" if script_name else ""
    log_file = log_dir / f"{script_prefix}lacrosse_{timestamp}.log"
    
    # Configure root logger if not already configured
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        # File handler with detailed formatting
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_level)
        
        # Console handler with simpler formatting
        console_handler = logging.StreamHandler(sys.stdout)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(log_level)
        
        # Configure root logger
        root_logger.setLevel(log_level)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
        
        # Log initial setup message
        root_logger.info(f"Logging initialized. Log file: {log_file}")
    
    # Return module-specific logger
    return logging.getLogger(module_name)


def log_script_start(logger, script_name, args=None):
    """Log script startup with arguments."""
    logger.info(f"=== Starting {script_name} ===")
    if args:
        logger.info(f"Arguments: {vars(args)}")


def log_script_end(logger, script_name, success=True, summary=None):
    """Log script completion with optional summary."""
    status = "completed successfully" if success else "failed"
    logger.info(f"=== {script_name} {status} ===")
    if summary:
        for key, value in summary.items():
            logger.info(f"{key}: {value}")


def log_error_with_context(logger, error, context=None):
    """Log error with additional context information."""
    logger.error(f"Error: {error}")
    if context:
        for key, value in context.items():
            logger.error(f"  {key}: {value}")


def log_performance_metric(logger, operation, duration, count=None):
    """Log performance metrics for operations."""
    rate_info = f" ({count/duration:.2f}/sec)" if count and duration > 0 else ""
    logger.info(f"Performance - {operation}: {duration:.2f}s{rate_info}")