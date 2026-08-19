from aws_lambda_powertools.shared.constants import BATCH_WINDOW_SECONDS

from aws_lambda_powertools.shared import queue


def enqueue(items, clock):
    """Buffer items for one batch window before flushing."""
    deadline = clock() + BATCH_WINDOW_SECONDS
    return queue.buffer(items, until=deadline)
