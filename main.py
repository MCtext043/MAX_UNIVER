from fastapi import FastAPI, Depends, HTTPException, Request, Form, File, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from database import get_db, init_db, SessionLocal
from models import *
from auth import *
from datetime import datetime, timedelta
import os
import shutil
from typing import Optional
import traceback

app = FastAPI(title="MAX UNIVER")

# Создаем директории для статики и шаблонов
os.makedirs("static", exist_ok=True)
os.makedirs("templates", exist_ok=True)
os.makedirs("uploads", exist_ok=True)

app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
templates = Jinja2Templates(directory="templates")

# Инициализация БД при запуске
@app.on_event("startup")
async def startup_event():
    init_db()
    # Всегда удаляем старые данные и заполняем новыми
    try:
        from fill_data import fill_test_data
        db = SessionLocal()
        try:
            fill_test_data(db)
            print("База данных очищена и заполнена новыми данными!")
        except Exception as e:
            print(f"Ошибка при заполнении данных: {e}")
        finally:
            db.close()
    except Exception as e:
        print(f"Не удалось импортировать fill_data: {e}")

# Глобальный обработчик ошибок
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    error_message = str(exc)
    if isinstance(exc, ValueError):
        error_message = f"Ошибка в данных: {error_message}"
    elif isinstance(exc, HTTPException):
        error_message = exc.detail
    else:
        error_message = "Произошла непредвиденная ошибка. Попробуйте позже."
    
    return templates.TemplateResponse("error.html", {
        "request": request,
        "error_message": error_message
    }, status_code=500)

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "error_message": "Ошибка валидации данных. Проверьте правильность введенных данных."
    }, status_code=400)

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("error.html", {
        "request": request,
        "error_message": exc.detail
    }, status_code=exc.status_code)

# ========== АУТЕНТИФИКАЦИЯ ==========

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form(...),
    role: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        if role not in ["student", "teacher", "deanery"]:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_message": "Неверная роль"
            }, status_code=400)
        
        if get_user_by_username(db, username):
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_message": "Пользователь с таким именем уже существует"
            }, status_code=400)
        
        if get_user_by_email(db, email):
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_message": "Пользователь с таким email уже существует"
            }, status_code=400)
        
        hashed_password = get_password_hash(password)
        user = User(
            username=username,
            email=email,
            hashed_password=hashed_password,
            full_name=full_name,
            role=role
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        
        access_token = create_access_token(data={"sub": user.username})
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="access_token", value=access_token, httponly=True)
        return response
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": f"Ошибка при регистрации: {str(e)}"
        }, status_code=500)

@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        user = authenticate_user(db, username, password)
        if not user:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_message": "Неверное имя пользователя или пароль"
            }, status_code=401)
        
        access_token = create_access_token(data={"sub": user.username})
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="access_token", value=access_token, httponly=True)
        return response
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": f"Ошибка при входе: {str(e)}"
        }, status_code=500)

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(key="access_token")
    return response

def get_current_user_from_cookie(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        user = get_user_by_username(db, username=username)
        return user
    except JWTError:
        return None

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "user": user
    })

# ========== РАСПИСАНИЕ ==========

@app.get("/schedule", response_class=HTMLResponse)
async def schedule_page(request: Request, db: Session = Depends(get_db)):
    try:
        user = get_current_user_from_cookie(request, db)
        if not user:
            return RedirectResponse(url="/login", status_code=303)
        
        schedules = db.query(Schedule).order_by(
            Schedule.day_of_week, Schedule.time_start
        ).all()
        
        days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        schedules_by_day = {}
        for day in days_order:
            schedules_by_day[day] = [s for s in schedules if s.day_of_week == day]
        
        has_schedules = any(schedules_by_day.values())
        
        return templates.TemplateResponse("schedule.html", {
            "request": request,
            "user": user,
            "schedules_by_day": schedules_by_day,
            "can_edit": user.role == "deanery",
            "has_schedules": has_schedules
        })
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": f"Ошибка при загрузке расписания: {str(e)}"
        }, status_code=500)

@app.post("/schedule/add")
async def add_schedule(
    request: Request,
    subject: str = Form(...),
    day_of_week: str = Form(...),
    time_start: str = Form(...),
    time_end: str = Form(...),
    room: str = Form(None),
    teacher_name: str = Form(None),
    db: Session = Depends(get_db)
):
    try:
        user = get_current_user_from_cookie(request, db)
        if not user or user.role != "deanery":
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_message": "Только деканат может добавлять расписание"
            }, status_code=403)
        
        schedule = Schedule(
            subject=subject,
            day_of_week=day_of_week,
            time_start=time_start,
            time_end=time_end,
            room=room,
            teacher_name=teacher_name,
            created_by=user.id
        )
        db.add(schedule)
        db.commit()
        return RedirectResponse(url="/schedule", status_code=303)
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": f"Ошибка при добавлении расписания: {str(e)}"
        }, status_code=500)

