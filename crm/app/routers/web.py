from datetime import date, datetime, timedelta, time
from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
import os

from app.core.config import settings
from app.core.database import get_db
from app.core.models import (
    Project, ProjectType, ProjectStage,
    SupplyItem, SupplyStatus, PaymentSettlement,
    Task, TaskStatus,
    FinanceRecord, FinanceRecordType, FinanceStatus, RecurrenceType,
    WalletState, Location
)
from app.core.executor import CommandExecutor
from app.core.budget_guard import BudgetGuard
from app.core.commands import (
    AddSupplyItemCmd, UpdateSupplyStatusCmd,
    CreateTaskCmd, UpdateTaskStatusCmd, DeleteTaskCmd,
    CreateProjectCmd, UpdateProjectCmd, DeleteProjectCmd,
    AddFinanceRecordCmd, ExecuteFinanceRecordCmd, DeleteFinanceRecordCmd,
    UpdateWalletCmd, UpdateCarMileageCmd, PayLoanInstallmentCmd,
    AutoScheduleWeekCmd
)

templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_dir)

# Helper function to expose url_prefix in all templates
def template_context(request: Request, extra: dict = None) -> dict:
    ctx = {
        "request": request,
        "prefix": settings.APP_PREFIX,
        "now": datetime.now(),
        "today": date.today()
    }
    if extra:
        ctx.update(extra)
    return ctx

router = APIRouter(tags=["Web Pages"])

# -------------------------------------------------------------
# 1. Main Dashboard & Master Calendar (GET /)
# -------------------------------------------------------------
@router.get("/", response_class=HTMLResponse)
def index_page(request: Request, loc: Optional[str] = None, db: Session = Depends(get_db)):
    radar = BudgetGuard.get_financial_radar(db)
    
    # Packages to pick up
    pickup_count = db.query(SupplyItem).filter(SupplyItem.status == SupplyStatus.ARRIVED_AT_PICKUP).count()

    # Today's tasks
    today = date.today()
    tasks_query = db.query(Task).filter(
        (Task.hard_due_date == today) | 
        (Task.scheduled_start >= datetime.combine(today, time(0, 0))) & (Task.scheduled_start <= datetime.combine(today, time(23, 59))) |
        ((Task.status == TaskStatus.TODO) & (Task.priority <= 2))
    )

    if loc and loc != "all":
        if loc == "pickup":
            tasks_query = tasks_query.filter(Task.depends_on_supply_id != None)
        else:
            tasks_query = tasks_query.join(Location, isouter=True).filter(Location.name == loc)

    today_tasks = tasks_query.order_by(Task.status.asc(), Task.priority.asc(), Task.scheduled_start.asc()).all()

    locations = db.query(Location).all()
    projects = db.query(Project).all()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context=template_context(request, {
            "radar": radar,
            "pickup_count": pickup_count,
            "today_tasks": today_tasks,
            "selected_loc": loc or "all",
            "locations": locations,
            "projects": projects
        })
    )

