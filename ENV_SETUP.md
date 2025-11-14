# Configuración de Variables de Entorno

## Backend

### Desarrollo Local

Crea un archivo `.env` en la raíz del proyecto con:

```bash
# Token de Hugging Face (obligatorio)
HF_TOKEN=tu_token_de_hugging_face

# Modelo a utilizar (opcional)
HF_MODEL_ID=mistralai/Mistral-7B-Instruct-v0.2

# CORS - Orígenes permitidos (separados por coma)
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

### Producción

Configura las siguientes variables en tu servicio de hosting:

- `HF_TOKEN`: Tu token de Hugging Face
- `HF_MODEL_ID`: Modelo a usar
- `ALLOWED_ORIGINS`: URLs permitidas, ejemplo: `https://tu-frontend.netlify.app,https://otro-dominio.com`

## Frontend

### Desarrollo Local

Crea un archivo `frontend/.env` con:

```bash
# URL del backend API
VITE_API_URL=http://localhost:8000
```

### Producción (Netlify)

En la configuración de Netlify, agrega la variable de entorno:

**Variable name:** `VITE_API_URL`  
**Value:** `https://tu-backend-api.com` (URL de tu backend desplegado)

#### Pasos en Netlify:

1. Ve a **Site configuration** → **Environment variables**
2. Haz clic en **Add a variable**
3. Agrega `VITE_API_URL` con la URL de tu backend
4. Guarda y redespliega

**Importante:** Las variables que comienzan con `VITE_` deben configurarse en tiempo de **build**, no en tiempo de ejecución.

## Docker Compose

El archivo `docker-compose.yml` está configurado para leer estas variables del archivo `.env` en la raíz del proyecto. Los valores por defecto se usarán si no se definen en el `.env`.
