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

# Imports para modelos locales (solo si USE_LOCAL_MODEL=true)
try:
    from transformers import AutoTokenizer, AutoModelForCausalLM, AutoModelForSeq2SeqLM, pipeline, BitsAndBytesConfig
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

HF_MODEL_ID = os.environ.get("HF_MODEL_ID", "Qwen/Qwen2.5-1.5B-Instruct")
USE_LOCAL_MODEL = os.environ.get("USE_LOCAL_MODEL", "false").lower() in ("true", "1", "yes")
USE_8BIT_QUANTIZATION = os.environ.get("USE_8BIT_QUANTIZATION", "false").lower() in ("true", "1", "yes")

# Cache global para el modelo local (evita recargarlo en cada request)
_local_model_cache = {"model": None, "tokenizer": None, "pipeline": None}

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

# CORS: Leer orígenes permitidos desde variable de entorno
allowed_origins_str = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
)
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]
logger.info(f"CORS allowed origins: {allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
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
        "IMPORTANTE: Siempre responde en español, sin importar el idioma de la pregunta. "
        "Tu trabajo es ayudar a los clientes a encontrar productos que se ajusten a sus necesidades. "
        "Usa el catálogo provisto para responder sobre disponibilidad, precios y características. "
        "Si no hay coincidencias exactas, sugiere alternativas similares. "
        "Sé amable, profesional y conciso. Todas tus respuestas deben estar completamente en español."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Catálogo de productos (JSON):\n{products_str}"},
        {"role": "user", "content": f"{question}\n\nPor favor responde en español."},
    ]
    return messages


def build_prompt(question: str, products: List[Dict[str, Any]]) -> str:
    """Construye un prompt estilo Mistral Instruct usando el catálogo completo."""
    products_str = json.dumps(products, ensure_ascii=False, indent=2)
    system_prompt = (
        "Eres un asistente de ventas de una tienda en línea. "
        "IMPORTANTE: Siempre responde en español, incluso si el cliente pregunta en otro idioma. "
        "Tu trabajo es ayudar a los clientes a encontrar productos que se ajusten a sus necesidades. "
        "Haz preguntas sobre tallas, precios, colores, disponibilidad y características importantes para el cliente. "
        "Usa el catálogo provisto para responder sobre disponibilidad, precios y características. "
        "Si no hay coincidencias exactas, sugiere alternativas similares. "
        "Sé amable, profesional y conciso. Todas tus respuestas deben estar en español."
    )
    prompt = (
        f"<s>[INST] <<SYS>>\n{system_prompt}\n<</SYS>>\n\n"
        f"Catálogo de productos (JSON):\n{products_str}\n\n"
        f"Pregunta del cliente: {question}\n"
        f"Responde en español:\n"
        f"[/INST]"
    )
    return prompt


