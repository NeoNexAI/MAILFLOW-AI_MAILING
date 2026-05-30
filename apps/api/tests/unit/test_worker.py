"""Smoke test del worker ARQ — verifica configuración sin arrancar Redis."""


def test_worker_settings_queue_name():
    from worker.main import WorkerSettings

    assert WorkerSettings.queue_name == "mailflow:default"


def test_worker_settings_has_process_function():
    from worker.main import WorkerSettings, process_account_cycle

    assert process_account_cycle in WorkerSettings.functions


def test_worker_settings_has_cron():
    from worker.main import WorkerSettings, schedule_cycles

    assert len(WorkerSettings.cron_jobs) == 1
    cron_job = WorkerSettings.cron_jobs[0]
    assert cron_job.coroutine is schedule_cycles


def test_worker_settings_has_retry_and_timeout():
    from worker.main import WorkerSettings, on_job_failure

    assert WorkerSettings.max_tries == 3
    assert WorkerSettings.job_timeout == 300
    assert WorkerSettings.on_job_failure is on_job_failure


async def test_on_job_failure_logs_dead_letter(caplog):
    import logging

    from worker.main import on_job_failure

    ctx = {"job_id": "cycle-abc", "job_name": "process_account_cycle"}
    with caplog.at_level(logging.ERROR, logger="mailflow.worker"):
        await on_job_failure(ctx, RuntimeError("db down"))

    assert any(
        "DEAD-LETTER" in r.message and "cycle-abc" in r.message for r in caplog.records
    )
