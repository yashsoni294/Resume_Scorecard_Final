# # database.py
# from sqlalchemy import create_engine
# from sqlalchemy.ext.declarative import declarative_base
# from sqlalchemy.orm import sessionmaker

# SQLALCHAMY_DATABASE_URL = "sqlite:///./database.db"

# engine = create_engine(SQLALCHAMY_DATABASE_URL, connect_args={
#                        "check_same_thread": False})

# SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False,)

# Base = declarative_base()


# # models.py

# from sqlalchemy import Column, Integer, String, ForeignKey, UUID, Text
# import uuid
# from database import Base


# class ResumeTable(Base):
#     __tablename__ = 'resume_table'

#     unique_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
#     resume_name = Column(String(100))
#     resume_content = Column(Text)
#     resume_key_aspect = Column(Text)
#     score = Column(Integer)


# # insert.py

# from sqlalchemy.orm import Session
# from models import ResumeTable
# from database import SessionLocal
# import uuid

# # Function to insert data into ResumeTable
# def insert_resume_data(unique_id, resume_name, resume_content, resume_key_aspect, score):
#     # Step 1: Create a new session
#     db: Session = SessionLocal()
    
#     # Step 2: Create an instance of ResumeTable with the provided data
#     new_resume = ResumeTable(
#         unique_id = unique_id,
#         resume_name=resume_name,
#         resume_content=resume_content,
#         resume_key_aspect=resume_key_aspect,
#         score=score
#     )
    
#     # Step 3: Add the instance to the session
#     db.add(new_resume)
    
#     # Step 4: Commit the session to save the data in the database
#     db.commit()
    
#     # Step 5: Close the session
#     db.refresh(new_resume)  # This will refresh the instance with data from the database
#     db.close()
    
#     return new_resume  # Optionally return the created record

# # Example usage
# # new_resume = insert_resume_data(
# #     resume_name="John Doe's Resume",
# #     resume_content="Experienced Software Developer...",
# #     resume_key_aspect="Expert in Python, Machine Learning",
# #     score=90
# # )

# for i in range(10000):
#     new_resume = insert_resume_data(
#     unique_id = uuid.uuid4(),
#     resume_name="John Doe's Resume",
#     resume_content="Experienced Software Developer...",
#     resume_key_aspect="Expert in Python, Machine Learning",
#     score=90
#     )
# print(f"New resume inserted with ID: {new_resume.unique_id}")


# # main_two.py

# import models
# from database import engine

# models.Base.metadata.create_all(engine)