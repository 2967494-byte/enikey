from datetime import date, timedelta
from typing import Dict, Any, List
from sqlalchemy.orm import Session
from app.core.models import FinanceRecord, FinanceRecordType, FinanceStatus, WalletState

class BudgetGuard:
    @staticmethod
    def get_financial_radar(db: Session) -> Dict[str, Any]:
        """
        Расчет финансового радара на 14 и 30 дней вперед.
        Доступный лимит = Текущий баланс + Ожидаемые поступления - Обязательные расходы.
        """
        wallet = db.query(WalletState).first()
        if not wallet:
            wallet = WalletState(current_balance=0.0, safety_threshold=50000.0)
            db.add(wallet)
            db.commit()
            db.refresh(wallet)

        current_balance = float(wallet.current_balance or 0.0)
        safety_threshold = float(wallet.safety_threshold or 0.0)

        today = date.today()
        date_14d = today + timedelta(days=14)
        date_30d = today + timedelta(days=30)

        # Get planned records
        records = db.query(FinanceRecord).filter(
            FinanceRecord.status == FinanceStatus.PLANNED,
            FinanceRecord.planned_date >= today,
            FinanceRecord.planned_date <= date_30d
        ).order_by(FinanceRecord.planned_date.asc()).all()

        income_14d = 0.0
        income_30d = 0.0
        mandatory_14d = 0.0
        mandatory_30d = 0.0
        birthdays_14d = 0.0
        birthdays_30d = 0.0
        wishlist_14d = 0.0
        wishlist_30d = 0.0

        upcoming_mandatory_items: List[Dict[str, Any]] = []

        for r in records:
            amt = float(r.amount)
            is_within_14 = r.planned_date <= date_14d

            if r.record_type == FinanceRecordType.INCOME_EXPECTED:
                income_30d += amt
                if is_within_14:
                    income_14d += amt
            elif r.record_type == FinanceRecordType.EXPENSE_MANDATORY:
                mandatory_30d += amt
                if is_within_14:
                    mandatory_14d += amt
                    upcoming_mandatory_items.append({
                        "title": r.title,
                        "amount": amt,
                        "date": r.planned_date.isoformat(),
                        "days_left": (r.planned_date - today).days,
                        "type": "Обязательный платеж"
                    })
            elif r.record_type == FinanceRecordType.EXPENSE_BIRTHDAY:
                birthdays_30d += amt
                if is_within_14:
                    birthdays_14d += amt
                    upcoming_mandatory_items.append({
                        "title": f"🎉 {r.title}",
                        "amount": amt,
                        "date": r.planned_date.isoformat(),
                        "days_left": (r.planned_date - today).days,
                        "type": "День рождения"
                    })
            elif r.record_type == FinanceRecordType.EXPENSE_WISHLIST:
                wishlist_30d += amt
                if is_within_14:
                    wishlist_14d += amt

        # Formulas
        total_mandatory_14d = mandatory_14d + birthdays_14d
        total_mandatory_30d = mandatory_30d + birthdays_30d

        available_limit_14d = current_balance + income_14d - total_mandatory_14d
        available_limit_30d = current_balance + income_30d - total_mandatory_30d

        has_deficit_14d = available_limit_14d < 0
        is_below_safety_14d = available_limit_14d < safety_threshold

        alerts: List[str] = []
        if has_deficit_14d:
            alerts.append(
                f"🚨 Внимание! Кассовый разрыв в ближайшие 14 дней. Дефицит: {abs(available_limit_14d):,.0f} ₽. "
                f"Обязательные списания: {total_mandatory_14d:,.0f} ₽."
            )
        elif is_below_safety_14d:
            alerts.append(
                f"⚠️ Внимание! Через 14 дней доступный остаток ({available_limit_14d:,.0f} ₽) "
                f"опустится ниже порога безопасности ({safety_threshold:,.0f} ₽)."
            )

        return {
            "current_balance": current_balance,
            "safety_threshold": safety_threshold,
            "available_limit_14d": available_limit_14d,
            "available_limit_30d": available_limit_30d,
            "income_14d": income_14d,
            "income_30d": income_30d,
            "mandatory_14d": total_mandatory_14d,
            "mandatory_30d": total_mandatory_30d,
            "wishlist_14d": wishlist_14d,
            "wishlist_30d": wishlist_30d,
            "has_deficit_14d": has_deficit_14d,
            "is_below_safety_14d": is_below_safety_14d,
            "upcoming_mandatory_items": upcoming_mandatory_items,
            "alerts": alerts
        }
