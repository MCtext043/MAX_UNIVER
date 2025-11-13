from database import SessionLocal, init_db
from models import User, Schedule, News, Group, GroupStudent, AttendanceRecord
from auth import get_password_hash
from datetime import datetime, timedelta

def fill_test_data(db):
    """Заполняет базу данных тестовыми данными"""
    
    # Создаем пользователей
    users_data = [
        {"username": "admin", "email": "admin@univer.ru", "password": "admin123", "full_name": "Администратор Деканата", "role": "deanery"},
        {"username": "teacher1", "email": "teacher1@univer.ru", "password": "teacher123", "full_name": "Иванов Иван Иванович", "role": "teacher"},
        {"username": "teacher2", "email": "teacher2@univer.ru", "password": "teacher123", "full_name": "Петрова Мария Сергеевна", "role": "teacher"},
        {"username": "student1", "email": "student1@univer.ru", "password": "student123", "full_name": "Сидоров Петр Александрович", "role": "student"},
        {"username": "student2", "email": "student2@univer.ru", "password": "student123", "full_name": "Козлова Анна Дмитриевна", "role": "student"},
        {"username": "student3", "email": "student3@univer.ru", "password": "student123", "full_name": "Морозов Дмитрий Викторович", "role": "student"},
    ]
    
    created_users = {}
    for user_data in users_data:
        existing = db.query(User).filter(User.username == user_data["username"]).first()
        if not existing:
            user = User(
                username=user_data["username"],
                email=user_data["email"],
                hashed_password=get_password_hash(user_data["password"]),
                full_name=user_data["full_name"],
                role=user_data["role"]
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            created_users[user_data["username"]] = user
        else:
            created_users[user_data["username"]] = existing
    
    # Создаем расписание
    if db.query(Schedule).count() == 0:
        schedules_data = [
            {"subject": "Математика", "day_of_week": "Monday", "time_start": "09:00", "time_end": "10:30", "room": "101", "teacher_name": "Иванов И.И."},
            {"subject": "Физика", "day_of_week": "Monday", "time_start": "10:45", "time_end": "12:15", "room": "205", "teacher_name": "Петрова М.С."},
            {"subject": "Программирование", "day_of_week": "Tuesday", "time_start": "09:00", "time_end": "10:30", "room": "301", "teacher_name": "Иванов И.И."},
            {"subject": "Базы данных", "day_of_week": "Tuesday", "time_start": "10:45", "time_end": "12:15", "room": "301", "teacher_name": "Иванов И.И."},
            {"subject": "Алгоритмы", "day_of_week": "Wednesday", "time_start": "09:00", "time_end": "10:30", "room": "301", "teacher_name": "Петрова М.С."},
            {"subject": "Математика", "day_of_week": "Thursday", "time_start": "09:00", "time_end": "10:30", "room": "101", "teacher_name": "Иванов И.И."},
            {"subject": "Физика", "day_of_week": "Friday", "time_start": "09:00", "time_end": "10:30", "room": "205", "teacher_name": "Петрова М.С."},
        ]
        
        admin_user = created_users.get("admin")
        for schedule_data in schedules_data:
            schedule = Schedule(
                **schedule_data,
                created_by=admin_user.id if admin_user else None
            )
            db.add(schedule)
        db.commit()
    
    # Создаем новости
    if db.query(News).count() == 0:
        news_data = [
            {
                "title": "Добро пожаловать в MAX UNIVER!",
                "description": "Мы рады приветствовать вас в нашей цифровой платформе. Здесь вы можете просматривать расписание, оформлять документы и многое другое.",
                "author_id": created_users["admin"].id,
                "status": "approved"
            },
            {
                "title": "Важное объявление о расписании",
                "description": "Обратите внимание: расписание на следующую неделю может быть изменено. Следите за обновлениями.",
                "author_id": created_users["admin"].id,
                "status": "approved"
            },
            {
                "title": "Начало нового учебного года",
                "description": "Поздравляем всех студентов и преподавателей с началом нового учебного года! Желаем успехов в учебе и работе.",
                "author_id": created_users["admin"].id,
                "status": "approved"
            },
        ]
        
        for news_item in news_data:
            news = News(**news_item, approved_at=datetime.utcnow())
            db.add(news)
        db.commit()
    
    # Создаем группы для преподавателей
    if db.query(Group).count() == 0:
        teacher1 = created_users.get("teacher1")
        teacher2 = created_users.get("teacher2")
        
        if teacher1:
            group1 = Group(name="Группа ИТ-21", teacher_id=teacher1.id)
            db.add(group1)
            db.commit()
            db.refresh(group1)
            
            # Добавляем студентов в группу
            student1 = created_users.get("student1")
            student2 = created_users.get("student2")
            if student1:
                group_student1 = GroupStudent(group_id=group1.id, student_id=student1.id)
                db.add(group_student1)
            if student2:
                group_student2 = GroupStudent(group_id=group1.id, student_id=student2.id)
                db.add(group_student2)
            
            # Добавляем записи посещаемости
            if student1:
                attendance1 = AttendanceRecord(
                    group_id=group1.id,
                    student_id=student1.id,
                    date=datetime.now() - timedelta(days=1),
                    present=True,
                    notes="Активное участие"
                )
                db.add(attendance1)
        
        if teacher2:
            group2 = Group(name="Группа ФИЗ-21", teacher_id=teacher2.id)
            db.add(group2)
            db.commit()
            db.refresh(group2)
            
            student3 = created_users.get("student3")
            if student3:
                group_student3 = GroupStudent(group_id=group2.id, student_id=student3.id)
                db.add(group_student3)
        
        db.commit()
    
    print("Тестовые данные успешно добавлены!")

if __name__ == "__main__":
    init_db()
    db = SessionLocal()
    try:
        fill_test_data(db)
    finally:
        db.close()

