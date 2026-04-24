from fastapi import APIRouter, Depends, Form
from sqlalchemy.orm import Session
from fastapi.responses import PlainTextResponse
from app.database import get_db
from app.services.ussd_service import handle_ussd

router = APIRouter(prefix="/ussd", tags=["ussd"])


@router.post("", response_class=PlainTextResponse)
def ussd_endpoint(
    sessionId: str = Form(..., min_length=1, max_length=120),
    serviceCode: str = Form(..., min_length=1, max_length=32),
    phoneNumber: str = Form(..., min_length=8, max_length=20),
    text: str = Form("", max_length=512),
    db: Session = Depends(get_db),
):
    return handle_ussd(db, sessionId, serviceCode, phoneNumber, text)
