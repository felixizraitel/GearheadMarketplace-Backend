from fastapi.middleware.cors import CORSMiddleware

from typing import List

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi import File, UploadFile, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy.sql.expression import null
from pydantic import BaseModel

from sql import crud, models, schemas
from sql.database import SessionLocal, engine

# AWS S3 
from botocore.client import BaseClient
from botocore.exceptions import ClientError
from s3.deps import s3_auth
from s3.upload import upload_file_to_bucket
from s3.download import download_file_from_bucket
from enum import Enum

models.Base.metadata.create_all(bind=engine)

app = FastAPI()

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

origins = [
    "http://localhost:3000",
    "localhost:3000",
    "localhost:8888",
    "http://localhost:8888",
    "http://localhost:8000",
    "localhost:8000",
    "localhost",
    "localhost:80",
    "http://localhost",
    "http://localhost:80",
    "https://gearheadmarketplace.herokuapp.com",
    "gearheadmarketplace.herokuapp.com",
    "https://www.gearheadmarketplace.herokuapp.com",
    "www.gearheadmarketplace.herokuapp.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

@app.get("/", tags=["root"])
async def read_root() -> dict:
    return {"message": "Welcome to your todo list."}

@app.get("/status")
async def return_server_status():
    if engine != null:
        return "online"
    return "offline"

@app.post("/users/", response_model=schemas.User)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if crud.get_user_by_email(db, email=user.email) or crud.get_user_by_user_name(db, user_name=user.user_name):
        raise HTTPException(status_code=400, detail="Email or username already registered")
    return crud.create_user(db=db, user=user)

@app.get("/users/", response_model=List[schemas.User])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = crud.get_users(db, skip=skip, limit=limit)
    return users

@app.get("/users/{user_id}", response_model=schemas.User)
def read_user(user_id: int, db: Session = Depends(get_db)):
    db_user = crud.get_user(db, user_id=user_id)
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return db_user

@app.post("/users/{user_id}/offers/", response_model=schemas.Offer)
def create_item_for_user(
    user_id: int, item: schemas.OfferCreate, db: Session = Depends(get_db)
):
    return crud.create_user_item(db=db, item=item, user_id=user_id)

@app.get("/users/{user_id}/offers/", response_model=List[schemas.Offer])
def read_user_items(user_id: int, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    items = crud.get_user_items(db, user_id, skip=skip, limit=limit)
    return items

@app.get("/offers/", response_model=List[schemas.Offer])
def read_items(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    items = crud.get_items(db, skip=skip, limit=limit)
    return items

@app.post("/login/")
def login_user(user: schemas.UserLogin, db: Session = Depends(get_db)):
    db_user = crud.get_user_by_email(db, email=user.email)
    if db_user is None:
        return "Username or password is wrong"
    if db_user.password == user.password:
        return "login success"
    return "Username or password is wrong"

@app.post("/upload_offer/", response_model="")
async def upload_offer(user_id: int = Form(...),
                        title: str = Form(...), 
                        description: str = Form(...), 
                        price: float = Form(...),
                        location: str = Form(...),
                        shipping_availability: bool = Form(...),
                        file: UploadFile = File(...), s3: BaseClient = Depends(s3_auth), db: Session = Depends(get_db)):
    offer = models.Offer(title=title, price=price, location = location,description=description, shipping_availability=shipping_availability, owner_id=user_id)

    offerMsg = crud.create_user_item(db=db, offer=offer)
    
    # offerID = crud.create_user_item(db=db, offer=offer)
    # offer1 = schemas.OfferCreate(title, price, location, description)
    # crud.create_user_item(db=db, offer)
    upload_obj = upload_file_to_bucket(s3_client=s3, file_obj=file.file,
                                       bucket="gearhead-images",
                                       folder="images",
                                       object_name=file.filename
                                       )
    if(upload_obj):
        imgURL = 'https://gearhead-images.s3.amazonaws.com/images/' + file.filename
        img = models.Image(link=imgURL, offer_id=offerMsg.id)
        crud.attach_offer_image(db=db, img=img)
    return {offerMsg, upload_obj}


# # testing AWS S3 STARTS
# @app.get("/buckets")
# def get_buckets(s3: BaseClient = Depends(s3_auth)):
#     response = s3.list_buckets()
#     return response['Buckets']

# @app.get("/buckets/list")
# def get_list_of_buckets(s3: BaseClient = Depends(s3_auth)):
#     response = s3.list_buckets()
#     buckets = []

#     for bucket in response['Buckets']:
#         buckets.append(bucket['Name'])
#         # print(bucket['Name'])

#     # BucketName = Enum('BucketName', buckets)
#     return buckets

# @app.get("/buckets/download" , status_code=status.HTTP_201_CREATED, summary="Download files from AWS S3 Buckets",
#              description="Download file from AWS S3 bucket", name="Get files from AWS S3",
#              response_description="Successfully uploaded file to S3 bucket")
# def download_file(bucket: str, folder: str, fileName: str, s3: BaseClient = Depends(s3_auth)):
#     # response = s3.list_buckets()
#     response = s3.list_objects(Bucket="gearhead-images")
#     # download_obj = download_file_from_bucket(s3, bucket, folder, fileName)
#     #s3.download_file('BUCKET_NAME', 'OBJECT_NAME', 'FILE_NAME')
# # response = s3_client.upload_fileobj(file_obj, bucket, f"{folder}/{object_name}")
#             # s3.upload_fileobj(f, "BUCKET_NAME", "OBJECT_NAME")

#     #this works... downloads the file into the computer
#     # downloadedFile = s3.download_file(bucket, f"{folder}/{fileName}", fileName)
#     return response['Contents']

# @app.post("/buckets/upload", status_code=status.HTTP_201_CREATED, summary="Upload files to AWS S3 Buckets",
#              description="Upload a valid file to AWS S3 bucket", name="POST files to AWS S3",
#              response_description="Successfully uploaded file to S3 bucket")
# def upload_file(folder: str, bucket: str, s3: BaseClient = Depends(s3_auth), file_obj: UploadFile = File(...)):
#     upload_obj = upload_file_to_bucket(s3_client=s3, file_obj=file_obj.file,
#                                        bucket=bucket,
#                                        folder=folder,
#                                        object_name=file_obj.filename
#                                        )
#     return upload_obj
#     if upload_obj:
#         return JSONResponse(content="Object has been uploaded to bucket successfully",
#                             status_code=status.HTTP_201_CREATED)
#     else:
#         raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#                             detail="File could not be uploaded")
# testing AWS S3 ENDS



#testing file upload to AWS S3
# @app.post("/uploadfile/", response_model="")
# async def create_upload_file(bucket: str = Form(...), folder: str = Form(...), file: UploadFile = File(...), s3: BaseClient = Depends(s3_auth)):
#     upload_obj = upload_file_to_bucket(s3_client=s3, file_obj=file.file,
#                                        bucket=bucket,
#                                        folder=folder,
#                                        object_name=file.filename
#                                        )
#     return {"bucket": bucket, "folder" : folder, "file name: " : file.filename}