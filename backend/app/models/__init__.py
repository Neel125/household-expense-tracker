"""SQLModel tables. Importing this package registers every table on the
shared metadata (see core.database.init_db)."""
from app.models.account import Account
from app.models.budget import CategoryBudget
from app.models.category import Category
from app.models.debt import Debt
from app.models.goal import Goal
from app.models.household import Household
from app.models.income import IncomeSource
from app.models.investment import Investment
from app.models.invite import Invite
from app.models.member import Member
from app.models.referral import Referral
from app.models.reward import (
    ChallengeEnrollment,
    CoinTransaction,
    HealthSnapshot,
)
from app.models.transaction import Transaction
from app.models.user import User
from app.models.vehicle import Vehicle, VehicleRecord

__all__ = [
    "Account",
    "CategoryBudget",
    "Category",
    "ChallengeEnrollment",
    "CoinTransaction",
    "Debt",
    "Goal",
    "HealthSnapshot",
    "Household",
    "IncomeSource",
    "Investment",
    "Invite",
    "Member",
    "Referral",
    "Transaction",
    "User",
    "Vehicle",
    "VehicleRecord",
]