@app.post("/schedule/delete/{schedule_id}")
async def delete_schedule(
    request: Request,
    schedule_id: int,
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(request, db)
    if not user or user.role != "deanery":
        raise HTTPException(status_code=403, detail="Only deanery can delete schedules")
    
    schedule = db.query(Schedule).filter(Schedule.id == schedule_id).first()
    if schedule:
        db.delete(schedule)
        db.commit()
    return RedirectResponse(url="/schedule", status_code=303)

# ========== ОБЩЕЖИТИЕ ==========

@app.get("/dormitory", response_class=HTMLResponse)
async def dormitory_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    requests = db.query(DormitoryRequest).filter(
        DormitoryRequest.user_id == user.id
    ).order_by(DormitoryRequest.created_at.desc()).all()
    
    return templates.TemplateResponse("dormitory.html", {
        "request": request,
        "user": user,
        "requests": requests
    })

@app.post("/dormitory/request")
async def create_dormitory_request(
    request: Request,
    request_type: str = Form(...),
    description: str = Form(None),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    dorm_request = DormitoryRequest(
        user_id=user.id,
        request_type=request_type,
        description=description,
        status="pending"
    )
    db.add(dorm_request)
    db.commit()
    return RedirectResponse(url="/dormitory", status_code=303)

@app.get("/dormitory/admin", response_class=HTMLResponse)
async def dormitory_admin(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user or user.role != "deanery":
        raise HTTPException(status_code=403, detail="Access denied")
    
    all_requests = db.query(DormitoryRequest).order_by(
        DormitoryRequest.created_at.desc()
    ).all()
    
    return templates.TemplateResponse("dormitory_admin.html", {
        "request": request,
        "user": user,
        "requests": all_requests
    })

@app.post("/dormitory/update/{request_id}")
async def update_dormitory_request(
    request: Request,
    request_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(request, db)
    if not user or user.role != "deanery":
        raise HTTPException(status_code=403, detail="Access denied")
    
    dorm_request = db.query(DormitoryRequest).filter(DormitoryRequest.id == request_id).first()
    if dorm_request:
        dorm_request.status = status
        dorm_request.processed_at = datetime.utcnow()
        db.commit()
    
    return RedirectResponse(url="/dormitory/admin", status_code=303)

# ========== ДОКУМЕНТЫ ==========

@app.get("/documents", response_class=HTMLResponse)
async def documents_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    docs = db.query(Document).filter(
        Document.user_id == user.id
    ).order_by(Document.created_at.desc()).all()
    
    return templates.TemplateResponse("documents.html", {
        "request": request,
        "user": user,
        "documents": docs
    })

@app.post("/documents/create")
async def create_document(
    request: Request,
    document_type: str = Form(...),
    description: str = Form(None),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    doc = Document(
        user_id=user.id,
        document_type=document_type,
        description=description,
        status="pending"
    )
    db.add(doc)
    db.commit()
    return RedirectResponse(url="/documents", status_code=303)

@app.get("/documents/admin", response_class=HTMLResponse)
async def documents_admin(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user or user.role != "deanery":
        raise HTTPException(status_code=403, detail="Access denied")
    
    all_docs = db.query(Document).order_by(Document.created_at.desc()).all()
    
    return templates.TemplateResponse("documents_admin.html", {
        "request": request,
        "user": user,
        "documents": all_docs
    })

@app.post("/documents/update/{doc_id}")
async def update_document(
    request: Request,
    doc_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(request, db)
    if not user or user.role != "deanery":
        raise HTTPException(status_code=403, detail="Access denied")
    
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc:
        doc.status = status
        doc.processed_at = datetime.utcnow()
        db.commit()
    
    return RedirectResponse(url="/documents/admin", status_code=303)

# ========== НОВОСТИ ==========

@app.get("/news", response_class=HTMLResponse)
async def news_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    approved_news = db.query(News).filter(
        News.status == "approved"
    ).order_by(News.created_at.desc()).all()
    
    return templates.TemplateResponse("news.html", {
        "request": request,
        "user": user,
        "news": approved_news
    })

@app.get("/news/create", response_class=HTMLResponse)
async def create_news_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    
    return templates.TemplateResponse("news_create.html", {"request": request, "user": user})

@app.post("/news/create")
async def create_news(
    request: Request,
    title: str = Form(...),
    description: str = Form(...),
    photo: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(request, db)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    photo_path = None
    if photo:
        filename = f"news_{int(datetime.now().timestamp())}_{photo.filename}"
        file_path = f"uploads/{filename}"
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(photo.file, buffer)
        photo_path = f"/uploads/{filename}"
    
    news = News(
        title=title,
        description=description,
        photo_path=photo_path,
        author_id=user.id,
        status="pending"
    )
    db.add(news)
    db.commit()
    return RedirectResponse(url="/news", status_code=303)

@app.get("/news/admin", response_class=HTMLResponse)
async def news_admin(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user or user.role != "deanery":
        raise HTTPException(status_code=403, detail="Access denied")
    
    pending_news = db.query(News).filter(
        News.status == "pending"
    ).order_by(News.created_at.desc()).all()
    
    return templates.TemplateResponse("news_admin.html", {
        "request": request,
        "user": user,
        "news": pending_news
    })

@app.post("/news/update/{news_id}")
async def update_news(
    request: Request,
    news_id: int,
    status: str = Form(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(request, db)
    if not user or user.role != "deanery":
        raise HTTPException(status_code=403, detail="Access denied")
    
    news = db.query(News).filter(News.id == news_id).first()
    if news:
        news.status = status
        if status == "approved":
            news.approved_at = datetime.utcnow()
        db.commit()
    
    return RedirectResponse(url="/news/admin", status_code=303)

# ========== ПРЕПОДАВАТЕЛЬ ==========

@app.get("/teacher", response_class=HTMLResponse)
async def teacher_page(request: Request, db: Session = Depends(get_db)):
    user = get_current_user_from_cookie(request, db)
    if not user or user.role != "teacher":
        raise HTTPException(status_code=403, detail="Access denied")
    
    groups = db.query(Group).filter(Group.teacher_id == user.id).all()
    
    return templates.TemplateResponse("teacher.html", {
        "request": request,
        "user": user,
        "groups": groups
    })

@app.post("/teacher/group/create")
async def create_group(
    request: Request,
    name: str = Form(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(request, db)
    if not user or user.role != "teacher":
        raise HTTPException(status_code=403, detail="Access denied")
    
    group = Group(name=name, teacher_id=user.id)
    db.add(group)
    db.commit()
    return RedirectResponse(url="/teacher", status_code=303)

@app.get("/teacher/group/{group_id}", response_class=HTMLResponse)
async def group_detail(
    request: Request,
    group_id: int,
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(request, db)
    if not user or user.role != "teacher":
        raise HTTPException(status_code=403, detail="Access denied")
    
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or group.teacher_id != user.id:
        raise HTTPException(status_code=404, detail="Group not found")
    
    students = db.query(User).join(GroupStudent).filter(
        GroupStudent.group_id == group_id
    ).all()
    
    all_students = db.query(User).filter(User.role == "student").all()
    
    attendance = db.query(AttendanceRecord).filter(
        AttendanceRecord.group_id == group_id
    ).order_by(AttendanceRecord.date.desc()).limit(50).all()
    
    return templates.TemplateResponse("group_detail.html", {
        "request": request,
        "user": user,
        "group": group,
        "students": students,
        "all_students": all_students,
        "attendance": attendance
    })

@app.post("/teacher/group/{group_id}/add_student")
async def add_student_to_group(
    request: Request,
    group_id: int,
    student_id: int = Form(...),
    db: Session = Depends(get_db)
):
    user = get_current_user_from_cookie(request, db)
    if not user or user.role != "teacher":
        raise HTTPException(status_code=403, detail="Access denied")
    
    group = db.query(Group).filter(Group.id == group_id).first()
    if not group or group.teacher_id != user.id:
        raise HTTPException(status_code=404, detail="Group not found")
    
    existing = db.query(GroupStudent).filter(
        GroupStudent.group_id == group_id,
        GroupStudent.student_id == student_id
    ).first()
    
    if not existing:
        group_student = GroupStudent(group_id=group_id, student_id=student_id)
        db.add(group_student)
        db.commit()
    
    return RedirectResponse(url=f"/teacher/group/{group_id}", status_code=303)

@app.post("/teacher/attendance")
async def mark_attendance(
    request: Request,
    group_id: int = Form(...),
    student_id: int = Form(...),
    date: str = Form(...),
    present: bool = Form(False),
    notes: str = Form(None),
    db: Session = Depends(get_db)
):
    try:
        user = get_current_user_from_cookie(request, db)
        if not user or user.role != "teacher":
            raise HTTPException(status_code=403, detail="Access denied")
        
        group = db.query(Group).filter(Group.id == group_id).first()
        if not group or group.teacher_id != user.id:
            raise HTTPException(status_code=404, detail="Group not found")
        
        # Безопасный парсинг даты
        try:
            if 'T' in date:
                parsed_date = datetime.fromisoformat(date.replace('Z', '+00:00'))
            else:
                # Пробуем разные форматы
                try:
                    parsed_date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S')
                except:
                    try:
                        parsed_date = datetime.strptime(date, '%Y-%m-%d %H:%M')
                    except:
                        parsed_date = datetime.strptime(date, '%Y-%m-%d')
        except Exception as e:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_message": f"Неверный формат даты. Используйте формат: ГГГГ-ММ-ДД ЧЧ:ММ"
            }, status_code=400)
        
        attendance = AttendanceRecord(
            group_id=group_id,
            student_id=student_id,
            date=parsed_date,
            present=present,
            notes=notes
        )
        db.add(attendance)
        db.commit()
        
        return RedirectResponse(url=f"/teacher/group/{group_id}", status_code=303)
    except HTTPException:
        raise
    except Exception as e:
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_message": f"Ошибка при сохранении посещаемости: {str(e)}"
        }, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

