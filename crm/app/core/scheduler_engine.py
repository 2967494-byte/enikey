from datetime import date, datetime, timedelta, time
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.core.models import Task, TaskStatus, Project, ProjectStage, Location

class SchedulerEngine:
    DAY_START_HOUR = 9
    DAY_END_HOUR = 22
    TOTAL_DAY_MINUTES = (DAY_END_HOUR - DAY_START_HOUR) * 60  # 13 hours = 780 mins
    MAX_DAILY_BUSY_MINUTES = int(TOTAL_DAY_MINUTES * 0.65)   # 65% max work, 35% buffer = 507 mins

    @classmethod
    def run(cls, db: Session, target_monday: Optional[date] = None) -> Dict[str, Any]:
        """
        Основной цикл автопланирования расписания на неделю.
        1. Сдвиг невыполненных авто-слотов из прошлого.
        2. Фиксация задач с жесткой датой (hard_due_date).
        3. Гео-группировка задач по одной локации.
        4. Распределение недельных квот проектов.
        """
        today = date.today()
        if not target_monday:
            target_monday = today - timedelta(days=today.weekday())

        week_dates = [target_monday + timedelta(days=i) for i in range(7)]
        now = datetime.now()

        # Step 1: Auto-shift uncompleted past auto-placed tasks
        past_auto_tasks = db.query(Task).filter(
            Task.is_auto_placed == True,
            Task.status.in_([TaskStatus.SCHEDULED, TaskStatus.TODO]),
            Task.scheduled_start != None,
            Task.scheduled_end < now
        ).all()

        for t in past_auto_tasks:
            t.scheduled_start = None
            t.scheduled_end = None
            t.status = TaskStatus.TODO

        db.flush()

        # Step 2: Build daily occupied slots map
        # daily_slots[d] = list of (start_dt, end_dt, task_id, location_id, project_id)
        daily_slots: Dict[date, List[Dict[str, Any]]] = {d: [] for d in week_dates}

        scheduled_tasks = db.query(Task).filter(
            Task.status.in_([TaskStatus.SCHEDULED, TaskStatus.DONE]),
            Task.scheduled_start != None
        ).all()

        for st in scheduled_tasks:
            st_date = st.scheduled_start.date()
            if st_date in daily_slots:
                daily_slots[st_date].append({
                    "start": st.scheduled_start,
                    "end": st.scheduled_end or (st.scheduled_start + timedelta(minutes=st.duration_minutes)),
                    "task": st
                })

        # Step 3: Schedule tasks with hard_due_date that are still TODO
        hard_due_tasks = db.query(Task).filter(
            Task.status == TaskStatus.TODO,
            Task.hard_due_date.in_(week_dates)
        ).order_by(Task.priority.asc()).all()

        for ht in hard_due_tasks:
            target_date = ht.hard_due_date
            if target_date < today:
                target_date = today  # shift forward if overdue
            slot = cls._find_free_slot(daily_slots, target_date, ht.duration_minutes)
            if slot:
                ht.scheduled_start = slot[0]
                ht.scheduled_end = slot[1]
                ht.status = TaskStatus.SCHEDULED
                ht.is_auto_placed = False
                daily_slots[target_date].append({"start": slot[0], "end": slot[1], "task": ht})

        db.flush()

        # Step 4: Geo-grouping (Задачи в ту же локацию)
        cls._apply_geo_grouping(db, daily_slots, week_dates, today)
        db.flush()

        # Step 5: Quota distribution for projects
        projects_with_quota = db.query(Project).filter(
            Project.weekly_quota_minutes > 0,
            Project.stage.in_([ProjectStage.ACTIVE, ProjectStage.MAINTENANCE, ProjectStage.NOT_STARTED])
        ).order_by(Project.priority.asc()).all()

        placed_quota_count = 0
        for p in projects_with_quota:
            needed_minutes = p.weekly_quota_minutes
            preferred_slot = max(30, p.preferred_slot_minutes or 60)

            # Count already scheduled/done minutes this week
            week_start_dt = datetime.combine(week_dates[0], time(0, 0))
            week_end_dt = datetime.combine(week_dates[-1], time(23, 59))

            existing_proj_tasks = db.query(Task).filter(
                Task.project_id == p.id,
                Task.scheduled_start >= week_start_dt,
                Task.scheduled_start <= week_end_dt,
                Task.status.in_([TaskStatus.SCHEDULED, TaskStatus.DONE])
            ).all()

            already_mins = sum(t.duration_minutes for t in existing_proj_tasks)
            remaining_mins = needed_minutes - already_mins

            if remaining_mins <= 0:
                continue

            # Find available backlog tasks for this project, or create auto-quota task
            backlog_tasks = db.query(Task).filter(
                Task.project_id == p.id,
                Task.status == TaskStatus.TODO,
                Task.scheduled_start == None
            ).order_by(Task.priority.asc()).all()

            for bt in backlog_tasks:
                if remaining_mins <= 0:
                    break
                duration = min(bt.duration_minutes, remaining_mins)
                slot = cls._find_first_available_slot(daily_slots, week_dates, today, duration)
                if slot:
                    bt.scheduled_start = slot[0]
                    bt.scheduled_end = slot[1]
                    bt.status = TaskStatus.SCHEDULED
                    bt.is_auto_placed = True
                    daily_slots[slot[0].date()].append({"start": slot[0], "end": slot[1], "task": bt})
                    remaining_mins -= duration
                    placed_quota_count += 1

            # If quota remains, create an auto project focus slot
            while remaining_mins > 0:
                slot_dur = min(preferred_slot, remaining_mins)
                slot = cls._find_first_available_slot(daily_slots, week_dates, today, slot_dur)
                if not slot:
                    break  # no more free slots with buffer
                quota_task = Task(
                    project_id=p.id,
                    title=f"Фокус по квоте: {p.title}",
                    status=TaskStatus.SCHEDULED,
                    priority=p.priority,
                    duration_minutes=slot_dur,
                    scheduled_start=slot[0],
                    scheduled_end=slot[1],
                    is_auto_placed=True,
                    notes="Слот автоматически назначен по недельной квоте проекта"
                )
                db.add(quota_task)
                daily_slots[slot[0].date()].append({"start": slot[0], "end": slot[1], "task": quota_task})
                remaining_mins -= slot_dur
                placed_quota_count += 1

        db.commit()
        return {
            "status": "success",
            "week_start": week_dates[0].isoformat(),
            "week_end": week_dates[-1].isoformat(),
            "placed_slots": placed_quota_count
        }

    @classmethod
    def _apply_geo_grouping(cls, db: Session, daily_slots: Dict[date, List[Dict[str, Any]]], week_dates: List[date], today: date):
        """Если на день запланирован выезд в локацию, подтянуть мелкие задачи туда же"""
        for d in week_dates:
            if d < today:
                continue
            slots = daily_slots[d]
            visited_locations = set()
            for s in slots:
                if s["task"].location_id:
                    visited_locations.add(s["task"].location_id)

            for loc_id in visited_locations:
                todo_for_loc = db.query(Task).filter(
                    Task.location_id == loc_id,
                    Task.status == TaskStatus.TODO,
                    Task.scheduled_start == None
                ).order_by(Task.priority.asc()).all()

                for t in todo_for_loc:
                    slot = cls._find_free_slot(daily_slots, d, t.duration_minutes)
                    if slot:
                        t.scheduled_start = slot[0]
                        t.scheduled_end = slot[1]
                        t.status = TaskStatus.SCHEDULED
                        t.is_auto_placed = True
                        slots.append({"start": slot[0], "end": slot[1], "task": t})

    @classmethod
    def _find_free_slot(cls, daily_slots: Dict[date, List[Dict[str, Any]]], target_date: date, duration_minutes: int) -> Optional[tuple[datetime, datetime]]:
        """Ищет свободный временной блок в окне 09:00 - 22:00 на указанный день"""
        day_slots = sorted(daily_slots.get(target_date, []), key=lambda s: s["start"])

        # Check total daily load
        current_daily_minutes = sum(
            int((s["end"] - s["start"]).total_seconds() / 60) for s in day_slots
        )
        if current_daily_minutes + duration_minutes > cls.MAX_DAILY_BUSY_MINUTES:
            return None

        day_start = datetime.combine(target_date, time(cls.DAY_START_HOUR, 0))
        day_end = datetime.combine(target_date, time(cls.DAY_END_HOUR, 0))

        cursor = day_start
        for s in day_slots:
            s_start = s["start"]
            s_end = s["end"]
            if s_start > cursor:
                gap_minutes = int((s_start - cursor).total_seconds() / 60)
                if gap_minutes >= duration_minutes:
                    return (cursor, cursor + timedelta(minutes=duration_minutes))
            if s_end > cursor:
                cursor = s_end

        if cursor < day_end:
            gap_minutes = int((day_end - cursor).total_seconds() / 60)
            if gap_minutes >= duration_minutes:
                return (cursor, cursor + timedelta(minutes=duration_minutes))

        return None

    @classmethod
    def _find_first_available_slot(cls, daily_slots: Dict[date, List[Dict[str, Any]]], week_dates: List[date], today: date, duration_minutes: int) -> Optional[tuple[datetime, datetime]]:
        """Ищет первое доступное окно в текущей неделе, начиная с сегодня"""
        for d in week_dates:
            if d < today:
                continue
            slot = cls._find_free_slot(daily_slots, d, duration_minutes)
            if slot:
                return slot
        return None
