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
    Project, ProjectType, ProjectStage, ProjectCategory,
    SupplyItem, SupplyStatus, PaymentSettlement,
    Task, TaskStatus,
    FinanceRecord, FinanceRecordType, FinanceStatus, RecurrenceType,
    WalletState, Location,
    IpPaymentGround, IpIncome, IpTaxPayment
)
from app.core.ip_accounting import calculate_ip_taxes, get_ip_incomes_grouped_by_month, FIXED_CONTRIBUTIONS
from app.core.executor import CommandExecutor
from app.core.budget_guard import BudgetGuard
from app.core.commands import (
    AddSupplyItemCmd, UpdateSupplyStatusCmd,
    CreateTaskCmd, UpdateTaskCmd, UpdateTaskStatusCmd, DeleteTaskCmd,
    CreateProjectCmd, UpdateProjectCmd, DeleteProjectCmd,
    AddFinanceRecordCmd, ExecuteFinanceRecordCmd, DeleteFinanceRecordCmd,
    UpdateWalletCmd, UpdateCarMileageCmd, PayLoanInstallmentCmd,
    AutoScheduleWeekCmd
)

templates_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "templates")
templates = Jinja2Templates(directory=templates_dir)

def format_money(val) -> str:
    if val is None or val == "":
        return "0"
    try:
        f = float(val)
        sign = "-" if f < 0 else ""
        abs_f = abs(f)
        if abs_f.is_integer():
            formatted = f"{int(abs_f):,}".replace(",", " ")
        else:
            formatted = f"{abs_f:,.2f}".replace(",", " ").replace(".", ",")
        return f"{sign}{formatted}"
    except (ValueError, TypeError):
        return str(val)

templates.env.filters["money"] = format_money

CATEGORY_ICONS = {
    "server": """<svg width="16" height="16" class="w-4 h-4 shrink-0 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M5.25 14.25h13.5m-13.5 0a3 3 0 01-3-3m3 3a3 3 0 100 6h13.5a3 3 0 100-6m-16.5-3a3 3 0 013-3h13.5a3 3 0 013 3m-19.5 0a4.5 4.5 0 01.9-2.7L5.75 5.1a2.25 2.25 0 011.8-1.1h8.9a2.25 2.25 0 011.8 1.1l2.1 3.45a4.5 4.5 0 01.9 2.7M6.75 17.25h.008v.008H6.75v-.008zm3 0h.008v.008H9.75v-.008z"/></svg>""",
    "lightbulb": """<svg width="16" height="16" class="w-4 h-4 shrink-0 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.439a3.75 3.75 0 11-4.5 0M12 2.25v2.25m6.364 1.886l-1.591 1.591M21.75 12h-2.25m-1.886 6.364l-1.591-1.591M2.25 12h2.25m1.886-6.364l1.591 1.591"/></svg>""",
    "wrench": """<svg width="16" height="16" class="w-4 h-4 shrink-0 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M11.42 15.17L17.25 21A2.652 2.652 0 0021 17.25l-5.877-5.877M11.42 15.17l2.496-3.03c.317-.384.74-.626 1.208-.766M11.42 15.17l-4.655 5.653a2.548 2.548 0 11-3.586-3.586l6.837-5.63m5.108-.233l2.87-2.87a2.25 2.25 0 00-3.182-3.182l-2.87 2.87m3.182 3.182l-2.87-2.87"/></svg>""",
    "credit-card": """<svg width="16" height="16" class="w-4 h-4 shrink-0 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 8.25h19.5M2.25 9h19.5m-16.5 5.25h6m-6 2.25h3m-6.75 3.75h16.5a1.5 1.5 0 001.5-1.5V5.25a1.5 1.5 0 00-1.5-1.5H3.75A1.5 1.5 0 002.25 5.25v13.5a1.5 1.5 0 001.5 1.5z"/></svg>""",
    "home": """<svg width="16" height="16" class="w-4 h-4 shrink-0 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25"/></svg>""",
    "car": """<svg width="16" height="16" class="w-4 h-4 shrink-0 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M8.25 18.75a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h7.5m-7.5 0l-.75-4.5h10.5l-.75 4.5m-9-4.5l1.5-6h6l1.5 6m-9 0h9m3 4.5a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0"/></svg>""",
    "folder": """<svg width="16" height="16" class="w-4 h-4 shrink-0 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z"/></svg>""",
    "briefcase": """<svg width="16" height="16" class="w-4 h-4 shrink-0 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M20.25 14.25v4.5a1.5 1.5 0 01-1.5 1.5H5.25a1.5 1.5 0 01-1.5-1.5v-4.5m16.5 0a2.25 2.25 0 00-2.25-2.25H16.5M20.25 14.25a2.25 2.25 0 01-2.25 2.25H6a2.25 2.25 0 01-2.25-2.25m16.5 0H3.75m16.5 0v-4.5a2.25 2.25 0 00-2.25-2.25h-15A2.25 2.25 0 001.5 9.75v4.5m18.75 0H3.75M9 6.75A2.25 2.25 0 0111.25 4.5h1.5A2.25 2.25 0 0115 6.75v1.5H9v-1.5z"/></svg>""",
    "heart": """<svg width="16" height="16" class="w-4 h-4 shrink-0 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z"/></svg>""",
    "star": """<svg width="16" height="16" class="w-4 h-4 shrink-0 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.75"><path stroke-linecap="round" stroke-linejoin="round" d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z"/></svg>"""
}

