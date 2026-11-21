"""All configuration comes from the single .env file at the repository root."""
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore", env_ignore_empty=True)

    # App
    APP_NAME: str
    APP_ENV: str = "development"
    APP_BASE_URL: str = "http://localhost:8000"
    SECRET_KEY: str
    FIELD_ENCRYPTION_KEY: str

    # Database and storage
    DATABASE_URL: str
    TEST_DATABASE_URL: str | None = None
    SUPABASE_URL: str | None = None
    SUPABASE_SERVICE_KEY: str | None = None
    STORAGE_BUCKET_PUBLIC: str | None = None
    STORAGE_BUCKET_PRIVATE: str | None = None

    # Auth
    OTP_TTL_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 5
    ACCESS_TOKEN_TTL_MINUTES: int = 15
    REFRESH_TOKEN_TTL_DAYS: int = 30
    TEST_FIXED_OTP: str | None = None
    TEST_SIGNIN_EMAILS: str | None = None  # comma separated; on staging the fixed code works only for these

    # Email
    EMAIL_PROVIDER: str | None = None
    EMAIL_API_KEY: str | None = None
    EMAIL_FROM: str | None = None

    # Payments. Off during testing: everyone gets full access and no billing route runs.
    PAYMENTS_ENABLED: bool = False
    PAYMENTS_MODE: str = "mock"
    RAZORPAY_KEY_ID: str | None = None
    RAZORPAY_KEY_SECRET: str | None = None
    RAZORPAY_WEBHOOK_SECRET: str | None = None
    RAZORPAY_PLAN_CONSUMER_MONTHLY: str | None = None
    RAZORPAY_PLAN_CONSUMER_YEARLY: str | None = None
    RAZORPAY_PLAN_BUSINESS_MONTHLY: str | None = None

    # Subscription rules
    TRIAL_DAYS: int = 7
    GRACE_DAYS: int = 5
    PRICE_CONSUMER_MONTHLY_INR: int | None = None
    PRICE_CONSUMER_YEARLY_INR: int | None = None
    MAX_DEVICES_PER_ACCOUNT: int = 3

    # AI
    AI_PROVIDER: str | None = None
    AI_API_KEY: str | None = None
    AI_MODEL_VISION: str | None = None
    AI_MODEL_CHAT: str | None = None
    AI_MODEL_EMBEDDING: str | None = None
    AI_MONTHLY_BUDGET_INR: float | None = None
    ASSISTANT_DAILY_QUESTIONS: int | None = None
    AI_PRICE_INPUT_INR_PER_MTOK: float | None = None
    AI_PRICE_OUTPUT_INR_PER_MTOK: float | None = None

    # Nutrition and trust
    SPREAD_VERIFIED: float = 0.05
    SPREAD_DECLARED: float = 0.15
    SPREAD_ESTIMATED: float = 0.30
    DISPLAY_RATIO_BAND: float = 1.25
    DISPLAY_RATIO_RANGE: float = 1.5
    DISPLAY_RATIO_EXCLUDE: float = 2.5
    VERIFICATION_EXPIRY_DAYS: int = 90
    DISPLAY_HYSTERESIS: float = 0.05
    PLAUSIBILITY_ENERGY_MARGIN: float = 0.5
    PLAUSIBILITY_YIELD_MIN: float = 0.4
    PLAUSIBILITY_YIELD_MAX: float = 3.0
    PLAUSIBILITY_MAX_FAT_SHARE: float = 0.35
    PLAUSIBILITY_PROTEIN_MIN_RATIO: float = 0.5
    PLAUSIBILITY_MAX_ENERGY_CHANGE: float = 0.30
    HEAVIER_WIDEN_STEP: float = 0.05
    CALORIE_FLOOR_KCAL: int | None = None
    OUTLET_BAND_MIN_MEALS: int = 30
    OUTLET_BAND_MIN_USERS: int = 15
    COVERAGE_MIN_RESTAURANTS: int | None = None

    # Discovery and ranking
    DISCOVERY_RADIUS_KM: float = 3.0
    MEAL_SHARE_OF_DAY: float = 0.35
    RANK_WEIGHT_CALORIE: float = 0.4
    RANK_WEIGHT_PROTEIN: float = 0.3
    RANK_WEIGHT_TRUST: float = 0.2
    RANK_WEIGHT_RELEVANCE: float = 0.1

    # Feedback loop
    CHECKIN_DELAY_MINUTES: int = 60
    CHECKIN_WINDOW_DAYS: int = 3
    HEAVIER_USERS_PER_STEP: int = 3
    INSIGHTS_MIN_USERS: int = 5

    # Hardening
    API_RATE_PER_MINUTE_PER_IP: int = 600
    MAX_JSON_BYTES: int = 1_000_000
    CRAWL_DISTINCT_DISHES_PER_HOUR: int = 300

    # Monitoring
    SENTRY_DSN: str | None = None

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @model_validator(mode="after")
    def _refuse_unsafe_production(self):
        try:
            from cryptography.fernet import Fernet
            Fernet(self.FIELD_ENCRYPTION_KEY.encode())
        except Exception as e:
            raise ValueError("Refusing to start: FIELD_ENCRYPTION_KEY is not a valid key") from e
        if self.is_production:
            if len(self.SECRET_KEY) < 32:
                raise ValueError("Refusing to start: SECRET_KEY must be at least 32 characters")
            if self.PAYMENTS_ENABLED:
                if self.PAYMENTS_MODE != "live":
                    raise ValueError("Refusing to start: production with payments on requires PAYMENTS_MODE=live")
                if not (self.RAZORPAY_KEY_ID and self.RAZORPAY_KEY_SECRET and self.RAZORPAY_WEBHOOK_SECRET):
                    raise ValueError("Refusing to start: live payments need the Razorpay keys and webhook secret")
            if self.TEST_FIXED_OTP:
                raise ValueError("Refusing to start: TEST_FIXED_OTP must be empty in production")
            if not self.APP_BASE_URL.startswith("https://"):
                raise ValueError("Refusing to start: production APP_BASE_URL must use https")
            needed = ["CALORIE_FLOOR_KCAL", "COVERAGE_MIN_RESTAURANTS", "ASSISTANT_DAILY_QUESTIONS"]
            if self.PAYMENTS_ENABLED:
                needed.append("PRICE_CONSUMER_MONTHLY_INR")
            missing = [k for k in needed if getattr(self, k) is None]
            if missing:
                raise ValueError(f"Refusing to start: production needs {', '.join(missing)}")
        if self.is_staging:
            if len(self.SECRET_KEY) < 32:
                raise ValueError("Refusing to start: SECRET_KEY must be at least 32 characters")
            if not self.APP_BASE_URL.startswith("https://"):
                raise ValueError("Refusing to start: staging APP_BASE_URL must use https")
            if self.TEST_FIXED_OTP and (len(self.TEST_FIXED_OTP) < 8 or not self.test_signin_emails):
                raise ValueError("Refusing to start: on staging TEST_FIXED_OTP needs 8+ characters and TEST_SIGNIN_EMAILS")
            if self.PAYMENTS_ENABLED and self.PAYMENTS_MODE == "live":
                raise ValueError("Refusing to start: staging never takes live payments")
        return self

    @property
    def is_staging(self) -> bool:
        return self.APP_ENV == "staging"

    @property
    def test_signin_emails(self) -> set[str]:
        return {e.strip().lower() for e in (self.TEST_SIGNIN_EMAILS or "").split(",") if e.strip()}

    def public_config(self) -> dict:
        """The only settings the frontend may see (GET /api/v1/config)."""
        return {
            "app_name": self.APP_NAME,
            "environment": self.APP_ENV,
            "payments_enabled": self.PAYMENTS_ENABLED,
            "payments_mode": self.PAYMENTS_MODE,
            "trial_days": self.TRIAL_DAYS,
            "price_monthly_inr": self.PRICE_CONSUMER_MONTHLY_INR,
            "price_yearly_inr": self.PRICE_CONSUMER_YEARLY_INR,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
