"""Before/after numbers for the feed ranking (Bloque 4).

Run before a weights change and again two or three weeks later:
    cd backend && python -m scripts.feed_metrics
Reads existing tables only. Teachers are counted like anyone else; the
numbers are for comparing weeks, not for grading.
"""
from collections import defaultdict
from datetime import datetime
from typing import AbstractSet, Iterable, List, Optional, Tuple


def _week(dt: datetime) -> str:
    y, w, _ = dt.isocalendar()
    return f"{y}-W{w:02d}"


def weekly_metrics(rows: Iterable[Tuple[int, int, Optional[int], datetime]],
                   assignment_roots: AbstractSet[int] = frozenset()
                   ) -> List[Tuple[str, float, float]]:
    # Tareas, exámenes and their entregas follow the homework calendar, not
    # the feed: leave them out or the numbers measure the syllabus.
    rows = [r for r in rows if (r[2] if r[2] is not None else r[0]) not in assignment_roots]
    answered = {root for _, _, root, _ in rows if root is not None}
    active = defaultdict(set)
    replies = defaultdict(int)
    roots = defaultdict(int)
    roots_answered = defaultdict(int)
    for pid, author, root, at in rows:
        wk = _week(at)
        active[wk].add(author)
        if root is None:
            roots[wk] += 1
            roots_answered[wk] += pid in answered
        else:
            replies[wk] += 1
    out = []
    for wk in sorted(active):
        rps = round(replies[wk] / len(active[wk]), 2)
        share = round(roots_answered[wk] / roots[wk], 2) if roots[wk] else 0.0
        out.append((wk, rps, share))
    return out


def main() -> None:
    from app.database import SessionLocal
    from app.models import Post
    from app.services.feed_query import root_ids_of

    db = SessionLocal()
    try:
        posts = db.query(Post.id, Post.author_id, Post.parent_id, Post.created_at, Post.type).filter(
            Post.status != "deleted").all()
        assignments = {p.id for p in posts if p.parent_id is None and p.type in ("tarea", "examen")}
        root_of = root_ids_of(db, [p.id for p in posts if p.parent_id is not None])
        rows = [(p.id, p.author_id, root_of.get(p.id) if p.parent_id else None, p.created_at)
                for p in posts]
    finally:
        db.close()
    print("semana      respuestas/alumno  posts con respuesta")
    for wk, rps, share in weekly_metrics(rows, assignments):
        print(f"{wk}   {rps:>17.2f}  {share:>18.0%}")


if __name__ == "__main__":
    main()