def render_cat_icon(icon_name: str) -> str:
    return CATEGORY_ICONS.get(icon_name, CATEGORY_ICONS["folder"])

templates.env.filters["cat_icon"] = render_cat_icon

def get_categories_catalog(db: Optional[Session]) -> list:
    defaults = [
        {"slug": "it_system", "title": "IT и Цифровые Системы", "icon": "server", "projects": [], "items": []},
        {"slug": "new_idea", "title": "Новые Идеи и Стартапы", "icon": "lightbulb", "projects": [], "items": []},
        {"slug": "diy_build", "title": "Сборка и Оборудование (DIY)", "icon": "wrench", "projects": [], "items": []},
        {"slug": "auto", "title": "Автомобили и Мотоциклы", "icon": "car", "projects": [], "items": []},
        {"slug": "loan", "title": "Кредиты и Обязательства", "icon": "credit-card", "projects": [], "items": []},
        {"slug": "household", "title": "Быт, Офисы и Поручения", "icon": "home", "projects": [], "items": []},
    ]
    if not db:
        for c in defaults:
            c["count"] = 0
        return defaults

    cat_map = {c["slug"]: c for c in defaults}

    try:
        custom_cats = db.query(ProjectCategory).order_by(ProjectCategory.sort_order.asc(), ProjectCategory.id.asc()).all()
        for cc in custom_cats:
            if cc.slug not in cat_map:
                entry = {"slug": cc.slug, "title": cc.title, "icon": cc.icon or "folder", "projects": [], "items": []}
                cat_map[cc.slug] = entry
                defaults.append(entry)
    except Exception:
        pass

    all_projects = db.query(Project).order_by(Project.priority.asc(), Project.title.asc()).all()
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

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

        # Assign to category
        c_slug = getattr(p, "category_slug", None)
        target_entry = None
        if c_slug and c_slug in cat_map:
            target_entry = cat_map[c_slug]
        elif c_slug == "auto_loan":
            if p.project_type == ProjectType.LOAN:
                target_entry = cat_map.get("loan")
            else:
                target_entry = cat_map.get("auto")
        else:
            if p.project_type == ProjectType.IT_SYSTEM:
                target_entry = cat_map.get("it_system")
            elif p.project_type == ProjectType.NEW_IDEA:
                target_entry = cat_map.get("new_idea")
            elif p.project_type == ProjectType.DIY_BUILD:
                target_entry = cat_map.get("diy_build")
            elif p.project_type == ProjectType.AUTO:
                target_entry = cat_map.get("auto")
            elif p.project_type == ProjectType.LOAN:
                target_entry = cat_map.get("loan")
            else:
                target_entry = cat_map.get("household")

        if target_entry:
            target_entry["projects"].append(p)
            target_entry["items"].append(p)

    for c in defaults:
        c["count"] = len(c["projects"])

    return defaults

