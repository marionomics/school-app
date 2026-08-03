from datetime import datetime, timezone
from typing import List, Optional, Set

from pydantic import BaseModel

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, selectinload

from app.auth.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Attachment, Class, Enrollment, Like, Post, Review, User, utcnow
from app.schemas import AttachmentOut, AuthorOut, PostOut, ReviewOut
from app.services import points
from app.services.attribution import resolve_default_class
from app.services.cursor import decode_cursor, encode_cursor
from app.services.dates import next_sunday_due
from app import storage

router = APIRouter(prefix="/api/posts", tags=["posts"])

MAX_FILES = 4


def _parse_due_date(raw: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        raise HTTPException(status_code=422, detail="Fecha de entrega inválida")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


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


def serialize_post(post: Post, liked_ids: Set[int], *, viewer: Optional[User] = None,
                   review_by_post: Optional[dict] = None) -> PostOut:
    # Only a DELETED post loses its text. A veto removes the points, not the
    # student's words — blanking them would leave an unexplained empty card in
    # the feed, and the veto reason it carries would have nothing to attach to.
    removed = post.status == "deleted"
    # Scores, feedback and veto reasons belong only to the student who wrote the
    # post. Classmates read the same thread, so this is withheld server-side.
    private = viewer is not None and (
        viewer.id == post.author_id or viewer.role == "teacher")
    review = (review_by_post or {}).get(post.id) if private else None
    return PostOut(
        id=post.id,
        author=AuthorOut.model_validate(post.author),
        type=post.type,
        class_id=post.class_id,
        class_name=post.klass.name if post.klass else None,
        content="" if removed else post.content,
        taps=post.taps,
        due_date=post.due_date,
        is_entrega=post.is_entrega,
        examen_mode=post.examen_mode,
        graded_at=post.graded_at,
        my_review=ReviewOut.model_validate(review) if review is not None else None,
        veto_reason=post.veto_reason if private else None,
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


feed_router = APIRouter(prefix="/api/feed", tags=["feed"])


def _liked_ids(db: Session, user: User, post_ids: List[int]) -> Set[int]:
    if not post_ids:
        return set()
    rows = db.query(Like.post_id).filter(Like.user_id == user.id,
                                         Like.post_id.in_(post_ids)).all()
    return {pid for (pid,) in rows}


@feed_router.get("")
def get_feed(
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = (
        db.query(Post)
        .options(selectinload(Post.author), selectinload(Post.klass),
                 selectinload(Post.attachments))
        # Vetoed posts stay in the feed: a student whose post silently vanished
        # gets no explanation, which is the opposite of what the veto flow
        # intends. They keep their text and carry a veto_reason that
        # serialize_post shows only to the author and the teacher. Deleted
        # posts stay hidden.
        .filter(Post.parent_id.is_(None), Post.status.in_(("active", "vetoed")))
    )
    if cursor:
        try:
            c_dt, c_id = decode_cursor(cursor)
        except Exception:
            raise HTTPException(status_code=422, detail="Cursor inválido")
        q = q.filter(or_(Post.last_activity_at < c_dt,
                         and_(Post.last_activity_at == c_dt, Post.id < c_id)))
    posts = q.order_by(Post.last_activity_at.desc(), Post.id.desc()).limit(limit + 1).all()
    has_more = len(posts) > limit
    posts = posts[:limit]
    liked = _liked_ids(db, user, [p.id for p in posts])
    next_cursor = encode_cursor(posts[-1].last_activity_at, posts[-1].id) if (has_more and posts) else None
    return {"items": [serialize_post(p, liked, viewer=user) for p in posts], "next_cursor": next_cursor}


@router.get("/{post_id}")
def get_thread(post_id: int, user: User = Depends(get_current_user),
               db: Session = Depends(get_db)):
    post = (
        db.query(Post)
        .options(selectinload(Post.author), selectinload(Post.klass),
                 selectinload(Post.attachments))
        .filter(Post.id == post_id).first()
    )
    if post is None or (post.status == "deleted" and post.reply_count == 0):
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    level2 = (
        db.query(Post)
        .options(selectinload(Post.author), selectinload(Post.klass),
                 selectinload(Post.attachments))
        .filter(Post.parent_id == post.id).all()
    )
    level3 = []
    if level2:
        level3 = (
            db.query(Post)
            .options(selectinload(Post.author), selectinload(Post.klass),
                     selectinload(Post.attachments))
            .filter(Post.parent_id.in_([r.id for r in level2])).all()
        )
    replies = sorted(level2 + level3, key=lambda p: p.created_at)
    liked = _liked_ids(db, user, [post.id] + [r.id for r in replies])
    entrega_ids = [r.id for r in replies if r.is_entrega]
    review_by_post = {}
    if entrega_ids:
        for rv in db.query(Review).filter(Review.entrega_post_id.in_(entrega_ids)).all():
            review_by_post[rv.entrega_post_id] = rv
    return {"post": serialize_post(post, liked, viewer=user),
            "replies": [serialize_post(r, liked, viewer=user,
                                       review_by_post=review_by_post) for r in replies]}


@router.post("", response_model=PostOut, status_code=201)
def create_post(
    content: str = Form(""),
    type: str = Form("regular"),
    taps: Optional[int] = Form(None),
    class_id: Optional[int] = Form(None),
    parent_id: Optional[int] = Form(None),
    due_date: Optional[str] = Form(None),
    is_entrega: bool = Form(False),
    examen_mode: Optional[str] = Form(None),
    files: List[UploadFile] = File([]),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if type not in ("regular", "participacion", "tarea", "examen"):
        raise HTTPException(status_code=422, detail="Tipo de publicación inválido")
    if not content.strip() and not files:
        raise HTTPException(status_code=422, detail="La publicación está vacía")

    if type in ("tarea", "examen") and user.role != "teacher":
        raise HTTPException(status_code=403,
                            detail="Solo el profesor puede crear tareas y exámenes")
    if type == "examen":
        examen_mode = examen_mode or "paper"
        if examen_mode not in ("paper", "digital"):
            raise HTTPException(status_code=422, detail="Modalidad de examen inválida")

    parent = None
    if parent_id is not None:
        parent = db.get(Post, parent_id)
        if parent is None or parent.status != "active":
            raise HTTPException(status_code=404, detail="Publicación no encontrada")
        if get_depth(db, parent) >= 3:
            raise HTTPException(status_code=422, detail="Máximo 3 niveles de respuestas")

    entrega = False
    if is_entrega:
        if parent is None or parent.type not in ("tarea", "examen"):
            raise HTTPException(
                status_code=422,
                detail="Solo puedes marcar como entrega una respuesta a una tarea")
        active = (
            db.query(Enrollment)
            .filter(Enrollment.user_id == user.id,
                    Enrollment.class_id == parent.class_id,
                    Enrollment.status == "active")
            .first()
        )
        if active is None:
            raise HTTPException(
                status_code=403,
                detail="Necesitas estar inscrito en la clase para entregar")
        # Latest wins: clear any previous entrega by this student on this tarea.
        (db.query(Post)
           .filter(Post.author_id == user.id,
                   Post.parent_id == parent.id,
                   Post.is_entrega.is_(True))
           .update({"is_entrega": False}, synchronize_session=False))
        entrega = True

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
    else:
        # A teacher is never *enrolled*, so attribution falls back to the class
        # they teach — otherwise a tarea composed without an explicit class_id
        # has nothing to attach to.
        resolved_class = resolve_default_class(db, user)

    if type in ("tarea", "examen") and resolved_class is None:
        raise HTTPException(status_code=422, detail="Una tarea necesita una clase")

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
        due_date=(
            _parse_due_date(due_date)
            if due_date
            else next_sunday_due(utcnow(), settings.timezone)
        ) if type == "tarea" else None,
        is_entrega=entrega,
        examen_mode=examen_mode if type == "examen" else None,
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


attachments_router = APIRouter(prefix="/api/attachments", tags=["attachments"])


@router.post("/{post_id}/like")
def toggle_like(post_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    post = db.get(Post, post_id)
    if post is None or post.status != "active":
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if post.author_id == user.id:
        raise HTTPException(status_code=400, detail="No puedes dar like a tu propia publicación")
    existing = db.query(Like).filter(Like.user_id == user.id,
                                     Like.post_id == post.id).first()
    if existing is not None:
        points.revoke_like(db, like_id=existing.id, revoked_by=user.id)
        db.delete(existing)
        post.like_count = max(0, post.like_count - 1)
        db.commit()
        return {"liked": False, "like_count": post.like_count}
    like = Like(user_id=user.id, post_id=post.id)
    db.add(like)
    db.flush()
    post.like_count += 1
    get_root(db, post).last_activity_at = utcnow()
    points.award_like(db, like=like, post=post, liker=user)
    db.commit()
    return {"liked": True, "like_count": post.like_count}


@router.delete("/{post_id}", status_code=204)
def remove_post(post_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    post = db.get(Post, post_id)
    if post is None or post.status != "active":
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if post.author_id == user.id:
        post.status = "deleted"
    elif user.role == "teacher":
        post.status = "vetoed"
    else:
        raise HTTPException(status_code=403, detail="No puedes eliminar esta publicación")
    points.revoke_post(db, post=post, revoked_by=user.id)
    if post.parent_id is not None:
        root = get_root(db, post)
        root.reply_count = max(0, root.reply_count - 1)
    db.commit()


def _teacher_item(db: Session, post_id: int, user: User) -> Post:
    """A tarea/examen in a class this teacher owns, or the right HTTP error."""
    post = db.get(Post, post_id)
    if post is None or post.status != "active":
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Solo el profesor puede calificar")
    if post.type not in ("tarea", "examen"):
        raise HTTPException(status_code=422, detail="Esta publicación no se califica")
    klass = db.get(Class, post.class_id) if post.class_id else None
    if klass is None or klass.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="No eres profesor de esa clase")
    return post


@router.post("/{post_id}/graded")
def mark_graded(post_id: int, user: User = Depends(get_current_user),
                db: Session = Depends(get_db)):
    post = _teacher_item(db, post_id, user)
    post.graded_at = utcnow()
    db.commit()
    return {"graded_at": post.graded_at}


@router.delete("/{post_id}/graded")
def unmark_graded(post_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    post = _teacher_item(db, post_id, user)
    post.graded_at = None
    db.commit()
    return {"graded_at": None}


class VetoIn(BaseModel):
    reason: Optional[str] = None


def _teacher_of_post(db: Session, post_id: int, user: User) -> Post:
    post = db.get(Post, post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Publicación no encontrada")
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Solo el profesor puede vetar")
    klass = db.get(Class, post.class_id) if post.class_id else None
    if klass is None or klass.teacher_id != user.id:
        raise HTTPException(status_code=403, detail="No eres profesor de esa clase")
    return post


@router.post("/{post_id}/veto")
def veto(post_id: int, body: VetoIn = VetoIn(),
         user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    post = _teacher_of_post(db, post_id, user)
    post.status = "vetoed"
    post.veto_reason = body.reason
    points.revoke_post(db, post=post, revoked_by=user.id)
    db.commit()
    return {"status": post.status, "veto_reason": post.veto_reason}


@router.delete("/{post_id}/veto")
def unveto(post_id: int, user: User = Depends(get_current_user),
           db: Session = Depends(get_db)):
    post = _teacher_of_post(db, post_id, user)
    post.status = "active"
    post.veto_reason = None
    points.restore_post(db, post=post)
    db.commit()
    return {"status": post.status, "veto_reason": None}


def _teacher_participacion(db: Session, post_id: int, user: User) -> Post:
    post = _teacher_of_post(db, post_id, user)
    if post.type != "participacion":
        raise HTTPException(status_code=422,
                            detail="Sólo las participaciones se revisan")
    return post


@router.post("/{post_id}/reviewed")
def mark_reviewed(post_id: int, user: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    """Records that the teacher looked. Moves no points — the student earned
    them on publish. This is the non-destructive twin of veto, and the two must
    never be collapsed into one control."""
    post = _teacher_participacion(db, post_id, user)
    post.reviewed_at = utcnow()
    post.reviewed_by = user.id
    db.commit()
    return {"reviewed": True}


@router.delete("/{post_id}/reviewed")
def unmark_reviewed(post_id: int, user: User = Depends(get_current_user),
                    db: Session = Depends(get_db)):
    post = _teacher_participacion(db, post_id, user)
    post.reviewed_at = None
    post.reviewed_by = None
    db.commit()
    return {"reviewed": False}


@attachments_router.get("/{attachment_id}/url")
def attachment_url(attachment_id: int, user: User = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    att = db.get(Attachment, attachment_id)
    if att is None:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    post = db.get(Post, att.post_id)
    if post is None or post.status != "active":
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    if not storage.is_r2_configured():
        raise HTTPException(status_code=400, detail="La descarga de archivos no está habilitada")
    return {"url": storage.generate_presigned_url(att.file_key)}
