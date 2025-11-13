from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, nullable=False)  # student, teacher, deanery
    full_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    schedules = relationship("Schedule", back_populates="created_by_user")
    dormitory_requests = relationship("DormitoryRequest", back_populates="user")
    documents = relationship("Document", back_populates="user")
    news = relationship("News", back_populates="author")
    attendance_records = relationship("AttendanceRecord", back_populates="student")
    groups = relationship("Group", back_populates="teacher")

class Schedule(Base):
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String, nullable=False)
    day_of_week = Column(String, nullable=False)  # Monday, Tuesday, etc.
    time_start = Column(String, nullable=False)  # HH:MM
    time_end = Column(String, nullable=False)  # HH:MM
    room = Column(String, nullable=True)
    teacher_name = Column(String, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    created_by_user = relationship("User", back_populates="schedules")

class DormitoryRequest(Base):
    __tablename__ = "dormitory_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    request_type = Column(String, nullable=False)  # pass, repair, payment
    description = Column(Text, nullable=True)
    status = Column(String, default="pending")  # pending, approved, rejected, completed
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="dormitory_requests")

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    document_type = Column(String, nullable=False)  # certificate, academic_leave, transfer, vacation
    description = Column(Text, nullable=True)
    status = Column(String, default="pending")  # pending, approved, rejected, issued
    created_at = Column(DateTime, default=datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    
    user = relationship("User", back_populates="documents")

class News(Base):
    __tablename__ = "news"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    photo_path = Column(String, nullable=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    status = Column(String, default="pending")  # pending, approved, rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    
    author = relationship("User", back_populates="news")

class Group(Base):
    __tablename__ = "groups"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    teacher_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    teacher = relationship("User", back_populates="groups")
    students = relationship("GroupStudent", back_populates="group")
    attendance_records = relationship("AttendanceRecord", back_populates="group")

class GroupStudent(Base):
    __tablename__ = "group_students"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    added_at = Column(DateTime, default=datetime.utcnow)
    
    group = relationship("Group", back_populates="students")
    student = relationship("User")

class AttendanceRecord(Base):
    __tablename__ = "attendance_records"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    present = Column(Boolean, default=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    group = relationship("Group", back_populates="attendance_records")
    student = relationship("User", back_populates="attendance_records")