# Helper function to expose url_prefix in all templates
def template_context(request: Request, extra: dict = None, db: Optional[Session] = None) -> dict:
    ctx = {
        "request": request,
        "prefix": settings.APP_PREFIX,
        "now": datetime.now(),
        "today": date.today(),
        "sidebar_categories": get_categories_catalog(db) if db else []
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
        }, db=db)
    )

# -------------------------------------------------------------
# 2. Projects Catalog (GET /projects)
# -------------------------------------------------------------
@router.get("/projects", response_class=HTMLResponse)
def projects_page(request: Request, db: Session = Depends(get_db)):
    categories = get_categories_catalog(db)
    return templates.TemplateResponse(
        request=request,
        name="projects.html",
        context=template_context(request, {
            "categories": categories,
            "all_categories_list": categories
        }, db=db)
    )

# -------------------------------------------------------------
# 2b. Isolated Category Page (GET /categories/{slug})
# -------------------------------------------------------------
@router.get("/categories/{slug}", response_class=HTMLResponse)
def category_detail_page(slug: str, request: Request, db: Session = Depends(get_db)):
    categories = get_categories_catalog(db)
    current_cat = next((c for c in categories if c["slug"] == slug), None)
    if not current_cat:
        return RedirectResponse(f"{settings.APP_PREFIX}/projects")

    return templates.TemplateResponse(
        request=request,
        name="category_detail.html",
        context=template_context(request, {
            "current_cat": current_cat,
            "projects": current_cat.get("projects", []),
            "all_categories": categories,
        }, db=db)
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
        }, db=db)
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
        }, db=db)
    )

