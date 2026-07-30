from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_teacher, get_current_user
from app.database import get_db
from app.models import Class, Enrollment, PointsConfig, User
from app.schemas import ClassCreate, ClassDetail, ClassOut, JoinRequest, MemberOut, MyClasses
from app.services.class_codes import generate_code

router = APIRouter(prefix="/api/classes", tags=["classes"])


@router.post("", response_model=ClassOut, status_code=201)
def create_class(
    body: ClassCreate,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    klass = Class(
        name=body.name,
        code=generate_code(db, body.code_prefix),
        teacher_id=teacher.id,
        start_date=body.start_date,
        end_date=body.end_date,
        schedule_json=[b.model_dump() for b in body.schedule],
        tareas_weight=body.tareas_weight,
        examenes_weight=body.examenes_weight,
    )
    db.add(klass)
    db.flush()
    db.add(PointsConfig(class_id=klass.id))
    db.commit()
    db.refresh(klass)
    return klass


@router.post("/join", response_model=ClassOut)
def join_class(
    body: JoinRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    klass = db.query(Class).filter(Class.code == body.code.strip().upper()).first()
    if klass is None:
        raise HTTPException(status_code=404, detail="Código de clase no encontrado")
    exists = (
        db.query(Enrollment)
        .filter(Enrollment.user_id == user.id, Enrollment.class_id == klass.id)
        .first()
    )
    if exists is not None:
        raise HTTPException(status_code=409, detail="Ya estás en esta clase")
    db.add(Enrollment(user_id=user.id, class_id=klass.id))
    db.commit()
    return klass


@router.get("/mine", response_model=MyClasses)
def my_classes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    teaching = db.query(Class).filter(Class.teacher_id == user.id).all()
    enrolled = (
        db.query(Class)
        .join(Enrollment, Enrollment.class_id == Class.id)
        .filter(Enrollment.user_id == user.id)
        .all()
    )
    return MyClasses(
        teaching=[ClassOut.model_validate(c) for c in teaching],
        enrolled=[ClassOut.model_validate(c) for c in enrolled],
    )


@router.get("/{class_id}", response_model=ClassDetail)
def class_detail(
    class_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    klass = db.get(Class, class_id)
    if klass is None:
        raise HTTPException(status_code=404, detail="Clase no encontrada")
    enrollments = db.query(Enrollment).filter(Enrollment.class_id == class_id).all()
    is_member = any(e.user_id == user.id for e in enrollments)
    if klass.teacher_id != user.id and not is_member:
        raise HTTPException(status_code=403, detail="No perteneces a esta clase")
    detail = ClassDetail.model_validate(klass)
    detail.members = [
        MemberOut(
            id=e.user.id,
            name=e.user.name,
            username=e.user.username,
            avatar_url=e.user.avatar_url,
            status=e.status,
        )
        for e in enrollments
    ]
    return detail
