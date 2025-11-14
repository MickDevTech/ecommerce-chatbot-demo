# Sistema Inteligente de Clasificación de Intenciones

## 🎯 Arquitectura de Dos Fases

El chatbot ahora usa un **sistema inteligente de dos fases** para garantizar respuestas precisas basadas únicamente en el catálogo:

```
┌─────────────────────────────────────────────────────────────┐
│                    PREGUNTA DEL USUARIO                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  FASE 1: CLASIFICACIÓN DE INTENCIÓN (Modelo Qwen2.5)        │
│  ─────────────────────────────────────────────────────────  │
│  El modelo analiza la pregunta y determina:                 │
│  • Tipo: producto_especifico, categoria, general, fuera     │
│  • Términos clave: ["laptop", "14"]                          │
│  • Categoría: "electrónica"                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  FASE 2: BÚSQUEDA INTELIGENTE EN CATÁLOGO                   │
│  ─────────────────────────────────────────────────────────  │
│  Según la intención, busca en el catálogo:                  │
│  • Producto específico: match exacto por términos           │
│  • Categoría: filtrado por categoría + términos             │
│  • General: productos destacados                            │
│  • Fuera catálogo: respuesta amigable sin productos         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  FASE 3: GENERACIÓN DE RESPUESTA (Modelo Qwen2.5)           │
│  ─────────────────────────────────────────────────────────  │
│  El modelo genera respuesta SOLO con info del catálogo      │
│  REGLA: NO puede inventar productos ni datos                │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Tipos de Intención

### 1. **producto_especifico**
Pregunta sobre UN producto en particular.

**Ejemplos:**
- "Dame información sobre Laptop 14"
- "¿Cuánto cuesta el Reloj Inteligente?"
- "Describe los Botines de Cuero"

**Comportamiento:**
- Busca match exacto por términos en el nombre del producto
- Devuelve SOLO 1 producto
- Muestra información completa (nombre, precio, categoría, stock, descripción)

---

### 2. **categoria**
Pregunta sobre una categoría de productos.

**Ejemplos:**
- "¿Tienes camisetas?"
- "Muéstrame productos de electrónica"
- "¿Qué zapatos vendes?"

**Comportamiento:**
- Busca por categoría exacta primero
- Si no hay match, busca por términos en nombre/descripción
- Devuelve hasta 10 productos
- Muestra información básica o completa según la pregunta

---

### 3. **general**
Pregunta general sobre el catálogo.

**Ejemplos:**
- "¿Qué productos vendes?"
- "Recomiéndame algo"
- "¿Qué tienes disponible?"

**Comportamiento:**
- Muestra productos destacados (primeros 8)
- Información básica (nombre y precio)
- Respuesta amigable y concisa

---

### 4. **fuera_catalogo**
Pregunta que NO es sobre productos.

**Ejemplos:**
- "Hola"
- "¿Cómo estás?"
- "¿Cuál es tu horario?"

**Comportamiento:**
- NO busca en el catálogo
- Responde amigablemente ofreciendo ayuda con productos
- Ejemplo: "Hola! Soy tu asistente de ventas. Estoy aquí para ayudarte con información sobre nuestros productos. ¿Qué te gustaría saber?"

---

## 🔍 Proceso de Clasificación

### Prompt de Clasificación

El modelo recibe un prompt estructurado:

```
<|im_start|>system
Eres un clasificador de preguntas. Analiza la pregunta del usuario y responde SOLO con un JSON.
Tipos de pregunta:
- 'producto_especifico': pregunta sobre UN producto en particular
- 'categoria': pregunta sobre una categoría de productos
- 'general': pregunta general sobre el catálogo
- 'fuera_catalogo': pregunta que NO es sobre productos

Responde SOLO con este formato JSON:
{"tipo": "tipo_de_pregunta", "terminos": ["palabra1", "palabra2"], "categoria": "categoria_si_aplica"}
<|im_end|>
<|im_start|>user
Pregunta: ¿Tienes camisetas?
<|im_end|>
<|im_start|>assistant
```

### Respuesta del Modelo

```json
{
  "tipo": "categoria",
  "terminos": ["camiseta"],
  "categoria": "ropa"
}
```

---

## 🛡️ Garantías del Sistema

### 1. **No Inventa Información**

Cada prompt incluye la regla:
```
REGLA IMPORTANTE: Solo puedes mencionar información que esté en el catálogo. 
NO inventes datos.
```

### 2. **Búsqueda Precisa**

- **Producto específico:** Match exacto por todos los términos
- **Categoría:** Filtrado por categoría + términos relacionados
- **General:** Productos reales del catálogo

### 3. **Fallback Inteligente**

Si no encuentra productos:
```
"Lo siento, no encontré productos que coincidan con tu búsqueda. 
¿Puedo ayudarte con algo más?"
```

---

## 📊 Ejemplos de Flujo Completo

### Ejemplo 1: Producto Específico

**Pregunta:** "Dame información sobre Laptop 14"

**FASE 1 - Clasificación:**
```json
{
  "tipo": "producto_especifico",
  "terminos": ["laptop", "14"],
  "categoria": "electrónica"
}
```

**FASE 2 - Búsqueda:**
- Busca productos donde TODOS los términos estén en el nombre
- Encuentra: `Laptop 14"`
- Devuelve: 1 producto

