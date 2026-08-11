from decimal import Decimal

from fastapi import (
    APIRouter,
    Depends,
    HTTPException
)

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.database import SessionLocal

from app.models.auth import User
from app.models.file import CompanyFile
from app.models.purchase import (
    PurchaseOrder,
    PurchasedDocument,
    PurchaseOrderItem
)

from app.schemas.purchase import (
    PurchaseCreateRequest
)

from app.dependencies.auth import (
    get_current_user
)

from app.services.razorpay_service import (
    create_order
)
from app.schemas.purchase import PaymentVerifyRequest

from app.services.razorpay_service import (
    verify_signature
)
from app.core.config import settings
router = APIRouter(
    prefix="/purchase",
    tags=["Purchase"]
)
# ---------------- DB Dependency ----------------
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# =====================================================
# CREATE PURCHASE ORDER
# =====================================================

@router.post("/create")
def create_purchase(
    request: PurchaseCreateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:

        # -------------------------------------------------
        # 1. Validate Request
        # -------------------------------------------------

        if not request.document_ids:
            raise HTTPException(
                status_code=400,
                detail="No documents selected"
            )

        document_ids = list(set(request.document_ids))

        # -------------------------------------------------
        # 2. Fetch Documents
        # -------------------------------------------------

        reports = (
            db.query(CompanyFile)
            .filter(
                CompanyFile.document_id.in_(document_ids)
            )
            .all()
        )

        if len(reports) != len(document_ids):

            found = {
                report.document_id
                for report in reports
            }

            missing = list(
                set(document_ids) - found
            )

            raise HTTPException(
                status_code=404,
                detail={
                    "message": "Some documents not found",
                    "missing": missing
                }
            )

        # -------------------------------------------------
        # 3. Check Already Purchased
        # -------------------------------------------------

        already_purchased = []

        for report in reports:

            exists = (
                db.query(PurchasedDocument)
                .filter(
                    PurchasedDocument.user_id == current_user.userid,
                    PurchasedDocument.document_id == report.document_id
                )
                .first()
            )

            if exists:
                already_purchased.append(
                    report.document_id
                )

        if already_purchased:

            raise HTTPException(
                status_code=400,
                detail={
                    "message": "Documents already purchased",
                    "documents": already_purchased
                }
            )
        
        # -------------------------------------------------
        # 4. Calculate & Validate Amount
        # -------------------------------------------------
        
        subtotal = Decimal("0.00")
        
        for report in reports:
            subtotal += Decimal(str(report.price or 0))
            
        # Bulk discount (10%)
        expected_discount = (
            subtotal * Decimal("0.10")
            if len(reports) > 1
            else Decimal("0.00")
        )
        taxable_amount = subtotal - expected_discount
        
        expected_gst = (taxable_amount * Decimal("0.18")).quantize(Decimal("0.01"))
        
        expected_total = ( taxable_amount + expected_gst).quantize(Decimal("0.01"))
        # Compare frontend amount
        if Decimal(str(request.total)).quantize(
            Decimal("0.01")
        ) != expected_total:
            
            raise HTTPException(status_code=400,
                                detail={
                                    "message": "Total amount mismatch",
                                    "expected": float(expected_total),
                                    "received": float(request.total)
                                })
        total_amount = expected_total

        
        # -------------------------------------------------
        # 5. Create Razorpay Order
        # -------------------------------------------------

        razorpay_order = create_order(
            float(total_amount)
        )

        # -------------------------------------------------
        # 6. Save Purchase Order
        # -------------------------------------------------

        purchase_order = PurchaseOrder(

            order_id=razorpay_order["id"],

            razorpay_order_id=razorpay_order["id"],

            receipt=razorpay_order["receipt"],

            user_id=current_user.userid,

            amount=float(total_amount),

            currency="INR",

            status="PENDING"
        )

        db.add(purchase_order)
        db.flush()
        
        # Save selected documents for this order
        for report in reports:
            item = PurchaseOrderItem(
                purchase_order_id=purchase_order.id,
                document_id=report.document_id,
                company=report.company,
                isin=report.isin,
                year=report.year,
                document_type=report.document_type,
                price=float(report.price),
                purchased_at=None
            )
            db.add(item)

        db.commit()

        db.refresh(purchase_order)

        # -------------------------------------------------
        # 7. Return Response
        # -------------------------------------------------

        return {

            "success": True,

            "purchase_id": purchase_order.id,

            "order_id": purchase_order.order_id,

            "razorpay_order_id": purchase_order.razorpay_order_id,

            "receipt": purchase_order.receipt,

            "amount": float(total_amount),
            "subtotal": float(subtotal),
            "discount": float(expected_discount),
            "gst": float(expected_gst),

            "currency": purchase_order.currency,

            "razorpay_key": settings.RAZORPAY_KEY_ID,

            "documents": [

                {
                    "document_id": report.document_id,
                    "company": report.company,
                    "year": report.year,
                    "document_type": report.document_type,
                    "price": float(report.price)
                }

                for report in reports

            ]

        }

    except HTTPException:
        raise

    except Exception as e:

        db.rollback()

        print("CREATE PURCHASE ERROR:", str(e))

        raise HTTPException(
            status_code=500,
            detail="Unable to create purchase order"
        )
        
        
@router.post("/verify")
def verify_payment(
    request: PaymentVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:

        # ---------------------------------------------
        # 1. Find Purchase Order
        # ---------------------------------------------

        order = (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.razorpay_order_id == request.razorpay_order_id,
                PurchaseOrder.user_id == current_user.userid
            )
            .first()
        )

        if not order:
            raise HTTPException(
                status_code=404,
                detail="Order not found"
            )

        # ---------------------------------------------
        # 2. Already Paid?
        # ---------------------------------------------

        if order.status == "PAID":
            return {
                "success": True,
                "message": "Payment already verified"
            }

        # ---------------------------------------------
        # 3. Verify Razorpay Signature
        # ---------------------------------------------

        verified = verify_signature(
            razorpay_order_id=request.razorpay_order_id,
            razorpay_payment_id=request.razorpay_payment_id,
            razorpay_signature=request.razorpay_signature
        )

        if not verified:

            order.status = "FAILED"

            db.commit()

            raise HTTPException(
                status_code=400,
                detail="Invalid payment signature"
            )

        # ---------------------------------------------
        # 4. Update Purchase Order
        # ---------------------------------------------

        order.status = "PAID"
        order.razorpay_payment_id = request.razorpay_payment_id
        order.razorpay_signature = request.razorpay_signature

        # ---------------------------------------------
        # 5. Save Purchased Documents
        # ---------------------------------------------

        for item in request.documents:

            report = (
                db.query(CompanyFile)
                .filter(
                    CompanyFile.document_id == item.document_id
                )
                .first()
            )

            if not report:
                continue

            already_exists = (
                db.query(PurchasedDocument)
                .filter(
                    PurchasedDocument.user_id == current_user.userid,
                    PurchasedDocument.document_id == report.document_id
                )
                .first()
            )

            if already_exists:
                continue

            purchased = PurchasedDocument(
                purchase_order_id=order.id,
                user_id=current_user.userid,
                document_id=report.document_id,
                company=report.company,
                year=report.year,
                document_type=report.document_type,
                price=float(report.price)
            )

            db.add(purchased)

        # ---------------------------------------------
        # 6. Commit
        # ---------------------------------------------

        db.commit()

        return {
            "success": True,
            "message": "Payment verified successfully",
            "order_id": order.order_id,
            "payment_id": order.razorpay_payment_id
        }

    except HTTPException:
        raise

    except Exception as e:

        db.rollback()

        print("VERIFY PAYMENT ERROR:", str(e))

        raise HTTPException(
            status_code=500,
            detail="Payment verification failed"
        )
@router.get("/check/{document_id}")
def check_purchase(

    document_id: str,

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db)

):

    try:


        purchase = (

            db.query(PurchasedDocument)

            .filter(

                PurchasedDocument.user_id
                ==
                current_user.userid,


                PurchasedDocument.document_id
                ==
                document_id

            )

            .first()

        )


        return {

            "success": True,

            "document_id":
            document_id,

            "purchased":
            purchase is not None

        }


    except Exception as e:


        raise HTTPException(

            status_code=500,

            detail=str(e)

        )
        