# -------------------------------------------------------------
# 2. Projects Catalog (GET /projects)
# -------------------------------------------------------------
@router.get("/projects", response_class=HTMLResponse)
def projects_page(request: Request, db: Session = Depends(get_db)):
    all_projects = db.query(Project).order_by(Project.priority.asc(), Project.title.asc()).all()
    
    # Group by category
    categories = {
        "IT_SYSTEM": {"title": "💻 IT и Цифровые Системы", "items": []},
        "NEW_IDEA": {"title": "💡 Новые Идеи и Стартапы", "items": []},
        "DIY_BUILD": {"title": "🛠️ Сборка и Оборудование (DIY)", "items": []},
        "AUTO_LOAN": {"title": "🚗 Автомобиль и Кредиты", "items": []},
        "HOUSEHOLD": {"title": "🏡 Быт, Офисы и Поручения", "items": []}
    }

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    # Enrich projects with quota progress
    for p in all_projects:
        # Calculate weekly quota done
        week_tasks = db.query(Task).filter(
            Task.project_id == p.id,
            Task.scheduled_start >= datetime.combine(week_start, time(0, 0)),
            Task.scheduled_start <= datetime.combine(week_end, time(23, 59)),
            Task.status == TaskStatus.DONE
        ).all()
        done_mins = sum(t.duration_minutes for t in week_tasks)
        p.quota_done_hours = round(done_mins / 60, 1)
        p.quota_total_hours = round(p.weekly_quota_minutes / 60, 1)

        # Alerts
        p.alert_badge = None
        if p.project_type == ProjectType.IT_SYSTEM:
            ssl_exp = (p.template_payload or {}).get("ssl_expires_at")
            if ssl_exp:
                try:
                    ssl_d = datetime.strptime(str(ssl_exp).split("T")[0], "%Y-%m-%d").date()
                    days = (ssl_d - today).days
                    if days <= 14:
                        p.alert_badge = f"SSL: {days} дн."
                except Exception:
                    pass
        elif p.project_type == ProjectType.AUTO:
            payload = p.template_payload or {}
            c_mileage = payload.get("current_mileage")
            if c_mileage is not None:
                rem = (int(payload.get("last_to_mileage", 0)) + int(payload.get("to_interval_km", 10000))) - int(c_mileage)
                if rem <= 1000:
                    p.alert_badge = f"ТО через {rem} км!"

        # Assign to categories
        if p.project_type == ProjectType.IT_SYSTEM:
            categories["IT_SYSTEM"]["items"].append(p)
        elif p.project_type == ProjectType.NEW_IDEA:
            categories["NEW_IDEA"]["items"].append(p)
        elif p.project_type == ProjectType.DIY_BUILD:
            categories["DIY_BUILD"]["items"].append(p)
        elif p.project_type in [ProjectType.AUTO, ProjectType.LOAN]:
            categories["AUTO_LOAN"]["items"].append(p)
        else:
            categories["HOUSEHOLD"]["items"].append(p)

    return templates.TemplateResponse(
        request=request,
        name="projects.html",
        context=template_context(request, {"categories": categories})
    )

# -------------------------------------------------------------
# 3. Individual Project Page (GET /projects/{project_id})
# -------------------------------------------------------------
@router.get("/projects/{project_id}", response_class=HTMLResponse)
def project_detail_page(project_id: int, request: Request, db: Session = Depends(get_db)):
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        return RedirectResponse(f"{settings.APP_PREFIX}/projects")

    # Tasks for this project
    tasks = db.query(Task).filter(Task.project_id == project_id).order_by(Task.status.asc(), Task.priority.asc()).all()

    # Supplies for this project
    supplies = db.query(SupplyItem).filter(SupplyItem.project_id == project_id).order_by(SupplyItem.status.asc()).all()

    # Finances for this project
    finances = db.query(FinanceRecord).filter(FinanceRecord.project_id == project_id).order_by(FinanceRecord.planned_date.desc()).all()

    # Compute DIY progress if DIY_BUILD
    diy_stats = None
    if project.project_type == ProjectType.DIY_BUILD:
        total_s = len(supplies)
        in_stock_s = sum(1 for s in supplies if s.status in [SupplyStatus.IN_STOCK, SupplyStatus.USED_OR_HANDED_OVER])
        in_transit_s = sum(1 for s in supplies if s.status in [SupplyStatus.ORDERED_IN_TRANSIT, SupplyStatus.ARRIVED_AT_PICKUP])
        need_buy_s = sum(1 for s in supplies if s.status == SupplyStatus.NEED_TO_BUY)
        percent = int((in_stock_s / total_s * 100)) if total_s > 0 else 0
        diy_stats = {
            "total": total_s,
            "in_stock": in_stock_s,
            "in_transit": in_transit_s,
            "need_buy": need_buy_s,
            "percent": percent
        }

    # Compute Auto stats if AUTO
    auto_stats = None
    if project.project_type == ProjectType.AUTO:
        payload = project.template_payload or {}
        cur_m = payload.get("current_mileage", 0)
        last_to_m = payload.get("last_to_mileage", 0)
        interval = payload.get("to_interval_km", 10000)
        rem_km = (int(last_to_m) + int(interval)) - int(cur_m)
        auto_stats = {
            "current_mileage": cur_m,
            "last_to_mileage": last_to_m,
            "remaining_km": rem_km,
            "insurance_until": payload.get("insurance_until", "Не указана")
        }

    locations = db.query(Location).all()

    return templates.TemplateResponse(
        request=request,
        name="project_detail.html",
        context=template_context(request, {
            "project": project,
            "tasks": tasks,
            "supplies": supplies,
            "finances": finances,
            "diy_stats": diy_stats,
            "auto_stats": auto_stats,
            "locations": locations
        })
    )

