"""FastAPI entry point for the Manufacturing Floor Assistant.

Serves auth (signup / email login), the role-gated chat UI with persistent sessions,
and an admin console for approving signup requests. `/api/chat` runs the LangGraph
agent when a Groq key is configured, and falls back to the stub otherwise.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app import stub
from app.auth import (
    AuthError,
    User,
    authenticate,
    create_access_token,
    decode_access_token,
    seed_accounts,
    signup,
)
from app.config import Settings, load_settings
from app.db import STATUS_ACTIVE, STATUS_DENIED, VALID_ROLES, Database

logger = logging.getLogger("floor_assistant")
logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent
COOKIE_NAME = "access_token"

settings: Settings = load_settings()  # fail fast on missing config
db = Database(settings.db_path)
USE_AGENT = bool(os.environ.get("GROQ_API_KEY"))


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Seed accounts and warm models on startup."""
    seed_accounts(db, settings)
    logger.info("accounts seeded (admin=%s)", settings.admin_email)
    if USE_AGENT:
        def _warm() -> None:
            try:
                from app.backend.agent import _retriever  # noqa: PLC0415

                _retriever()
                logger.info("agent models warmed")
            except Exception:  # noqa: BLE001
                logger.exception("model warmup failed")

        threading.Thread(target=_warm, daemon=True).start()
    else:
        logger.info("agent disabled (no GROQ_API_KEY) — using stub responses")
    yield


app = FastAPI(title="Manufacturing Floor Assistant", version="0.2.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# --- Auth dependencies ------------------------------------------------------

def current_user(
    access_token: Annotated[str | None, Cookie(alias=COOKIE_NAME)] = None,
) -> User | None:
    """Resolve the logged-in user from the session cookie, or None."""
    if not access_token:
        return None
    return decode_access_token(access_token, settings)


def require_user(user: Annotated[User | None, Depends(current_user)]) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_admin(user: Annotated[User, Depends(require_user)]) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


def _set_session_cookie(response, user: User) -> None:
    token = create_access_token(user, settings)
    response.set_cookie(
        key=COOKIE_NAME, value=token, httponly=True, samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )


# --- Request/response models ------------------------------------------------

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    session_id: int | None = None


class FeedbackRequest(BaseModel):
    message_id: int
    rating: str = Field(pattern="^(up|down)$")


class DecisionRequest(BaseModel):
    decision: str = Field(pattern="^(approve|deny)$")
    role: str | None = None


# --- Page routes ------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index(user: Annotated[User | None, Depends(current_user)]) -> RedirectResponse:
    return RedirectResponse(url="/chat" if user else "/login", status_code=302)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login", response_model=None)
def login_submit(
    email: Annotated[str, Form()], password: Annotated[str, Form()], request: Request
) -> HTMLResponse | RedirectResponse:
    try:
        user = authenticate(db, email, password)
    except AuthError as exc:
        return templates.TemplateResponse(
            request, "login.html", {"error": str(exc)}, status_code=401
        )
    response = RedirectResponse(url="/chat", status_code=302)
    _set_session_cookie(response, user)
    logger.info("login success email=%s role=%s", user.email, user.role)
    return response


@app.get("/signup", response_class=HTMLResponse)
def signup_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "signup.html", {"error": None, "done": False})


@app.post("/signup", response_model=None)
def signup_submit(
    request: Request,
    email: Annotated[str, Form()],
    name: Annotated[str, Form()],
    password: Annotated[str, Form()],
    requested_role: Annotated[str, Form()],
) -> HTMLResponse:
    try:
        signup(db, email, name, password, requested_role)
    except AuthError as exc:
        return templates.TemplateResponse(
            request, "signup.html", {"error": str(exc), "done": False}, status_code=400
        )
    logger.info("signup request email=%s role=%s", email, requested_role)
    return templates.TemplateResponse(request, "signup.html", {"error": None, "done": True})


