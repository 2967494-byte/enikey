from datetime import date, datetime
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import extract, func
from app.core.models import IpIncome, IpPaymentGround, IpTaxPayment

FIXED_RATES = {
    2023: 45842.0,
    2024: 49500.0,
    2025: 53658.0,
    2026: 57390.0,
    2027: 61154.0,
}
FIXED_CONTRIBUTIONS = FIXED_RATES
FIXED_CONTRIBUTIONS_BY_YEAR = FIXED_RATES

RU_MONTHS = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"
]

def get_ip_incomes_grouped_by_month(db: Session) -> List[Dict[str, Any]]:
    """Группирует все поступления ИП по Году и Месяцу в порядке убывания дат."""
    incomes = db.query(IpIncome).order_by(IpIncome.payment_date.desc(), IpIncome.id.desc()).all()
    
    groups_dict = {}
    today = date.today()

    for inc in incomes:
        y = inc.payment_date.year
        m = inc.payment_date.month
        key = (y, m)
        if key not in groups_dict:
            groups_dict[key] = {
                "year": y,
                "month": m,
                "month_name": f"{RU_MONTHS[m]} {y}",
                "is_current": (y == today.year and m == today.month),
                "total_amount": 0.0,
                "incomes": [],
                "items": []
            }
        groups_dict[key]["total_amount"] += float(inc.amount)
        groups_dict[key]["incomes"].append(inc)
        groups_dict[key]["items"].append(inc)

    return list(groups_dict.values())

