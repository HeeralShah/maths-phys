"""Worker boundary; intentionally no model SDK or paid inference integration.

An external worker can claim queued rows and transition status as deployment
configuration becomes available. This stub never performs synthesis.
"""
MODEL_WORKER_CONFIGURED = False

def run_job(job: dict) -> dict:
    raise RuntimeError("Synthesis worker is unconfigured; queued job was preserved")
