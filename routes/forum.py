"""
Forum routes — class-scoped posts, threaded replies (max 2 levels), likes, and casino points.
"""
import random
from typing import Optional
from datetime import datetime, timedelta, date as date_type
from fastapi import APIRouter, Depends, HTTPException, status, Form, File, UploadFile, Body
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.database import get_db
from models.models import Student, Class, StudentClass, ForumPost, ForumReply, ForumLike, ForumPoints
from app.auth import get_current_student

router = APIRouter(prefix="/api/forum", tags=["forum"])


# ==================== Schemas ====================

class ForumPostCreate(BaseModel):
    class_id: int
    title: Optional[str] = None
    content: str


class ForumReplyCreate(BaseModel):
    content: str
    parent_reply_id: Optional[int] = None


class DeletePostRequest(BaseModel):
    penalty: float = 0.0
    message: Optional[str] = None


# ==================== Helpers ====================

def _check_class_access(user: Student, class_id: int, db: Session):
    """Verify user has access to this class (enrolled student or teaching teacher)."""
    if user.role == "teacher":
        cls = db.query(Class).filter(
            Class.id == class_id,
            Class.teacher_id == user.id,
        ).first()
        if not cls:
            raise HTTPException(status_code=403, detail="No tienes acceso a esta clase")
        return cls
    else:
        enrollment = db.query(StudentClass).filter(
            StudentClass.student_id == user.id,
            StudentClass.class_id == class_id,
        ).first()
        if not enrollment or not enrollment.class_:
            raise HTTPException(status_code=403, detail="No estás inscrito en esta clase")
        return enrollment.class_


def _calculate_like_points(total_likes: int) -> float:
    """Slow progression: points per like based on cumulative like count."""
    if total_likes <= 10:
        return 0.1
    elif total_likes <= 25:
        return 0.2
    elif total_likes <= 50:
        return 0.3
    else:
        return 0.5


def _roll_bonus(base_pts: float) -> tuple:
    """Casino roll: returns (bonus_type, points_awarded). Rare events only."""
    roll = random.random()
    if roll < 0.002:    # 0.2% jackpot → flat +5.0
        return ('jackpot', 5.0)
    elif roll < 0.02:   # 2% double → 2× the base increment
        return ('double', round(base_pts * 2, 3))
    elif roll < 0.05:   # 5% mini → base + flat 0.2
        return ('mini', round(base_pts + 0.2, 3))
    else:
        return ('normal', base_pts)


def _post_dict(post: ForumPost, user_id: int, db: Session) -> dict:
    liked = db.query(ForumLike).filter(
        ForumLike.user_id == user_id,
        ForumLike.post_id == post.id,
    ).first() is not None
    return {
        "id": post.id,
        "author_id": post.author_id,
        "author_name": post.author.name if post.author else "Desconocido",
        "class_id": post.class_id,
        "class_name": post.class_.name if post.class_ else "",
        "title": post.title,
        "content": post.content,
        "created_at": post.created_at.isoformat(),
        "like_count": post.like_count,
        "comment_count": post.comment_count,
        "pinned": post.pinned,
        "locked": post.locked,
        "liked_by_me": liked,
        "author_role": post.author.role if post.author else "student",
        "points_earned": post.points_earned or 0.0,
        "has_file": bool(post.file_key),
        "file_name": post.file_name,
        "file_size": post.file_size,
    }


def _reply_dict(reply: ForumReply) -> dict:
    """Build reply dict (including 1 level of children)."""
    children = []
    for child in sorted(reply.children, key=lambda r: r.created_at):
        children.append({
            "id": child.id,
            "author_id": child.author_id,
            "author_name": child.author.name if child.author else "Desconocido",
            "author_role": child.author.role if child.author else "student",
            "content": child.content,
            "created_at": child.created_at.isoformat(),
            "parent_reply_id": child.parent_reply_id,
            "children": [],  # max depth enforced at API level
        })
    return {
        "id": reply.id,
        "author_id": reply.author_id,
        "author_name": reply.author.name if reply.author else "Desconocido",
        "author_role": reply.author.role if reply.author else "student",
        "content": reply.content,
        "created_at": reply.created_at.isoformat(),
        "parent_reply_id": reply.parent_reply_id,
        "children": children,
    }


# ==================== Endpoints ====================

