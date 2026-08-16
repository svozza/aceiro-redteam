def validate(cfg):
    chunk = cfg.get("chunk_size", 1024)
    retries = cfg.get("retries", 3)
    timeout = cfg.get("timeout", 30)
    return (chunk, retries, timeout)
