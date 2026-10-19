from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.executor import CommandExecutor
from app.core.commands import (
    AddSupplyItemCmd, UpdateSupplyStatusCmd,
    CreateTaskCmd, UpdateTaskStatusCmd,
    CreateProjectCmd, UpdateProjectCmd,
    AddFinanceRecordCmd, ExecuteFinanceRecordCmd,
    UpdateWalletCmd, UpdateCarMileageCmd, PayLoanInstallmentCmd,
    AutoScheduleWeekCmd
)
from app.core.models import Task, TaskStatus, Project

router = APIRouter(prefix="/api/v1", tags=["Universal Command Gateway & AI Tools"])

COMMAND_REGISTRY = {
    "AddSupplyItemCmd": AddSupplyItemCmd,
    "UpdateSupplyStatusCmd": UpdateSupplyStatusCmd,
    "CreateTaskCmd": CreateTaskCmd,
    "UpdateTaskStatusCmd": UpdateTaskStatusCmd,
    "CreateProjectCmd": CreateProjectCmd,
    "UpdateProjectCmd": UpdateProjectCmd,
    "AddFinanceRecordCmd": AddFinanceRecordCmd,
    "ExecuteFinanceRecordCmd": ExecuteFinanceRecordCmd,
    "UpdateWalletCmd": UpdateWalletCmd,
    "UpdateCarMileageCmd": UpdateCarMileageCmd,
    "PayLoanInstallmentCmd": PayLoanInstallmentCmd,
    "AutoScheduleWeekCmd": AutoScheduleWeekCmd,
}

@router.post("/commands", summary="Универсальный шлюз команд (Command Bus) для ИИ и мобильных приложений")
def dispatch_command(payload: Dict[str, Any], db: Session = Depends(get_db)):
    cmd_name = payload.get("command")
    if not cmd_name or cmd_name not in COMMAND_REGISTRY:
        raise HTTPException(status_code=400, detail=f"Неизвестная команда '{cmd_name}'. Доступные: {list(COMMAND_REGISTRY.keys())}")

    model_cls = COMMAND_REGISTRY[cmd_name]
    cmd_args = payload.get("payload", {})
    try:
        cmd_obj = model_cls(**cmd_args)
        result = CommandExecutor.execute(cmd_obj, db)
        return {"status": "ok", "command": cmd_name, "result": result}
    except Exception as e:
        raise HTTPException(status_code=422, detail=str(e))

# Direct typed endpoints for convenience
@router.post("/commands/add-supply")
def api_add_supply(cmd: AddSupplyItemCmd, db: Session = Depends(get_db)):
    return CommandExecutor.execute(cmd, db)

@router.post("/commands/update-supply-status")
def api_update_supply_status(cmd: UpdateSupplyStatusCmd, db: Session = Depends(get_db)):
    return CommandExecutor.execute(cmd, db)

@router.post("/commands/create-task")
def api_create_task(cmd: CreateTaskCmd, db: Session = Depends(get_db)):
    return CommandExecutor.execute(cmd, db)

@router.post("/commands/update-task-status")
def api_update_task_status(cmd: UpdateTaskStatusCmd, db: Session = Depends(get_db)):
    return CommandExecutor.execute(cmd, db)

@router.post("/commands/create-project")
def api_create_project(cmd: CreateProjectCmd, db: Session = Depends(get_db)):
    return CommandExecutor.execute(cmd, db)

@router.post("/commands/update-project")
def api_update_project(cmd: UpdateProjectCmd, db: Session = Depends(get_db)):
    return CommandExecutor.execute(cmd, db)

@router.post("/commands/add-finance-record")
def api_add_finance_record(cmd: AddFinanceRecordCmd, db: Session = Depends(get_db)):
    return CommandExecutor.execute(cmd, db)

@router.post("/commands/execute-finance-record")
def api_execute_finance_record(cmd: ExecuteFinanceRecordCmd, db: Session = Depends(get_db)):
    return CommandExecutor.execute(cmd, db)

@router.post("/commands/update-wallet")
def api_update_wallet(cmd: UpdateWalletCmd, db: Session = Depends(get_db)):
    return CommandExecutor.execute(cmd, db)

@router.post("/commands/update-mileage")
def api_update_mileage(cmd: UpdateCarMileageCmd, db: Session = Depends(get_db)):
    return CommandExecutor.execute(cmd, db)

@router.post("/commands/pay-loan")
def api_pay_loan(cmd: PayLoanInstallmentCmd, db: Session = Depends(get_db)):
    return CommandExecutor.execute(cmd, db)

@router.post("/commands/auto-schedule")
def api_auto_schedule(cmd: AutoScheduleWeekCmd, db: Session = Depends(get_db)):
    return CommandExecutor.execute(cmd, db)

@router.get("/tools", summary="Экспорт описаний инструментов для LLM Function Calling")
def export_ai_tools():
    """
    Возвращает список всех Pydantic-команд в формате JSON Schema (OpenAI / Gemini function calling tools).
    """
    tools = []
    for name, model_cls in COMMAND_REGISTRY.items():
        schema = model_cls.model_json_schema()
        tools.append({
            "type": "function",
            "function": {
                "name": name,
                "description": model_cls.__doc__ or schema.get("description", ""),
                "parameters": schema
            }
        })
    return {"tools_count": len(tools), "tools": tools}

@router.get("/calendar/events", summary="JSON-источник событий для FullCalendar")
def get_calendar_events(project_id: int = None, db: Session = Depends(get_db)):
    """Отдает список задач со временем для FullCalendar"""
    query = db.query(Task).filter(
        Task.scheduled_start != None
    )
    if project_id:
        query = query.filter(Task.project_id == project_id)

    tasks = query.all()
    events = []
    for t in tasks:
        color = t.project.color_hex if t.project and t.project.color_hex else "#3b82f6"
        loc_name = f" [{t.location.name}]" if t.location else ""
        events.append({
            "id": t.id,
            "title": f"{t.title}{loc_name}",
            "start": t.scheduled_start.isoformat(),
            "end": (t.scheduled_end or t.scheduled_start).isoformat(),
            "backgroundColor": color,
            "borderColor": color,
            "textColor": "#ffffff",
            "extendedProps": {
                "status": t.status.value,
                "priority": t.priority,
                "projectTitle": t.project.title if t.project else "Общие дела",
                "isAutoPlaced": t.is_auto_placed
            }
        })
    return events
