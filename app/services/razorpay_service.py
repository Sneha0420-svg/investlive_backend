import razorpay

from app.core.config import settings


client = razorpay.Client(
    auth=(
        settings.RAZORPAY_KEY_ID,
        settings.RAZORPAY_KEY_SECRET
    )
)

from uuid import uuid4


def create_order(
    amount: float,
    currency: str = "INR"
):
    """
    amount = Rupees
    Razorpay expects amount in paise.
    """

    receipt = f"INV-{uuid4().hex[:12].upper()}"

    order = client.order.create(
        {
            "amount": int(amount * 100),
            "currency": currency,
            "receipt": receipt,
            "payment_capture": 1
        }
    )

    return order


def verify_signature(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str
):
    """
    Returns True if signature is valid.
    """

    try:

        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )

        return True

    except razorpay.errors.SignatureVerificationError:

        return False
    
    
def verify_signature(
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str
):
    """
    Returns True if signature is valid.
    """

    try:

        client.utility.verify_payment_signature(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )

        return True

    except razorpay.errors.SignatureVerificationError:

        return False
    
def fetch_payment(
    payment_id: str
):
    return client.payment.fetch(payment_id)

def fetch_order(
    order_id: str
):
    return client.order.fetch(order_id)


def refund_payment(
    payment_id: str,
    amount=None
):
    """
    amount=None -> Full Refund

    amount=500
    means ₹5.00
    """

    data = {}

    if amount:
        data["amount"] = amount

    return client.payment.refund(
        payment_id,
        data
    )
    
    
def verify_webhook_signature(
    body: bytes,
    signature: str
):
    try:

        client.utility.verify_webhook_signature(
            body,
            signature,
            settings.RAZORPAY_WEBHOOK_SECRET
        )

        return True

    except razorpay.errors.SignatureVerificationError:

        return False