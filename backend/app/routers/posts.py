from typing import List, Optional, Set

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session, selectinload

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Attachment, Class, Enrollment, Post, User, utcnow
from app.schemas import AttachmentOut, AuthorOut, PostOut
from app.services import points
from app.services.attribution import resolve_default_class
from app import storage

router = APIRouter(prefix="/api/posts", tags=["posts"])

MAX_FILES = 4


def get_depth(db: Session, post: Post) -> int:
    depth, cur = 1, post
    while cur.parent_id is not None:
        cur = db.get(Post, cur.parent_id)
        depth += 1
    return depth


def get_root(db: Session, post: Post) -> Post:
    cur = post
    while cur.parent_id is not None:
        cur = db.get(Post, cur.parent_id)
    return cur


def serialize_post(post: Post, liked_ids: Set[int]) -> PostOut:
    removed = post.status != "active"
    return PostOut(
        id=post.id,
        author=AuthorOut.model_validate(post.author),
        type=post.type,
        class_id=post.class_id,
        class_name=post.klass.name if post.klass else None,
        content="" if removed else post.content,
        taps=post.taps,
        status=post.status,
        like_count=post.like_count,
        reply_count=post.reply_count,
        liked_by_me=post.id in liked_ids,
        attachments=[] if removed else [AttachmentOut.model_validate(a) for a in post.attachments],
        created_at=post.created_at,
        last_activity_at=post.last_activity_at,
        parent_id=post.parent_id,
    )


def _resolve_class_for_student(db: Session, user: User, sent: Optional[int]) -> int:
    if sent is not None:
        enr = (
            db.query(Enrollment)
            .filter(Enrollment.user_id == user.id, Enrollment.class_id == sent,
                    Enrollment.status == "active")
            .first()
        )
        if enr is None:
            raise HTTPException(status_code=403, detail="No estás inscrito en esa clase")
        return sent
    default = resolve_default_class(db, user)
    if default is None:
        raise HTTPException(status_code=422, detail="Selecciona la clase para tu publicación")
    return default


@router.get("/default-class")
def default_class(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"class_id": resolve_default_class(db, user)}


@router.post("", response_model=PostOut, status_code=201)
def create_post(
    content: str = Form(""),
    type: str = Form("regular"),
    taps: Optional[int] = Form(None),
    class_id: Optional[int] = Form(None),
    parent_id: Optional[int] = Form(None),
    files: List[UploadFile] = File([]),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if type not in ("regular", "participacion"):
        raise HTTPException(status_code=422, detail="Tipo de publicación inválido")
    if not content.strip() and not files:
        raise HTTPException(status_code=422, detail="La publicación está vacía")

    parent = None
    if parent_id is not None:
        parent = db.get(Post, parent_id)
        if parent is None or parent.status != "active":
            raise HTTPException(status_code=404, detail="Publicación no encontrada")
        if get_depth(db, parent) >= 3:
            raise HTTPException(status_code=422, detail="Máximo 3 niveles de respuestas")

    if type == "participacion":
        if parent is not None:
            raise HTTPException(status_code=422, detail="Una participación no puede ser respuesta")
        if taps is None or not 1 <= taps <= 3:
            raise HTTPException(status_code=422, detail="La participación necesita de 1 a 3 taps")
        if len(content.strip()) < 10:
            raise HTTPException(status_code=422, detail="Explica tu participación con más detalle")

    resolved_class: Optional[int] = None
    if user.role != "teacher":
        resolved_class = _resolve_class_for_student(db, user, class_id)
    elif class_id is not None:
        klass = db.get(Class, class_id)
        if klass is None or klass.teacher_id != user.id:
            raise HTTPException(status_code=403, detail="No eres profesor de esa clase")
        resolved_class = class_id

    if files and len(files) > MAX_FILES:
        raise HTTPException(status_code=422, detail="Máximo 4 archivos por publicación")
    if files and not storage.is_r2_configured():
        raise HTTPException(status_code=400, detail="La subida de archivos no está habilitada")

    file_payloads = []
    for f in files:
        data = f.file.read()
        error = storage.validate_file(f.filename or "", len(data))
        if error:
            raise HTTPException(status_code=422, detail=error)
        file_payloads.append((f.filename, data, f.content_type or "application/octet-stream"))

    post = Post(
        author_id=user.id, type=type, class_id=resolved_class,
        parent_id=parent_id, content=content.strip(),
        taps=taps if type == "participacion" else None,
    )
    db.add(post)
    db.flush()

    for i, (name, data, ctype) in enumerate(file_payloads):
        ext = name.rsplit(".", 1)[1].lower()
        key = f"posts/{user.id}_{post.id}_{i}_{int(utcnow().timestamp())}.{ext}"
        storage.upload_bytes(data, key, ctype)
        db.add(Attachment(post_id=post.id, file_key=key, file_name=name,
                          file_size=len(data), mime_type=ctype))

    if parent is not None:
        root = get_root(db, parent)
        root.reply_count += 1
        root.last_activity_at = utcnow()

    if type == "participacion":
        points.award_participacion(db, post)

    db.commit()
    post = (
        db.query(Post).options(selectinload(Post.author), selectinload(Post.klass),
                               selectinload(Post.attachments))
        .filter(Post.id == post.id).one()
    )
    return serialize_post(post, liked_ids=set())
