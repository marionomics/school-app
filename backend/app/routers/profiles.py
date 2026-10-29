from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, selectinload

from app.auth.deps import get_current_user
from app.database import get_db
from app.models import Class, Enrollment, Post, User
from app.routers.grades import _summary
from app.routers.posts import _liked_ids, _teacher_aura_ids, get_root, serialize_post
from app.services.cursor import decode_cursor, encode_cursor
from app.services.media import avatar_for
from app.services.visibility import assignment_visible, root_visible, viewer_class_ids

router = APIRouter(prefix="/api/users", tags=["profiles"])

EXCERPT = 120


def _is_submission(db: Session, post: Post) -> bool:
    """Homework a student handed in: a marked entrega, or a reply with files
    straight under a tarea or examen — the same "reply with files is the
    submission" rule as grades.examen_submission. A text-only reply
    there is a question, not an answer. The Respuestas tab hides these and
    blanks the excerpt of a reply to one, so a profile can't be used to
    browse and copy someone's work."""
    if post.is_entrega:
        return True
    if post.parent_id is None or not post.attachments:
        return False
    parent = db.get(Post, post.parent_id)
    return parent is not None and parent.type in ("tarea", "examen")


def _user_or_404(db: Session, username: str) -> User:
    u = db.query(User).filter(User.username == username.lower()).first()
    if u is None:
        raise HTTPException(status_code=404, detail="Ese usuario no existe")
    return u


def _visible_grades(db: Session, viewer: User, u: User) -> Optional[List[dict]]:
    """A grade is seen by its owner and by a teacher who teaches that student
    — nobody else. None means the key is left out entirely."""
    base = db.query(Class).join(Enrollment, Enrollment.class_id == Class.id) \
        .filter(Enrollment.user_id == u.id)
    if viewer.id == u.id:
        classes = base.filter(Enrollment.status == "active").order_by(Class.id).all()
    elif viewer.role == "teacher":
        classes = base.filter(Class.teacher_id == viewer.id).order_by(Class.id).all()
        if not classes:
            return None
    else:
        return None
    return [{"class_id": k.id, "class_name": k.name, "summary": _summary(db, u.id, k)}
            for k in classes]


@router.get("/{username}")
def profile(username: str, viewer: User = Depends(get_current_user),
            db: Session = Depends(get_db)):
    u = _user_or_404(db, username)
    aura = (
        db.query(func.coalesce(func.sum(Post.like_count), 0))
        .filter(Post.author_id == u.id, Post.status == "active")
        .scalar()
    )
    out = {
        "id": u.id, "username": u.username, "name": u.name, "bio": u.bio,
        "avatar_url": avatar_for(u), "role": u.role, "is_me": viewer.id == u.id,
        "aura_received": int(aura), "has_own_avatar": u.has_own_avatar,
    }
    grades = _visible_grades(db, viewer, u)
    if grades is not None:
        out["grades"] = grades
    return out


@router.get("/{username}/posts")
def profile_posts(username: str,
                  tab: str = Query("posts", pattern="^(posts|replies)$"),
                  cursor: Optional[str] = Query(None),
                  limit: int = Query(20, ge=1, le=50),
                  viewer: User = Depends(get_current_user),
                  db: Session = Depends(get_db)):
    u = _user_or_404(db, username)
    class_ids = viewer_class_ids(db, viewer)
    q = (
        db.query(Post)
        .options(selectinload(Post.author), selectinload(Post.klass),
                 selectinload(Post.attachments))
        .filter(Post.author_id == u.id,
                Post.status.in_(("active", "vetoed")),
                assignment_visible(class_ids))
    )
    if tab == "posts":
        q = q.filter(Post.parent_id.is_(None))
    else:
        # Cheap prefilter for flagged entregas; _is_submission below is the
        # full definition (it also catches unflagged answers with files).
        q = q.filter(Post.parent_id.isnot(None), Post.is_entrega.is_(False))
    if cursor:
        try:
            c_dt, c_id = decode_cursor(cursor)
        except Exception:
            raise HTTPException(status_code=422, detail="Cursor inválido")
        q = q.filter(or_(Post.created_at < c_dt,
                         and_(Post.created_at == c_dt, Post.id < c_id)))
    rows = q.order_by(Post.created_at.desc(), Post.id.desc()).limit(limit + 1).all()
    has_more = len(rows) > limit
    rows = rows[:limit]
    # The cursor comes from the last FETCHED row, so a page whose rows were all
    # filtered out below still lets the client reach older ones.
    next_cursor = encode_cursor(rows[-1].created_at, rows[-1].id) if (has_more and rows) else None

    kept = []
    for p in rows:
        if tab == "replies" and (_is_submission(db, p)
                                 or not root_visible(get_root(db, p), class_ids)):
            continue
        kept.append(p)

    ids = [p.id for p in kept]
    liked = _liked_ids(db, viewer, ids)
    aura_ids = _teacher_aura_ids(db, ids)
    items = []
    for p in kept:
        d = serialize_post(p, liked, viewer=viewer, teacher_aura_ids=aura_ids).model_dump()
        if tab == "replies":
            parent = db.get(Post, p.parent_id)
            d["parent"] = {
                "id": parent.id,
                "author_username": parent.author.username,
                "excerpt": ("" if parent.status == "deleted" or _is_submission(db, parent)
                            else parent.content[:EXCERPT]),
            }
        items.append(d)
    return {"items": items, "next_cursor": next_cursor}
