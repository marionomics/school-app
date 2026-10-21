from typing import List

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import Class, Enrollment, Post, User

ASSIGNMENT_TYPES = ("tarea", "examen")


def viewer_class_ids(db: Session, viewer: User) -> List[int]:
    """Classes whose assignments this viewer may see: every enrollment —
    no status filter on purpose, ghost and polizón are in the class — plus
    every class they teach."""
    ids = [cid for (cid,) in db.query(Enrollment.class_id)
           .filter(Enrollment.user_id == viewer.id).all()]
    ids += [cid for (cid,) in db.query(Class.id)
            .filter(Class.teacher_id == viewer.id).all()]
    return ids


def assignment_visible(class_ids: List[int]):
    """Social content is global — all classes, all semesters. Assignments are
    not: a student cannot tell another class's tarea from work they owe."""
    return or_(Post.type.notin_(ASSIGNMENT_TYPES), Post.class_id.in_(class_ids))


def root_visible(root: Post, class_ids: List[int]) -> bool:
    """The same rule, for a thread's root already in memory."""
    return root.type not in ASSIGNMENT_TYPES or root.class_id in class_ids