@app.post("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse(url="/login", status_code=302)
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/chat", response_class=HTMLResponse, response_model=None)
def chat_page(
    request: Request, user: Annotated[User | None, Depends(current_user)]
) -> HTMLResponse | RedirectResponse:
    if user is None:
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(request, "chat.html", {"user": user})


@app.get("/admin", response_class=HTMLResponse, response_model=None)
def admin_page(
    request: Request, user: Annotated[User | None, Depends(current_user)]
) -> HTMLResponse | RedirectResponse:
    if user is None:
        return RedirectResponse(url="/login", status_code=302)
    if not user.is_admin:
        return RedirectResponse(url="/chat", status_code=302)
    return templates.TemplateResponse(request, "admin.html", {"user": user})


# --- API: identity & sessions ----------------------------------------------

@app.get("/api/me")
def api_me(user: Annotated[User, Depends(require_user)]) -> dict:
    return {"email": user.email, "name": user.name, "role": user.role, "is_admin": user.is_admin}


@app.get("/api/sessions")
def api_sessions(user: Annotated[User, Depends(require_user)]) -> list[dict]:
    return [
        {"id": s["id"], "title": s["title"], "updated_at": s["updated_at"]}
        for s in db.list_sessions(user.id)
    ]


@app.get("/api/sessions/{session_id}/messages")
def api_session_messages(
    session_id: int, user: Annotated[User, Depends(require_user)]
) -> list[dict]:
    if db.get_session(session_id, user.id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    out = []
    for m in db.list_messages(session_id):
        item = {"id": m["id"], "role": m["role"], "content": m["content"]}
        if m["meta_json"]:
            item["meta"] = json.loads(m["meta_json"])
        if m["role"] == "assistant":
            fb = db.get_feedback(m["id"])
            item["feedback"] = fb["rating"] if fb else None
        out.append(item)
    return out


# --- API: chat & feedback ---------------------------------------------------

@app.post("/api/chat")
def api_chat(
    payload: ChatRequest, user: Annotated[User, Depends(require_user)]
) -> JSONResponse:
    """Answer a question, persisting the exchange into a chat session."""
    # Resolve or create the session (owned by this user).
    session = db.get_session(payload.session_id, user.id) if payload.session_id else None
    if session is None:
        session = db.create_session(user.id, title=payload.message[:60])
    db.add_message(session["id"], "user", payload.message)

    if USE_AGENT:
        try:
            from app.backend.agent import answer_question  # noqa: PLC0415

            result = answer_question(payload.message).to_dict()
        except Exception:  # noqa: BLE001
            logger.exception("agent failed for user=%s", user.email)
            result = {
                "answer": "Sorry — the assistant hit an error reaching the model. "
                "Please try again in a moment.",
                "domain": "unrouted",
                "confidence": {"level": "low", "score": 0.0},
                "citations": [],
            }
    else:
        result = stub.answer(payload.message)

    assistant_msg = db.add_message(session["id"], "assistant", result["answer"], meta=result)
    logger.info(
        "chat user=%s session=%s domain=%s conf=%s",
        user.email, session["id"], result["domain"], result["confidence"]["score"],
    )
    result["session_id"] = session["id"]
    result["message_id"] = assistant_msg["id"]
    result["session_title"] = session["title"]
    return JSONResponse(result)


@app.post("/api/feedback")
def api_feedback(
    payload: FeedbackRequest, user: Annotated[User, Depends(require_user)]
) -> JSONResponse:
    """Record thumbs feedback with the surrounding user/assistant messages."""
    msg = db.get_message(payload.message_id)
    if msg is None or msg["owner_id"] != user.id or msg["role"] != "assistant":
        raise HTTPException(status_code=404, detail="Message not found")

    # The question is the most recent user message before this answer.
    question = ""
    for m in db.list_messages(msg["session_id"]):
        if m["id"] >= payload.message_id:
            break
        if m["role"] == "user":
            question = m["content"]
    db.add_feedback(payload.message_id, user.id, payload.rating, question, msg["content"])
    logger.info("feedback user=%s message=%s rating=%s", user.email, payload.message_id, payload.rating)
    return JSONResponse({"status": "recorded"})


# --- API: admin -------------------------------------------------------------

@app.get("/api/admin/users")
def api_admin_users(_: Annotated[User, Depends(require_admin)]) -> list[dict]:
    fields = ("id", "email", "name", "requested_role", "role", "status", "created_at")
    return [{k: u[k] for k in fields} for u in db.list_users()]


@app.post("/api/admin/users/{user_id}/decision")
def api_admin_decision(
    user_id: int, payload: DecisionRequest, admin: Annotated[User, Depends(require_admin)]
) -> JSONResponse:
    """Approve (with a granted role) or deny a signup request."""
    target = db.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    if payload.decision == "deny":
        db.decide_user(user_id, status=STATUS_DENIED, role=None, admin_id=admin.id)
    else:
        role = payload.role or target["requested_role"]
        if role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail="Invalid role")
        # Guard against removing the last admin by editing themselves.
        db.decide_user(user_id, status=STATUS_ACTIVE, role=role, admin_id=admin.id)
    logger.info("admin=%s decided user=%s -> %s", admin.email, user_id, payload.decision)
    return JSONResponse({"status": "ok"})


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}
