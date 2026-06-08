"""
nlq_service.py - Natural Language Query engine (powered by GPT).

Role in system: Translates plain-English warehouse questions into data-backed answers.
Fetches live inventory context from Postgres, injects it into a GPT prompt, and
streams the response token-by-token to the caller via an async generator.

The "grounding" approach (fetching real data first) is key: without it, GPT would
hallucinate inventory numbers. By injecting actual counts and dates, the model
answers accurately without needing access to the database itself.

Example flow:
  User: "What dairy items are expiring this week?"
  → _fetch_context() queries Postgres for expiring rows
  → ask_vikram_stream() sends context + question to GPT-4o-mini
  → GPT streams: "You have 3 dairy items expiring this week:
     • Amul Butter [AMU-BUT-042]: 12 units, expires in 2 days..."
"""

from datetime import date, timedelta
from typing import AsyncGenerator

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from dotenv import load_dotenv
import os

from app.models.inventory import SKU, InventoryRecord

load_dotenv()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is not set.")

_openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# The system prompt defines Vikram's persona and answer style.
# It is sent with every request as the first message so GPT stays in character.
SYSTEM_PROMPT = """You are Vikram, an intelligent warehouse assistant for StockSense.
You have access to real-time inventory data provided in each message.
Rules:
- Answer only from the data provided — never invent stock numbers or dates.
- Be concise (under 200 words) unless the user asks for more detail.
- Use bullet points for lists of items.
- Always include SKU codes in brackets: [SKU-CODE].
- If the data doesn't answer the question, say so clearly.
- Be professional and helpful."""


async def _fetch_inventory_context(db: AsyncSession) -> str:
    """
    Query Postgres for current alerts and inventory state to use as GPT context.

    Fetches expiring items, expired items, low-stock items, and category summary.
    These ~60 rows of real data become the "memory" that GPT reasons over.

    Why async: every SQLAlchemy query via AsyncSession requires await — each one
    is a network call to Postgres.

    Returns:
        A formatted multi-line string ready to embed in the GPT prompt.
    """
    today = date.today()
    week_ahead = today + timedelta(days=7)

    # ── Items expiring within 7 days ──────────────────────────────────────────
    expiring_stmt = (
        select(
            SKU.name,
            SKU.code,
            SKU.category,
            InventoryRecord.quantity,
            InventoryRecord.expiry_date,
        )
        .join(InventoryRecord, SKU.id == InventoryRecord.sku_id)
        .where(InventoryRecord.expiry_date >= today)
        .where(InventoryRecord.expiry_date <= week_ahead)
        .where(InventoryRecord.quantity > 0)
        .order_by(InventoryRecord.expiry_date.asc())
        .limit(25)
    )
    # await: Postgres SELECT
    expiring_rows = (await db.execute(expiring_stmt)).all()

    # ── Already expired (still in stock) ─────────────────────────────────────
    expired_stmt = (
        select(
            SKU.name,
            SKU.code,
            SKU.category,
            InventoryRecord.quantity,
            InventoryRecord.expiry_date,
        )
        .join(InventoryRecord, SKU.id == InventoryRecord.sku_id)
        .where(InventoryRecord.expiry_date < today)
        .where(InventoryRecord.quantity > 0)
        .order_by(InventoryRecord.expiry_date.asc())
        .limit(20)
    )
    expired_rows = (await db.execute(expired_stmt)).all()  # await: Postgres SELECT

    # ── Low stock — total quantity ≤ reorder level ────────────────────────────
    # Subquery: sum quantity per SKU across all batches
    stock_sq = (
        select(
            InventoryRecord.sku_id,
            func.sum(InventoryRecord.quantity).label("total"),
        )
        .group_by(InventoryRecord.sku_id)
        .subquery()
    )
    low_stock_stmt = (
        select(SKU.name, SKU.code, SKU.category, SKU.unit, SKU.reorder_level, stock_sq.c.total)
        .join(stock_sq, SKU.id == stock_sq.c.sku_id)
        .where(stock_sq.c.total <= SKU.reorder_level)
        .order_by(stock_sq.c.total.asc())
        .limit(20)
    )
    low_stock_rows = (await db.execute(low_stock_stmt)).all()  # await: Postgres SELECT

    # ── Category counts ───────────────────────────────────────────────────────
    cat_stmt = (
        select(SKU.category, func.count(SKU.id).label("cnt"))
        .group_by(SKU.category)
        .order_by(SKU.category)
    )
    cat_rows = (await db.execute(cat_stmt)).all()  # await: Postgres SELECT

    # ── Build the context string ──────────────────────────────────────────────
    # Python note: list.append() + "\n".join() is the idiomatic way to build
    # multi-line strings in Python. C# equivalent: StringBuilder.AppendLine().
    lines: list[str] = [
        f"Date: {today.isoformat()}",
        "\nCategory overview: "
        + ", ".join(f"{r.category}({r.cnt} SKUs)" for r in cat_rows),
    ]

    if expiring_rows:
        lines.append(f"\nItems expiring within 7 days ({len(expiring_rows)}):")
        for r in expiring_rows:
            days_left = (r.expiry_date - today).days
            lines.append(
                f"  [{r.code}] {r.name} ({r.category}): "
                f"{r.quantity} units, {days_left} day(s) left"
            )
    else:
        lines.append("\nNo items expiring within 7 days.")

    if expired_rows:
        lines.append(f"\nAlready expired (still in stock) ({len(expired_rows)}):")
        for r in expired_rows:
            overdue = (today - r.expiry_date).days
            lines.append(
                f"  [{r.code}] {r.name} ({r.category}): "
                f"{r.quantity} units, {overdue} day(s) overdue"
            )

    if low_stock_rows:
        lines.append(f"\nLow stock items ({len(low_stock_rows)}):")
        for r in low_stock_rows:
            lines.append(
                f"  [{r.code}] {r.name} ({r.category}): "
                f"{r.total} {r.unit} (reorder level: {r.reorder_level})"
            )

    return "\n".join(lines)


