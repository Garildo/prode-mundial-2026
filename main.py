import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import football_api
import models
from database import SessionLocal, engine
from routers import admin, auth, groups, matches, predictions, rankings

load_dotenv()


def create_tables():
    models.Base.metadata.create_all(bind=engine)


scheduler = AsyncIOScheduler()


async def _scheduled_sync():
    db = SessionLocal()
    try:
        await football_api.sync_matches(db)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_tables()
    scheduler.add_job(_scheduled_sync, "interval", minutes=5, id="sync_matches")
    scheduler.start()
    # Sync inicial al arrancar (no crítico — si falla la app sigue)
    db = SessionLocal()
    try:
        await football_api.sync_matches(db)
    except Exception:
        pass
    finally:
        db.close()
    yield
    scheduler.shutdown()


app = FastAPI(title="Prode Mundial 2026", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

app.include_router(admin.router)
app.include_router(auth.router)
app.include_router(groups.router)
app.include_router(matches.router)
app.include_router(predictions.router)
app.include_router(rankings.router)


@app.get("/")
async def page_login(request: Request):
    return templates.TemplateResponse(request=request, name="login.html")


@app.get("/app")
async def page_home(request: Request):
    return templates.TemplateResponse(request=request, name="home.html")


@app.get("/app/group/{group_id}")
async def page_group(request: Request, group_id: int):
    return templates.TemplateResponse(request=request, name="group.html")


@app.get("/app/predict/{match_id}")
async def page_predict(request: Request, match_id: int):
    return templates.TemplateResponse(request=request, name="predict.html")


@app.get("/app/matches")
async def page_matches(request: Request):
    return templates.TemplateResponse(request=request, name="matches.html")


@app.get("/admin")
async def page_admin(request: Request):
    return templates.TemplateResponse(request=request, name="admin.html")


@app.get("/ping")
async def ping():
    return {"status": "ok"}
