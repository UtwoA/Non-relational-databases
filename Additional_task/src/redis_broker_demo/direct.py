from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
import threading
import time

from .metrics import MetricsStore
from .models import Job


class DirectProcessor:
    def __init__(
        self,
        metrics: MetricsStore,
        workers: int = 2,
        processing_ms: int = 300,
        acquire_timeout_ms: int = 10,
    ) -> None:
        self.metrics = metrics
        self.semaphore = threading.Semaphore(workers)
        self.processing_ms = processing_ms
        self.acquire_timeout_ms = acquire_timeout_ms

    def handle(self, job: Job) -> bool:
        acquired = self.semaphore.acquire(timeout=self.acquire_timeout_ms / 1000)
        if not acquired:
            self.metrics.record_rejected("direct")
            return False

        self.metrics.record_accepted("direct")
        try:
            time.sleep(self.processing_ms / 1000)
            latency_ms = (time.time() - job.created_at) * 1000
            self.metrics.record_processed("direct", latency_ms)
            return True
        finally:
            self.semaphore.release()


def run_direct_load(
    metrics: MetricsStore,
    jobs: int,
    burst: int,
    workers: int,
    processing_ms: int,
    acquire_timeout_ms: int,
) -> dict:
    metrics.reset_mode("direct")
    processor = DirectProcessor(
        metrics=metrics,
        workers=workers,
        processing_ms=processing_ms,
        acquire_timeout_ms=acquire_timeout_ms,
    )

    samples = [metrics.snapshot("direct")]
    with ThreadPoolExecutor(max_workers=max(jobs, workers)) as executor:
        futures = []
        for index in range(jobs):
            metrics.record_produced("direct")
            futures.append(executor.submit(processor.handle, Job.create("direct")))
            if burst > 0 and (index + 1) % burst == 0:
                samples.append(metrics.snapshot("direct"))
                time.sleep(0.02)
        wait(futures)

    samples.append(metrics.snapshot("direct"))
    return {"summary": metrics.read_mode("direct"), "samples": samples}