def load_local_model():
    """Carga el modelo local usando transformers (solo se ejecuta una vez)."""
    if not TRANSFORMERS_AVAILABLE:
        raise ImportError("transformers no está instalado. Ejecuta: pip install transformers torch accelerate")
    
    if _local_model_cache["pipeline"] is not None:
        logger.info("[local] usando modelo en caché")
        return _local_model_cache["pipeline"]
    
    logger.info(f"[local] cargando modelo {HF_MODEL_ID}...")
    
    # Detectar tipo de modelo
    model_lower = HF_MODEL_ID.lower()
    is_seq2seq = any(x in model_lower for x in ["t5", "bart", "pegasus"])
    
    # Configurar opciones de carga según disponibilidad de memoria
    load_kwargs = {}
    if USE_8BIT_QUANTIZATION:
        logger.info("[local] usando cuantización 8-bit para reducir uso de memoria")
        # Configuración correcta para cuantización 8-bit en CPU
        quantization_config = BitsAndBytesConfig(
            load_in_8bit=True,
            llm_int8_enable_fp32_cpu_offload=True  # Permite offload a CPU
        )
        load_kwargs["quantization_config"] = quantization_config
        load_kwargs["device_map"] = "auto"
        load_kwargs["low_cpu_mem_usage"] = True
    else:
        load_kwargs["torch_dtype"] = "auto"
    
    if is_seq2seq:
        logger.info("[local] detectado modelo seq2seq (T5/BART), usando text2text-generation")
        tokenizer = AutoTokenizer.from_pretrained(HF_MODEL_ID)
        model = AutoModelForSeq2SeqLM.from_pretrained(HF_MODEL_ID, **load_kwargs)
    else:
        logger.info("[local] detectado modelo causal (GPT/Llama), usando text-generation")
        tokenizer = AutoTokenizer.from_pretrained(HF_MODEL_ID)
        model = AutoModelForCausalLM.from_pretrained(HF_MODEL_ID, **load_kwargs)
    
    pipe = pipeline(
        "text-generation" if not is_seq2seq else "text2text-generation",
        model=model,
        tokenizer=tokenizer,
        max_length=500,
        temperature=0.8,  # Mayor temperatura para más variedad
        do_sample=True,
        top_p=0.95,
        repetition_penalty=1.2,  # Evitar repeticiones
        num_beams=2,  # Mejora calidad de generación
    )
    
    _local_model_cache["tokenizer"] = tokenizer
    _local_model_cache["model"] = model
    _local_model_cache["pipeline"] = pipe
    _local_model_cache["is_seq2seq"] = is_seq2seq
    
    device = "GPU" if torch.cuda.is_available() else "CPU"
    model_type = "seq2seq" if is_seq2seq else "causal"
    logger.info(f"[local] modelo {model_type} cargado exitosamente en {device}")
    
    return pipe


def normalize_word(word: str) -> str:
    """Normaliza una palabra eliminando plurales y acentos para mejor matching."""
    # Remover acentos comunes
    replacements = {'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u', 'ñ': 'n'}
    for old, new in replacements.items():
        word = word.replace(old, new)
    
    # Convertir plurales comunes a singular
    if word.endswith('es') and len(word) > 3:
        word = word[:-2]  # zapatos -> zapato, camisetas -> camiseta
    elif word.endswith('s') and len(word) > 3:
        word = word[:-1]  # gorras -> gorra
    
    return word


def filter_relevant_products(question: str, products: List[Dict[str, Any]], max_products: int = 10) -> List[Dict[str, Any]]:
    """Filtra productos relevantes basándose en la pregunta del usuario."""
    question_lower = question.lower()
    
    # Remover signos de puntuación y caracteres especiales
    import string
    translator = str.maketrans('', '', string.punctuation + '¿¡')
    question_clean = question_lower.translate(translator)
    
    # Extraer palabras clave (eliminar palabras comunes)
    stop_words = {'que', 'qué', 'cual', 'cuál', 'tiene', 'tienes', 'hay', 'vende', 'vendes', 
                  'me', 'puedes', 'puede', 'mostrar', 'ver', 'busco', 'quiero', 'necesito',
                  'un', 'una', 'el', 'la', 'los', 'las', 'de', 'del', 'para', 'con'}
    keywords = [normalize_word(word) for word in question_clean.split() if word not in stop_words and len(word) > 2]
    
    logger.info(f"[filter] keywords extraídos: {keywords}")
    
    # Si no hay keywords específicos, detectar si pregunta por todo el catálogo
    if not keywords or any(word in question_lower for word in ['todos', 'todo', 'catálogo', 'catalogo', 'productos']):
        logger.info(f"[filter] pregunta general, mostrando primeros {max_products} productos")
        return products[:max_products]
    
    # Calcular puntuación de relevancia para cada producto
    scored_products = []
    for product in products:
        score = 0
        # Obtener y normalizar textos del producto
        product_name = product.get('name', '').lower()
        product_category = product.get('category', '').lower()
        product_desc = product.get('description', '').lower()
        
        # Normalizar palabras individuales del producto
        product_name_words = [normalize_word(w) for w in product_name.split()]
        product_category_words = [normalize_word(w) for w in product_category.split()]
        product_desc_words = [normalize_word(w) for w in product_desc.split()]
        
        all_product_words = product_name_words + product_category_words + product_desc_words
        
        # Buscar coincidencias de keywords
        for keyword in keywords:
            if keyword in all_product_words:
                score += 10
                # Bonus si está en el nombre
                if keyword in product_name_words:
                    score += 20
                # Bonus si está en la categoría
                if keyword in product_category_words:
                    score += 15
        
        if score > 0:
            scored_products.append((score, product))
    
    # Ordenar por relevancia y tomar los top N
    scored_products.sort(reverse=True, key=lambda x: x[0])
    relevant_products = [p for _, p in scored_products[:max_products]]
    
    # Si no se encontraron productos relevantes, mostrar algunos aleatorios
    if not relevant_products:
        logger.info(f"[filter] sin coincidencias, mostrando primeros {max_products} productos")
        relevant_products = products[:max_products]
    else:
        logger.info(f"[filter] encontrados {len(relevant_products)} productos relevantes para: {keywords}")
    
    return relevant_products


