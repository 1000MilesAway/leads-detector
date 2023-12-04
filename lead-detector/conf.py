import os


def get_env(name, default=None):
    var = os.getenv(name)
    if var is not None:
        return var
    else:
        return default



POCKETBASE_URL = get_env("POCKETBASE_URL", "https://aix-pocket.kekw.life")
POCKETBASE_TOKEN = get_env("POCKETBASE_TOKEN")
GPT_TOKEN = get_env("GPT_TOKEN")
PER_PAGE = int(get_env("PER_PAGE", 500))
DAYS_TO_SEARCH = int(get_env("DAYS_TO_SEARCH", 1))