def calculate_ip_taxes(db: Session, target_year: Optional[int] = None) -> Dict[str, Any]:
    """
    Расчет налогов УСН 6% (Доходы) и страховых взносов ИП за себя.
    Учитывает правила ФЗ № 389-ФЗ: налог уменьшается до 100% на подлежащие уплате взносы.
    """
    today = date.today()
    year = target_year or today.year

    start_of_year = date(year, 1, 1)
    end_of_year = date(year, 12, 31)

    # 1. Поступления за выбранный год
    year_incomes = db.query(IpIncome).filter(
        IpIncome.payment_date >= start_of_year,
        IpIncome.payment_date <= end_of_year
    ).order_by(IpIncome.payment_date.asc()).all()

    # Разделение по кварталам
    q1_incomes = [i for i in year_incomes if 1 <= i.payment_date.month <= 3]
    q2_incomes = [i for i in year_incomes if 4 <= i.payment_date.month <= 6]
    q3_incomes = [i for i in year_incomes if 7 <= i.payment_date.month <= 9]
    q4_incomes = [i for i in year_incomes if 10 <= i.payment_date.month <= 12]

    sum_q1 = sum(float(i.amount) for i in q1_incomes)
    sum_q2 = sum(float(i.amount) for i in q2_incomes)
    sum_q3 = sum(float(i.amount) for i in q3_incomes)
    sum_q4 = sum(float(i.amount) for i in q4_incomes)

    # Нарастающий итог доходов
    rev_q1 = sum_q1
    rev_h1 = rev_q1 + sum_q2
    rev_9m = rev_h1 + sum_q3
    rev_year = rev_9m + sum_q4

    # Исчисленный налог (6%) нарастающим итогом
    tax_q1_raw = round(rev_q1 * 0.06, 2)
    tax_h1_raw = round(rev_h1 * 0.06, 2)
    tax_9m_raw = round(rev_9m * 0.06, 2)
    tax_year_raw = round(rev_year * 0.06, 2)

    # 2. Страховые взносы ИП за себя
    fixed_contributions = FIXED_RATES.get(year, 57390.0)
    one_percent_base = max(0.0, rev_year - 300000.0)
    one_percent_amount = round(one_percent_base * 0.01, 2)
    total_contributions = round(fixed_contributions + one_percent_amount, 2)

    # 3. Налоговый вычет (уменьшение налога на взносы по 389-ФЗ)
    # Налог можно уменьшать на всю годовую сумму взносов вплоть до нуля (100% вычет)
    deduction_q1 = min(tax_q1_raw, fixed_contributions)
    advance_q1_due = max(0.0, round(tax_q1_raw - deduction_q1, 2))

    deduction_h1 = min(tax_h1_raw, fixed_contributions)
    advance_q2_due = max(0.0, round(tax_h1_raw - deduction_h1 - advance_q1_due, 2))

    deduction_9m = min(tax_9m_raw, fixed_contributions)
    advance_q3_due = max(0.0, round(tax_9m_raw - deduction_9m - advance_q1_due - advance_q2_due, 2))

    deduction_year = min(tax_year_raw, total_contributions)
    tax_year_due = max(0.0, round(tax_year_raw - deduction_year - advance_q1_due - advance_q2_due - advance_q3_due, 2))

    total_usn_due = round(advance_q1_due + advance_q2_due + advance_q3_due + tax_year_due, 2)

    # Фактические платежи из базы данных
    actual_payments = db.query(IpTaxPayment).filter(IpTaxPayment.year == year).all()
    paid_map = {}
    for ap in actual_payments:
        paid_map[ap.period] = paid_map.get(ap.period, 0.0) + float(ap.amount)

    paid_q1 = paid_map.get("Q1", 0.0)
    paid_q2 = paid_map.get("Q2", 0.0)
    paid_q3 = paid_map.get("Q3", 0.0)
    paid_year = paid_map.get("YEAR", 0.0)
    paid_fixed = paid_map.get("FIXED", 0.0)
    paid_one_percent = paid_map.get("ONE_PERCENT", 0.0)

    # Сроки уплаты
    d_q1 = date(year, 4, 28)
    d_q2 = date(year, 7, 28)
    d_q3 = date(year, 10, 28)
    d_fixed = date(year, 12, 31)
    d_year = date(year + 1, 4, 28)
    d_one_percent = date(year + 1, 7, 1)

    quarters = [
        {
            "key": "Q1",
            "title": "1 квартал",
            "period_text": "01.01 – 31.03",
            "deadline_date": d_q1,
            "deadline_text": f"28 апреля {year}",
            "revenue": round(sum_q1, 2),
            "cum_revenue": round(rev_q1, 2),
            "tax_raw": round(tax_q1_raw, 2),
            "deduction": round(deduction_q1, 2),
            "due": advance_q1_due,
            "paid": paid_q1,
            "status": "PAID" if paid_q1 >= advance_q1_due and advance_q1_due > 0 else ("ZERO" if advance_q1_due == 0 else ("OVERDUE" if today > d_q1 else "WAITING"))
        },
        {
            "key": "Q2",
            "title": "2 квартал (полугодие)",
            "period_text": "01.04 – 30.06",
            "deadline_date": d_q2,
            "deadline_text": f"28 июля {year}",
            "revenue": round(sum_q2, 2),
            "cum_revenue": round(rev_h1, 2),
            "tax_raw": round(tax_h1_raw, 2),
            "deduction": round(deduction_h1, 2),
            "due": advance_q2_due,
            "paid": paid_q2,
            "status": "PAID" if paid_q2 >= advance_q2_due and advance_q2_due > 0 else ("ZERO" if advance_q2_due == 0 else ("OVERDUE" if today > d_q2 else "WAITING"))
        },
        {
            "key": "Q3",
            "title": "3 квартал (9 месяцев)",
            "period_text": "01.07 – 30.09",
            "deadline_date": d_q3,
            "deadline_text": f"28 октября {year}",
            "revenue": round(sum_q3, 2),
            "cum_revenue": round(rev_9m, 2),
            "tax_raw": round(tax_9m_raw, 2),
            "deduction": round(deduction_9m, 2),
            "due": advance_q3_due,
            "paid": paid_q3,
            "status": "PAID" if paid_q3 >= advance_q3_due and advance_q3_due > 0 else ("ZERO" if advance_q3_due == 0 else ("OVERDUE" if today > d_q3 else "WAITING"))
        },
        {
            "key": "YEAR",
            "title": "4 квартал (Итог за год)",
            "period_text": "01.10 – 31.12",
            "deadline_date": d_year,
            "deadline_text": f"28 апреля {year + 1}",
            "revenue": round(sum_q4, 2),
            "cum_revenue": round(rev_year, 2),
            "tax_raw": round(tax_year_raw, 2),
            "deduction": round(deduction_year, 2),
            "due": tax_year_due,
            "paid": paid_year,
            "status": "PAID" if paid_year >= tax_year_due and tax_year_due > 0 else ("ZERO" if tax_year_due == 0 else ("OVERDUE" if today > d_year else "WAITING"))
        }
    ]

    # Календарь ближайших платежей (Ближайшие дедлайны)
    milestones = [
        {
            "key": "Q1",
            "title": f"Аванс УСН 6% за 1 кв. {year}",
            "due_amount": advance_q1_due,
            "paid_amount": paid_q1,
            "deadline": d_q1,
            "description": f"Авансовый платеж УСН от выручки {sum_q1:,.0f} ₽".replace(",", " ")
        },
        {
            "key": "Q2",
            "title": f"Аванс УСН 6% за 2 кв. {year}",
            "due_amount": advance_q2_due,
            "paid_amount": paid_q2,
            "deadline": d_q2,
            "description": f"Авансовый платеж УСН от выручки {sum_q2:,.0f} ₽".replace(",", " ")
        },
        {
            "key": "Q3",
            "title": f"Аванс УСН 6% за 3 кв. {year}",
            "due_amount": advance_q3_due,
            "paid_amount": paid_q3,
            "deadline": d_q3,
            "description": f"Авансовый платеж УСН от выручки {sum_q3:,.0f} ₽".replace(",", " ")
        },
        {
            "key": "FIXED",
            "title": f"Фиксированные взносы ИП за {year} год",
            "due_amount": fixed_contributions,
            "paid_amount": paid_fixed,
            "deadline": d_fixed,
            "description": f"Обязательные взносы в Соцфонд (ОПС + ОМС)"
        },
        {
            "key": "YEAR",
            "title": f"Итоговый налог УСН 6% за {year} год",
            "due_amount": tax_year_due,
            "paid_amount": paid_year,
            "deadline": d_year,
            "description": f"Окончательный расчет налога за весь {year} год"
        },
        {
            "key": "ONE_PERCENT",
            "title": f"Взнос 1% с доходов свыше 300 000 ₽ за {year}",
            "due_amount": one_percent_amount,
            "paid_amount": paid_one_percent,
            "deadline": d_one_percent,
            "description": f"Пенсионный взнос 1% от суммы {one_percent_base:,.0f} ₽".replace(",", " ")
        }
    ]

    # Вычисляем статус и дни для каждого платежа
    for m in milestones:
        diff_days = (m["deadline"] - today).days
        m["days_remaining"] = diff_days
        m["is_paid"] = m["paid_amount"] >= m["due_amount"] and m["due_amount"] > 0
        m["is_zero"] = m["due_amount"] == 0
        m["is_overdue"] = diff_days < 0 and not m["is_paid"] and not m["is_zero"]

    # Ближайшие платежи (не оплаченные или предстоящие)
    upcoming_payments = [m for m in milestones if not m["is_paid"] and not m["is_zero"]]
    upcoming_payments.sort(key=lambda x: x["deadline"])

    # Года, в которых есть поступления (для селектора)
    dates_db = db.query(IpIncome.payment_date).all()
    available_years = sorted(list(set([d[0].year for d in dates_db if d[0]] + [today.year, today.year - 1])), reverse=True)

    # Сводные показатели за все время
    all_time_income = db.query(func.coalesce(func.sum(IpIncome.amount), 0)).scalar() or 0.0
    all_time_count = db.query(func.count(IpIncome.id)).scalar() or 0

    return {
        "selected_year": year,
        "available_years": available_years,
        "rev_year": round(rev_year, 2),
        "fixed_contributions": round(fixed_contributions, 2),
        "one_percent_base": round(one_percent_base, 2),
        "one_percent_amount": round(one_percent_amount, 2),
        "total_contributions": round(total_contributions, 2),
        "tax_year_raw": round(tax_year_raw, 2),
        "total_usn_due": round(total_usn_due, 2),
        "total_paid_year": round(sum(paid_map.values()), 2),
        "quarters": quarters,
        "milestones": milestones,
        "upcoming_payments": upcoming_payments,
        "all_time_income": float(all_time_income),
        "all_time_count": all_time_count
    }
