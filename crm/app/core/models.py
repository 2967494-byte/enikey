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

class ProjectCategory(Base):
    __tablename__ = "project_categories"

    id = Column(Integer, primary_key=True, index=True)
    slug = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(100), nullable=False)
    icon = Column(String(50), default="folder")
    color = Column(String(30), default="#6366f1")
    sort_order = Column(Integer, default=100)
    created_at = Column(DateTime, default=datetime.utcnow)

class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, default="")
    project_type = Column(Enum(ProjectType), nullable=False, default=ProjectType.HOUSEHOLD)
    category_slug = Column(String(50), nullable=True)
    stage = Column(Enum(ProjectStage), nullable=False, default=ProjectStage.ACTIVE)
    priority = Column(Integer, default=3)  # 1: Critical, 2: High, 3: Normal, 4: Low
    color_hex = Column(String(20), default="#3b82f6")
    weekly_quota_minutes = Column(Integer, default=0)
    preferred_slot_minutes = Column(Integer, default=60)
    template_payload = Column(JSON, default=dict)
    parent_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    parent = relationship("Project", remote_side=[id], back_populates="subprojects")
    subprojects = relationship("Project", back_populates="parent", cascade="all, delete-orphan", foreign_keys=[parent_id])
    tasks = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    supply_items = relationship("SupplyItem", back_populates="project", cascade="all, delete-orphan")
    finance_records = relationship("FinanceRecord", back_populates="project", cascade="all, delete-orphan")
    material_assets = relationship("MaterialAsset", back_populates="project", cascade="all, delete-orphan", order_by="MaterialAsset.id.desc()")

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
    is_urgent = Column(Boolean, default=False)
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

class Counterparty(Base):
    """Справочник контрагентов (Юридические лица, ИП, партнеры)"""
    __tablename__ = "counterparties"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True) # Краткое наименование: ООО "Вектор"
    full_name = Column(String(500), nullable=True) # Полное наименование по ЕГРЮЛ
    inn = Column(String(12), nullable=True, index=True) # ИНН (10 или 12 знаков)
    kpp = Column(String(9), nullable=True) # КПП (9 знаков)
    ogrn = Column(String(15), nullable=True) # ОГРН / ОГРНИП
    legal_address = Column(Text, nullable=True) # Юридический адрес
    actual_address = Column(Text, nullable=True) # Фактический / почтовый адрес
    bank_name = Column(String(255), nullable=True) # Наименование банка
    bik = Column(String(9), nullable=True) # БИК банка (9 цифр)
    corr_account = Column(String(20), nullable=True) # Корр. счет (20 цифр)
    checking_account = Column(String(20), nullable=True) # Расчетный счет контрагента (20 цифр)
    contact_person = Column(String(255), nullable=True) # ФИО директора / контактного лица
    contact_phone = Column(String(50), nullable=True) # Телефон
    contact_email = Column(String(100), nullable=True) # Email
    notes = Column(Text, default="") # Дополнительные примечания
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    grounds = relationship("IpPaymentGround", back_populates="counterparty")
    incomes = relationship("IpIncome", back_populates="counterparty")

class IpPaymentGround(Base):
    """Справочник оснований платежей / договоров ИП"""
    __tablename__ = "ip_payment_grounds"

    id = Column(Integer, primary_key=True, index=True)
    counterparty_id = Column(Integer, ForeignKey("counterparties.id", ondelete="SET NULL"), nullable=True)
    name = Column(String(255), nullable=False) # e.g. "Договор №12/24 от 15.01.2024"
    client_name = Column(String(255), nullable=True) # Заказчик / плательщик
    default_account = Column(String(100), default="Т-Банк (Тинькофф)")
    description = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    counterparty = relationship("Counterparty", back_populates="grounds")
    incomes = relationship("IpIncome", back_populates="ground")

class IpIncome(Base):
    """Отдельный учет поступлений на расчетный счет ИП"""
    __tablename__ = "ip_incomes"

    id = Column(Integer, primary_key=True, index=True)
    payment_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    account_name = Column(String(100), default="Т-Банк (Тинькофф)", nullable=False) # Т-Банк, Точка, Сбер
    invoice_number = Column(String(100), nullable=True) # Номер счета на оплату
    ground_id = Column(Integer, ForeignKey("ip_payment_grounds.id", ondelete="SET NULL"), nullable=True)
    ground_title = Column(String(255), nullable=True) # Название договора / основания
    counterparty_id = Column(Integer, ForeignKey("counterparties.id", ondelete="SET NULL"), nullable=True)
    client_name = Column(String(255), nullable=True) # Контрагент / Клиент
    payment_type = Column(String(50), default="Оплата за месяц") # Аванс, Оплата за месяц, Окончательный расчет
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    ground = relationship("IpPaymentGround", back_populates="incomes")
    counterparty = relationship("Counterparty", back_populates="incomes")

class IpTaxPayment(Base):
    """Фактические платежи по налогам и взносам ИП"""
    __tablename__ = "ip_tax_payments"

    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, nullable=False, index=True)
    period = Column(String(30), nullable=False) # Q1, Q2, Q3, YEAR, FIXED, ONE_PERCENT
    title = Column(String(255), nullable=False)
    amount = Column(Numeric(14, 2), nullable=False)
    payment_date = Column(Date, nullable=False)
    status = Column(String(20), default="PAID") # PAID, PLANNED
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class MaterialAsset(Base):
    __tablename__ = "material_assets"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(String(100), default="Другое")  # e.g. "ИБП / Электропитание", "Компьютеры / ПК", "Мониторы", "Ноутбуки", "Комплектующие / ЗИП", "Оргтехника", "Другое"
    model_name = Column(String(200), nullable=True)
    serial_number = Column(String(100), nullable=True)
    quantity = Column(Integer, default=1)
    purchase_date = Column(Date, nullable=True)
    battery_replaced_at = Column(Date, nullable=True)
    status = Column(String(50), default="В работе")  # "В работе", "В резерве", "Требует ремонта", "Списано"
    is_shared = Column(Boolean, default=False)  # Галка "Для всех подпроектов данного проекта"
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="material_assets")
