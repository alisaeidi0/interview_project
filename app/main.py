"""FastAPI entry point for the Manufacturing Floor Assistant frontend.

Serves the login and chat pages, issues JWT session cookies, and exposes the
`/api/chat` and `/api/feedback` endpoints. `/api/chat` runs the LangGraph agent when
a Groq key is configured, and falls back to the stub otherwise so the UI always runs.
"""

from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Annotated

from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from app import stub
from app.auth import (
    User,
    UserStore,
    create_access_token,
    decode_access_token,
)
from app.config import Settings, load_settings

logger = logging.getLogger("floor_assistant")
logging.basicConfig(level=logging.INFO)

BASE_DIR = Path(__file__).resolve().parent
COOKIE_NAME = "access_token"

# Fail fast at import time if required config is missing.
settings: Settings = load_settings()
user_store = UserStore(settings.demo_username, settings.demo_password)

# Use the real agent when a Groq key is present; otherwise the stub keeps the UI usable.
USE_AGENT = bool(os.environ.get("GROQ_API_KEY"))

app = FastAPI(title="Manufacturing Floor Assistant", version="0.1.0")


@app.on_event("startup")
def _warm_models() -> None:
    """Preload retrieval models in the background so the first query is fast."""
    if not USE_AGENT:
        logger.info("agent disabled (no GROQ_API_KEY) - using stub responses")
        return

    def _warm() -> None:
        try:
            from app.backend.agent import _retriever  # noqa: PLC0415

            _retriever()  # triggers embedder + reranker load
            logger.info("agent models warmed")
        except Exception:  # noqa: BLE001
            logger.exception("model warmup failed")

    threading.Thread(target=_warm, daemon=True).start()
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


def require_user(
    user: Annotated[User | None, Depends(current_user)],
) -> User:
    """Dependency that rejects unauthenticated API requests."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )
    return user


# --- Request/response models ------------------------------------------------

class ChatRequest(BaseModel):
    """A supervisor's question."""

    message: str = Field(min_length=1, max_length=2000)


class FeedbackRequest(BaseModel):
    """Thumbs up/down on an assistant answer."""

    message_id: str = Field(min_length=1, max_length=100)
    rating: str = Field(pattern="^(up|down)$")
    question: str = Field(default="", max_length=2000)


# --- Page routes ------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def index(user: Annotated[User | None, Depends(current_user)]) -> RedirectResponse:
    """Send authenticated users to chat, everyone else to login."""
    target = "/chat" if user else "/login"
    return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    """Render the login page."""
    return templates.TemplateResponse(request, "login.html", {"error": None})


@app.post("/login", response_model=None)
def login_submit(
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
    request: Request,
) -> HTMLResponse | RedirectResponse:
    """Validate credentials and set the session cookie on success."""
    user = user_store.authenticate(username, password)
    if user is None:
        logger.info("Failed login attempt for username=%s", username)
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Invalid username or password."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )
    token = create_access_token(user, settings)
    response = RedirectResponse(url="/chat", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60,
    )
    logger.info("Login success for username=%s", user.username)
    return response


@app.post("/logout")
def logout() -> RedirectResponse:
    """Clear the session cookie."""
    response = RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    response.delete_cookie(COOKIE_NAME)
    return response


@app.get("/chat", response_class=HTMLResponse, response_model=None)
def chat_page(
    request: Request, user: Annotated[User | None, Depends(current_user)]
) -> HTMLResponse | RedirectResponse:
    """Render the chat UI for authenticated users."""
    if user is None:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request, "chat.html", {"username": user.username}
    )


# --- API routes (stubbed) ---------------------------------------------------

@app.post("/api/chat")
def api_chat(
    payload: ChatRequest, user: Annotated[User, Depends(require_user)]
) -> JSONResponse:
    """Answer a question via the LangGraph agent (or the stub if no Groq key).

    Returns the shared response schema: answer, domain, confidence, citations.
    """
    if USE_AGENT:
        try:
            from app.backend.agent import answer_question  # noqa: PLC0415

            result = answer_question(payload.message).to_dict()
        except Exception:  # noqa: BLE001
            logger.exception("agent failed for user=%s", user.username)
            result = {
                "answer": "Sorry — the assistant hit an error reaching the model. "
                "Please try again in a moment.",
                "domain": "unrouted",
                "confidence": {"level": "low", "score": 0.0},
                "citations": [],
            }
    else:
        result = stub.answer(payload.message)

    logger.info(
        "chat user=%s domain=%s confidence=%s",
        user.username, result["domain"], result["confidence"]["score"],
    )
    return JSONResponse(result)


@app.post("/api/feedback")
def api_feedback(
    payload: FeedbackRequest, user: Annotated[User, Depends(require_user)]
) -> JSONResponse:
    """Accept thumbs up/down. Stub: logs it (persists to Postgres later)."""
    logger.info(
        "feedback user=%s message_id=%s rating=%s",
        user.username, payload.message_id, payload.rating,
    )
    return JSONResponse({"status": "recorded"})


@app.get("/healthz")
def healthz() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok"}
