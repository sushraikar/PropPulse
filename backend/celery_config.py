"""
Celery configuration for PropPulse risk engine

This module configures Celery for background processing of risk assessment tasks:
- Daily data ingestion (02:00 GST)
- Monte Carlo simulation runner (03:00 GST)
- Secondary market price adjuster (04:30 GST)
"""
import os
from celery import Celery
from celery.schedules import crontab
from datetime import timedelta
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Celery app
app = Celery('proppulse_risk')

# Load configuration from environment variables
app.conf.broker_url = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
app.conf.result_backend = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Configure task queues with priorities
app.conf.task_queues = {
    'risk': {'exchange': 'risk', 'routing_key': 'risk', 'queue_arguments': {'x-max-priority': 10}},
    'price-watcher': {'exchange': 'price-watcher', 'routing_key': 'price-watcher', 'queue_arguments': {'x-max-priority': 10}},
    'ingest': {'exchange': 'ingest', 'routing_key': 'ingest', 'queue_arguments': {'x-max-priority': 10}},
    'default': {'exchange': 'default', 'routing_key': 'default', 'queue_arguments': {'x-max-priority': 10}}
}

# Configure task routes
app.conf.task_routes = {
    'tasks.risk_data_ingestor.*': {'queue': 'ingest', 'priority': 4},
    'tasks.monte_carlo_irr_agent.*': {'queue': 'risk', 'priority': 5},
    'tasks.price_watcher.*': {'queue': 'price-watcher', 'priority': 3},
    'tasks.alert_agent.*': {'queue': 'risk', 'priority': 6},
    'tasks.risk_score_composer.*': {'queue': 'risk', 'priority': 5}
}

# Configure task time limits
app.conf.task_time_limit = 600  # 10 minutes
app.conf.task_soft_time_limit = 540  # 9 minutes

# Configure concurrency
app.conf.worker_concurrency = 2

# Configure scheduled tasks
app.conf.beat_schedule = {
    'risk-ingest-daily': {
        'task': 'tasks.risk_data_ingestor.ingest_daily_data',
        'schedule': crontab(hour=2, minute=0),  # 02:00 GST
        'options': {'queue': 'ingest', 'priority': 4}
    },
    'mc-sim-runner': {
        'task': 'tasks.monte_carlo_irr_agent.run_batch_simulation',
        'schedule': crontab(hour=3, minute=0),  # 03:00 GST
        'options': {'queue': 'risk', 'priority': 5}
    },
    'price-adjuster': {
        'task': 'tasks.alert_agent.adjust_market_prices',
        'schedule': crontab(hour=4, minute=30),  # 04:30 GST
        'options': {'queue': 'risk', 'priority': 6}
    }
}

# Configure task serialization
app.conf.accept_content = ['json']
app.conf.task_serializer = 'json'
app.conf.result_serializer = 'json'

# Configure task result expiration
app.conf.result_expires = timedelta(days=1)

# Configure task acks late
app.conf.task_acks_late = True

# Configure task prefetch multiplier
app.conf.worker_prefetch_multiplier = 1

# Configure task default rate limit
app.conf.task_default_rate_limit = '10/m'

# Configure task default retry delay
app.conf.task_default_retry_delay = 300  # 5 minutes

# Configure task max retries
app.conf.task_default_max_retries = 3

# Configure task ignore result
app.conf.task_ignore_result = False

# Configure task store errors even if ignored
app.conf.task_store_errors_even_if_ignored = True

# Configure task track started
app.conf.task_track_started = True

# Configure task send events
app.conf.worker_send_task_events = True

# Configure task send task sent events
app.conf.task_send_sent_event = True

# Configure task remote tracebacks
app.conf.task_remote_tracebacks = True

# Configure task compression
app.conf.task_compression = 'gzip'

# Configure task reject on worker lost
app.conf.task_reject_on_worker_lost = True

# Configure task publish retry
app.conf.task_publish_retry = True

# Configure task publish retry policy
app.conf.task_publish_retry_policy = {
    'max_retries': 3,
    'interval_start': 0,
    'interval_step': 0.2,
    'interval_max': 0.5
}

# Include tasks
app.autodiscover_tasks(['tasks'])

if __name__ == '__main__':
    app.start()
