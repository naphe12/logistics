from fastapi import APIRouter, Depends, Form
from sqlalchemy.orm import Session
from fastapi.responses import PlainTextResponse
from app.database import get_db
from app.services.ussd_service import handle_ussd

router = APIRouter(prefix="/ussd", tags=["ussd"])


@router.post("", response_class=PlainTextResponse)
def ussd_endpoint(
    sessionId: str = Form(...),
    serviceCode: str = Form(...),
    phoneNumber: str = Form(...),
    text: str = Form(""),
    db: Session = Depends(get_db),
):
    return handle_ussd(db, sessionId, serviceCode, phoneNumber, text)
