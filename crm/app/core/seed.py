from datetime import date, datetime, timedelta, time
from sqlalchemy.orm import Session
from app.core.models import (
    Location, Project, ProjectType, ProjectStage,
    SupplyItem, SupplyStatus, PaymentSettlement,
    Task, TaskStatus,
    FinanceRecord, FinanceRecordType, FinanceStatus, RecurrenceType,
    WalletState
)

def seed_initial_data(db: Session):
    # Check if already seeded
    if db.query(Project).count() > 0:
        return

    print("Seeding initial data for Personal ERP (Второй Мозг)...")

    # 1. Locations
    locations = [
        Location(name="Дом", color="#10b981"),
        Location(name="Офис 1", color="#6366f1"),
        Location(name="Офис 2", color="#8b5cf6"),
        Location(name="ПВЗ / Доставка", color="#f59e0b"),
        Location(name="Автосервис", color="#ef4444")
    ]
    db.add_all(locations)
    db.flush()

    loc_map = {loc.name: loc.id for loc in locations}

    # 2. Wallet
    wallet = WalletState(
        current_balance=185000.0,
        safety_threshold=60000.0
    )
    db.add(wallet)
    db.flush()

    today = date.today()

    # 3. Project: IT_SYSTEM (Enikey & Servers)
    proj_it = Project(
        title="Инфраструктура Enikey & VPN",
        description="Сайт enikey.tech, XRay Reality мост США-РФ, резервные копии и продление SSL/доменов.",
        project_type=ProjectType.IT_SYSTEM,
        stage=ProjectStage.ACTIVE,
        priority=1,
        color_hex="#4f46e5",
        weekly_quota_minutes=120,
        preferred_slot_minutes=60,
        template_payload={
            "domains": ["enikey.tech", "www.enikey.tech"],
            "ssl_expires_at": (today + timedelta(days=85)).isoformat(),
            "servers": [
                {"ip": "95.163.229.153", "provider": "Reg.ru МСК", "monthly_cost": 450, "pay_day": 15},
                {"ip": "192.236.187.178", "provider": "HostEONS США", "monthly_cost": 650, "pay_day": 20}
            ],
            "access_notes": "SSH ключи ed25519 в ~/.ssh/id_ed25519. Порты: 8443 Nginx, 10443 WS, 443 HAProxy.",
            "backlog_notes": "Настроить автоматический бекап базы данных sqlite раз в неделю."
        }
    )
    db.add(proj_it)
    db.flush()

    # 4. Project: DIY_BUILD (3D-принтер Voron 2.4)
    proj_diy = Project(
        title="Сборка 3D-принтера Voron 2.4",
        description="Проект сборки высокоточного 3D-принтера с областью печати 350x350мм.",
        project_type=ProjectType.DIY_BUILD,
        stage=ProjectStage.ACTIVE,
        priority=2,
        color_hex="#06b6d4",
        weekly_quota_minutes=180,
        preferred_slot_minutes=90,
        template_payload={
            "specs": "Кинематика CoreXY, рельсы MGN12, плата BTT Octopus Pro, стол 220V.",
            "budget_limit": 95000.0
        }
    )
    db.add(proj_diy)
    db.flush()

    # 5. Project: AUTO (Автомобиль ТО)
    proj_auto = Project(
        title="Обслуживание автомобиля",
        description="Регулярный контроль пробега, замена масла и страховка.",
        project_type=ProjectType.AUTO,
        stage=ProjectStage.ACTIVE,
        priority=2,
        color_hex="#f97316",
        weekly_quota_minutes=60,
        preferred_slot_minutes=60,
        template_payload={
            "car_model": "Skoda Octavia A7",
            "current_mileage": 108400,
            "last_to_mileage": 100000,
            "to_interval_km": 10000,
            "insurance_until": (today + timedelta(days=120)).isoformat(),
            "service_log": "100 000 км: Замена масла Motul 5W-40, фильтры салона и воздуха."
        }
    )
    db.add(proj_auto)
    db.flush()

    # 6. Project: LOAN (Автокредит)
    proj_loan = Project(
        title="Автокредит Альфа-Банк",
        description="Погашение кредита на покупку авто.",
        project_type=ProjectType.LOAN,
        stage=ProjectStage.ACTIVE,
        priority=1,
        color_hex="#ef4444",
        weekly_quota_minutes=0,
        template_payload={
            "bank_name": "Альфа-Банк",
            "total_loan_amount": 600000.0,
            "remaining_balance": 240000.0,
            "interest_rate": 14.5,
            "monthly_payment": 24500.0,
            "payment_day": 25
        }
    )
    db.add(proj_loan)
    db.flush()

    # 7. Project: HOUSEHOLD (Быт и Офис)
    proj_house = Project(
        title="Офис 1 и Домашние дела",
        description="Текущие задачи по оборудованию рабочих пространств.",
        project_type=ProjectType.HOUSEHOLD,
        stage=ProjectStage.ACTIVE,
        priority=3,
        color_hex="#10b981",
        weekly_quota_minutes=120
    )
    db.add(proj_house)
    db.flush()

    # 8. Supply items
    supplies = [
        SupplyItem(
            project_id=proj_diy.id,
            item_name="Рельсы направляющие MGN12H 350mm (комплект)",
            status=SupplyStatus.IN_STOCK,
            vendor="AliExpress",
            cost=6400.0
        ),
        SupplyItem(
            project_id=proj_diy.id,
            item_name="Шаговые двигатели NEMA 17 Moons",
            status=SupplyStatus.ARRIVED_AT_PICKUP,
            vendor="Ozon ПВЗ",
            order_link_or_track="OZON-9482718",
            cost=5200.0
        ),
        SupplyItem(
            project_id=proj_diy.id,
            item_name="Блок питания MeanWell 24V 350W",
            status=SupplyStatus.ORDERED_IN_TRANSIT,
            vendor="Чип и Дип",
            expected_date=today + timedelta(days=4),
            cost=4800.0
        ),
        SupplyItem(
            project_id=proj_diy.id,
            item_name="Экструдер Stealthburner с мотором",
            status=SupplyStatus.NEED_TO_BUY,
            vendor="AliExpress",
            cost=3900.0
        ),
        # Order for friend
        SupplyItem(
            project_id=proj_house.id,
            item_name="SSD NVMe Samsung 980 1TB",
            status=SupplyStatus.ARRIVED_AT_PICKUP,
            vendor="DNS",
            cost=8500.0,
            target_person="Иван (коллега)",
            payment_settlement=PaymentSettlement.PAID_BY_ME_DEBT
        )
    ]
    db.add_all(supplies)
    db.flush()

    # 9. Tasks
    tasks = [
        Task(
            project_id=proj_house.id,
            location_id=loc_map["Офис 1"],
            title="Сделать домофон и подключить панель вызова",
            status=TaskStatus.SCHEDULED,
            priority=2,
            duration_minutes=90,
            hard_due_date=today,
            scheduled_start=datetime.combine(today, time(10, 0)),
            scheduled_end=datetime.combine(today, time(11, 30))
        ),
        Task(
            project_id=proj_house.id,
            location_id=loc_map["Офис 1"],
            title="Проверить разводку интернет-розеток (Офис 1)",
            status=TaskStatus.SCHEDULED,
            priority=3,
            duration_minutes=60,
            scheduled_start=datetime.combine(today, time(11, 30)),
            scheduled_end=datetime.combine(today, time(12, 30)),
            notes="Подтянута автопланировщиком по гео-группировке"
        ),
        Task(
            project_id=proj_diy.id,
            title="Собрать нижнюю раму и портал 3D-принтера",
            status=TaskStatus.BLOCKED,
            priority=2,
            duration_minutes=120,
            depends_on_supply_id=supplies[1].id, # waits for motors
            notes="Ждет забора моторов из ПВЗ"
        ),
        Task(
            project_id=proj_auto.id,
            location_id=loc_map["Автосервис"],
            title="Пройти ТО: замена масла и фильтров (Skoda Octavia)",
            status=TaskStatus.SCHEDULED,
            priority=1,
            duration_minutes=120,
            scheduled_start=datetime.combine(today + timedelta(days=2), time(14, 0)),
            scheduled_end=datetime.combine(today + timedelta(days=2), time(16, 0))
        ),
        Task(
            project_id=proj_house.id,
            location_id=loc_map["ПВЗ / Доставка"],
            title="Забрать заказ: SSD NVMe Samsung 980 (DNS)",
            status=TaskStatus.TODO,
            priority=2,
            duration_minutes=30,
            depends_on_supply_id=supplies[4].id
        )
    ]
    db.add_all(tasks)

    # 10. Finances
    finances = [
        FinanceRecord(
            project_id=proj_loan.id,
            title="Платеж по автокредиту",
            record_type=FinanceRecordType.EXPENSE_MANDATORY,
            amount=24500.0,
            planned_date=today + timedelta(days=6),
            is_annual_or_monthly=RecurrenceType.MONTHLY
        ),
        FinanceRecord(
            title="День рождения друга (Максим)",
            record_type=FinanceRecordType.EXPENSE_BIRTHDAY,
            amount=10000.0,
            planned_date=today + timedelta(days=9),
            is_annual_or_monthly=RecurrenceType.YEARLY
        ),
        FinanceRecord(
            project_id=proj_auto.id,
            title="Масло и расходники для ТО",
            record_type=FinanceRecordType.EXPENSE_MANDATORY,
            amount=12000.0,
            planned_date=today + timedelta(days=2)
        ),
        FinanceRecord(
            title="Ожидаемая выплата по контракту",
            record_type=FinanceRecordType.INCOME_EXPECTED,
            amount=150000.0,
            planned_date=today + timedelta(days=12)
        ),
        FinanceRecord(
            title="Покупка: Новый монитор 27' 4K (Wishlist)",
            record_type=FinanceRecordType.EXPENSE_WISHLIST,
            amount=38000.0,
            planned_date=today + timedelta(days=14)
        )
    ]
    db.add_all(finances)

    db.commit()
    print("Seeding completed successfully!")
