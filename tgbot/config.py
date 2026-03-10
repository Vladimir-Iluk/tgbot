from dataclasses import dataclass

from environs import Env


@dataclass
class DbConfig:
    host: str
    password: str
    user: str
    database: str


@dataclass
class TgBot:
    token: str
    admin_ids: list[int]
    use_redis: bool
    gemini_api_key: str
    donatello_api_key: str
    wayforpay_merchant: str  # Додано
    wayforpay_secret: str


@dataclass
class Miscellaneous:
    other_params: str = None


@dataclass
class Config:
    tg_bot: TgBot
    db: DbConfig
    misc: Miscellaneous


def load_config(path: str = None):
    env = Env()
    env.read_env(path)

    return Config(
        tg_bot=TgBot(
            token=env.str("BOT_TOKEN"),
            admin_ids=list(map(int, env.list("ADMINS"))),
            use_redis=env.bool("USE_REDIS"),
            gemini_api_key=env.str("GEMINI_API_KEY"),
            donatello_api_key=env.str("DONATELLO_API_KEY"),
            wayforpay_merchant=env.str("WAYFORPAY_MERCHANT"),
            wayforpay_secret=env.str("WAYFORPAY_SECRET")




        ),
        db=DbConfig(
            host=env.str('DB_HOST'),
            password=env.str('DB_PASS'),
            user=env.str('DB_USER'),
            database=env.str('DB_NAME')
        ),
        misc=Miscellaneous()
    )
