from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Float, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import TableBase
from app.models._types import JSONB, TS, fk


class MealEntry(TableBase):
    __tablename__ = "meal_entries"
    __table_args__ = (Index("ix_meal_entries_user_eaten", "user_id", "eaten_at"),)
    user_id = fk("users.id", nullable=True, ondelete="SET NULL")  # NULL once anonymised
    branch_id = fk("branches.id", nullable=True)
    eaten_at: Mapped[datetime] = mapped_column(TS, index=True)
    meal_type: Mapped[str] = mapped_column(String(16))
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True)


class MealEntryItem(TableBase):
    """Keeps the snapshot shown at logging time AND the recipe version (fixed rule 5)."""
    __tablename__ = "meal_entry_items"
    meal_entry_id = fk("meal_entries.id", ondelete="CASCADE")
    menu_item_id = fk("menu_items.id", nullable=True)
    recipe_version_id = fk("recipe_versions.id", nullable=True)
    serving_option_id = fk("serving_options.id", nullable=True)
    component_label: Mapped[str | None] = mapped_column(String(128))  # thali / buffet component
    share_fraction: Mapped[float] = mapped_column(Float, default=1.0)
    modifiers: Mapped[list] = mapped_column(JSONB, default=list)
    nutrition_snapshot: Mapped[dict] = mapped_column(JSONB)


class Checkin(TableBase):
    __tablename__ = "checkins"
    __table_args__ = (CheckConstraint("felt IN ('lighter','as_expected','heavier')", name="felt"),)
    meal_entry_id = fk("meal_entries.id", ondelete="CASCADE")
    felt: Mapped[str | None] = mapped_column(String(16))
    recommend: Mapped[bool | None] = mapped_column(Boolean)
    recommended_item_id = fk("menu_items.id", nullable=True)


class Report(TableBase):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint("type IN ('menu_changed','portion_wrong','allergen_concern')", name="type"),
        CheckConstraint("status IN ('open','reviewing','resolved','dismissed')", name="status"),
    )
    user_id = fk("users.id", nullable=True, ondelete="SET NULL")
    menu_item_id = fk("menu_items.id")
    type: Mapped[str] = mapped_column(String(24))
    detail: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_by = fk("users.id", nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(TS)


class Dispute(TableBase):
    """A restaurant contesting a report or flag. It can never hide or remove the report (rule 14)."""
    __tablename__ = "disputes"
    business_id = fk("businesses.id", ondelete="CASCADE")
    report_id = fk("reports.id", nullable=True)
    flag_id = fk("plausibility_flags.id", nullable=True)
    detail: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | upheld | rejected
    raised_by = fk("users.id", nullable=True, ondelete="SET NULL")
    resolution_note: Mapped[str | None] = mapped_column(Text)
    resolved_by = fk("users.id", nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(TS)


class DishStats(TableBase):
    __tablename__ = "dish_stats"
    menu_item_id = fk("menu_items.id", ondelete="CASCADE")
    sample_meals: Mapped[int] = mapped_column(Integer, default=0)
    sample_users: Mapped[int] = mapped_column(Integer, default=0)
    recommend_rate: Mapped[float | None] = mapped_column(Float)
    views_7d: Mapped[int] = mapped_column(Integer, default=0)
    # Distinct users whose check-in said "heavier than expected" for the current recipe version.
    heavier_users: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    heavier_version_id = fk("recipe_versions.id", nullable=True)
    computed_at: Mapped[datetime | None] = mapped_column(TS)


class OutletStats(TableBase):
    __tablename__ = "outlet_stats"
    __table_args__ = (CheckConstraint("band_source IN ('logged','modelled')", name="band_source"),)
    branch_id = fk("branches.id", ondelete="CASCADE")
    sample_meals: Mapped[int] = mapped_column(Integer, default=0)
    sample_users: Mapped[int] = mapped_column(Integer, default=0)
    recommend_rate: Mapped[float | None] = mapped_column(Float)
    kcal_p25: Mapped[float | None] = mapped_column(Float)
    kcal_p75: Mapped[float | None] = mapped_column(Float)
    computed_at: Mapped[datetime | None] = mapped_column(TS)
    band_source: Mapped[str] = mapped_column(String(16), default="modelled")


class Event(TableBase):
    """First-party product analytics; no third-party tracker."""
    __tablename__ = "events"
    __table_args__ = (Index("ix_events_name_created", "name", "created_at"),)
    user_id = fk("users.id", nullable=True, ondelete="SET NULL")
    name: Mapped[str] = mapped_column(String(64), index=True)
    properties: Mapped[dict | None] = mapped_column(JSONB)


class AuditLog(TableBase):
    __tablename__ = "audit_logs"
    actor_user_id = fk("users.id", nullable=True, ondelete="SET NULL")
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str | None] = mapped_column(String(64))
    target_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict | None] = mapped_column(JSONB)


class JobRun(TableBase):
    """One row per scheduled job run, shown on the admin health screen."""
    __tablename__ = "job_runs"
    name: Mapped[str] = mapped_column(String(64), index=True)
    started_at: Mapped[datetime] = mapped_column(TS)
    finished_at: Mapped[datetime | None] = mapped_column(TS)
    status: Mapped[str] = mapped_column(String(16), default="running")  # running | ok | failed
    detail: Mapped[dict | None] = mapped_column(JSONB)


class AiUsage(TableBase):
    """One row per model call: tokens, and cost when the owner has set prices. Feeds the monthly budget."""
    __tablename__ = "ai_usage"
    user_id = fk("users.id", nullable=True, ondelete="SET NULL")
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(64))
    purpose: Mapped[str] = mapped_column(String(32))          # assistant | menu_extraction
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_inr: Mapped[float | None] = mapped_column(Float)


class AssistantMessage(TableBase):
    """The assistant conversation, kept for context and the daily cap. Deleted with the account."""
    __tablename__ = "assistant_messages"
    __table_args__ = (Index("ix_assistant_messages_user_created", "user_id", "created_at"),)
    user_id = fk("users.id", ondelete="CASCADE")
    role: Mapped[str] = mapped_column(String(16))             # user | assistant
    content: Mapped[str] = mapped_column(Text)
    cited: Mapped[list | None] = mapped_column(JSONB)          # dish cards shown with the answer
    mode: Mapped[str | None] = mapped_column(String(16))      # ai | basic
