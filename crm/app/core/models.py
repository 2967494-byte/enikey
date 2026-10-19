import enum
from datetime import datetime, date
from typing import Optional
from sqlalchemy import (
    Column, Integer, String, Text, Numeric, Boolean, Date, DateTime,
    ForeignKey, Enum, JSON
)
from sqlalchemy.orm import relationship
from app.core.database import Base

class ProjectType(str, enum.Enum):
    IT_SYSTEM = "IT_SYSTEM"
    NEW_IDEA = "NEW_IDEA"
    DIY_BUILD = "DIY_BUILD"
    AUTO = "AUTO"
    LOAN = "LOAN"
    HOUSEHOLD = "HOUSEHOLD"

class ProjectStage(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    ACTIVE = "ACTIVE"
    MAINTENANCE = "MAINTENANCE"
    ON_HOLD = "ON_HOLD"
    COMPLETED = "COMPLETED"

class SupplyStatus(str, enum.Enum):
    NEED_TO_BUY = "NEED_TO_BUY"
    ORDERED_IN_TRANSIT = "ORDERED_IN_TRANSIT"
    ARRIVED_AT_PICKUP = "ARRIVED_AT_PICKUP"
    IN_STOCK = "IN_STOCK"
    USED_OR_HANDED_OVER = "USED_OR_HANDED_OVER"

class PaymentSettlement(str, enum.Enum):
    SELF = "SELF"
    WAIT_FOR_ORDER = "WAIT_FOR_ORDER"
    PREPAID_BY_FRIEND = "PREPAID_BY_FRIEND"
    PAID_BY_ME_DEBT = "PAID_BY_ME_DEBT"
    CLOSED = "CLOSED"

class TaskStatus(str, enum.Enum):
    BLOCKED = "BLOCKED"
    TODO = "TODO"
    SCHEDULED = "SCHEDULED"
    DONE = "DONE"

class FinanceRecordType(str, enum.Enum):
    INCOME_EXPECTED = "INCOME_EXPECTED"
    EXPENSE_MANDATORY = "EXPENSE_MANDATORY"
    EXPENSE_BIRTHDAY = "EXPENSE_BIRTHDAY"
    EXPENSE_WISHLIST = "EXPENSE_WISHLIST"

class RecurrenceType(str, enum.Enum):
    NONE = "NONE"
    MONTHLY = "MONTHLY"
    YEARLY = "YEARLY"

class FinanceStatus(str, enum.Enum):
    PLANNED = "PLANNED"
    EXECUTED = "EXECUTED"

class Location(Base):
    __tablename__ = "locations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True)
    color = Column(String(30), default="#6366f1")

    tasks = relationship("Task", back_populates="location")

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    project_type = Column(Enum(ProjectType), nullable=False, default=ProjectType.HOUSEHOLD)
    stage = Column(Enum(ProjectStage), nullable=False, default=ProjectStage.ACTIVE)
    priority = Column(Integer, default=3)  # 1: Critical, 2: High, 3: Normal, 4: Low
    color_hex = Column(String(20), default="#3b82f6")
    weekly_quota_minutes = Column(Integer, default=0)
    preferred_slot_minutes = Column(Integer, default=60)
    template_payload = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    supply_items = relationship("SupplyItem", back_populates="project", cascade="all, delete-orphan")
    finance_records = relationship("FinanceRecord", back_populates="project", cascade="all, delete-orphan")

class SupplyItem(Base):
    __tablename__ = "supply_items"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    item_name = Column(String(255), nullable=False)
    status = Column(Enum(SupplyStatus), default=SupplyStatus.NEED_TO_BUY, nullable=False)
    vendor = Column(String(100), nullable=True)
    order_link_or_track = Column(String(500), nullable=True)
    expected_date = Column(Date, nullable=True)
    cost = Column(Numeric(12, 2), default=0.0)
    target_person = Column(String(100), nullable=True)
    payment_settlement = Column(Enum(PaymentSettlement), default=PaymentSettlement.SELF, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="supply_items")
    dependent_tasks = relationship("Task", back_populates="depends_on_supply", foreign_keys="Task.depends_on_supply_id")

class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    location_id = Column(Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.TODO, nullable=False)
    priority = Column(Integer, default=3)
    duration_minutes = Column(Integer, default=60)
    hard_due_date = Column(Date, nullable=True)
    scheduled_start = Column(DateTime, nullable=True)
    scheduled_end = Column(DateTime, nullable=True)
    is_auto_placed = Column(Boolean, default=False)
    depends_on_supply_id = Column(Integer, ForeignKey("supply_items.id", ondelete="SET NULL"), nullable=True)
    depends_on_task_id = Column(Integer, ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="tasks")
    location = relationship("Location", back_populates="tasks")
    depends_on_supply = relationship("SupplyItem", back_populates="dependent_tasks", foreign_keys=[depends_on_supply_id])
    depends_on_task = relationship("Task", remote_side=[id], foreign_keys=[depends_on_task_id], backref="subtasks")

class WalletState(Base):
    __tablename__ = "wallet_state"

    id = Column(Integer, primary_key=True)
    current_balance = Column(Numeric(14, 2), default=0.0)
    safety_threshold = Column(Numeric(14, 2), default=50000.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class FinanceRecord(Base):
    __tablename__ = "finance_records"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="SET NULL"), nullable=True)
    supply_item_id = Column(Integer, ForeignKey("supply_items.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(255), nullable=False)
    record_type = Column(Enum(FinanceRecordType), default=FinanceRecordType.EXPENSE_MANDATORY, nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    planned_date = Column(Date, nullable=False)
    is_annual_or_monthly = Column(Enum(RecurrenceType), default=RecurrenceType.NONE, nullable=False)
    status = Column(Enum(FinanceStatus), default=FinanceStatus.PLANNED, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="finance_records")
    supply_item = relationship("SupplyItem")