**FASE 3 - Respuesta:**
```
¡Claro! Aquí está toda la información sobre la Laptop 14":

• Laptop 14"

• Precio: $799.99

• Categoría: electrónica

• Stock disponible: 8 unidades

• Descripción: Portátil 14 pulgadas, 16GB RAM, 512GB SSD.

¿Te gustaría saber algo más sobre este producto?
```

---

### Ejemplo 2: Categoría

**Pregunta:** "¿Tienes camisetas?"

**FASE 1 - Clasificación:**
```json
{
  "tipo": "categoria",
  "terminos": ["camiseta"],
  "categoria": "ropa"
}
```

**FASE 2 - Búsqueda:**
- Busca productos con categoría "ropa"
- Filtra por término "camiseta" en nombre/descripción
- Encuentra: Camiseta Básica Blanca, Camiseta Estampada, etc.
- Devuelve: hasta 10 productos

**FASE 3 - Respuesta:**
```
¡Por supuesto! Tenemos estas camisetas disponibles:

• Camiseta Básica Blanca - $19.99
• Camiseta Estampada - $24.99
• Camiseta Deportiva - $29.99

¿Te gustaría más información sobre alguna?
```

---

### Ejemplo 3: Fuera del Catálogo

**Pregunta:** "Hola, ¿cómo estás?"

**FASE 1 - Clasificación:**
```json
{
  "tipo": "fuera_catalogo",
  "terminos": [],
  "categoria": null
}
```

**FASE 2 - Búsqueda:**
- NO busca en el catálogo (tipo = fuera_catalogo)
- Devuelve: []

**FASE 3 - Respuesta:**
```
Hola! Soy tu asistente de ventas. Estoy aquí para ayudarte con 
información sobre nuestros productos. ¿Qué te gustaría saber?
```

---

## 🎯 Ventajas del Sistema

### ✅ Precisión
- Clasifica correctamente la intención antes de buscar
- Búsqueda dirigida según el tipo de pregunta
- Reduce falsos positivos

### ✅ Eficiencia
- No busca en el catálogo si no es necesario
- Búsqueda optimizada según intención
- Menos procesamiento innecesario

### ✅ Seguridad
- NUNCA inventa información
- Solo responde con datos del catálogo
- Reglas explícitas en cada prompt

### ✅ Experiencia de Usuario
- Respuestas más relevantes
- Maneja preguntas fuera del catálogo amigablemente
- Información precisa y confiable

---

## 🔧 Configuración

El sistema usa **Qwen2.5-1.5B-Instruct** con parámetros optimizados:

### Clasificación de Intención
```python
max_new_tokens = 100
temperature = 0.3      # Baja para respuestas determinísticas
top_p = 0.9
```

### Generación de Respuesta
```python
# Producto específico/detalles:
max_tokens = 350
temperature = 0.6

# Consulta general:
max_tokens = 250
temperature = 0.7
```

---

## 📝 Logs del Sistema

El sistema genera logs detallados para debugging:

```
[INFO] [intent] clasificación: {'tipo': 'producto_especifico', 'terminos': ['laptop', '14'], 'categoria': 'electrónica'}
[INFO] [catalog] buscando por tipo='producto_especifico', términos=['laptop', '14'], categoría='electrónica'
[INFO] [catalog] encontrado producto específico: Laptop 14"
[INFO] [local] productos filtrados: 1
[INFO] [local] producto específico por intent: Laptop 14"
[INFO] [local] generando respuesta con modelo Qwen2.5-1.5B-Instruct...
[INFO] [local] respuesta del modelo: ¡Claro! Aquí está toda la información...
```

---

## 🚀 Resultado Final

Un chatbot que:
- ✅ Entiende la intención del usuario
- ✅ Busca inteligentemente en el catálogo
- ✅ Responde SOLO con información real
- ✅ Maneja preguntas fuera del catálogo
- ✅ Proporciona respuestas precisas y naturales

**¡El chatbot nunca inventará productos o información!** 🎉
