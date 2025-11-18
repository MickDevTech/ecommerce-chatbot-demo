#!/usr/bin/env python3
"""
Script para probar la clasificación de intenciones localmente.
Útil para debugging y análisis de problemas de clasificación.
"""

import requests
import json
import time

# Configuración
API_URL = "http://localhost:8000/api/chat"

# Casos de prueba
test_cases = [
    {
        "name": "Caso del bug: Mochila para Portátil",
        "message": "Mochila para Portátil",
        "expected_category": "accesorios",
        "expected_type": "producto_especifico"
    },
    {
        "name": "Categoría electrónica",
        "message": "Muéstrame electrónica",
        "expected_category": "electrónica",
        "expected_type": "categoria"
    },
    {
        "name": "Producto específico: Laptop",
        "message": "Dame información sobre Laptop 14",
        "expected_category": "electrónica",
        "expected_type": "producto_especifico"
    },
    {
        "name": "Categoría calzado",
        "message": "¿Tienes zapatos?",
        "expected_category": "calzado",
        "expected_type": "categoria"
    },
    {
        "name": "Categorías disponibles",
        "message": "¿Qué categorías tienes?",
        "expected_category": None,
        "expected_type": "categorias_disponibles"
    }
]

def test_classification(test_case):
    """Envía una pregunta y analiza la clasificación."""
    print(f"\n{'='*80}")
    print(f"🧪 TEST: {test_case['name']}")
    print(f"{'='*80}")
    print(f"📝 Mensaje: '{test_case['message']}'")
    print(f"✅ Esperado: tipo='{test_case['expected_type']}', categoría='{test_case['expected_category']}'")
    
    try:
        # Enviar request
        response = requests.post(
            API_URL,
            json={"message": test_case['message']},
            timeout=120  # 2 minutos de timeout
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"\n📤 Respuesta del chatbot:")
            print(f"   {data.get('response', 'Sin respuesta')[:200]}...")
            
            # Nota: La clasificación no se devuelve en la respuesta,
            # pero puedes verla en los logs del backend
            print(f"\n💡 Revisa los logs del backend para ver la clasificación real")
            print(f"   docker compose logs backend --tail=50")
            
        else:
            print(f"❌ Error: Status {response.status_code}")
            print(f"   {response.text}")
            
    except requests.exceptions.Timeout:
        print(f"⏱️  Timeout: El modelo está tardando mucho (>2 min)")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Esperar un poco entre requests
    time.sleep(2)

def main():
    print("""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    TEST DE CLASIFICACIÓN DE INTENCIONES                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

Este script prueba la clasificación de intenciones del chatbot.
Los resultados de clasificación aparecerán en los logs del backend.

Para ver los logs en tiempo real:
  docker compose logs -f backend

""")
    
    # Verificar que el backend esté corriendo
    try:
        response = requests.get("http://localhost:8000/health", timeout=5)
        print("✅ Backend está corriendo\n")
    except:
        print("❌ ERROR: Backend no está corriendo")
        print("   Ejecuta: docker compose up -d")
        return
    
    # Ejecutar tests
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n\n{'#'*80}")
        print(f"# Test {i}/{len(test_cases)}")
        print(f"{'#'*80}")
        test_classification(test_case)
    
    print(f"\n\n{'='*80}")
    print("✅ TESTS COMPLETADOS")
    print(f"{'='*80}")
    print("\n📊 Para analizar los resultados:")
    print("   1. Revisa los logs: docker compose logs backend | grep -A 5 'clasificación'")
    print("   2. Compara la clasificación real vs la esperada")
    print("   3. Identifica patrones de errores\n")

if __name__ == "__main__":
    main()
