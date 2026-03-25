from pydantic import BaseModel
from typing import Optional, List


class WhatsAppMessage(BaseModel):
    object: str
    entry:  list


class ExpenseLog(BaseModel):
    credit_debit: str
    purpose:      str
    amount:       float
    balance:      float


class EmailRequest(BaseModel):
    to:      str
    subject: str
    body:    str


class CalendarEvent(BaseModel):
    title:       str
    start:       str
    end:         str
    description: Optional[str] = ""
    attendees:   Optional[List[str]] = []