@router.get("/history")
def purchase_history(

    current_user: User = Depends(get_current_user),

    db: Session = Depends(get_db)

):

    try:


        orders = (

            db.query(PurchaseOrder)

            .filter(

                PurchaseOrder.user_id
                ==
                current_user.userid

            )

            .order_by(

                PurchaseOrder.created_at.desc()

            )

            .all()

        )


        response = []


        for order in orders:


            documents = (

                db.query(PurchaseOrderItem)

                .filter(

                    PurchaseOrderItem.purchase_order_id
                    ==
                    order.id

                )

                .all()

            )


            response.append({

                "order_id":
                order.order_id,


                "razorpay_order_id":
                order.razorpay_order_id,


                "payment_id":
                order.razorpay_payment_id,


                "amount":
                float(order.amount),


                "currency":
                order.currency,


                "status":
                order.status,


                "created_at":
                order.created_at,


                "documents":

                [

                    {

                        "document_id":
                        doc.document_id,


                        "company":
                        doc.company,
                        "isin":
                        doc.isin,


                        "year":
                        doc.year,


                        "document_type":
                        doc.document_type,


                        "price":
                        float(doc.price),


                        "purchased_at":
                        doc.purchased_at

                    }

                    for doc in documents

                ]

            })


        return {

            "success": True,

            "total":
            len(response),

            "purchases":
            response

        }


    except Exception as e:


        raise HTTPException(

            status_code=500,

            detail=str(e)

        )
        