# -------------------------------------------------------------
# 4. Logistics Tracker (GET /logistics)
# -------------------------------------------------------------
@router.get("/logistics", response_class=HTMLResponse)
def logistics_page(request: Request, db: Session = Depends(get_db)):
    all_supplies = db.query(SupplyItem).order_by(SupplyItem.expected_date.asc(), SupplyItem.id.desc()).all()

    # Columns
    cols = {
        "NEED_TO_BUY": [s for s in all_supplies if s.status == SupplyStatus.NEED_TO_BUY],
        "ORDERED_IN_TRANSIT": [s for s in all_supplies if s.status == SupplyStatus.ORDERED_IN_TRANSIT],
        "ARRIVED_AT_PICKUP": [s for s in all_supplies if s.status == SupplyStatus.ARRIVED_AT_PICKUP],
        "IN_STOCK": [s for s in all_supplies if s.status == SupplyStatus.IN_STOCK],
    }

    # Friends orders block
    friend_orders = [s for s in all_supplies if s.target_person]

    projects = db.query(Project).all()

    return templates.TemplateResponse(
        request=request,
        name="logistics.html",
        context=template_context(request, {
            "cols": cols,
            "friend_orders": friend_orders,
            "projects": projects
        })
    )

# -------------------------------------------------------------
# 5. Finance Page (GET /finance)
# -------------------------------------------------------------
@router.get("/finance", response_class=HTMLResponse)
def finance_page(request: Request, db: Session = Depends(get_db)):
    radar = BudgetGuard.get_financial_radar(db)

    # All records
    records = db.query(FinanceRecord).order_by(FinanceRecord.planned_date.asc()).all()

    # Incomes Breakdown:
    # 1. Planned future one-time incomes (status=PLANNED, recurrence=NONE)
    planned_incomes = [
        r for r in records
        if r.record_type == FinanceRecordType.INCOME_EXPECTED
        and r.status == FinanceStatus.PLANNED
        and r.is_annual_or_monthly == RecurrenceType.NONE
    ]

    # 2. Recurring incomes (status=PLANNED, recurrence!=NONE)
    recurring_incomes = [
        r for r in records
        if r.record_type == FinanceRecordType.INCOME_EXPECTED
        and r.is_annual_or_monthly != RecurrenceType.NONE
        and r.status == FinanceStatus.PLANNED
    ]

    # 3. Executed / Past incomes (status=EXECUTED)
    executed_incomes = [
        r for r in records
        if r.record_type == FinanceRecordType.INCOME_EXPECTED
        and r.status == FinanceStatus.EXECUTED
    ]
    executed_incomes.sort(key=lambda x: x.planned_date, reverse=True)

    # Wishlist
    wishlist = [r for r in records if r.record_type == FinanceRecordType.EXPENSE_WISHLIST and r.status == FinanceStatus.PLANNED]

    # Birthdays & Recurring Expenses
    birthdays = [r for r in records if r.record_type == FinanceRecordType.EXPENSE_BIRTHDAY and r.status == FinanceStatus.PLANNED]
    recurring_expenses = [r for r in records if r.record_type != FinanceRecordType.INCOME_EXPECTED and r.is_annual_or_monthly != RecurrenceType.NONE and r.status == FinanceStatus.PLANNED]

    # Past Expenses (history)
    executed_expenses = [
        r for r in records
        if r.record_type != FinanceRecordType.INCOME_EXPECTED
        and r.status == FinanceStatus.EXECUTED
    ]
    executed_expenses.sort(key=lambda x: x.planned_date, reverse=True)

    projects = db.query(Project).all()

    # Sum totals for UI badges
    total_planned_incomes = sum(float(r.amount) for r in planned_incomes)
    total_recurring_incomes = sum(float(r.amount) for r in recurring_incomes)
    total_past_incomes = sum(float(r.amount) for r in executed_incomes)

    return templates.TemplateResponse(
        request=request,
        name="finance.html",
        context=template_context(request, {
            "radar": radar,
            "records": records,
            "planned_incomes": planned_incomes,
            "recurring_incomes": recurring_incomes,
            "executed_incomes": executed_incomes,
            "total_planned_incomes": total_planned_incomes,
            "total_recurring_incomes": total_recurring_incomes,
            "total_past_incomes": total_past_incomes,
            "wishlist": wishlist,
            "birthdays": birthdays,
            "recurring": recurring_expenses,
            "executed_expenses": executed_expenses,
            "projects": projects
        })
    )


