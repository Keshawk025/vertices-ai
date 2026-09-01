import logging
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from api.upload import router as upload_router
from api.auth import router as auth_router, get_current_user, User

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(title="Veritas AI")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(upload_router) # Dependencies now handled in the upload endpoint
from api.documents import router as documents_router
from api.conversations import router as conversations_router
from api.dashboard import router as dashboard_router
app.include_router(documents_router)
app.include_router(conversations_router)
app.include_router(dashboard_router)

import os
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# Mount static files directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def serve_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {
        "message": "Veritas AI Backend Running"
    }

@app.get("/api/health")
def api_health():
    return {
        "message": "Veritas AI Backend Running",
        "status": "healthy"
    }

@app.post("/ask")
def ask_question(current_user: User = Depends(get_current_user)):
    return {"message": "Protected ask endpoint"}

@app.post("/evaluation")
def run_eval(current_user: User = Depends(get_current_user)):
    return {"message": "Protected evaluation endpoint"}
