from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.auth.deps import get_current_teacher
from app.database import get_db
from app.models import Class, PointsConfig, User
from app.schemas import ClassSettingsOut, ClassSettingsUpdate

router = APIRouter(prefix="/api/classes", tags=["settings"])


def _owned_class_and_config(
    db: Session, class_id: int, teacher: User
) -> tuple[Class, PointsConfig]:
    klass = db.get(Class, class_id)
    if klass is None:
        raise HTTPException(status_code=404, detail="Clase no encontrada")
    if klass.teacher_id != teacher.id:
        raise HTTPException(status_code=403, detail="No eres profesor de esa clase")
    cfg = db.query(PointsConfig).filter(PointsConfig.class_id == class_id).first()
    if cfg is None:
        cfg = PointsConfig(class_id=class_id)
        db.add(cfg)
        db.flush()
    return klass, cfg


def _to_out(klass: Class, cfg: PointsConfig) -> ClassSettingsOut:
    return ClassSettingsOut(
        tareas_weight=klass.tareas_weight,
        examenes_weight=klass.examenes_weight,
        tap_value=cfg.tap_value,
        like_value=cfg.like_value,
        like_exponent=cfg.like_exponent,
    )


@router.get("/{class_id}/settings", response_model=ClassSettingsOut)
def get_settings(
    class_id: int,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    klass, cfg = _owned_class_and_config(db, class_id, teacher)
    return _to_out(klass, cfg)


@router.patch("/{class_id}/settings", response_model=ClassSettingsOut)
def update_settings(
    class_id: int,
    body: ClassSettingsUpdate,
    teacher: User = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    klass, cfg = _owned_class_and_config(db, class_id, teacher)
    if body.tareas_weight is not None:
        klass.tareas_weight = body.tareas_weight
    if body.examenes_weight is not None:
        klass.examenes_weight = body.examenes_weight
    if body.tap_value is not None:
        cfg.tap_value = body.tap_value
    if body.like_value is not None:
        cfg.like_value = body.like_value
    if body.like_exponent is not None:
        cfg.like_exponent = body.like_exponent
    db.commit()
    db.refresh(klass)
    db.refresh(cfg)
    return _to_out(klass, cfg)
