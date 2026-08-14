from aws_lambda_powertools.shared.constants import BATCH_WINDOW


def window_summary():
    return {"window_seconds": BATCH_WINDOW}
