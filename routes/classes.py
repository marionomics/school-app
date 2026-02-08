"""
Class management routes for teachers and students.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from models.database import get_db
from models.models import Student, Class, StudentClass
from models.schemas import (
    ClassCreate,
    ClassResponse,
    JoinClassRequest,
    StudentClassResponse,
    ClassWithStudents,
    StudentResponse,
)
from app.auth import get_current_student, get_current_teacher, get_student_or_impersonated

router = APIRouter(prefix="/api/classes", tags=["classes"])


# Teacher endpoints

@router.post("/", response_model=ClassResponse)
async def create_class(
    data: ClassCreate,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Create a new class (teacher only)."""
    code = Class.generate_code(data.code_prefix or "")

    # Ensure code is unique (regenerate if collision)
    while db.query(Class).filter(Class.code == code).first():
        code = Class.generate_code(data.code_prefix or "")

    new_class = Class(
        name=data.name,
        code=code,
        teacher_id=teacher.id,
    )
    db.add(new_class)
    db.commit()
    db.refresh(new_class)

    return ClassResponse(
        id=new_class.id,
        name=new_class.name,
        code=new_class.code,
        teacher_id=new_class.teacher_id,
        created_at=new_class.created_at,
        student_count=0,
    )


@router.get("/teaching", response_model=list[ClassResponse])
async def list_teaching_classes(
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """List all classes taught by the current teacher."""
    classes = db.query(Class).filter(Class.teacher_id == teacher.id).all()

    result = []
    for c in classes:
        student_count = db.query(func.count(StudentClass.id)).filter(
            StudentClass.class_id == c.id
        ).scalar()
        result.append(ClassResponse(
            id=c.id,
            name=c.name,
            code=c.code,
            teacher_id=c.teacher_id,
            created_at=c.created_at,
            student_count=student_count,
        ))

    return result


@router.get("/teaching/{class_id}", response_model=ClassWithStudents)
async def get_class_details(
    class_id: int,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Get class details with enrolled students (teacher only)."""
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.teacher_id == teacher.id,
    ).first()

    if not class_:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clase no encontrada",
        )

    # Get enrolled students
    enrollments = db.query(StudentClass).filter(StudentClass.class_id == class_id).all()
    students = [StudentResponse(
        id=e.student.id,
        name=e.student.name,
        email=e.student.email,
        role=e.student.role,
        created_at=e.student.created_at,
    ) for e in enrollments]

    return ClassWithStudents(
        id=class_.id,
        name=class_.name,
        code=class_.code,
        teacher_id=class_.teacher_id,
        created_at=class_.created_at,
        student_count=len(students),
        students=students,
    )


@router.delete("/teaching/{class_id}")
async def delete_class(
    class_id: int,
    teacher: Student = Depends(get_current_teacher),
    db: Session = Depends(get_db),
):
    """Delete a class (teacher only)."""
    class_ = db.query(Class).filter(
        Class.id == class_id,
        Class.teacher_id == teacher.id,
    ).first()

    if not class_:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Clase no encontrada",
        )

    db.delete(class_)
    db.commit()

    return {"message": "Clase eliminada exitosamente"}


# Student endpoints

@router.get("/enrolled", response_model=list[StudentClassResponse])
async def list_enrolled_classes(
    student: Student = Depends(get_student_or_impersonated),
    db: Session = Depends(get_db),
):
    """List all classes the current student is enrolled in."""
    enrollments = db.query(StudentClass).filter(
        StudentClass.student_id == student.id
    ).all()

    return [StudentClassResponse(
        id=e.id,
        class_id=e.class_.id,
        class_name=e.class_.name,
        class_code=e.class_.code,
        joined_at=e.joined_at,
    ) for e in enrollments]


@router.post("/join", response_model=StudentClassResponse)
async def join_class(
    data: JoinClassRequest,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Join a class using its code."""
    # Teachers cannot join classes as students
    if student.role == "teacher":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Los profesores no pueden inscribirse como estudiantes",
        )

    # Find class by code
    class_ = db.query(Class).filter(Class.code == data.code.upper()).first()
    if not class_:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Codigo de clase invalido",
        )

    # Check if already enrolled
    existing = db.query(StudentClass).filter(
        StudentClass.student_id == student.id,
        StudentClass.class_id == class_.id,
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya estas inscrito en esta clase",
        )

    enrollment = StudentClass(
        student_id=student.id,
        class_id=class_.id,
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    return StudentClassResponse(
        id=enrollment.id,
        class_id=class_.id,
        class_name=class_.name,
        class_code=class_.code,
        joined_at=enrollment.joined_at,
    )


@router.delete("/leave/{class_id}")
async def leave_class(
    class_id: int,
    student: Student = Depends(get_current_student),
    db: Session = Depends(get_db),
):
    """Leave a class (student only)."""
    enrollment = db.query(StudentClass).filter(
        StudentClass.student_id == student.id,
        StudentClass.class_id == class_id,
    ).first()

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No estas inscrito en esta clase",
        )

    db.delete(enrollment)
    db.commit()

    return {"message": "Has salido de la clase exitosamente"}
