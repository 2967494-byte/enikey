from datetime import date, datetime, timedelta
from typing import Dict, Any, Union, Optional
from sqlalchemy.orm import Session

from app.core.models import (
    Project, ProjectType, ProjectStage,
    SupplyItem, SupplyStatus, PaymentSettlement,
    Task, TaskStatus,
    FinanceRecord, FinanceRecordType, FinanceStatus, RecurrenceType,
    WalletState, Location
)
from app.core.commands import (
    AddSupplyItemCmd, UpdateSupplyStatusCmd,
    CreateTaskCmd, UpdateTaskCmd, UpdateTaskStatusCmd, DeleteTaskCmd,
    CreateProjectCmd, UpdateProjectCmd, DeleteProjectCmd,
    AddFinanceRecordCmd, ExecuteFinanceRecordCmd, DeleteFinanceRecordCmd,
    UpdateWalletCmd, UpdateCarMileageCmd, PayLoanInstallmentCmd,
    AutoScheduleWeekCmd
)
from app.core.scheduler_engine import SchedulerEngine

class CommandExecutor:
    """
    Единый шлюз выполнения команд (Command Bus).
    Все операции мутации данных проходят через этот класс.
    """

    @classmethod
    def execute(cls, cmd: Any, db: Session) -> Dict[str, Any]:
        if isinstance(cmd, AddSupplyItemCmd):
            return cls._handle_add_supply(cmd, db)
        elif isinstance(cmd, UpdateSupplyStatusCmd):
            return cls._handle_update_supply_status(cmd, db)
        elif isinstance(cmd, CreateTaskCmd):
            return cls._handle_create_task(cmd, db)
        elif isinstance(cmd, UpdateTaskCmd):
            return cls._handle_update_task(cmd, db)
        elif isinstance(cmd, UpdateTaskStatusCmd):
            return cls._handle_update_task_status(cmd, db)
        elif isinstance(cmd, DeleteTaskCmd):
            return cls._handle_delete_task(cmd, db)
        elif isinstance(cmd, CreateProjectCmd):
            return cls._handle_create_project(cmd, db)
        elif isinstance(cmd, UpdateProjectCmd):
            return cls._handle_update_project(cmd, db)
        elif isinstance(cmd, DeleteProjectCmd):
            return cls._handle_delete_project(cmd, db)
        elif isinstance(cmd, AddFinanceRecordCmd):
            return cls._handle_add_finance_record(cmd, db)
        elif isinstance(cmd, ExecuteFinanceRecordCmd):
            return cls._handle_execute_finance_record(cmd, db)
        elif isinstance(cmd, DeleteFinanceRecordCmd):
            return cls._handle_delete_finance_record(cmd, db)
        elif isinstance(cmd, UpdateWalletCmd):
            return cls._handle_update_wallet(cmd, db)
        elif isinstance(cmd, UpdateCarMileageCmd):
            return cls._handle_update_car_mileage(cmd, db)
        elif isinstance(cmd, PayLoanInstallmentCmd):
            return cls._handle_pay_loan(cmd, db)
        elif isinstance(cmd, AutoScheduleWeekCmd):
            return SchedulerEngine.run(db, cmd.start_date)
        else:
            raise ValueError(f"Неизвестная команда: {type(cmd)}")

    # -------------------------------------------------------------
    # 1. Supply Items & Logistics Pipeline
    # -------------------------------------------------------------
    @classmethod
    def _handle_add_supply(cls, cmd: AddSupplyItemCmd, db: Session) -> Dict[str, Any]:
        item = SupplyItem(
            project_id=cmd.project_id,
            item_name=cmd.item_name,
            status=SupplyStatus(cmd.status),
            vendor=cmd.vendor,
            order_link_or_track=cmd.order_link_or_track,
            expected_date=cmd.expected_date,
            cost=cmd.cost,
            target_person=cmd.target_person,
            payment_settlement=PaymentSettlement(cmd.payment_settlement)
        )
        db.add(item)
        db.flush()

        auto_tasks_created = []

        # Trigger 1: Order for friend (WAIT_FOR_ORDER)
        if cmd.target_person and cmd.payment_settlement == "WAIT_FOR_ORDER":
            task = Task(
                project_id=cmd.project_id,
                title=f"Заказать {cmd.item_name} для {cmd.target_person}",
                status=TaskStatus.TODO,
                priority=2,
                duration_minutes=30,
                notes=f"Поручение: заказать в {cmd.vendor or 'магазине'}"
            )
            db.add(task)
            auto_tasks_created.append("task_order_for_friend")

        # Trigger 2: Arrived at pickup
        if cmd.status == "ARRIVED_AT_PICKUP":
            task = Task(
                project_id=cmd.project_id,
                title=f"Забрать заказ: {cmd.item_name} ({cmd.vendor or 'ПВЗ'})",
                status=TaskStatus.TODO,
                priority=2,
                duration_minutes=45,
                depends_on_supply_id=item.id,
                notes=f"Трек/ссылка: {cmd.order_link_or_track or 'нет'}"
            )
            db.add(task)
            auto_tasks_created.append("task_pickup_order")

        # Trigger 3: Mandatory or Wishlist expense if cost specified
        if cmd.cost > 0 and cmd.payment_settlement == "SELF":
            rec_type = FinanceRecordType.EXPENSE_WISHLIST if cmd.status == "NEED_TO_BUY" else FinanceRecordType.EXPENSE_MANDATORY
            rec = FinanceRecord(
                project_id=cmd.project_id,
                supply_item_id=item.id,
                title=f"Покупка: {cmd.item_name}",
                record_type=rec_type,
                amount=cmd.cost,
                planned_date=cmd.expected_date or date.today(),
                status=FinanceStatus.PLANNED
            )
            db.add(rec)

        db.commit()
        db.refresh(item)
        return {
            "success": True,
            "supply_id": item.id,
            "auto_tasks_created": auto_tasks_created
        }

    @classmethod
    def _handle_update_supply_status(cls, cmd: UpdateSupplyStatusCmd, db: Session) -> Dict[str, Any]:
        item = db.query(SupplyItem).filter(SupplyItem.id == cmd.supply_id).first()
        if not item:
            raise ValueError(f"Позиция комплектации ID={cmd.supply_id} не найдена")

        old_status = item.status
        new_status = SupplyStatus(cmd.status)
        item.status = new_status

        if cmd.payment_settlement:
            item.payment_settlement = PaymentSettlement(cmd.payment_settlement)

        auto_actions = []

        # Transition to ARRIVED_AT_PICKUP
        if new_status == SupplyStatus.ARRIVED_AT_PICKUP and old_status != SupplyStatus.ARRIVED_AT_PICKUP:
            pickup_task = Task(
                project_id=item.project_id,
                title=f"Забрать заказ: {item.item_name} ({item.vendor or 'ПВЗ'})",
                status=TaskStatus.TODO,
                priority=2,
                duration_minutes=45,
                depends_on_supply_id=item.id,
                notes=f"Трек/ссылка: {item.order_link_or_track or 'нет'}"
            )
            db.add(pickup_task)
            auto_actions.append("created_pickup_task")

        # Transition to IN_STOCK (Получено на руки)
        if new_status == SupplyStatus.IN_STOCK and old_status != SupplyStatus.IN_STOCK:
            # 1. If for friend -> create handover task
            if item.target_person:
                debt_text = f" (Забрать деньги: {float(item.cost):,.0f} ₽)" if item.payment_settlement == PaymentSettlement.PAID_BY_ME_DEBT else ""
                handover_task = Task(
                    project_id=item.project_id,
                    title=f"Передать {item.item_name} → {item.target_person}{debt_text}",
                    status=TaskStatus.TODO,
                    priority=2,
                    duration_minutes=45,
                    depends_on_supply_id=item.id
                )
                db.add(handover_task)
                auto_actions.append("created_handover_task")
            else:
                # 2. If for own project -> unblock dependent tasks
                blocked_tasks = db.query(Task).filter(
                    Task.depends_on_supply_id == item.id,
                    Task.status == TaskStatus.BLOCKED
                ).all()

                for bt in blocked_tasks:
                    bt.status = TaskStatus.TODO
                    auto_actions.append(f"unblocked_task_{bt.id}")

                # Check DIY_BUILD assembly tasks if all project supplies are in stock
                if item.project_id:
                    project = db.query(Project).filter(Project.id == item.project_id).first()
                    if project and project.project_type == ProjectType.DIY_BUILD:
                        pending_supplies = db.query(SupplyItem).filter(
                            SupplyItem.project_id == project.id,
                            SupplyItem.status.in_([SupplyStatus.NEED_TO_BUY, SupplyStatus.ORDERED_IN_TRANSIT, SupplyStatus.ARRIVED_AT_PICKUP])
                        ).count()
                        if pending_supplies == 0:
                            # All supplies are in stock -> unblock project assembly tasks
                            diy_tasks = db.query(Task).filter(
                                Task.project_id == project.id,
                                Task.status == TaskStatus.BLOCKED
                            ).all()
                            for dt in diy_tasks:
                                dt.status = TaskStatus.TODO
                                auto_actions.append(f"unblocked_diy_task_{dt.id}")

        db.commit()
        return {"success": True, "supply_id": item.id, "auto_actions": auto_actions}

    # -------------------------------------------------------------
    # 2. Tasks
    # -------------------------------------------------------------
    @classmethod
    def _handle_create_task(cls, cmd: CreateTaskCmd, db: Session) -> Dict[str, Any]:
        location_id = cmd.location_id
        if not location_id and cmd.location_name:
            loc = db.query(Location).filter(Location.name == cmd.location_name.strip()).first()
            if not loc:
                loc = Location(name=cmd.location_name.strip(), color="#6366f1")
                db.add(loc)
                db.flush()
            location_id = loc.id

        # Determine initial status: if depends on supply that is not yet IN_STOCK, set BLOCKED
        initial_status = TaskStatus.TODO
        if cmd.depends_on_supply_id:
            supply = db.query(SupplyItem).filter(SupplyItem.id == cmd.depends_on_supply_id).first()
            if supply and supply.status not in [SupplyStatus.IN_STOCK, SupplyStatus.USED_OR_HANDED_OVER]:
                initial_status = TaskStatus.BLOCKED

        # Also check parent task dependency: if parent task not DONE, set BLOCKED
        if cmd.depends_on_task_id:
            parent = db.query(Task).filter(Task.id == cmd.depends_on_task_id).first()
            if parent and parent.status != TaskStatus.DONE:
                initial_status = TaskStatus.BLOCKED

        if cmd.scheduled_start and initial_status != TaskStatus.BLOCKED:
            initial_status = TaskStatus.SCHEDULED

        scheduled_end = None
        if cmd.scheduled_start:
            scheduled_end = cmd.scheduled_start + timedelta(minutes=cmd.duration_minutes)

        task = Task(
            project_id=cmd.project_id,
            location_id=location_id,
            title=cmd.title,
            status=initial_status,
            priority=cmd.priority,
            duration_minutes=cmd.duration_minutes,
            hard_due_date=cmd.hard_due_date,
            scheduled_start=cmd.scheduled_start,
            scheduled_end=scheduled_end,
            is_auto_placed=False,
            is_urgent=bool(getattr(cmd, "is_urgent", False)),
            depends_on_supply_id=cmd.depends_on_supply_id,
            depends_on_task_id=cmd.depends_on_task_id,
            notes=cmd.notes or ""
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return {"success": True, "task_id": task.id, "status": task.status.value}

    @classmethod
    def _handle_update_task(cls, cmd: UpdateTaskCmd, db: Session) -> Dict[str, Any]:
        task = db.query(Task).filter(Task.id == cmd.task_id).first()
        if not task:
            raise ValueError(f"Задача ID={cmd.task_id} не найдена")
        if cmd.title is not None:
            task.title = cmd.title
        if cmd.duration_minutes is not None:
            task.duration_minutes = cmd.duration_minutes
        if hasattr(cmd, "hard_due_date"):
            task.hard_due_date = cmd.hard_due_date
        if cmd.priority is not None:
            task.priority = cmd.priority
        if cmd.is_urgent is not None:
            task.is_urgent = cmd.is_urgent
        if cmd.notes is not None:
            task.notes = cmd.notes
        db.commit()
        db.refresh(task)
        return {"success": True, "task_id": task.id, "project_id": task.project_id}

    @classmethod
    def _handle_update_task_status(cls, cmd: UpdateTaskStatusCmd, db: Session) -> Dict[str, Any]:
        task = db.query(Task).filter(Task.id == cmd.task_id).first()
        if not task:
            raise ValueError(f"Задача ID={cmd.task_id} не найдена")

        old_status = task.status
        new_status = TaskStatus(cmd.status)
        task.status = new_status

        auto_unblocked = []
        auto_blocked = []

        if new_status == TaskStatus.DONE and old_status != TaskStatus.DONE:
            # Unblock any tasks that depend on this task
            dependent = db.query(Task).filter(
                Task.depends_on_task_id == task.id,
                Task.status == TaskStatus.BLOCKED
            ).all()
            for dep in dependent:
                # Ensure supply is also satisfied
                supply_ok = True
                if dep.depends_on_supply_id:
                    s = db.query(SupplyItem).filter(SupplyItem.id == dep.depends_on_supply_id).first()
                    if s and s.status not in [SupplyStatus.IN_STOCK, SupplyStatus.USED_OR_HANDED_OVER]:
                        supply_ok = False
                if supply_ok:
                    dep.status = TaskStatus.TODO
                    auto_unblocked.append(dep.id)

        elif old_status == TaskStatus.DONE and new_status != TaskStatus.DONE:
            # Re-block tasks that depend on this task
            dependent = db.query(Task).filter(
                Task.depends_on_task_id == task.id,
                Task.status.in_([TaskStatus.TODO, TaskStatus.SCHEDULED])
            ).all()
            for dep in dependent:
                dep.status = TaskStatus.BLOCKED
                auto_blocked.append(dep.id)

        db.commit()
        return {
            "success": True,
            "task_id": task.id,
            "new_status": new_status.value,
            "auto_unblocked": auto_unblocked,
            "auto_blocked": auto_blocked
        }

    @classmethod
    def _handle_delete_task(cls, cmd: DeleteTaskCmd, db: Session) -> Dict[str, Any]:
        task = db.query(Task).filter(Task.id == cmd.task_id).first()
        if not task:
            raise ValueError(f"Задача ID={cmd.task_id} не найдена")
        project_id = task.project_id
        db.delete(task)
        db.commit()
        return {"success": True, "deleted_task_id": cmd.task_id, "project_id": project_id}

    @classmethod
    def _handle_delete_project(cls, cmd: DeleteProjectCmd, db: Session) -> Dict[str, Any]:
        proj = db.query(Project).filter(Project.id == cmd.project_id).first()
        if not proj:
            raise ValueError(f"Проект ID={cmd.project_id} не найден")
        db.delete(proj)
        db.commit()
        return {"success": True, "deleted_project_id": cmd.project_id}

    # -------------------------------------------------------------
    # 3. Projects
    # -------------------------------------------------------------
    @classmethod
    def _handle_create_project(cls, cmd: CreateProjectCmd, db: Session) -> Dict[str, Any]:
        proj = Project(
            title=cmd.title,
            description=cmd.description or "",
            project_type=ProjectType(cmd.project_type),
            stage=ProjectStage(cmd.stage),
            priority=cmd.priority,
            color_hex=cmd.color_hex,
            weekly_quota_minutes=cmd.weekly_quota_minutes,
            preferred_slot_minutes=cmd.preferred_slot_minutes,
            template_payload=cmd.template_payload or {}
        )
        db.add(proj)
        db.flush()

        # Handle initial template triggers
        cls._process_project_triggers(proj, db)

        db.commit()
        db.refresh(proj)
        return {"success": True, "project_id": proj.id}

    @classmethod
    def _handle_update_project(cls, cmd: UpdateProjectCmd, db: Session) -> Dict[str, Any]:
        proj = db.query(Project).filter(Project.id == cmd.project_id).first()
        if not proj:
            raise ValueError(f"Проект ID={cmd.project_id} не найден")

        if cmd.title is not None:
            proj.title = cmd.title
        if cmd.description is not None:
            proj.description = cmd.description
        if cmd.stage is not None:
            proj.stage = ProjectStage(cmd.stage)
        if cmd.priority is not None:
            proj.priority = cmd.priority
        if cmd.color_hex is not None:
            proj.color_hex = cmd.color_hex
        if cmd.weekly_quota_minutes is not None:
            proj.weekly_quota_minutes = cmd.weekly_quota_minutes
        if cmd.preferred_slot_minutes is not None:
            proj.preferred_slot_minutes = cmd.preferred_slot_minutes
        if cmd.template_payload is not None:
            proj.template_payload = cmd.template_payload

        cls._process_project_triggers(proj, db)

        db.commit()
        return {"success": True, "project_id": proj.id}

    @classmethod
    def _process_project_triggers(cls, proj: Project, db: Session):
        """Проверка автоматических триггеров для шаблонов проектов"""
        payload = proj.template_payload or {}
        today = date.today()

        # 1. IT_SYSTEM: SSL & Domain expiration tasks, server expenses
        if proj.project_type == ProjectType.IT_SYSTEM:
            ssl_exp = payload.get("ssl_expires_at")
            if ssl_exp:
                try:
                    ssl_date = datetime.strptime(str(ssl_exp).split("T")[0], "%Y-%m-%d").date()
                    days_left = (ssl_date - today).days
                    if days_left <= 14:
                        existing_task = db.query(Task).filter(
                            Task.project_id == proj.id,
                            Task.title.like("%Продлить SSL%"),
                            Task.status != TaskStatus.DONE
                        ).first()
                        if not existing_task:
                            db.add(Task(
                                project_id=proj.id,
                                title=f"Продлить SSL сертификат ({proj.title})",
                                status=TaskStatus.TODO,
                                priority=1,
                                hard_due_date=ssl_date,
                                duration_minutes=30,
                                notes=f"SSL истекает через {days_left} дн."
                            ))
                except Exception:
                    pass

            # Servers monthly cost in finance
            servers = payload.get("servers", [])
            for s in servers:
                cost = float(s.get("monthly_cost", 0))
                pay_day = int(s.get("pay_day", 1))
                if cost > 0:
                    try:
                        planned = date(today.year, today.month, min(28, pay_day))
                        if planned < today:
                            planned = (planned.replace(day=1) + timedelta(days=32)).replace(day=min(28, pay_day))
                        existing_rec = db.query(FinanceRecord).filter(
                            FinanceRecord.project_id == proj.id,
                            FinanceRecord.title == f"Сервер {s.get('ip', '')} ({s.get('provider', '')})",
                            FinanceRecord.planned_date == planned
                        ).first()
                        if not existing_rec:
                            db.add(FinanceRecord(
                                project_id=proj.id,
                                title=f"Сервер {s.get('ip', '')} ({s.get('provider', '')})",
                                record_type=FinanceRecordType.EXPENSE_MANDATORY,
                                amount=cost,
                                planned_date=planned,
                                is_annual_or_monthly=RecurrenceType.MONTHLY
                            ))
                        else:
                            existing_rec.amount = cost
                    except Exception:
                        pass

        # 2. AUTO: ТО remaining km
        elif proj.project_type == ProjectType.AUTO:
            current_mileage = payload.get("current_mileage")
            last_to_mileage = payload.get("last_to_mileage", 0)
            to_interval = payload.get("to_interval_km", 10000)
            if current_mileage is not None:
                remaining_km = (int(last_to_mileage) + int(to_interval)) - int(current_mileage)
                if remaining_km <= 1000:
                    existing_task = db.query(Task).filter(
                        Task.project_id == proj.id,
                        Task.title.like("%Пройти ТО%"),
                        Task.status != TaskStatus.DONE
                    ).first()
                    if not existing_task:
                        db.add(Task(
                            project_id=proj.id,
                            title=f"Пройти ТО: {payload.get('car_model', proj.title)} (осталось {remaining_km} км)",
                            status=TaskStatus.TODO,
                            priority=1,
                            duration_minutes=120,
                            notes=f"Текущий пробег: {current_mileage} км. До ТО: {remaining_km} км."
                        ))

        # 3. LOAN: monthly payment reserve
        elif proj.project_type == ProjectType.LOAN:
            monthly_payment = float(payload.get("monthly_payment", 0))
            payment_day = int(payload.get("payment_day", 15))
            if monthly_payment > 0:
                planned = date(today.year, today.month, min(28, payment_day))
                if planned < today:
                    planned = (planned.replace(day=1) + timedelta(days=32)).replace(day=min(28, payment_day))
                existing_rec = db.query(FinanceRecord).filter(
                    FinanceRecord.project_id == proj.id,
                    FinanceRecord.title.like("%Платеж по кредиту%"),
                    FinanceRecord.planned_date == planned
                ).first()
                if not existing_rec:
                    db.add(FinanceRecord(
                        project_id=proj.id,
                        title=f"Платеж по кредиту ({payload.get('bank_name', proj.title)})",
                        record_type=FinanceRecordType.EXPENSE_MANDATORY,
                        amount=monthly_payment,
                        planned_date=planned,
                        is_annual_or_monthly=RecurrenceType.MONTHLY
                    ))

    # -------------------------------------------------------------
    # 4. Mileage & Loans Specialized Commands
    # -------------------------------------------------------------
    @classmethod
    def _handle_update_car_mileage(cls, cmd: UpdateCarMileageCmd, db: Session) -> Dict[str, Any]:
        proj = db.query(Project).filter(Project.id == cmd.project_id).first()
        if not proj or proj.project_type != ProjectType.AUTO:
            raise ValueError(f"Проект ID={cmd.project_id} не найден или не является типом AUTO")

        payload = dict(proj.template_payload or {})
        payload["current_mileage"] = cmd.current_mileage
        proj.template_payload = payload

        cls._process_project_triggers(proj, db)
        db.commit()

        last_to = int(payload.get("last_to_mileage", 0))
        interval = int(payload.get("to_interval_km", 10000))
        remaining = (last_to + interval) - cmd.current_mileage

        return {
            "success": True,
            "project_id": proj.id,
            "current_mileage": cmd.current_mileage,
            "remaining_km_to_to": remaining
        }

    @classmethod
    def _handle_pay_loan(cls, cmd: PayLoanInstallmentCmd, db: Session) -> Dict[str, Any]:
        proj = db.query(Project).filter(Project.id == cmd.project_id).first()
        if not proj or proj.project_type != ProjectType.LOAN:
            raise ValueError(f"Проект ID={cmd.project_id} не найден или не является типом LOAN")

        payload = dict(proj.template_payload or {})
        old_balance = float(payload.get("remaining_balance", 0.0))
        new_balance = max(0.0, old_balance - cmd.amount_paid)
        payload["remaining_balance"] = new_balance
        if "remaining_months" in payload and payload["remaining_months"]:
            try:
                months = int(payload["remaining_months"])
                if months > 0:
                    payload["remaining_months"] = months - 1
                    if "monthly_payment" in payload and payload["monthly_payment"]:
                        payload["calculated_remaining_sum"] = (months - 1) * float(payload["monthly_payment"])
            except Exception:
                pass
        proj.template_payload = payload

        # Record executed expense
        rec = FinanceRecord(
            project_id=proj.id,
            title=f"Оплата платежа по кредиту: {proj.title}",
            record_type=FinanceRecordType.EXPENSE_MANDATORY,
            amount=cmd.amount_paid,
            planned_date=date.today(),
            status=FinanceStatus.EXECUTED
        )
        db.add(rec)

        # Deduct from wallet
        wallet = db.query(WalletState).first()
        if wallet:
            wallet.current_balance = float(wallet.current_balance) - cmd.amount_paid

        db.commit()
        return {
            "success": True,
            "project_id": proj.id,
            "paid": cmd.amount_paid,
            "remaining_balance": new_balance
        }

    # -------------------------------------------------------------
    # 5. Finances
    # -------------------------------------------------------------
    @classmethod
    def _handle_add_finance_record(cls, cmd: AddFinanceRecordCmd, db: Session) -> Dict[str, Any]:
        rec = FinanceRecord(
            project_id=cmd.project_id,
            supply_item_id=cmd.supply_item_id,
            title=cmd.title,
            record_type=FinanceRecordType(cmd.record_type),
            amount=cmd.amount,
            planned_date=cmd.planned_date,
            is_annual_or_monthly=RecurrenceType(cmd.is_annual_or_monthly),
            status=FinanceStatus.PLANNED
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        return {"success": True, "record_id": rec.id}

    @classmethod
    def _handle_execute_finance_record(cls, cmd: ExecuteFinanceRecordCmd, db: Session) -> Dict[str, Any]:
        rec = db.query(FinanceRecord).filter(FinanceRecord.id == cmd.record_id).first()
        if not rec:
            raise ValueError(f"Финансовая запись ID={cmd.record_id} не найдена")

        rec.status = FinanceStatus.EXECUTED

        wallet = db.query(WalletState).first()
        if not wallet:
            wallet = WalletState(current_balance=0.0, safety_threshold=50000.0)
            db.add(wallet)
            db.flush()

        amount = float(rec.amount)
        if rec.record_type == FinanceRecordType.INCOME_EXPECTED:
            wallet.current_balance = float(wallet.current_balance) + amount
        else:
            wallet.current_balance = float(wallet.current_balance) - amount

        # Auto-spawn next occurrence for recurring records (incomes or expenses)
        if rec.is_annual_or_monthly == RecurrenceType.MONTHLY:
            try:
                next_date = (rec.planned_date.replace(day=1) + timedelta(days=32)).replace(day=min(28, rec.planned_date.day))
                db.add(FinanceRecord(
                    project_id=rec.project_id,
                    title=rec.title,
                    record_type=rec.record_type,
                    amount=rec.amount,
                    planned_date=next_date,
                    is_annual_or_monthly=rec.is_annual_or_monthly,
                    status=FinanceStatus.PLANNED
                ))
            except Exception:
                pass
        elif rec.is_annual_or_monthly == RecurrenceType.YEARLY:
            try:
                next_date = rec.planned_date.replace(year=rec.planned_date.year + 1)
                db.add(FinanceRecord(
                    project_id=rec.project_id,
                    title=rec.title,
                    record_type=rec.record_type,
                    amount=rec.amount,
                    planned_date=next_date,
                    is_annual_or_monthly=rec.is_annual_or_monthly,
                    status=FinanceStatus.PLANNED
                ))
            except Exception:
                pass

        db.commit()
        return {
            "success": True,
            "record_id": rec.id,
            "new_wallet_balance": float(wallet.current_balance)
        }

    @classmethod
    def _handle_delete_finance_record(cls, cmd: DeleteFinanceRecordCmd, db: Session) -> Dict[str, Any]:
        rec = db.query(FinanceRecord).filter(FinanceRecord.id == cmd.record_id).first()
        if not rec:
            raise ValueError(f"Финансовая запись ID={cmd.record_id} не найдена")
        db.delete(rec)
        db.commit()
        return {"success": True, "record_id": cmd.record_id}


    @classmethod
    def _handle_update_wallet(cls, cmd: UpdateWalletCmd, db: Session) -> Dict[str, Any]:
        wallet = db.query(WalletState).first()
        if not wallet:
            wallet = WalletState(current_balance=cmd.current_balance, safety_threshold=cmd.safety_threshold or 50000.0)
            db.add(wallet)
        else:
            wallet.current_balance = cmd.current_balance
            if cmd.safety_threshold is not None:
                wallet.safety_threshold = cmd.safety_threshold

        db.commit()
        return {
            "success": True,
            "current_balance": float(wallet.current_balance),
            "safety_threshold": float(wallet.safety_threshold)
        }
