import json

from fastapi import (
    APIRouter,
    Request,
    Header,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session

from app.database import SessionLocal

from app.models.purchase import (
    PurchaseOrder,
    PurchasedDocument
)

from app.models.file import CompanyFile

from app.services.razorpay_service import (
    verify_webhook_signature
)


router = APIRouter(
    prefix="/webhook",
    tags=["Webhook"]
)

# -------------------- DB DEPENDENCY --------------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/razorpay")
async def razorpay_webhook(

    request: Request,

    x_razorpay_signature: str = Header(None),

    db: Session = Depends(get_db)

):

    try:


        # -----------------------------------------
        # 1. Read Raw Body
        # -----------------------------------------

        body = await request.body()



        if not x_razorpay_signature:

            raise HTTPException(

                status_code=400,

                detail="Missing signature"

            )



        # -----------------------------------------
        # 2. Verify Razorpay Signature
        # -----------------------------------------


        verified = verify_webhook_signature(

            body,

            x_razorpay_signature

        )


        if not verified:


            raise HTTPException(

                status_code=400,

                detail="Invalid webhook signature"

            )



        # -----------------------------------------
        # 3. Parse Event
        # -----------------------------------------


        payload = json.loads(body)



        event = payload.get(
            "event"
        )



        # -----------------------------------------
        # 4. Payment Captured
        # -----------------------------------------


        if event == "payment.captured":


            payment = (

                payload
                ["payload"]
                ["payment"]
                ["entity"]

            )


            razorpay_payment_id = (
                payment["id"]
            )


            razorpay_order_id = (
                payment["order_id"]
            )



            order = (

                db.query(PurchaseOrder)

                .filter(

                    PurchaseOrder.razorpay_order_id
                    ==
                    razorpay_order_id

                )

                .first()

            )



            if order:


                order.status = "PAID"


                order.razorpay_payment_id = (
                    razorpay_payment_id
                )



                db.commit()



        # -----------------------------------------
        # 5. Payment Failed
        # -----------------------------------------


        elif event == "payment.failed":


            payment = (

                payload
                ["payload"]
                ["payment"]
                ["entity"]

            )


            razorpay_order_id = (
                payment.get("order_id")
            )



            order = (

                db.query(PurchaseOrder)

                .filter(

                    PurchaseOrder.razorpay_order_id
                    ==
                    razorpay_order_id

                )

                .first()

            )



            if order:


                order.status = "FAILED"


                db.commit()



        return {


            "success": True

        }



    except HTTPException:

        raise



    except Exception as e:


        db.rollback()


        print(
            "RAZORPAY WEBHOOK ERROR:",
            str(e)
        )


        raise HTTPException(

            status_code=500,

            detail="Webhook processing failed"

        )