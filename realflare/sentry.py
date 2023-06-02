from realflare.storage import Storage


def init() -> None:
    storage = Storage()

    if storage.settings.sentry:
        import sentry_sdk

        sentry_sdk.init(
            dsn='https://ca69319449554a2885eb98218ede9110@o4504738332016640.ingest.sentry.io/4504738333655040',
            traces_sample_rate=1.0,
        )
