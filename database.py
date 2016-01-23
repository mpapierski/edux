from sqlalchemy import Column, Date, String, Integer, ForeignKey
from sqlalchemy.orm import relationship, backref
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()
Session = sessionmaker()


class Course(Base):
    __tablename__ = 'courses'
    course_id = Column(Integer, primary_key=True)
    title = Column(String)


class Announcement(Base):
    __tablename__ = 'announcements'
    announcement_id = Column(Integer, primary_key=True)
    course_id = Column(Integer, ForeignKey('courses.course_id'))
    created_at = Column(Date)
    message = Column(String)
    # Use cascade='delete,all' to propagate the deletion of a Department onto
    # its Employees
    course = relationship(
        Course,
        backref=backref('announcements',
                        cascade='delete,all'))

from sqlalchemy import create_engine
engine = create_engine('sqlite:///db.sqlite')


Session.configure(bind=engine)
Base.metadata.create_all(engine)
