import logging
from fastapi import FastAPI, Depends
from api.upload import router as upload_router
from api.auth import router as auth_router, get_current_user, User

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

app = FastAPI(title="Veritas AI")

app.include_router(auth_router)
app.include_router(upload_router) # Dependencies now handled in the upload endpoint
from api.documents import router as documents_router
from api.conversations import router as conversations_router
from api.dashboard import router as dashboard_router
app.include_router(documents_router)
app.include_router(conversations_router)
app.include_router(dashboard_router)

@app.get("/")
def root():
    return {
        "message": "Veritas AI Backend Running"
    }

@app.post("/ask")
def ask_question(current_user: User = Depends(get_current_user)):
    return {"message": "Protected ask endpoint"}

@app.post("/evaluation")
def run_eval(current_user: User = Depends(get_current_user)):
    return {"message": "Protected evaluation endpoint"}