@router.get("/classes")
async def get_forum_classes(
    user: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Return classes the user can post in."""
    if user.role == "teacher":
        classes = db.query(Class).filter(Class.teacher_id == user.id).order_by(Class.name).all()
    else:
        enrollments = db.query(StudentClass).filter(
            StudentClass.student_id == user.id,
        ).all()
        classes = [e.class_ for e in enrollments if e.class_]
        classes.sort(key=lambda c: c.name)
    return [{"id": c.id, "name": c.name} for c in classes]


@router.get("/posts")
async def list_posts(
    class_id: Optional[int] = None,
    page: int = 1,
    limit: int = 20,
    user: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """List posts across all accessible classes (or a specific class), newest first with pinned on top."""
    if class_id is not None:
        _check_class_access(user, class_id, db)
        class_ids = [class_id]
    else:
        if user.role == "teacher":
            classes = db.query(Class).filter(Class.teacher_id == user.id).all()
        else:
            enrollments = db.query(StudentClass).filter(StudentClass.student_id == user.id).all()
            classes = [e.class_ for e in enrollments if e.class_]
        class_ids = [c.id for c in classes]

    if not class_ids:
        return {"posts": [], "has_more": False, "page": page}

    offset = (page - 1) * limit
    posts = (
        db.query(ForumPost)
        .filter(ForumPost.class_id.in_(class_ids))
        .order_by(ForumPost.pinned.desc(), ForumPost.created_at.desc())
        .offset(offset)
        .limit(limit + 1)
        .all()
    )

    has_more = len(posts) > limit
    posts = posts[:limit]

    return {
        "posts": [_post_dict(p, user.id, db) for p in posts],
        "has_more": has_more,
        "page": page,
    }


@router.post("/posts")
async def create_post(
    class_id: int = Form(...),
    title: Optional[str] = Form(None),
    content: str = Form(...),
    file: Optional[UploadFile] = File(None),
    user: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Create a new forum post (multipart/form-data; file is optional, teacher-only)."""
    content = (content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="El contenido no puede estar vacío")

    _check_class_access(user, class_id, db)

    # Anti-spam: max 3 posts per day per student
    if user.role == "student":
        today_start = datetime.combine(date_type.today(), datetime.min.time())
        tomorrow_start = today_start + timedelta(days=1)
        daily_count = db.query(func.count(ForumPost.id)).filter(
            ForumPost.author_id == user.id,
            ForumPost.created_at >= today_start,
            ForumPost.created_at < tomorrow_start,
        ).scalar() or 0
        if daily_count >= 3:
            raise HTTPException(status_code=429, detail="Máximo 3 publicaciones por día")

    # File upload (teacher only)
    file_key = None
    file_name = None
    file_size = None
    if file and file.filename:
        if user.role != "teacher":
            raise HTTPException(status_code=403, detail="Solo profesores pueden adjuntar archivos")
        from app.storage import is_r2_configured, validate_file, upload_file
        if not is_r2_configured():
            raise HTTPException(status_code=501, detail="Subida de archivos no configurada")
        import time as _time
        file_data = await file.read()
        ext = validate_file(file.filename, file_data)
        key = f"forum/post_{int(_time.time())}.{ext}"
        upload_file(key, file_data, file.content_type)
        file_key = key
        file_name = file.filename
        file_size = len(file_data)

    post = ForumPost(
        author_id=user.id,
        class_id=class_id,
        title=(title or "").strip() or None,
        content=content,
        file_key=file_key,
        file_name=file_name,
        file_size=file_size,
    )
    db.add(post)
    db.flush()  # get post.id before commit

    # Award +0.1 creation points to students
    if user.role == "student":
        post.points_earned = 0.1
        db.add(ForumPoints(
            user_id=user.id,
            post_id=post.id,
            points_earned=0.1,
            bonus_type='post',
        ))

    db.commit()
    db.refresh(post)

    return _post_dict(post, user.id, db)


@router.get("/posts/{post_id}")
async def get_post(
    post_id: int,
    user: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Get a single post with nested replies."""
    post = db.query(ForumPost).filter(ForumPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post no encontrado")

    _check_class_access(user, post.class_id, db)

    top_replies = (
        db.query(ForumReply)
        .filter(ForumReply.post_id == post_id, ForumReply.parent_reply_id.is_(None))
        .order_by(ForumReply.created_at)
        .all()
    )

    data = _post_dict(post, user.id, db)
    data["replies"] = [_reply_dict(r) for r in top_replies]
    return data


@router.post("/posts/{post_id}/replies")
async def create_reply(
    post_id: int,
    data: ForumReplyCreate,
    user: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Create a reply to a post (or a nested reply, max 2 levels)."""
    post = db.query(ForumPost).filter(ForumPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post no encontrado")
    if post.locked:
        raise HTTPException(status_code=403, detail="Este post está bloqueado")

    _check_class_access(user, post.class_id, db)

    content = (data.content or "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="La respuesta no puede estar vacía")

    if data.parent_reply_id:
        parent = db.query(ForumReply).filter(ForumReply.id == data.parent_reply_id).first()
        if not parent or parent.post_id != post_id:
            raise HTTPException(status_code=404, detail="Respuesta padre no encontrada")
        if parent.parent_reply_id is not None:
            raise HTTPException(
                status_code=400,
                detail="No se puede responder más de 2 niveles de profundidad",
            )

    reply = ForumReply(
        post_id=post_id,
        author_id=user.id,
        parent_reply_id=data.parent_reply_id,
        content=content,
    )
    db.add(reply)
    post.comment_count += 1
    db.commit()
    db.refresh(reply)

    return {
        "id": reply.id,
        "author_id": reply.author_id,
        "author_name": user.name,
        "author_role": user.role,
        "content": reply.content,
        "created_at": reply.created_at.isoformat(),
        "parent_reply_id": reply.parent_reply_id,
        "children": [],
    }


@router.post("/posts/{post_id}/like")
async def toggle_like(
    post_id: int,
    user: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Toggle like on a post. Cannot like your own posts."""
    post = db.query(ForumPost).filter(ForumPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post no encontrado")

    _check_class_access(user, post.class_id, db)

    if post.author_id == user.id:
        raise HTTPException(status_code=400, detail="No puedes dar like a tu propio post")

    existing = db.query(ForumLike).filter(
        ForumLike.user_id == user.id,
        ForumLike.post_id == post_id,
    ).first()

    points_awarded = 0.0
    bonus_type = 'normal'

    if existing:
        db.delete(existing)
        post.like_count = max(0, post.like_count - 1)
        liked = False
    else:
        like = ForumLike(user_id=user.id, post_id=post_id)
        db.add(like)
        db.flush()  # get like.id
        post.like_count += 1
        liked = True

        # Award points: only when student likes a student post
        if user.role != "teacher" and post.author.role != "teacher":
            # Rule 1: post needs at least 2 likes before points kick in (anti-spam)
            qualifies = post.like_count >= 2

            # Rule 2: can't award points to the same author more than once per day
            today_start = datetime.combine(date_type.today(), datetime.min.time())
            already_liked_author_today = qualifies and db.query(ForumPoints).join(
                ForumPost, ForumPoints.post_id == ForumPost.id
            ).filter(
                ForumPoints.user_id == user.id,
                ForumPost.author_id == post.author_id,
                ForumPoints.like_id.isnot(None),
                ForumPoints.created_at >= today_start,
            ).first() is not None

            if qualifies and not already_liked_author_today:
                base_pts = _calculate_like_points(post.like_count)
                bonus_type, points_awarded = _roll_bonus(base_pts)

                db.add(ForumPoints(
                    user_id=post.author_id,
                    post_id=post_id,
                    like_id=like.id,
                    points_earned=points_awarded,
                    bonus_type=bonus_type,
                ))
                post.points_earned = round((post.points_earned or 0.0) + points_awarded, 3)
            else:
                bonus_type = 'normal'

    db.commit()
    return {
        "liked": liked,
        "like_count": post.like_count,
        "points_awarded": points_awarded,
        "bonus_type": bonus_type,
        "author_name": post.author.name if post.author else "",
        "post_points_earned": post.points_earned or 0.0,
    }


@router.get("/posts/{post_id}/file")
async def get_forum_post_file(
    post_id: int,
    user: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Get a presigned download URL for a post's attached file."""
    post = db.query(ForumPost).filter(ForumPost.id == post_id).first()
    if not post or not post.file_key:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    _check_class_access(user, post.class_id, db)
    from app.storage import is_r2_configured, generate_presigned_url
    if not is_r2_configured():
        raise HTTPException(status_code=501, detail="Almacenamiento no configurado")
    url = generate_presigned_url(post.file_key)
    return {"download_url": url, "file_name": post.file_name}


@router.delete("/posts/{post_id}")
async def delete_post(
    post_id: int,
    payload: Optional[DeletePostRequest] = Body(default=None),
    user: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Delete a post. Only author or teacher can delete.
    Teachers deleting another user's post may pass {penalty, message} to deduct extra points.
    All ForumPoints earned by this post are always revoked on moderation delete.
    """
    post = db.query(ForumPost).filter(ForumPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post no encontrado")

    if post.author_id != user.id and user.role != "teacher":
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar este post")

    is_moderation = user.role == "teacher" and post.author_id != user.id
    points_revoked = 0.0
    penalty_amount = 0.0

    if is_moderation:
        # Revoke all points earned from this post
        point_records = db.query(ForumPoints).filter(ForumPoints.post_id == post_id).all()
        points_revoked = sum(abs(r.points_earned) for r in point_records)
        for r in point_records:
            db.delete(r)

        # Apply optional extra penalty
        penalty_amount = round((payload.penalty if payload else 0.0) or 0.0, 2)
        penalty_message = (payload.message if payload else None)
        if penalty_amount > 0:
            db.add(ForumPoints(
                user_id=post.author_id,
                post_id=None,
                class_id=post.class_id,
                points_earned=-penalty_amount,
                bonus_type="penalty",
                message=penalty_message,
            ))

    if post.file_key:
        from app.storage import is_r2_configured, delete_file
        if is_r2_configured():
            delete_file(post.file_key)

    db.delete(post)
    db.commit()
    return {
        "message": "Post eliminado",
        "points_revoked": round(points_revoked, 2),
        "penalty_applied": penalty_amount,
    }


@router.delete("/replies/{reply_id}")
async def delete_reply(
    reply_id: int,
    user: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Delete a reply. Only author or teacher can delete."""
    reply = db.query(ForumReply).filter(ForumReply.id == reply_id).first()
    if not reply:
        raise HTTPException(status_code=404, detail="Respuesta no encontrada")

    if reply.author_id != user.id and user.role != "teacher":
        raise HTTPException(status_code=403, detail="No tienes permiso para eliminar esta respuesta")

    post = db.query(ForumPost).filter(ForumPost.id == reply.post_id).first()
    if post:
        post.comment_count = max(0, post.comment_count - 1)

    db.delete(reply)
    db.commit()
    return {"message": "Respuesta eliminada"}


@router.get("/points/summary")
async def get_points_summary(
    class_id: int,
    user: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Total forum points earned by the current user in a given class."""
    total = db.query(func.sum(ForumPoints.points_earned)).filter(
        ForumPoints.user_id == user.id,
        ForumPoints.post_id.in_(
            db.query(ForumPost.id).filter(ForumPost.class_id == class_id)
        ),
    ).scalar() or 0.0
    return {"total": round(float(total), 2)}


@router.get("/points/recent")
async def get_recent_points(
    user: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Last 20 forum point awards for the current user (across all classes)."""
    records = (
        db.query(ForumPoints)
        .filter(ForumPoints.user_id == user.id)
        .order_by(ForumPoints.created_at.desc())
        .limit(20)
        .all()
    )
    result = []
    for r in records:
        post = r.post
        result.append({
            "id": r.id,
            "post_id": r.post_id,
            "post_snippet": (post.title or post.content[:60]) if post else "",
            "points_earned": r.points_earned,
            "bonus_type": r.bonus_type,
            "created_at": r.created_at.isoformat(),
        })
    return result


@router.get("/penalties/recent")
async def get_recent_penalties(
    user: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
    class_id: Optional[int] = None,
):
    """Penalty records for the current user in the last 7 days.
    Pass class_id to filter to one class; omit to get all classes.
    """
    cutoff = datetime.utcnow() - timedelta(days=7)
    q = db.query(ForumPoints).filter(
        ForumPoints.user_id == user.id,
        ForumPoints.bonus_type == "penalty",
        ForumPoints.created_at >= cutoff,
    )
    if class_id is not None:
        q = q.filter(ForumPoints.class_id == class_id)
    records = q.order_by(ForumPoints.created_at.desc()).all()
    return [
        {
            "points_earned": r.points_earned,
            "message": r.message,
            "created_at": r.created_at.isoformat(),
        }
        for r in records
    ]


@router.patch("/posts/{post_id}/pin")
async def toggle_pin(
    post_id: int,
    user: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Toggle pin on a post. Teacher only."""
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Solo los profesores pueden fijar publicaciones")

    post = db.query(ForumPost).filter(ForumPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post no encontrado")

    _check_class_access(user, post.class_id, db)
    post.pinned = not post.pinned
    db.commit()
    return {"pinned": post.pinned}


@router.patch("/posts/{post_id}/lock")
async def toggle_lock(
    post_id: int,
    user: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Toggle lock on a post. Teacher only."""
    if user.role != "teacher":
        raise HTTPException(status_code=403, detail="Solo los profesores pueden bloquear publicaciones")

    post = db.query(ForumPost).filter(ForumPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post no encontrado")

    _check_class_access(user, post.class_id, db)
    post.locked = not post.locked
    db.commit()
    return {"locked": post.locked}