# -------------------------------------------------------------
# 5. Finance Page (GET /finance)
# -------------------------------------------------------------
@router.get("/finance", response_class=HTMLResponse)
def finance_page(
    request: Request,
    tab: str = "radar",
    year: Optional[int] = None,
    db: Session = Depends(get_db)
):
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
    total_recurring_expenses = sum(float(r.amount) for r in recurring_expenses if r.is_annual_or_monthly == RecurrenceType.MONTHLY)

    # --- IP Finances & Accounting ---
    current_year = date.today().year
    target_year = year or current_year

    ip_monthly_groups = get_ip_incomes_grouped_by_month(db)
    ip_grounds = db.query(IpPaymentGround).order_by(IpPaymentGround.name.asc()).all()
    all_ip_incomes = db.query(IpIncome).order_by(IpIncome.payment_date.desc()).all()

    # Available years for selector
    years_set = {current_year - 2, current_year - 1, current_year, current_year + 1}
    for inc in all_ip_incomes:
        years_set.add(inc.payment_date.year)
    available_years = sorted(list(years_set), reverse=True)

    ip_taxes = calculate_ip_taxes(db, target_year=target_year)

    total_ip_revenue = sum(float(i.amount) for i in all_ip_incomes)
    year_ip_revenue = sum(float(i.amount) for i in all_ip_incomes if i.payment_date.year == target_year)

    return templates.TemplateResponse(
        request=request,
        name="finance.html",
        context=template_context(request, {
            "active_tab": tab,
            "target_year": target_year,
            "available_years": available_years,
            "ip_monthly_groups": ip_monthly_groups,
            "ip_grounds": ip_grounds,
            "all_ip_incomes": all_ip_incomes,
            "total_ip_revenue": total_ip_revenue,
            "year_ip_revenue": year_ip_revenue,
            "ip_taxes": ip_taxes,
            # Radar & personal finance:
            "radar": radar,
            "records": records,
            "planned_incomes": planned_incomes,
            "recurring_incomes": recurring_incomes,
            "executed_incomes": executed_incomes,
            "total_planned_incomes": total_planned_incomes,
            "total_recurring_incomes": total_recurring_incomes,
            "total_past_incomes": total_past_incomes,
            "total_recurring_expenses": total_recurring_expenses,
            "wishlist": wishlist,
            "birthdays": birthdays,
            "recurring": recurring_expenses,
            "executed_expenses": executed_expenses,
            "projects": projects
        }, db=db)
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
    is_urgent: bool = Form(False),
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
        priority=priority,
        is_urgent=is_urgent
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
    category_slug: Optional[str] = Form(None),
    stage: str = Form("ACTIVE"),
    priority: int = Form(3),
    color_hex: str = Form("#3b82f6"),
    weekly_quota_minutes: int = Form(0),
    preferred_slot_minutes: int = Form(60),
    redirect_to: Optional[str] = Form(None),
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
    if category_slug:
        p = db.query(Project).filter(Project.id == res["project_id"]).first()
        if p:
            p.category_slug = category_slug.strip() or None
            db.commit()
    return RedirectResponse(redirect_to or f"{settings.APP_PREFIX}/projects/{res['project_id']}", status_code=303)

@router.post("/actions/create-category")
def action_create_category(
    title: str = Form(...),
    icon: str = Form("folder"),
    redirect_to: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    import re
    cleaned_title = title.strip()
    slug = re.sub(r'[^a-zA-Z0-9_]+', '_', cleaned_title.lower()).strip('_')
    if not slug:
        slug = f"cat_{int(datetime.now().timestamp())}"
    existing = db.query(ProjectCategory).filter(ProjectCategory.slug == slug).first()
    if existing:
        slug = f"{slug}_{int(datetime.now().timestamp())}"

    new_cat = ProjectCategory(
        slug=slug,
        title=cleaned_title,
        icon=icon.strip() or "folder"
    )
    db.add(new_cat)
    db.commit()

    return RedirectResponse(redirect_to or f"{settings.APP_PREFIX}/projects#cat-{slug}", status_code=303)

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

@router.post("/actions/edit-finance/{record_id}")
def action_edit_finance(
    record_id: int,
    title: str = Form(...),
    amount: float = Form(...),
    planned_date: str = Form(...),
    is_annual_or_monthly: str = Form("NONE"),
    project_id: Optional[int] = Form(None),
    redirect_to: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    rec = db.query(FinanceRecord).filter(FinanceRecord.id == record_id).first()
    if rec:
        rec.title = title
        rec.amount = amount
        try:
            rec.planned_date = datetime.strptime(planned_date, "%Y-%m-%d").date()
        except Exception:
            pass
        try:
            rec.is_annual_or_monthly = RecurrenceType(is_annual_or_monthly)
        except Exception:
            pass
        rec.project_id = project_id if project_id else None
        db.commit()
    return RedirectResponse(redirect_to or f"{settings.APP_PREFIX}/finance", status_code=303)

# -------------------------------------------------------------
# 5b. IP Income & Accounting Action Endpoints
# -------------------------------------------------------------
@router.post("/actions/add-ip-income")
def action_add_ip_income(
    payment_date: str = Form(...),
    amount: float = Form(...),
    account_name: Optional[str] = Form("Основной счет ИП"),
    invoice_number: Optional[str] = Form(None),
    ground_id: Optional[int] = Form(None),
    ground_title: Optional[str] = Form(None),
    client_name: Optional[str] = Form(None),
    payment_type: Optional[str] = Form("Оплата за месяц"),
    notes: Optional[str] = Form(None),
    redirect_to: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    try:
        p_date = datetime.strptime(payment_date, "%Y-%m-%d").date()
    except Exception:
        p_date = date.today()

    resolved_ground_title = (ground_title or "").strip()
    resolved_client = (client_name or "").strip()
    if ground_id:
        ground = db.query(IpPaymentGround).filter(IpPaymentGround.id == ground_id).first()
        if ground:
            if not resolved_ground_title:
                resolved_ground_title = ground.name
            if not resolved_client and ground.client_name:
                resolved_client = ground.client_name

    income = IpIncome(
        payment_date=p_date,
        amount=amount,
        account_name=(account_name or "Основной счет ИП").strip(),
        invoice_number=invoice_number.strip() if invoice_number else None,
        ground_id=ground_id if ground_id else None,
        ground_title=resolved_ground_title or None,
        client_name=resolved_client or None,
        payment_type=(payment_type or "Оплата за месяц").strip(),
        notes=notes.strip() if notes else None
    )
    db.add(income)
    db.commit()
    return RedirectResponse(redirect_to or f"{settings.APP_PREFIX}/finance?tab=ip_incomes", status_code=303)

@router.post("/actions/edit-ip-income/{income_id}")
def action_edit_ip_income(
    income_id: int,
    payment_date: str = Form(...),
    amount: float = Form(...),
    account_name: Optional[str] = Form("Основной счет ИП"),
    invoice_number: Optional[str] = Form(None),
    ground_id: Optional[int] = Form(None),
    ground_title: Optional[str] = Form(None),
    client_name: Optional[str] = Form(None),
    payment_type: Optional[str] = Form("Оплата за месяц"),
    notes: Optional[str] = Form(None),
    redirect_to: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    inc = db.query(IpIncome).filter(IpIncome.id == income_id).first()
    if inc:
        try:
            inc.payment_date = datetime.strptime(payment_date, "%Y-%m-%d").date()
        except Exception:
            pass
        inc.amount = amount
        inc.account_name = (account_name or "Основной счет ИП").strip()
        inc.invoice_number = invoice_number.strip() if invoice_number else None
        inc.ground_id = ground_id if ground_id else None

        resolved_ground_title = (ground_title or "").strip()
        resolved_client = (client_name or "").strip()
        if ground_id:
            ground = db.query(IpPaymentGround).filter(IpPaymentGround.id == ground_id).first()
            if ground:
                if not resolved_ground_title:
                    resolved_ground_title = ground.name
                if not resolved_client and ground.client_name:
                    resolved_client = ground.client_name

        inc.ground_title = resolved_ground_title or None
        inc.client_name = resolved_client or None
        inc.payment_type = (payment_type or "Оплата за месяц").strip()
        inc.notes = notes.strip() if notes else None
        db.commit()
    return RedirectResponse(redirect_to or f"{settings.APP_PREFIX}/finance?tab=ip_incomes", status_code=303)

@router.post("/actions/delete-ip-income/{income_id}")
def action_delete_ip_income(
    income_id: int,
    redirect_to: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    inc = db.query(IpIncome).filter(IpIncome.id == income_id).first()
    if inc:
        db.delete(inc)
        db.commit()
    return RedirectResponse(redirect_to or f"{settings.APP_PREFIX}/finance?tab=ip_incomes", status_code=303)

@router.post("/actions/add-ip-ground")
def action_add_ip_ground(
    name: str = Form(...),
    client_name: Optional[str] = Form(None),
    default_account: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    redirect_to: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    ground = IpPaymentGround(
        name=name.strip(),
        client_name=client_name.strip() if client_name else None,
        default_account=default_account.strip() if default_account else None,
        description=description.strip() if description else None
    )
    db.add(ground)
    db.commit()
    return RedirectResponse(redirect_to or f"{settings.APP_PREFIX}/finance?tab=ip_incomes", status_code=303)

@router.post("/actions/delete-ip-ground/{ground_id}")
def action_delete_ip_ground(
    ground_id: int,
    redirect_to: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    g = db.query(IpPaymentGround).filter(IpPaymentGround.id == ground_id).first()
    if g:
        db.delete(g)
        db.commit()
    return RedirectResponse(redirect_to or f"{settings.APP_PREFIX}/finance?tab=ip_incomes", status_code=303)

@router.post("/actions/record-tax-payment")
def action_record_tax_payment(
    year: int = Form(...),
    period: str = Form(...),
    title: str = Form(...),
    amount: float = Form(...),
    payment_date: str = Form(...),
    notes: Optional[str] = Form(None),
    redirect_to: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    try:
        p_date = datetime.strptime(payment_date, "%Y-%m-%d").date()
    except Exception:
        p_date = date.today()
    tp = IpTaxPayment(
        year=year,
        period=period,
        title=title.strip(),
        amount=amount,
        payment_date=p_date,
        status="PAID",
        notes=notes.strip() if notes else None
    )
    db.add(tp)
    db.commit()
    return RedirectResponse(redirect_to or f"{settings.APP_PREFIX}/finance?tab=accounting&year={year}", status_code=303)




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
    is_urgent: bool = Form(False),
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
        is_urgent=is_urgent,
        depends_on_task_id=depends_on_task_id,
        depends_on_supply_id=depends_on_supply_id,
        notes=notes
    )
    CommandExecutor.execute(cmd, db)
    return RedirectResponse(f"{settings.APP_PREFIX}/projects/{project_id}", status_code=303)

@router.post("/actions/edit-task/{task_id}")
def action_edit_task(
    task_id: int,
    title: str = Form(...),
    duration_minutes: int = Form(60),
    hard_due_date: Optional[str] = Form(None),
    priority: int = Form(3),
    is_urgent: bool = Form(False),
    notes: Optional[str] = Form(""),
    redirect_to: Optional[str] = Form(None),
    db: Session = Depends(get_db)
):
    due = None
    if hard_due_date and hard_due_date.strip():
        try:
            due = datetime.strptime(hard_due_date.strip(), "%Y-%m-%d").date()
        except Exception:
            pass

    cmd = UpdateTaskCmd(
        task_id=task_id,
        title=title,
        duration_minutes=duration_minutes,
        hard_due_date=due,
        priority=priority,
        is_urgent=is_urgent,
        notes=notes or ""
    )
    res = CommandExecutor.execute(cmd, db)
    proj_id = res.get("project_id")
    if redirect_to:
        return RedirectResponse(redirect_to, status_code=303)
    if proj_id:
        return RedirectResponse(f"{settings.APP_PREFIX}/projects/{proj_id}", status_code=303)
    return RedirectResponse(f"{settings.APP_PREFIX}/", status_code=303)

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
    category_slug: Optional[str] = Form(None),
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
        if "remaining_months" in form_data:
            val = form_data.get("remaining_months")
            if val is not None and str(val).strip() != "":
                try:
                    payload["remaining_months"] = int(val)
                except Exception:
                    pass
            else:
                payload.pop("remaining_months", None)
        if "calculated_remaining_sum" in form_data:
            val = form_data.get("calculated_remaining_sum")
            if val is not None and str(val).strip() != "":
                try:
                    payload["calculated_remaining_sum"] = float(val)
                except Exception:
                    pass
            elif payload.get("remaining_months") and payload.get("monthly_payment"):
                payload["calculated_remaining_sum"] = float(payload["remaining_months"]) * float(payload["monthly_payment"])
            else:
                payload.pop("calculated_remaining_sum", None)

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
    if category_slug is not None:
        p = db.query(Project).filter(Project.id == project_id).first()
        if p:
            p.category_slug = category_slug.strip() if category_slug.strip() else None
            db.commit()
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


