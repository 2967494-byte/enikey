from datetime import date, datetime
from typing import Optional, Literal, Dict, Any, List
from pydantic import BaseModel, Field

class AddSupplyItemCmd(BaseModel):
    """Команда добавления детали, покупки или заказа для знакомого"""
    project_id: Optional[int] = Field(None, description="ID проекта (например, 3D-принтер или Авто)")
    item_name: str = Field(..., description="Название детали или покупки")
    status: Literal["NEED_TO_BUY", "ORDERED_IN_TRANSIT", "ARRIVED_AT_PICKUP", "IN_STOCK", "USED_OR_HANDED_OVER"] = Field(
        "NEED_TO_BUY", description="Статус детали"
    )
    vendor: Optional[str] = Field(None, description="Где заказано: AliExpress, Ozon, Exist и т.д.")
    order_link_or_track: Optional[str] = Field(None, description="Ссылка на заказ или трек-номер")
    expected_date: Optional[date] = Field(None, description="Ожидаемая дата доставки (ГГГГ-ММ-ДД)")
    cost: float = Field(0.0, description="Стоимость в рублях")
    target_person: Optional[str] = Field(None, description="Имя знакомого, если заказ для него")
    payment_settlement: Literal["SELF", "WAIT_FOR_ORDER", "PREPAID_BY_FRIEND", "PAID_BY_ME_DEBT", "CLOSED"] = Field(
        "SELF", description="Статус расчетов со знакомым"
    )

class UpdateSupplyStatusCmd(BaseModel):
    """Команда обновления статуса детали или расчета за заказ"""
    supply_id: int = Field(..., description="ID позиции детали/заказа")
    status: Literal["NEED_TO_BUY", "ORDERED_IN_TRANSIT", "ARRIVED_AT_PICKUP", "IN_STOCK", "USED_OR_HANDED_OVER"] = Field(
        ..., description="Новый статус детали"
    )
    payment_settlement: Optional[Literal["SELF", "WAIT_FOR_ORDER", "PREPAID_BY_FRIEND", "PAID_BY_ME_DEBT", "CLOSED"]] = Field(
        None, description="Обновленный статус расчетов"
    )

class CreateTaskCmd(BaseModel):
    """Команда создания задачи или выезда в локацию"""
    title: str = Field(..., description="Суть задачи, например: Сделать домофон")
    project_id: Optional[int] = Field(None, description="ID проекта")
    location_id: Optional[int] = Field(None, description="ID локации")
    location_name: Optional[str] = Field(None, description="Название точки: Дом, Офис 1, Офис 2")
    hard_due_date: Optional[date] = Field(None, description="Дата жесткой привязки к дню")
    duration_minutes: int = Field(60, description="Оценка времени выполнения в минутах")
    priority: int = Field(3, description="Приоритет: 1 (критический) .. 4 (фоновый)")
    depends_on_supply_id: Optional[int] = Field(None, description="ID детали/шкафа, которую нужно дождаться")
    scheduled_start: Optional[datetime] = Field(None, description="Точное время начала в календаре")
    notes: Optional[str] = Field(None, description="Дополнительные заметки к задаче")

class UpdateTaskStatusCmd(BaseModel):
    """Команда смены статуса задачи (TODO / DONE / BLOCKED / SCHEDULED)"""
    task_id: int = Field(..., description="ID задачи")
    status: Literal["BLOCKED", "TODO", "SCHEDULED", "DONE"] = Field(..., description="Новый статус задачи")

class CreateProjectCmd(BaseModel):
    """Команда создания нового проекта"""
    title: str = Field(..., description="Название проекта")
    description: Optional[str] = Field("", description="Описание, цели, документация")
    project_type: Literal["IT_SYSTEM", "NEW_IDEA", "DIY_BUILD", "AUTO", "LOAN", "HOUSEHOLD"] = Field(
        ..., description="Тип проекта"
    )
    stage: Literal["NOT_STARTED", "ACTIVE", "MAINTENANCE", "ON_HOLD", "COMPLETED"] = Field(
        "ACTIVE", description="Стадия проекта"
    )
    priority: int = Field(3, description="Приоритет 1..4")
    color_hex: str = Field("#3b82f6", description="Цвет карточки и слотов в календаре (HEX)")
    weekly_quota_minutes: int = Field(0, description="Обязательная недельная квота времени в минутах (например, 120)")
    preferred_slot_minutes: int = Field(60, description="Минимальный размер слота автопланировщика в минутах")
    template_payload: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Специфические поля шаблона")

class UpdateProjectCmd(BaseModel):
    """Команда редактирования параметров и шаблона проекта"""
    project_id: int = Field(..., description="ID проекта")
    title: Optional[str] = Field(None, description="Новое название")
    description: Optional[str] = Field(None, description="Новое описание")
    stage: Optional[Literal["NOT_STARTED", "ACTIVE", "MAINTENANCE", "ON_HOLD", "COMPLETED"]] = None
    priority: Optional[int] = None
    color_hex: Optional[str] = None
    weekly_quota_minutes: Optional[int] = None
    preferred_slot_minutes: Optional[int] = None
    template_payload: Optional[Dict[str, Any]] = None

class AddFinanceRecordCmd(BaseModel):
    """Команда внесения планового расхода, дохода или дня рождения"""
    title: str = Field(..., description="Описание операции: Оплата договора, Платеж по кредиту, ДР друга")
    amount: float = Field(..., description="Сумма в рублях")
    record_type: Literal["INCOME_EXPECTED", "EXPENSE_MANDATORY", "EXPENSE_BIRTHDAY", "EXPENSE_WISHLIST"] = Field(
        ..., description="Тип финансовой записи"
    )
    planned_date: date = Field(..., description="Дата наступления события (ГГГГ-ММ-ДД)")
    project_id: Optional[int] = Field(None, description="ID проекта, если относится к проекту")
    supply_item_id: Optional[int] = Field(None, description="ID закупки, если запись привязана к детали")
    is_annual_or_monthly: Literal["NONE", "MONTHLY", "YEARLY"] = Field("NONE", description="Периодичность")

class ExecuteFinanceRecordCmd(BaseModel):
    """Команда подтверждения фактического проведения платежа/поступления"""
    record_id: int = Field(..., description="ID финансовой записи")

class UpdateWalletCmd(BaseModel):
    """Команда обновления фактического остатка кошелька и порога безопасности"""
    current_balance: float = Field(..., description="Текущий баланс средств")
    safety_threshold: Optional[float] = Field(50000.0, description="Неснижаемый порог финансовой безопасности")

class UpdateCarMileageCmd(BaseModel):
    """Команда обновления показаний одометра автомобиля"""
    project_id: int = Field(..., description="ID проекта автомобиля (тип AUTO)")
    current_mileage: int = Field(..., description="Текущий пробег в километрах")

class PayLoanInstallmentCmd(BaseModel):
    """Команда проведения очередного платежа по кредиту со снижением остатка долга"""
    project_id: int = Field(..., description="ID проекта кредита (тип LOAN)")
    amount_paid: float = Field(..., description="Внесенная сумма")

class AutoScheduleWeekCmd(BaseModel):
    """Команда запуска алгоритма автопланирования квот и задач на неделю"""
    start_date: Optional[date] = Field(None, description="Начальная дата недели (по умолчанию текущий понедельник)")
