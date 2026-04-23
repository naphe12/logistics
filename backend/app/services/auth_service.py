from sqlalchemy.orm import Session
from app.models.users import User
from app.security import create_access_token
from app.enums import UserTypeEnum


def login_or_create(db: Session, phone_e164: str) -> str:
    user = db.query(User).filter(User.phone_e164 == phone_e164).first()
    if not user:
        user = User(phone_e164=phone_e164, user_type=UserTypeEnum.customer)
        db.add(user)
        db.commit()
        db.refresh(user)
    return create_access_token(str(user.id))