def get_available_categories(products: List[Dict[str, Any]]) -> List[str]:
    """Extrae las categorías únicas del catálogo de productos."""
    categories = set()
    for p in products:
        if 'category' in p and p['category']:
            categories.add(p['category'])
    return sorted(list(categories))


def classify_question_intent(question: str, pipe) -> Dict[str, Any]:
    """Clasifica la intención de la pregunta del usuario usando el modelo."""
    classification_prompt = (
        f"<|im_start|>system\n"
        f"Eres un clasificador de preguntas. Analiza la pregunta del usuario y responde SOLO con un JSON.\n\n"
        f"CATEGORÍAS DISPONIBLES Y SUS PRODUCTOS:\n"
        f"- ropa: camisetas, pantalones, vestidos, sudaderas, blusas, faldas, camperas\n"
        f"- calzado: zapatillas, zapatos, botines, sandalias, botas, tenis, mocasines\n"
        f"- electrónica: laptops, tablets, relojes inteligentes, auriculares, monitores, mouse, bocinas, cámaras\n"
        f"- accesorios: mochilas, gafas, gorras, cinturones, riñoneras, bufandas, carteras, sombreros\n\n"
        f"TIPOS DE PREGUNTA:\n"
        f"- 'categorias_disponibles': pregunta QUÉ categorías existen\n"
        f"- 'categoria': pide VER productos de UNA categoría\n"
        f"- 'producto_especifico': pregunta por UN producto en particular\n"
        f"- 'general': pregunta general sobre el catálogo\n"
        f"- 'fuera_catalogo': NO es sobre productos\n\n"
        f"Responde SOLO JSON: {{\"tipo\": \"...\", \"terminos\": [...], \"categoria\": \"...\"}}\n\n"
        f"EJEMPLOS:\n"
        f"'Qué categorías tienes?' -> {{\"tipo\": \"categorias_disponibles\", \"terminos\": [], \"categoria\": null}}\n"
        f"'Muéstrame electrónica' -> {{\"tipo\": \"categoria\", \"terminos\": [\"electronica\"], \"categoria\": \"electrónica\"}}\n"
        f"'Mochila para Portátil' -> {{\"tipo\": \"producto_especifico\", \"terminos\": [\"mochila\", \"portatil\"], \"categoria\": \"accesorios\"}}\n"
        f"'Tienes camisetas?' -> {{\"tipo\": \"categoria\", \"terminos\": [\"camiseta\"], \"categoria\": \"ropa\"}}\n"
        f"'Laptop 14' -> {{\"tipo\": \"producto_especifico\", \"terminos\": [\"laptop\", \"14\"], \"categoria\": \"electrónica\"}}\n"
        f"'Zapatos' -> {{\"tipo\": \"categoria\", \"terminos\": [\"zapatos\"], \"categoria\": \"calzado\"}}<|im_end|>\n"
        f"<|im_start|>user\n"
        f"Pregunta: {question}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )
    
    try:
        result = pipe(
            classification_prompt,
            max_new_tokens=100,
            temperature=0.3,  # Baja temperatura para respuestas más determinísticas
            do_sample=True,
            top_p=0.9,
            pad_token_id=pipe.tokenizer.eos_token_id
        )
        
        # Extraer y limpiar respuesta
        if isinstance(result, list) and len(result) > 0:
            text = result[0].get("generated_text", "")
        else:
            text = str(result)
        
        if "<|im_start|>assistant" in text:
            text = text.split("<|im_start|>assistant")[-1].strip()
        
        text = text.replace("<|im_end|>", "").strip()
        text = text.replace("<|im_start|>", "").strip()
        
        # Intentar parsear JSON
        import json
        # Buscar JSON en la respuesta
        if "{" in text and "}" in text:
            json_start = text.find("{")
            json_end = text.rfind("}") + 1
            json_str = text[json_start:json_end]
            intent = json.loads(json_str)
            logger.info(f"[intent] clasificación: {intent}")
            return intent
        else:
            logger.warning(f"[intent] no se pudo parsear JSON, usando fallback")
            return {"tipo": "general", "terminos": [], "categoria": None}
    
    except Exception as e:
        logger.warning(f"[intent] error en clasificación: {e}, usando fallback")
        return {"tipo": "general", "terminos": [], "categoria": None}


def search_catalog_by_intent(intent: Dict[str, Any], question: str, products: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Busca en el catálogo según la intención clasificada."""
    tipo = intent.get("tipo", "general")
    terminos = intent.get("terminos", [])
    categoria = intent.get("categoria")
    
    logger.info(f"[catalog] buscando por tipo='{tipo}', términos={terminos}, categoría='{categoria}'")
    
    if tipo == "fuera_catalogo" or tipo == "categorias_disponibles":
        # No buscar productos para estas intenciones
        return []
    
    if tipo == "producto_especifico":
        # Buscar producto específico por términos
        matching_products = []
        for p in products:
            product_name_lower = p['name'].lower()
            # Verificar si todos los términos están en el nombre del producto
            if terminos and all(normalize_word(term) in normalize_word(product_name_lower) for term in terminos):
                matching_products.append(p)
        
        if matching_products:
            logger.info(f"[catalog] encontrado producto específico: {matching_products[0]['name']}")
            return matching_products[:1]  # Solo el primero
        else:
            # Fallback: buscar por similitud
            return filter_relevant_products(question, products, max_products=3)
    
    elif tipo == "categoria":
        # Buscar por categoría o términos relacionados
        matching_products = []
        
        logger.info(f"[catalog] buscando categoría exacta: '{categoria}'")
        
        # Primero intentar por categoría exacta
        if categoria:
            # Debug: mostrar algunas categorías del catálogo
            sample_categories = list(set([p.get('category', '') for p in products[:5]]))
            logger.info(f"[catalog] categorías de ejemplo en catálogo: {sample_categories}")
            
            for p in products:
                product_category = p.get('category', '').lower()
                if categoria.lower() == product_category:
                    matching_products.append(p)
                    logger.info(f"[catalog] match: {p['name']} (categoría: {product_category})")
            
            if matching_products:
                logger.info(f"[catalog] encontrados {len(matching_products)} productos de categoría '{categoria}'")
                return matching_products  # Todos los de la categoría
            else:
                logger.warning(f"[catalog] NO se encontraron productos con categoría exacta '{categoria}'")
        
        # Si no hay coincidencias por categoría exacta, buscar por términos en nombre o descripción
        if not matching_products and terminos:
            logger.info(f"[catalog] buscando por términos: {terminos}")
            for p in products:
                product_text = f"{p['name']} {p.get('description', '')} {p.get('category', '')}".lower()
                if any(normalize_word(term) in normalize_word(product_text) for term in terminos):
                    matching_products.append(p)
                    logger.info(f"[catalog] match por término: {p['name']}")
        
        if matching_products:
            logger.info(f"[catalog] encontrados {len(matching_products)} productos relacionados")
            return matching_products[:15]  # Máximo 15 para categorías
        else:
            # Fallback: usar filtro inteligente
            logger.warning(f"[catalog] usando fallback con filtro inteligente")
            return filter_relevant_products(question, products, max_products=10)
    
    else:  # general
        # Para preguntas generales, mostrar productos variados
        logger.info(f"[catalog] pregunta general, mostrando productos destacados")
        return products[:8]  # Primeros 8 productos


def generate_local(question: str, products: List[Dict[str, Any]]) -> str:
    """Genera una respuesta natural usando el modelo con información de productos filtrados."""
    pipe = load_local_model()
    
    # FASE 1: Clasificar la intención de la pregunta
    intent = classify_question_intent(question, pipe)
    
    # FASE 2: Buscar en el catálogo según la intención
    relevant_products = search_catalog_by_intent(intent, question, products)
    
    logger.info(f"[local] productos filtrados: {len(relevant_products)}")
    
    # Manejar preguntas sobre categorías disponibles
    if intent.get("tipo") == "categorias_disponibles":
        categories = get_available_categories(products)
        categories_text = "\n".join([f"• {cat.capitalize()}" for cat in categories])
        return (
            f"¡Claro! Tenemos productos en las siguientes categorías:\n\n"
            f"{categories_text}\n\n"
            f"¿Te gustaría ver productos de alguna categoría en particular?"
        )
    
    # Manejar preguntas fuera del catálogo
    if intent.get("tipo") == "fuera_catalogo":
        return "Hola! Soy tu asistente de ventas. Estoy aquí para ayudarte con información sobre nuestros productos. ¿Qué te gustaría saber?"
    
    if not relevant_products:
        return "Lo siento, no encontré productos que coincidan con tu búsqueda. ¿Puedo ayudarte con algo más?"
    
    # Detectar si pregunta por información detallada
    detail_keywords = ['detalles', 'detalle', 'información', 'info', 'características', 'más sobre', 
                       'describe', 'cuéntame', 'stock', 'categoría', 'categoria', 'descripción', 
                       'descripcion', 'disponible', 'cuántos', 'cuantos', 'sobre', 'del', 'de la']
    asking_details = any(keyword in question.lower() for keyword in detail_keywords)
    
    # Usar la clasificación del modelo para determinar si es producto específico
    specific_product = None
    if intent.get("tipo") == "producto_especifico" and len(relevant_products) == 1:
        specific_product = relevant_products[0]
        asking_details = True
        logger.info(f"[local] producto específico por intent: {specific_product['name']}")
    
    # Preparar información detallada de productos para el prompt del modelo
    products_info = []
    for p in relevant_products:
        if asking_details or specific_product:
            # Información completa para el modelo
            products_info.append(
                f"{p['name']}: ${p['price']:.2f}, "
                f"Categoría: {p.get('category', 'N/A')}, "
                f"Stock: {p.get('stock', 0)} unidades, "
                f"Descripción: {p.get('description', 'N/A')}"
            )
        else:
            # Información básica
            products_info.append(f"{p['name']}: ${p['price']:.2f}")
    
    products_text = "\n".join(products_info)
    
    # Prompt optimizado para Qwen2.5 - IMPORTANTE: Solo responder con info del catálogo
    if specific_product:
        # Prompt para producto específico (formato Qwen)
        prompt = (
            f"<|im_start|>system\n"
            f"Eres un asistente de ventas profesional y amable. Siempre respondes en español.\n"
            f"REGLA IMPORTANTE: Solo puedes mencionar información que esté en el catálogo. NO inventes datos.<|im_end|>\n"
            f"<|im_start|>user\n"
            f"Información del producto:\n{products_text}\n\n"
            f"El cliente pregunta: {question}\n\n"
            f"Por favor, presenta la información del producto {specific_product['name']} en formato bullets (•) con doble salto de línea:\n"
            f"• Nombre\n• Precio\n• Categoría\n• Stock disponible\n• Descripción<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
    elif intent.get("tipo") == "categoria" and intent.get("categoria"):
        # Prompt para categoría específica (formato Qwen)
        categoria_nombre = intent.get("categoria").capitalize()
        prompt = (
            f"<|im_start|>system\n"
            f"Eres un asistente de ventas amable. Siempre respondes en español.\n"
            f"REGLA IMPORTANTE: Solo menciona productos que estén en el catálogo. NO inventes productos ni datos.<|im_end|>\n"
            f"<|im_start|>user\n"
            f"Productos de la categoría '{categoria_nombre}':\n{products_text}\n\n"
            f"Pregunta: {question}\n\n"
            f"Por favor, presenta los productos de {categoria_nombre} con nombre y precio usando formato bullets (•). Sé amable y menciona cuántos productos hay disponibles.<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
    elif asking_details:
        # Prompt para información detallada (formato Qwen)
        prompt = (
            f"<|im_start|>system\n"
            f"Eres un asistente de ventas amable. Siempre respondes en español.\n"
            f"REGLA IMPORTANTE: Solo menciona productos e información que esté en el catálogo. NO inventes datos.<|im_end|>\n"
            f"<|im_start|>user\n"
            f"Productos disponibles:\n{products_text}\n\n"
            f"Pregunta: {question}\n\n"
            f"Por favor, lista los productos con toda su información (nombre, precio, categoría, stock, descripción) usando formato bullets (•).<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
    else:
        # Prompt para consulta general (formato Qwen)
        prompt = (
            f"<|im_start|>system\n"
            f"Eres un asistente de ventas amable. Siempre respondes en español.\n"
            f"REGLA IMPORTANTE: Solo menciona productos que estén en el catálogo. NO inventes productos ni datos.<|im_end|>\n"
            f"<|im_start|>user\n"
            f"Productos disponibles:\n{products_text}\n\n"
            f"Pregunta: {question}\n\n"
            f"Por favor, lista los productos relevantes con nombre y precio usando formato bullets (•). Sé breve y amable.<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
    
    logger.info(f"[local] generando respuesta con modelo {HF_MODEL_ID.split('/')[-1]}...")
    
    try:
        # Ajustar parámetros según el tipo de consulta (optimizado para Qwen2.5-1.5B)
        if specific_product or asking_details:
            max_tokens = 350  # Qwen2.5 es eficiente y conciso
            temp = 0.6        # Balance entre creatividad y precisión
        else:
            max_tokens = 250  # Suficiente para listas
            temp = 0.7        # Natural pero controlado
        
        result = pipe(
            prompt,
            max_new_tokens=max_tokens,
            temperature=temp,
            do_sample=True,
            top_p=0.9,
            repetition_penalty=1.05,  # Qwen2.5 maneja muy bien las repeticiones
            pad_token_id=pipe.tokenizer.eos_token_id
        )
        
        # Extraer texto generado
        if isinstance(result, list) and len(result) > 0:
            text = result[0].get("generated_text", "")
        else:
            text = str(result)
        
        # Limpiar el prompt de la respuesta (formato Qwen)
        # Qwen devuelve todo el prompt + respuesta
        if "<|im_start|>assistant" in text:
            text = text.split("<|im_start|>assistant")[-1].strip()
        
        # Remover tokens especiales de Qwen
        text = text.replace("<|im_end|>", "").strip()
        text = text.replace("<|im_start|>", "").strip()
        
        # Limpiar prefijos residuales
        text = text.lstrip(": ").strip()
        
        model_response = text.strip()
        
        logger.info(f"[local] respuesta del modelo: {model_response[:100]}...")
        
        # Validar si la respuesta es útil
        # Solo rechazar si es CLARAMENTE inglés (frases completas, no palabras sueltas)
        english_phrases = ['yes we have', 'sure we have', 'we can help', 'our store', 'available in', 'here are the']
        is_english = any(phrase in model_response.lower() for phrase in english_phrases)
        
        # Verificar si tiene contenido en español
        spanish_indicators = ['¡', '¿', 'á', 'é', 'í', 'ó', 'ú', 'ñ', 'tenemos', 'productos', 'precio', 'disponible']
        has_spanish = any(indicator in model_response.lower() for indicator in spanish_indicators)
        
        if len(model_response) < 10 or (is_english and not has_spanish):
            logger.warning(f"[local] respuesta del modelo inválida (inglés o muy corta), usando fallback estructurado")
            # Usar fallback con filtrado inteligente
            if specific_product:
                # Si es un producto específico, mostrar solo ese con toda la info
                filtered_products = [specific_product]
            else:
                filtered_products = filter_relevant_products(question, products, max_products=8)
            
            products_display = []
            for p in filtered_products:
                if asking_details:
                    # Información completa en formato bullets con saltos de línea
                    products_display.append(
                        f"• {p['name']}\n\n"
                        f"• Precio: ${p['price']:.2f}\n\n"
                        f"• Categoría: {p.get('category', 'N/A')}\n\n"
                        f"• Stock disponible: {p.get('stock', 0)} unidades\n\n"
                        f"• Descripción: {p.get('description', 'N/A')}"
                    )
                else:
                    # Solo nombre y precio
                    products_display.append(f"• {p['name']} - ${p['price']:.2f}")
            
            separator = "\n\n" if asking_details else "\n"
            products_list_str = separator.join(products_display)
            
            if specific_product:
                response = f"¡Claro! Aquí está toda la información:\n\n{products_list_str}"
            else:
                response = f"¡Claro! Estos son nuestros productos:\n\n{products_list_str}"
        else:
            # Usar la respuesta del modelo
            logger.info(f"[local] usando respuesta del modelo ({len(model_response)} chars)")
            response = model_response[:800]  # Limitar a 800 caracteres
            
    except Exception as e:
        logger.warning(f"[local] error en modelo, usando fallback estructurado: {e}")
        # Fallback con filtrado
        if specific_product:
            # Si es un producto específico, mostrar solo ese con toda la info
            filtered_products = [specific_product]
        else:
            filtered_products = filter_relevant_products(question, products, max_products=8)
        
        products_display = []
        for p in filtered_products:
            if asking_details:
                # Información completa en formato bullets con saltos de línea
                products_display.append(
                    f"• {p['name']}\n\n"
                    f"• Precio: ${p['price']:.2f}\n\n"
                    f"• Categoría: {p.get('category', 'N/A')}\n\n"
                    f"• Stock disponible: {p.get('stock', 0)} unidades\n\n"
                    f"• Descripción: {p.get('description', 'N/A')}"
                )
            else:
                # Solo nombre y precio
                products_display.append(f"• {p['name']} - ${p['price']:.2f}")
        
        separator = "\n\n" if asking_details else "\n"
        products_list_str = separator.join(products_display)
        
        if specific_product:
            response = f"¡Por supuesto! Aquí está toda la información:\n\n{products_list_str}"
        else:
            response = f"¡Por supuesto! Mira lo que tenemos:\n\n{products_list_str}"
    
    logger.info(f"[local] respuesta generada ({len(response)} chars)")
    
    return response

@app.post("/api/chat")
def chat(message: ChatMessage):
    products = load_products()
    if not products:
        raise HTTPException(status_code=500, detail="No se pudo cargar el catálogo de productos")
    
    logger.info("[chat] received message: %s", (message.content or "").strip()[:120])
    
    # Si USE_LOCAL_MODEL=true, usar modelo local
    if USE_LOCAL_MODEL:
        logger.info("[chat] usando modelo LOCAL con transformers")
        try:
            response_text = generate_local(message.content, products)
            return {"response": response_text}
        except Exception as e:
            logger.error(f"[chat] error generando respuesta: {e}")
            raise HTTPException(status_code=500, detail=f"Error generando respuesta: {str(e)}")
    
    # Si USE_LOCAL_MODEL=false, usar API de Hugging Face (requiere cuota)
    openai_api_key = os.environ.get("OPENAI_API_KEY") or os.environ.get("HF_TOKEN")
    openai_api_base = os.environ.get("OPENAI_API_BASE", "https://router.huggingface.co/v1")
    openai_model = os.environ.get("OPENAI_MODEL") or os.environ.get("HF_MODEL_ID", "gpt-3.5-turbo")
    # Evitar valores literales heredados de docker-compose como '${HF_MODEL_ID}'
    if openai_model in ("${HF_MODEL_ID}", "${HF_MODEL_ID:-gpt2}"):
        openai_model = os.environ.get("HF_MODEL_ID", "gpt-3.5-turbo")

    hf_token = os.environ.get("HF_TOKEN")
    if not openai_api_key and not hf_token:
        raise HTTPException(status_code=500, detail="Falta OPENAI_API_KEY o HF_TOKEN en variables de entorno")

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
                    # Manejo especial para error 402 (sin créditos)
                    if resp.status_code == 402:
                        raise HTTPException(
                            status_code=402,
                            detail="Has excedido tus créditos mensuales en Hugging Face. Por favor cambia HF_MODEL_ID a un modelo gratuito como 'mistralai/Mistral-7B-Instruct-v0.2' o suscríbete a HF Pro."
                        )
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