async def ask_vikram_stream(
    question: str,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    Stream a GPT response grounded in live inventory data.

    Why async generator: FastAPI's StreamingResponse expects an iterable that
    yields text chunks. As OpenAI streams tokens back one at a time, we yield
    each chunk immediately — the user sees text appearing word by word.

    Python note: 'async def' + 'yield' creates an async generator. Callers
    iterate it with 'async for chunk in ask_vikram_stream(...)'. C# equivalent:
    'async IAsyncEnumerable<string>' with 'yield return' in an async method.

    Args:
        question: Plain-English question from the user.
        db: AsyncSession used to fetch inventory context.

    Yields:
        String fragments (tokens) as they arrive from OpenAI.
    """
    # Fetch real inventory data to ground the model's answer
    context = await _fetch_inventory_context(db)  # await: multiple DB queries

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"Current inventory data:\n{context}\n\n"
                f"Question: {question}"
            ),
        },
    ]

    # stream=True tells OpenAI to use Server-Sent Events, sending tokens as they
    # are generated rather than waiting for the full response.
    # await: establishes the streaming HTTP connection to OpenAI
    stream = await _openai_client.chat.completions.create(
        model="gpt-4o-mini",  # fast + cheap; good enough for structured inventory Q&A
        messages=messages,
        stream=True,
        max_tokens=400,
        temperature=0.2,  # lower = more factual/deterministic
    )

    # Python note: 'async for' consumes an async iterator — each iteration
    # awaits the next chunk from OpenAI's streaming response.
    # C# equivalent: 'await foreach (var chunk in stream)'
    async for chunk in stream:
        choices = chunk.choices
        if choices:
            delta = choices[0].delta
            if delta and delta.content:
                yield delta.content  # yield sends this token to FastAPI's StreamingResponse
