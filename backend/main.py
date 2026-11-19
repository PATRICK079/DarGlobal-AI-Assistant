
import logging
from typing import Annotated, Literal

import httpx
import psycopg
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, StringConstraints

load_dotenv()

from rag import answer

app = FastAPI(title="DarGlobal Property Assistant")
logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=1,
            max_length=4000,
        ),
    ]


class CatalogueFilters(BaseModel):
    property_type: str | None = Field(default=None, max_length=32)
    category: Literal["residential", "commercial"] | None = None
    transaction_type: Literal["sale", "rent"] | None = None
    rental_period: Literal["monthly", "yearly"] | None = None
    max_price: int | None = Field(default=None, ge=1, le=999_999_999_999)
    strict_max: bool = False
    min_bedrooms: int | None = Field(default=None, ge=0, le=99)
    bedrooms: int | None = Field(default=None, ge=0, le=99)
    price_order: Literal["lowest", "highest"] | None = None


class SearchState(BaseModel):
    location: str | None = Field(default=None, max_length=80)
    filters: CatalogueFilters
    page: int = Field(default=1, ge=1, le=1000)
    listing_id: str | None = Field(default=None, pattern=r"^[0-9]{1,30}$")


class ChatRequest(BaseModel):
    question: Annotated[
        str,
        StringConstraints(
            strip_whitespace=True,
            min_length=2,
            max_length=1000,
        ),
    ]

    search_state: SearchState | None = None

    history: list[ChatMessage] = Field(
        default_factory=list,
        max_length=20,
    )


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest):
    try:
        history = [
            message.model_dump()
            for message in request.history
        ]

        reply = answer(
            request.question, history=history,
            search_state=request.search_state.model_dump() if request.search_state else None,
        )
        return {"properties": [], **reply}

    except httpx.HTTPStatusError as error:
        logger.warning(
            "Chat request to %s returned HTTP %s",
            error.request.url.host,
            error.response.status_code,
        )

        if error.response.status_code == 429:
            if "free-models-per-day" in error.response.text.lower():
                detail = (
                    "Today's free chat limit has been reached. "
                    "Please try again after the daily limit resets."
                )
            else:
                detail = (
                    "Chat is busy right now. "
                    "Please try again shortly."
                )

            raise HTTPException(
                status_code=429,
                detail=detail,
            ) from error

        raise HTTPException(
            status_code=503,
            detail="The chat provider is temporarily unavailable.",
        ) from error

    except (
        httpx.HTTPError,
        psycopg.Error,
        KeyError,
        ValueError,
        IndexError,
    ):
        logger.error(
            "Chat dependency failed. Check database "
            "and model provider configuration.",
            exc_info=False,
        )

        raise HTTPException(
            status_code=503,
            detail="Chat is temporarily unavailable.",
        ) from None
