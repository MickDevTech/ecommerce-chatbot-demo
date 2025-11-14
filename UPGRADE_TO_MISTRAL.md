# Upgrade a Mistral-7B-Instruct-v0.2

## ✅ Cambios Realizados en el Código

Se ha optimizado el código para usar **Mistral-7B-Instruct-v0.2**, un modelo mucho más capaz que TinyLlama:

### Comparación de Modelos

| Característica | TinyLlama-1.1B | Mistral-7B |
|----------------|----------------|------------|
| **Parámetros** | 1.1B | 7B (6.4x más grande) |
| **Razonamiento** | Limitado | Excelente |
| **Coherencia** | Baja | Alta |
| **Seguimiento de instrucciones** | Regular | Excelente |
| **Respuestas largas** | Difícil | Natural |
| **Velocidad (CPU)** | ~20-30 seg | ~40-60 seg |
| **RAM requerida** | ~2GB | ~8-10GB |

---

## 📝 Paso 1: Actualizar `.env`

Abre tu archivo `.env` y cambia estas líneas:

```bash
# CAMBIAR ESTAS LÍNEAS:
HF_MODEL_ID=mistralai/Mistral-7B-Instruct-v0.2
USE_LOCAL_MODEL=true
USE_8BIT_QUANTIZATION=true  # Reduce uso de memoria de ~14GB a ~7GB
```

**IMPORTANTE:** La cuantización 8-bit es NECESARIA para ejecutar Mistral-7B en máquinas con menos de 16GB de RAM.

**Archivo completo `.env` debería verse así:**

```bash
HF_TOKEN=tu_token_de_hugging_face
HF_MODEL_ID=mistralai/Mistral-7B-Instruct-v0.2
USE_LOCAL_MODEL=true
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,*
VITE_API_URL=http://localhost:8000
```

---

## 🚀 Paso 2: Reiniciar el Backend

```bash
docker compose down
docker compose up -d
```

**Primera carga:** El modelo se descargará (~4GB) y puede tardar 2-5 minutos.

---

## 🎯 Mejoras Implementadas

### 1. **Prompts Optimizados para Mistral**

Ahora usa el formato oficial de Mistral:
```
<s>[INST] Instrucciones... [/INST]
```

### 2. **Parámetros Ajustados**

```python
# Productos específicos/detalles:
max_tokens = 400      # Más espacio (antes: 300)
temperature = 0.7     # Más creativo (antes: 0.4)

# Consultas generales:
max_tokens = 300      # Más espacio (antes: 200)
temperature = 0.8     # Más natural (antes: 0.6)

# Otros:
repetition_penalty = 1.1  # Menos restrictivo (antes: 1.3)
```

### 3. **Limpieza de Respuestas Mejorada**

Maneja correctamente el formato de salida de Mistral:
```
<s>[INST]...[/INST] RESPUESTA_AQUÍ</s>
```

---

## 📊 Resultados Esperados

### Antes (TinyLlama):
```
Usuario: "Dame información sobre Laptop 14"
Bot: "Laptop 14 price $799.99"  ❌ (corto, poco natural)
```

### Ahora (Mistral-7B):
```
Usuario: "Dame información sobre Laptop 14"
Bot: "¡Claro! Aquí está toda la información sobre la Laptop 14":

• Laptop 14"

• Precio: $799.99

• Categoría: electrónica

• Stock disponible: 8 unidades

• Descripción: Portátil 14 pulgadas, 16GB RAM, 512GB SSD.

¿Te gustaría saber algo más sobre este producto?"
```
✅ (completo, natural, bien formateado)

---

## ⚠️ Consideraciones

### Requisitos de Hardware

**Con cuantización 8-bit (USE_8BIT_QUANTIZATION=true):**
- **RAM mínima:** 7-8GB
- **Espacio en disco:** ~5GB para el modelo
- **CPU:** Cualquier procesador moderno (más cores = más rápido)

**Sin cuantización (USE_8BIT_QUANTIZATION=false):**
- **RAM mínima:** 14-16GB
- **Mejor calidad** pero mucho más lento

### Tiempos de Respuesta

- **Primera consulta:** ~2-3 minutos (carga del modelo)
- **Consultas siguientes:** ~40-60 segundos
- **Con GPU:** ~5-10 segundos (si tienes NVIDIA GPU)

### Alternativas si es muy lento

Si Mistral-7B es muy lento en tu máquina, puedes usar:

1. **Mistral-7B vía API** (más rápido, pero con cuotas):
   ```bash
   USE_LOCAL_MODEL=false
   ```

2. **Modelo más pequeño** (menos capaz pero más rápido):
   ```bash
   HF_MODEL_ID=google/flan-t5-large
   ```

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
[INFO] generando respuesta con modelo Mistral-7B-Instruct-v0.2...
[INFO] respuesta del modelo: ¡Claro! Aquí está toda la información...
```

---

## 🐛 Troubleshooting

### Error: "Out of memory"
- Reduce `max_tokens` a 200-300
- Cierra otras aplicaciones
- Considera usar la API en lugar de local

### Error: "Model download failed"
- Verifica tu conexión a internet
- Verifica que tu `HF_TOKEN` sea válido
- Intenta descargar manualmente: `huggingface-cli download mistralai/Mistral-7B-Instruct-v0.2`

### Respuestas en inglés
- Mistral maneja mucho mejor el español que TinyLlama
- Si persiste, verifica que el prompt incluya "Responde en español"

---

## ✨ Beneficios del Upgrade

1. ✅ **Respuestas más largas y completas**
2. ✅ **Mejor seguimiento de instrucciones**
3. ✅ **Formato más consistente**
4. ✅ **Razonamiento mejorado**
5. ✅ **Menos respuestas en inglés**
6. ✅ **Tono más natural y amable**

---

¡Disfruta de tu chatbot mejorado! 🚀
