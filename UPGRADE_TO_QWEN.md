# Upgrade a Qwen2.5-1.5B-Instruct

## ✅ Modelo Actualizado

Se ha cambiado de **Mistral-7B** a **Qwen2.5-1.5B-Instruct**, un modelo mucho más eficiente:

### Comparación de Modelos

| Característica | TinyLlama-1.1B | Mistral-7B | **Qwen2.5-1.5B** |
|----------------|----------------|------------|------------------|
| **Parámetros** | 1.1B | 7B | **1.5B** |
| **Razonamiento** | Limitado | Excelente | **Muy bueno** |
| **Coherencia** | Baja | Alta | **Alta** |
| **Seguimiento de instrucciones** | Regular | Excelente | **Excelente** |
| **Respuestas largas** | Difícil | Natural | **Natural** |
| **Velocidad (CPU)** | ~20-30 seg | ~40-60 seg | **~10-15 seg** ⚡ |
| **RAM requerida** | ~2GB | ~14GB (7GB con 8-bit) | **~3-4GB** |
| **Español** | Regular | Excelente | **Excelente** |

---

## 📝 Paso 1: Actualizar `.env`

Abre tu archivo `.env` y cambia estas líneas:

```bash
# CAMBIAR ESTAS LÍNEAS:
HF_MODEL_ID=Qwen/Qwen2.5-1.5B-Instruct
USE_LOCAL_MODEL=true
USE_8BIT_QUANTIZATION=false  # Qwen2.5-1.5B NO necesita cuantización
```

**Archivo completo `.env` debería verse así:**

```bash
HF_TOKEN=tu_token_de_hugging_face
HF_MODEL_ID=Qwen/Qwen2.5-1.5B-Instruct
USE_LOCAL_MODEL=true
USE_8BIT_QUANTIZATION=false
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,*
VITE_API_URL=http://localhost:8000
```

---

## 🚀 Paso 2: Reiniciar el Backend

```bash
docker compose restart backend
```

**Primera carga:** El modelo se descargará (~3GB) y puede tardar 1-2 minutos.

---

## 🎯 Mejoras Implementadas

### 1. **Prompts Optimizados para Qwen2.5**

Ahora usa el formato oficial de Qwen:
```
<|im_start|>system
Eres un asistente de ventas...
<|im_end|>
<|im_start|>user
Pregunta del cliente...
<|im_end|>
<|im_start|>assistant
```

### 2. **Parámetros Ajustados**

```python
# Productos específicos/detalles:
max_tokens = 350      # Qwen es eficiente
temperature = 0.6     # Balance creatividad/precisión

# Consultas generales:
max_tokens = 250      # Suficiente para listas
temperature = 0.7     # Natural pero controlado

# Otros:
repetition_penalty = 1.05  # Qwen maneja muy bien repeticiones
```

### 3. **Sin Cuantización Necesaria**

Qwen2.5-1.5B es lo suficientemente pequeño para correr sin cuantización:
- **Más rápido** (sin overhead de cuantización)
- **Mejor calidad** (precisión completa)
- **Menos RAM** que Mistral-7B con cuantización

---

## 📊 Ventajas de Qwen2.5-1.5B

### ✅ Velocidad

| Modelo | Primera Carga | Respuesta |
|--------|---------------|-----------|
| TinyLlama-1.1B | ~30 seg | ~20-30 seg |
| Mistral-7B (8-bit) | ~2-3 min | ~40-60 seg |
| **Qwen2.5-1.5B** | **~1 min** | **~10-15 seg** ⚡ |

### ✅ Memoria

| Modelo | RAM Requerida |
|--------|---------------|
| TinyLlama-1.1B | ~2GB |
| Mistral-7B | ~14GB (7GB con 8-bit) |
| **Qwen2.5-1.5B** | **~3-4GB** |

### ✅ Calidad

- **Excelente seguimiento de instrucciones**
- **Respuestas coherentes y naturales**
- **Muy bueno en español**
- **Balance perfecto entre velocidad y calidad**

---

## 📖 Ejemplo de Respuesta

### Consulta: "Dame información sobre Laptop 14"

**Respuesta de Qwen2.5-1.5B:**
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

## ⚠️ Consideraciones

### Requisitos de Hardware

- **RAM mínima:** 4GB (recomendado: 8GB)
- **Espacio en disco:** ~3GB para el modelo
- **CPU:** Cualquier procesador moderno

### Tiempos de Respuesta

- **Primera consulta:** ~1 minuto (carga del modelo)
- **Consultas siguientes:** ~10-15 segundos
- **Con GPU:** ~2-3 segundos (si tienes NVIDIA GPU)

### Comparación con Otros Modelos

**¿Por qué Qwen2.5-1.5B y no otros?**

| Modelo | Ventaja | Desventaja |
|--------|---------|------------|
| TinyLlama-1.1B | Muy rápido | Calidad limitada |
| Mistral-7B | Mejor calidad | Muy lento en CPU |
| **Qwen2.5-1.5B** | **Balance perfecto** | - |
| Phi-3-mini | Similar a Qwen | Menos optimizado para español |

---

## 🧪 Pruebas Sugeridas

Después de reiniciar, prueba estas consultas:

1. **Producto específico:**
   - "Dame información sobre Laptop 14"
   - "¿Qué stock hay de Auriculares Inalámbricos?"

2. **Categoría:**
   - "¿Tienes camisetas?"
   - "Muéstrame productos de electrónica"

3. **Consulta compleja:**
   - "Recomiéndame algo para trabajar desde casa"
   - "¿Qué productos tienes entre $50 y $150?"

---

## 📈 Monitoreo

Observa los logs para ver el progreso:

```bash
docker compose logs -f backend
```

Deberías ver:
```
[INFO] cargando modelo Qwen2.5-1.5B-Instruct...
[INFO] detectado modelo causal (GPT/Llama), usando text-generation
[INFO] modelo causal cargado exitosamente en CPU
[INFO] generando respuesta con modelo Qwen2.5-1.5B-Instruct...
[INFO] respuesta del modelo: ¡Claro! Aquí está toda la información...
```

---

## 🐛 Troubleshooting

### Respuestas en inglés
- Qwen2.5 maneja muy bien el español
- Si persiste, verifica que el prompt incluya "Siempre respondes en español"

### Modelo descarga lento
- Qwen2.5 es solo ~3GB (vs 14GB de Mistral)
- Debería descargar en 1-2 minutos con conexión normal

### Error de memoria
- Qwen2.5 solo necesita ~3-4GB de RAM
- Si tienes error, cierra otras aplicaciones

---

## ✨ Beneficios del Upgrade

1. ✅ **3-4x más rápido** que Mistral-7B
2. ✅ **Usa 50% menos RAM** que Mistral-7B con cuantización
3. ✅ **Mejor que TinyLlama** en calidad
4. ✅ **Excelente en español**
5. ✅ **Balance perfecto** velocidad/calidad
6. ✅ **No necesita cuantización**

---

¡Disfruta de tu chatbot optimizado con Qwen2.5! 🚀
