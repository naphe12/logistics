from enum import Enum


class UserTypeEnum(str, Enum):
    customer = "customer"
    business = "business"
    agent = "agent"
    hub = "hub"
    driver = "driver"
    admin = "admin"


class CodePurposeEnum(str, Enum):
    pickup = "pickup"
    delivery = "delivery"
    otp = "otp"
    payment = "payment"


class NotificationChannelEnum(str, Enum):
    sms = "sms"
    ussd = "ussd"
    push = "push"
    email = "email"