# -------------------------------------------------------------
# 6. HTMX Action Endpoints
# -------------------------------------------------------------
@router.post("/actions/toggle-task/{task_id}")
def action_toggle_task(task_id: int, request: Request, db: Session = Depends(get_db)):
    task = db.query(Task).filter(Task.id == task_id).first()
    if task:
        new_status = "DONE" if task.status != TaskStatus.DONE else "TODO"
        CommandExecutor.execute(UpdateTaskStatusCmd(task_id=task_id, status=new_status), db)

    # Return refreshed task row or trigger refresh
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Refresh": "true"})
    return RedirectResponse(f"{settings.APP_PREFIX}/", status_code=303)

@router.post("/actions/quick-task")
def action_quick_task(
    title: str = Form(...),
    project_id: Optional[int] = Form(None),
    location_name: Optional[str] = Form(None),
    hard_due_date: Optional[str] = Form(None),
    duration_minutes: int = Form(60),
    priority: int = Form(3),
    redirect_to: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    due = None
    if hard_due_date:
        try:
            due = datetime.strptime(hard_due_date, "%Y-%m-%d").date()
        except Exception:
            pass

    cmd = CreateTaskCmd(
        title=title,
        project_id=project_id,
        location_name=location_name,
        hard_due_date=due,
        duration_minutes=duration_minutes,
        priority=priority
    )
    CommandExecutor.execute(cmd, db)
    return RedirectResponse(redirect_to or f"{settings.APP_PREFIX}/", status_code=303)

@router.post("/actions/auto-schedule")
def action_auto_schedule(request: Request, db: Session = Depends(get_db)):
    CommandExecutor.execute(AutoScheduleWeekCmd(), db)
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Refresh": "true"})
    return RedirectResponse(f"{settings.APP_PREFIX}/", status_code=303)

@router.post("/actions/add-supply")
def action_add_supply(
    item_name: str = Form(...),
    project_id: Optional[int] = Form(None),
    status: str = Form("NEED_TO_BUY"),
    vendor: Optional[str] = Form(None),
    order_link_or_track: Optional[str] = Form(None),
    expected_date: Optional[str] = Form(None),
    cost: float = Form(0.0),
    target_person: Optional[str] = Form(None),
    payment_settlement: str = Form("SELF"),
    redirect_to: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    exp = None
    if expected_date:
        try:
            exp = datetime.strptime(expected_date, "%Y-%m-%d").date()
        except Exception:
            pass

    cmd = AddSupplyItemCmd(
        item_name=item_name,
        project_id=project_id,
        status=status,
        vendor=vendor,
        order_link_or_track=order_link_or_track,
        expected_date=exp,
        cost=cost,
        target_person=target_person,
        payment_settlement=payment_settlement
    )
    CommandExecutor.execute(cmd, db)
    return RedirectResponse(redirect_to or f"{settings.APP_PREFIX}/logistics", status_code=303)

@router.post("/actions/update-supply-status/{supply_id}")
def action_update_supply_status(
    supply_id: int,
    status: str = Form(...),
    payment_settlement: Optional[str] = Form(None),
    request: Request = None,
    redirect_to: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    cmd = UpdateSupplyStatusCmd(
        supply_id=supply_id,
        status=status,
        payment_settlement=payment_settlement
    )
    CommandExecutor.execute(cmd, db)
    if request and request.headers.get("HX-Request"):
        return Response(headers={"HX-Refresh": "true"})
    return RedirectResponse(redirect_to or f"{settings.APP_PREFIX}/logistics", status_code=303)

@router.post("/actions/create-project")
def action_create_project(
    title: str = Form(...),
    description: Optional[str] = Form(""),
    project_type: str = Form("HOUSEHOLD"),
    stage: str = Form("ACTIVE"),
    priority: int = Form(3),
    color_hex: str = Form("#3b82f6"),
    weekly_quota_minutes: int = Form(0),
    preferred_slot_minutes: int = Form(60),
    db: Session = Depends(get_db)
):
    cmd = CreateProjectCmd(
        title=title,
        description=description,
        project_type=project_type,
        stage=stage,
        priority=priority,
        color_hex=color_hex,
        weekly_quota_minutes=weekly_quota_minutes,
        preferred_slot_minutes=preferred_slot_minutes
    )
    res = CommandExecutor.execute(cmd, db)
    return RedirectResponse(f"{settings.APP_PREFIX}/projects/{res['project_id']}", status_code=303)

@router.post("/actions/update-mileage/{project_id}")
def action_update_mileage(
    project_id: int,
    current_mileage: int = Form(...),
    db: Session = Depends(get_db)
):
    cmd = UpdateCarMileageCmd(project_id=project_id, current_mileage=current_mileage)
    CommandExecutor.execute(cmd, db)
    return RedirectResponse(f"{settings.APP_PREFIX}/projects/{project_id}", status_code=303)

@router.post("/actions/pay-loan/{project_id}")
def action_pay_loan(
    project_id: int,
    amount_paid: float = Form(...),
    db: Session = Depends(get_db)
):
    cmd = PayLoanInstallmentCmd(project_id=project_id, amount_paid=amount_paid)
    CommandExecutor.execute(cmd, db)
    return RedirectResponse(f"{settings.APP_PREFIX}/projects/{project_id}", status_code=303)

@router.post("/actions/add-finance")
def action_add_finance(
    title: str = Form(...),
    amount: float = Form(...),
    record_type: str = Form(...),
    planned_date: str = Form(...),
    project_id: Optional[int] = Form(None),
    is_annual_or_monthly: str = Form("NONE"),
    redirect_to: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    cmd = AddFinanceRecordCmd(
        title=title,
        amount=amount,
        record_type=record_type,
        planned_date=datetime.strptime(planned_date, "%Y-%m-%d").date(),
        project_id=project_id,
        is_annual_or_monthly=is_annual_or_monthly
    )
    CommandExecutor.execute(cmd, db)
    return RedirectResponse(redirect_to or f"{settings.APP_PREFIX}/finance", status_code=303)

@router.post("/actions/execute-finance/{record_id}")
def action_execute_finance(record_id: int, request: Request, db: Session = Depends(get_db)):
    cmd = ExecuteFinanceRecordCmd(record_id=record_id)
    CommandExecutor.execute(cmd, db)
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Refresh": "true"})
    return RedirectResponse(f"{settings.APP_PREFIX}/finance", status_code=303)

@router.post("/actions/delete-finance/{record_id}")
def action_delete_finance(record_id: int, redirect_to: Optional[str] = Form(None), db: Session = Depends(get_db)):
    cmd = DeleteFinanceRecordCmd(record_id=record_id)
    CommandExecutor.execute(cmd, db)
    return RedirectResponse(redirect_to or f"{settings.APP_PREFIX}/finance", status_code=303)


@router.post("/actions/update-wallet")
def action_update_wallet(
    current_balance: float = Form(...),
    safety_threshold: float = Form(50000.0),
    db: Session = Depends(get_db)
):
    cmd = UpdateWalletCmd(current_balance=current_balance, safety_threshold=safety_threshold)
    CommandExecutor.execute(cmd, db)
    return RedirectResponse(f"{settings.APP_PREFIX}/finance", status_code=303)

@router.post("/actions/add-project-task/{project_id}")
def action_add_project_task(
    project_id: int,
    title: str = Form(...),
    location_id: Optional[int] = Form(None),
    location_name: Optional[str] = Form(None),
    hard_due_date: Optional[str] = Form(None),
    duration_minutes: int = Form(60),
    priority: int = Form(3),
    depends_on_task_id: Optional[int] = Form(None),
    depends_on_supply_id: Optional[int] = Form(None),
    notes: Optional[str] = Form(""),
    db: Session = Depends(get_db)
):
    due = None
    if hard_due_date:
        try:
            due = datetime.strptime(hard_due_date, "%Y-%m-%d").date()
        except Exception:
            pass

    cmd = CreateTaskCmd(
        title=title,
        project_id=project_id,
        location_id=location_id,
        location_name=location_name,
        hard_due_date=due,
        duration_minutes=duration_minutes,
        priority=priority,
        depends_on_task_id=depends_on_task_id,
        depends_on_supply_id=depends_on_supply_id,
        notes=notes
    )
    CommandExecutor.execute(cmd, db)
    return RedirectResponse(f"{settings.APP_PREFIX}/projects/{project_id}", status_code=303)

@router.post("/actions/delete-task/{task_id}")
def action_delete_task(task_id: int, redirect_to: Optional[str] = Form(None), db: Session = Depends(get_db)):
    res = CommandExecutor.execute(DeleteTaskCmd(task_id=task_id), db)
    proj_id = res.get("project_id")
    if redirect_to:
        return RedirectResponse(redirect_to, status_code=303)
    if proj_id:
        return RedirectResponse(f"{settings.APP_PREFIX}/projects/{proj_id}", status_code=303)
    return RedirectResponse(f"{settings.APP_PREFIX}/", status_code=303)

@router.post("/actions/edit-project/{project_id}")
async def action_edit_project(
    project_id: int,
    request: Request,
    title: str = Form(...),
    description: Optional[str] = Form(""),
    stage: str = Form("ACTIVE"),
    priority: int = Form(3),
    color_hex: str = Form("#3b82f6"),
    weekly_quota_minutes: int = Form(0),
    preferred_slot_minutes: int = Form(60),
    db: Session = Depends(get_db)
):
    form_data = await request.form()
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        return RedirectResponse(f"{settings.APP_PREFIX}/projects", status_code=303)

    payload = dict(proj.template_payload or {})

    # Extract template fields based on type
    if proj.project_type == ProjectType.IT_SYSTEM:
        if "ssl_expires_at" in form_data and form_data.get("ssl_expires_at"):
            payload["ssl_expires_at"] = str(form_data.get("ssl_expires_at"))
        if "access_notes" in form_data:
            payload["access_notes"] = str(form_data.get("access_notes"))
        if "backlog_notes" in form_data:
            payload["backlog_notes"] = str(form_data.get("backlog_notes"))
        if "domains" in form_data:
            domains_raw = str(form_data.get("domains") or "")
            payload["domains"] = [d.strip() for d in domains_raw.replace("\n", ",").split(",") if d.strip()]

    elif proj.project_type == ProjectType.AUTO:
        if "car_model" in form_data:
            payload["car_model"] = str(form_data.get("car_model"))
        if "current_mileage" in form_data and form_data.get("current_mileage"):
            try:
                payload["current_mileage"] = int(form_data.get("current_mileage"))
            except Exception:
                pass
        if "last_to_mileage" in form_data and form_data.get("last_to_mileage"):
            try:
                payload["last_to_mileage"] = int(form_data.get("last_to_mileage"))
            except Exception:
                pass
        if "to_interval_km" in form_data and form_data.get("to_interval_km"):
            try:
                payload["to_interval_km"] = int(form_data.get("to_interval_km"))
            except Exception:
                pass
        if "insurance_until" in form_data and form_data.get("insurance_until"):
            payload["insurance_until"] = str(form_data.get("insurance_until"))
        if "service_log" in form_data:
            payload["service_log"] = str(form_data.get("service_log"))

    elif proj.project_type == ProjectType.LOAN:
        if "bank_name" in form_data:
            payload["bank_name"] = str(form_data.get("bank_name"))
        if "total_loan_amount" in form_data and form_data.get("total_loan_amount"):
            try:
                payload["total_loan_amount"] = float(form_data.get("total_loan_amount"))
            except Exception:
                pass
        if "remaining_balance" in form_data and form_data.get("remaining_balance"):
            try:
                payload["remaining_balance"] = float(form_data.get("remaining_balance"))
            except Exception:
                pass
        if "interest_rate" in form_data and form_data.get("interest_rate"):
            try:
                payload["interest_rate"] = float(form_data.get("interest_rate"))
            except Exception:
                pass
        if "monthly_payment" in form_data and form_data.get("monthly_payment"):
            try:
                payload["monthly_payment"] = float(form_data.get("monthly_payment"))
            except Exception:
                pass
        if "payment_day" in form_data and form_data.get("payment_day"):
            try:
                payload["payment_day"] = int(form_data.get("payment_day"))
            except Exception:
                pass

    elif proj.project_type == ProjectType.DIY_BUILD:
        if "specs" in form_data:
            payload["specs"] = str(form_data.get("specs"))
        if "budget_limit" in form_data and form_data.get("budget_limit"):
            try:
                payload["budget_limit"] = float(form_data.get("budget_limit"))
            except Exception:
                pass

    elif proj.project_type == ProjectType.NEW_IDEA:
        if "concept_pitch" in form_data:
            payload["concept_pitch"] = str(form_data.get("concept_pitch"))
        if "estimated_budget" in form_data and form_data.get("estimated_budget"):
            try:
                payload["estimated_budget"] = float(form_data.get("estimated_budget"))
            except Exception:
                pass

    cmd = UpdateProjectCmd(
        project_id=project_id,
        title=title,
        description=description,
        stage=stage,
        priority=priority,
        color_hex=color_hex,
        weekly_quota_minutes=weekly_quota_minutes,
        preferred_slot_minutes=preferred_slot_minutes,
        template_payload=payload
    )
    CommandExecutor.execute(cmd, db)
    return RedirectResponse(f"{settings.APP_PREFIX}/projects/{project_id}", status_code=303)

@router.post("/actions/delete-project/{project_id}")
def action_delete_project(project_id: int, db: Session = Depends(get_db)):
    CommandExecutor.execute(DeleteProjectCmd(project_id=project_id), db)
    return RedirectResponse(f"{settings.APP_PREFIX}/projects", status_code=303)


@router.post("/actions/update-servers/{project_id}")
async def action_update_servers(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db)
):
    form_data = await request.form()
    proj = db.query(Project).filter(Project.id == project_id).first()
    if not proj:
        return RedirectResponse(f"{settings.APP_PREFIX}/projects", status_code=303)

    ips = form_data.getlist("server_ip")
    providers = form_data.getlist("server_provider")
    costs = form_data.getlist("server_cost")
    pay_days = form_data.getlist("server_pay_day")

    new_servers = []
    for i in range(len(ips)):
        ip = str(ips[i]).strip()
        if not ip:
            continue
        provider = str(providers[i]).strip() if i < len(providers) else ""
        try:
            cost = float(costs[i]) if i < len(costs) else 0.0
        except Exception:
            cost = 0.0
        try:
            p_day = int(pay_days[i]) if i < len(pay_days) else 15
        except Exception:
            p_day = 15

        new_servers.append({
            "ip": ip,
            "provider": provider,
            "monthly_cost": cost,
            "pay_day": p_day
        })

    payload = dict(proj.template_payload or {})
    payload["servers"] = new_servers
    proj.template_payload = payload
    flag_modified(proj, "template_payload")

    # Clear old planned server records for this project so they accurately reflect the updated costs
    db.query(FinanceRecord).filter(
        FinanceRecord.project_id == proj.id,
        FinanceRecord.status == FinanceStatus.PLANNED,
        FinanceRecord.title.like("Сервер %")
    ).delete(synchronize_session=False)

    # Re-trigger creation/updating of mandatory recurring server records
    CommandExecutor._process_project_triggers(proj, db)

    db.commit()
    db.refresh(proj)

    return RedirectResponse(f"{settings.APP_PREFIX}/projects/{project_id}", status_code=303)


