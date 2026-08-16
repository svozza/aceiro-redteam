def validate(cfg):
    chunk = int(cfg.get("chunk_size", 1024))
    retries = cfg.get("retries", 3)
    timeout = int(cfg.get("timeout", 30))
    return (chunk, retries, timeout)
