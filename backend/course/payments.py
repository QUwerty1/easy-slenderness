"""Платёжный сервис.

The module talks to the payment service only through ``get_gateway()``.
Personal data of the user is never sent: only the order id (internal numbers of
the user and the course), the course name and price and the return URL.

* ``FakeGateway`` (default, ``PAYMENT_GATEWAY = "fake"``) imitates the service for
  development: the payment page is the client route ``/payment/fake``.
* ``YooKassaGateway`` (``PAYMENT_GATEWAY = "yookassa"``) uses the YooKassa REST
  API v3; set ``YOOKASSA_SHOP_ID`` and ``YOOKASSA_SECRET_KEY``.
"""

import base64
import json
import uuid
from dataclasses import dataclass
from decimal import Decimal
from urllib import error, request
from urllib.parse import urlencode

from django.conf import settings


class GatewayError(Exception):
    """The payment service refused the operation or did not answer."""


@dataclass
class PaymentResult:
    order_id: str
    succeeded: bool
    amount: Decimal | None = None
    transaction_id: str = ""


def make_order_id(user_id, course_id):
    return f"{user_id}-{course_id}"


def parse_order_id(order_id):
    try:
        user_id, course_id = (int(part) for part in str(order_id).split("-"))
    except ValueError:
        return None
    return user_id, course_id


class FakeGateway:
    name = "fake"

    def create_payment(self, order_id, description, amount, return_url):
        query = urlencode(
            {
                "order": order_id,
                "amount": str(amount),
                "description": description,
                "return": return_url,
            }
        )
        return f"{settings.FRONTEND_URL}/payment/fake?{query}"

    def refund(self, transaction_id, amount):
        if not transaction_id:
            raise GatewayError("Не найден идентификатор платежа.")
        return f"refund-{uuid.uuid4().hex[:12]}"

    def parse_notification(self, payload):
        return PaymentResult(
            order_id=str(payload.get("order_id", "")),
            succeeded=bool(payload.get("success")),
            amount=Decimal(str(payload["amount"])) if payload.get("amount") else None,
            transaction_id=f"fake-{uuid.uuid4().hex[:12]}",
        )


class YooKassaGateway:
    name = "yookassa"
    api = "https://api.yookassa.ru/v3/"

    def _call(self, method, path, body=None):
        credentials = f"{settings.YOOKASSA_SHOP_ID}:{settings.YOOKASSA_SECRET_KEY}"
        headers = {
            "Authorization": "Basic " + base64.b64encode(credentials.encode()).decode(),
            "Content-Type": "application/json",
            "Idempotence-Key": str(uuid.uuid4()),
        }
        data = json.dumps(body).encode() if body is not None else None
        req = request.Request(
            self.api + path, data=data, headers=headers, method=method
        )
        try:
            with request.urlopen(req, timeout=15) as response:
                return json.load(response)
        except (error.URLError, TimeoutError, ValueError) as exc:
            raise GatewayError("Платёжный сервис не ответил.") from exc

    def create_payment(self, order_id, description, amount, return_url):
        data = self._call(
            "POST",
            "payments",
            {
                "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
                "capture": True,
                "confirmation": {"type": "redirect", "return_url": return_url},
                "description": description[:128],
                "metadata": {"order_id": order_id},
            },
        )
        return data["confirmation"]["confirmation_url"]

    def refund(self, transaction_id, amount):
        data = self._call(
            "POST",
            "refunds",
            {
                "payment_id": transaction_id,
                "amount": {"value": f"{amount:.2f}", "currency": "RUB"},
            },
        )
        if data.get("status") != "succeeded":
            raise GatewayError("Платёжный сервис отклонил возврат.")
        return data["id"]

    def parse_notification(self, payload):
        # The notification itself is not trusted: the payment is re-read from the API
        payment_id = (payload.get("object") or {}).get("id")
        if not payment_id:
            raise GatewayError("Неверное уведомление платёжного сервиса.")
        payment = self._call("GET", f"payments/{payment_id}")
        return PaymentResult(
            order_id=str((payment.get("metadata") or {}).get("order_id", "")),
            succeeded=payment.get("status") == "succeeded",
            amount=Decimal(payment["amount"]["value"]),
            transaction_id=payment["id"],
        )


GATEWAYS = {"fake": FakeGateway, "yookassa": YooKassaGateway}


def get_gateway():
    return GATEWAYS[getattr(settings, "PAYMENT_GATEWAY", "fake")]()
