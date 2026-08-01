from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.models.file import CompanyFile
from app.database import SessionLocal
from app.models.cart import Cart
from app.schemas.cart import CartCreate, CartResponse,BulkCartCreate
from typing import List

router = APIRouter(
    prefix="/cart",
    tags=["Cart"]
)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
@router.post("/", response_model=CartResponse)
def add_to_cart(cart: CartCreate, db: Session = Depends(get_db)):

    # Prevent duplicate document in cart
    existing = (
        db.query(Cart)
        .filter(
            Cart.user_id == cart.user_id,
            Cart.document_id == cart.document_id,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=400,
            detail="Document already exists in cart."
        )

    item = Cart(**cart.model_dump())

    db.add(item)
    db.commit()
    db.refresh(item)

    return item


@router.post("/bulk", response_model=List[CartResponse])
def bulk_add_to_cart(
    data: BulkCartCreate,
    db: Session = Depends(get_db)
):
    created_items = []

    reports = (
        db.query(CompanyFile)
        .filter(CompanyFile.document_id.in_(data.document_ids))
        .all()
    )

    for report in reports:

        # Prevent duplicate document in cart
        existing = (
            db.query(Cart)
            .filter(
                Cart.user_id == data.user_id,
                Cart.document_id == report.document_id,
            )
            .first()
        )

        if existing:
            continue

        item = Cart(
            user_id=data.user_id,
            username=data.username,
            company=report.company,
            isin=report.isin,
            doc_type=report.document_type,
            year=str(report.year),
            price=report.price,
            document_id=report.document_id,
        )

        db.add(item)
        created_items.append(item)

    db.commit()

    for item in created_items:
        db.refresh(item)

    return created_items
@router.get("/{user_id}", response_model=list[CartResponse])
def get_cart(user_id: int, db: Session = Depends(get_db)):

    return (
        db.query(Cart)
        .filter(Cart.user_id == user_id)
        .order_by(Cart.created_at.desc())
        .all()
    )
    
@router.delete("/{cart_id}")
def delete_cart_item(cart_id: int, db: Session = Depends(get_db)):

    item = db.query(Cart).filter(Cart.id == cart_id).first()

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Cart item not found."
        )

    db.delete(item)
    db.commit()

    return {"message": "Item removed from cart"}

@router.delete("/clear/{user_id}")
def clear_cart(user_id: int, db: Session = Depends(get_db)):

    db.query(Cart).filter(
        Cart.user_id == user_id
    ).delete()

    db.commit()

    return {"message": "Cart cleared successfully"}

@router.get("/count/{user_id}")
def cart_count(user_id: int, db: Session = Depends(get_db)):

    count = (
        db.query(Cart)
        .filter(Cart.user_id == user_id)
        .count()
    )

    return {
        "user_id": user_id,
        "count": count
    }
    
@router.delete("/{user_id}/{cart_id}")
def delete_cart_item(
    user_id: int,
    cart_id: int,
    db: Session = Depends(get_db)
):
    item = (
        db.query(Cart)
        .filter(
            Cart.id == cart_id,
            Cart.user_id == user_id
        )
        .first()
    )

    if not item:
        raise HTTPException(
            status_code=404,
            detail="Cart item not found."
        )

    db.delete(item)
    db.commit()

    return {
        "message": "Item removed from cart",
        "cart_id": cart_id,
        "user_id": user_id
    }