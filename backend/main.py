from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.auth import router as auth_router
from app.api.categories import router as categories_router
from app.api.experts import router as experts_router
from app.api.expert_documents import router as expert_documents_router
from app.api.admin import router as admin_router
from app.api.chat import router as chat_router
from app.api.speech import router as speech_router

app = FastAPI(title="ExpertHub API", version="1.0.0", debug=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(categories_router)
app.include_router(experts_router)
app.include_router(expert_documents_router)
app.include_router(admin_router)
app.include_router(chat_router)
app.include_router(speech_router)

@app.get("/")
def root():
    return {"message": "ExpertHub API ishlayapti!"}