@router.get("/order/{order_id}")
def get_order(
    order_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:

        # ---------------------------------------------
        # 1. Find Purchase Order
        # ---------------------------------------------

        order = (
            db.query(PurchaseOrder)
            .filter(
                PurchaseOrder.order_id == order_id,
                PurchaseOrder.user_id == current_user.userid
            )
            .first()
        )

        if not order:
            raise HTTPException(
                status_code=404,
                detail="Order not found"
            )

        # ---------------------------------------------
        # 2. Get documents selected for this order
        #    Works for PENDING / FAILED / PAID
        # ---------------------------------------------

        documents = (
            db.query(PurchaseOrderItem)
            .filter(
                PurchaseOrderItem.purchase_order_id == order.id
            )
            .all()
        )

        return {
            "success": True,

            "order": {
                "order_id": order.order_id,
                "razorpay_order_id": order.razorpay_order_id,
                "payment_id": order.razorpay_payment_id,
                "amount": float(order.amount),
                "currency": order.currency,
                "status": order.status,
                "created_at": order.created_at
            },

            "documents": [
                {
                    "document_id": doc.document_id,
                    "company": doc.company,
                    "year": doc.year,
                    "document_type": doc.document_type,
                    "price": float(doc.price)
                }
                for doc in documents
            ]
        }

    except HTTPException:
        raise

    except Exception as e:

        print("GET ORDER ERROR:", str(e))

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )
    
@router.get("/all-history")
def all_purchase_history(
    db: Session = Depends(get_db)
):
    try:

        orders = (
            db.query(PurchaseOrder)
            .order_by(
                PurchaseOrder.created_at.desc()
            )
            .all()
        )

        response = []

        for order in orders:

            documents = (
                db.query(PurchaseOrderItem)
                .filter(
                    PurchaseOrderItem.purchase_order_id == order.id
                )
                .all()
            )

            response.append({

                # Purchase order details
                "purchase_id": order.id,
                "order_id": order.order_id,
                "razorpay_order_id": order.razorpay_order_id,
                "payment_id": order.razorpay_payment_id,

                # User
                "user_id": order.user_id,

                # Payment
                "amount": float(order.amount),
                "currency": order.currency,
                "status": order.status,

                # Dates
                "created_at": order.created_at,

                # Purchased documents
                "documents": [
                    {
                        "document_id": doc.document_id,
                        "company": doc.company,
                        "isin": doc.isin,
                        "year": doc.year,
                        "document_type": doc.document_type,
                        "price": float(doc.price),
                        "purchased_at": doc.purchased_at
                    }
                    for doc in documents
                ]

            })

        return {
            "success": True,
            "total": len(response),
            "purchases": response
        }

    except Exception as e:

        print("ALL PURCHASE HISTORY ERROR:", str(e))

        raise HTTPException(
            status_code=500,
            detail="Unable to fetch purchase history"
        )