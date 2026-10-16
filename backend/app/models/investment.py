from typing import Optional

from sqlmodel import Field, SQLModel

# The kinds we recognise. Front-end presents these in a dropdown; the DB
# stores the plain string so adding a new kind later is a no-op migration.
INVESTMENT_KINDS = {
    "fd",           # Fixed deposit
    "rd",           # Recurring deposit
    "sip",          # Systematic investment plan (mutual fund SIP)
    "mutual_fund",  # Lump-sum mutual fund investment
    "stock",        # Direct equity
    "bond",         # Bonds / debentures
    "gold",         # Gold / SGB / ETF
    "ppf_epf",      # PPF / EPF / NPS-like retirement corpora
    "other",
}


class Investment(SQLModel, table=True):
    """A household-level asset that appreciates over time. This is a
    tracker — values are manually entered/updated by the user; nothing on
    this row moves account balances automatically. The Tools calculators
    can produce a projected `current_value` that the user then saves."""

    id: Optional[int] = Field(default=None, primary_key=True)
    household_id: int = Field(index=True, foreign_key="household.id")
    name: str
    kind: str = "other"
    institution: str = ""            # bank / broker / AMC — free text
    amount_invested: float = 0       # total principal (sum of contributions)
    current_value: float = 0         # market/maturity value as of today
    annual_return_pct: float = 0     # expected or realised return %
    monthly_contribution: float = 0  # for SIPs/RDs; 0 for lump-sum products
    start_date: str = ""             # YYYY-MM-DD
    maturity_date: str = ""          # YYYY-MM-DD, optional
    notes: str = ""
    # A closed holding is no longer an asset — its proceeds went to a
    # bank (withdrawal) or into a successor holding (reinvest). The row
    # stays so contribution history is still inspectable.
    closed: bool = False
    closed_at: str = ""              # YYYY-MM-DD
    closed_to_account: str = ""      # Account.name the proceeds landed in
    successor_id: Optional[int] = Field(default=None)
    created_at: str = ""
    updated_at: Optional[str] = None
