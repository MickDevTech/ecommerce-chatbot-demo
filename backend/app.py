import os
import json
from typing import List, Dict, Any
import logging
import sys
import re

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from huggingface_hub import InferenceClient
import httpx

HF_MODEL_ID = os.environ.get("HF_MODEL_ID", "mistralai/Mistral-7B-Instruct-v0.2")

app = FastAPI()

# Logging config
logger = logging.getLogger("backend")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler(sys.stdout)
_handler.setLevel(logging.INFO)
_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
if not logger.handlers:
    logger.addHandler(_handler)
# Evita doble logging cuando uvicorn configura el root
logger.propagate = False

# Logger de Uvicorn (para asegurar visibilidad en `docker compose logs`)
uvicorn_logger = logging.getLogger("uvicorn.error")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    content: str


def load_products() -> List[Dict[str, Any]]:
    try:
        products_path = os.environ.get("PRODUCTS_PATH", os.path.join(os.path.dirname(__file__), "products.json"))
        with open(products_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("products", [])
    except Exception as e:
        logger.exception("Error loading products")
        return []


def _mask_token(token: str) -> str:
    try:
        if not token:
            return "<EMPTY>"
        if len(token) <= 8:
            return "***" + token[-2:]
        return token[:6] + "..." + token[-4:]
    except Exception:
        return "<MASK_ERROR>"


def build_messages(question: str, products: List[Dict[str, Any]]):
    products_str = json.dumps(products, ensure_ascii=False, indent=2)

    system_prompt = (
        "Eres un asistente de ventas de una tienda en línea. "
        "Tu trabajo es ayudar a los clientes a encontrar productos que se ajusten a sus necesidades. "
        "Usa el catálogo provisto para responder sobre disponibilidad, precios y características. "
        "Si no hay coincidencias exactas, sugiere alternativas similares. Sé amable, profesional y conciso."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Catálogo de productos (JSON):\n{products_str}"},
        {"role": "user", "content": question},
    ]
    return messages


def build_prompt(question: str, products: List[Dict[str, Any]]) -> str:
    """Construye un prompt estilo Mistral Instruct usando el catálogo completo."""
    products_str = json.dumps(products, ensure_ascii=False, indent=2)
    system_prompt = (
        "Eres un asistente de ventas de una tienda en línea. "
        "Tu trabajo es ayudar a los clientes a encontrar productos que se ajusten a sus necesidades. "
        "Has preguntas sobre talllas, precios, colores, disponibilidad y características importantes para el cliente. "
        "Usa el catálogo provisto para responder sobre disponibilidad, precios y características. "
        "Si no hay coincidencias exactas, sugiere alternativas similares. Sé amable, profesional y conciso."
    )
    prompt = (
        f"<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n"
        f"Catálogo de productos (JSON):\n{products_str}\n\n"
        f"Pregunta del cliente: {question}\n"
        f"[/INST]"
    )
    return prompt

@app.post("/api/chat")
def chat(message: ChatMessage):
    # Prefer OpenAI-compatible provider if configured
    openai_api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("HF_TOKEN")
    openai_api_base = os.environ.get("OPENAI_API_BASE", "https://router.huggingface.co/v1")
    openai_model = os.environ.get("OPENAI_MODEL") or os.environ.get("HF_MODEL_ID", "gpt-3.5-turbo")
    # Evitar valores literales heredados de docker-compose como '${HF_MODEL_ID}'
    if openai_model in ("${HF_MODEL_ID}", "${HF_MODEL_ID:-gpt2}"):
        openai_model = os.environ.get("HF_MODEL_ID", "gpt-3.5-turbo")

    hf_token = os.environ.get("HF_TOKEN")
    if not openai_api_key and not hf_token:
        raise HTTPException(status_code=500, detail="Falta OPENAI_API_KEY o HF_TOKEN en variables de entorno")

    products = load_products()
    if not products:
        raise HTTPException(status_code=500, detail="No se pudo cargar el catálogo de productos")

    # Logging del token (enmascarado) y del modelo configurado
    logger.info("[chat] received message: %s", (message.content or "").strip()[:120])
    uvicorn_logger.info("[chat] received message: %s", (message.content or "").strip()[:120])
    logger.info("[chat] HF_MODEL_ID=%s", HF_MODEL_ID)
    logger.info("[chat] HF_TOKEN(masked)=%s", _mask_token(hf_token))
    uvicorn_logger.info("[chat] HF_MODEL_ID=%s", HF_MODEL_ID)
    uvicorn_logger.info("[chat] HF_TOKEN(masked)=%s", _mask_token(hf_token))

    messages = build_messages(message.content, products)

    # OpenAI-compatible path (Router HF si OPENAI_API_BASE=router y se usa HF_TOKEN)
    if openai_api_key:
        try:
            logger.info("[chat] using OpenAI-compatible provider: %s | model=%s", openai_api_base, openai_model)
            uvicorn_logger.info("[chat] using OpenAI-compatible provider: %s | model=%s", openai_api_base, openai_model)
            url = openai_api_base.rstrip('/') + "/chat/completions"
            headers = {
                "Authorization": f"Bearer {openai_api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": openai_model,
                "messages": messages,
                "max_tokens": 400,
                "temperature": 0.7,
            }
            with httpx.Client(timeout=60) as client:
                resp = client.post(url, headers=headers, json=payload)
                if resp.status_code != 200:
                    logger.error("[chat] OpenAI-compatible error %s: %s", resp.status_code, resp.text)
                    raise HTTPException(status_code=resp.status_code, detail=resp.text)
                data = resp.json()
                text = data.get("choices", [{}])[0].get("message", {}).get("content")
                if not text:
                    text = str(data)
                # Strip <think>...</think>
                cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
                logger.info("[chat] sending response (%d chars)", len(cleaned))
                uvicorn_logger.info("[chat] sending response (%d chars)", len(cleaned))
                return {"response": cleaned}
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("[chat] OpenAI-compatible failure: %r", e)
            raise HTTPException(status_code=500, detail=str(e))

    # Fallback HF path
    try:
        client = InferenceClient(api_key=hf_token, base_url="https://router.huggingface.co/hf-inference")
        prompt = build_prompt(message.content, products)
        logger.info("[chat] invoking HF text_generation ...")
        uvicorn_logger.info("[chat] invoking HF text_generation ...")
        tg = client.text_generation(
            prompt,
            model=HF_MODEL_ID,
            max_new_tokens=400,
            temperature=0.7,
            return_full_text=False,
            do_sample=True,
            top_p=0.95,
            repetition_penalty=1.1,
            stop_sequences=["</s>", "[/INST]"],
        )
        text = tg if isinstance(tg, str) else getattr(tg, "generated_text", str(tg))
        logger.info("[chat] HF text_generation received")
        uvicorn_logger.info("[chat] HF text_generation received")
        cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()
        logger.info("[chat] sending response (%d chars)", len(cleaned))
        uvicorn_logger.info("[chat] sending response (%d chars)", len(cleaned))
        return {"response": cleaned}
    except Exception as e1:
        logger.exception("[chat] HF failure: %r", e1)
        detail = str(e1)
        if "410" in detail or "403" in detail:
            detail = (
                "El modelo configurado no está disponible o está restringido. "
                "Prueba cambiando HF_MODEL_ID a un modelo público o utiliza un proveedor OpenAI-compatible."
            )
        raise HTTPException(status_code=500, detail=detail)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
