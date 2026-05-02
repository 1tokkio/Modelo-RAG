"""
main.py
-------
Agente principal de gestión de inventario — RetailSur S.A.
Integra el pipeline RAG con el ERP simulado (Odoo mock).

Modos de uso:
  1. Interfaz de chat interactiva:     python main.py
  2. Demo automático con casos reales: python main.py --demo
  3. Reconstruir índice vectorial:     python main.py --rebuild

Flujo del agente:
  Usuario → consulta en lenguaje natural
         → RAG recupera contexto relevante (ERP + externo)
         → GPT-4o genera recomendación estructurada y trazable
         → (Opcional) Agente crea orden de compra en ERP
"""

import argparse
import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv

# Asegurar que los módulos del proyecto están en el path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from rag.pipeline import RetailSurRAGPipeline
from erp.odoo_mock import OdooMockClient
from rag.prompts import GENERAL_ALERT_PROMPT


def print_banner():
    print("""
╔══════════════════════════════════════════════════════════╗
║     RetailSur S.A. — Agente de Gestión de Inventario     ║
║     Stack: LangChain · GPT-4o · ChromaDB · Odoo Mock     ║
║     Proyecto ISY0101 — Ingeniería de Soluciones con IA    ║
╚══════════════════════════════════════════════════════════╝
    """)


def demo_mode(pipeline: RetailSurRAGPipeline, erp: OdooMockClient):
    """
    Ejecuta una secuencia de casos de uso representativos del proyecto.
    Útil para demostrar el sistema al docente evaluador.
    """
    print("\n" + "="*60)
    print("  MODO DEMO — CASOS DE USO REPRESENTATIVOS")
    print("="*60)

    # --- Caso 1: Consulta general de alertas ---
    print("\n[CASO 1] Revisión de alertas automáticas de reorden")
    alerts = erp.get_reorder_alerts()
    alerts_text = json.dumps(alerts, indent=2, ensure_ascii=False)

    result = pipeline.query(
        f"El sistema detectó las siguientes alertas de reorden:\n{alerts_text}\n"
        "Genera un informe ejecutivo con prioridades de compra considerando el contexto externo."
    )

    # --- Caso 2: Análisis de SKU específico con contexto externo ---
    print("\n[CASO 2] Análisis SKU ELEC-001 (Smart TV) con contexto Cyber Monday")
    result2 = pipeline.query(
        "Analiza el SKU ELEC-001 (Smart TV 55 pulgadas). "
        "Considera las tendencias de búsqueda actuales y el Cyber Monday próximo. "
        "¿Cuántas unidades debo pedir y cuándo?"
    )

    # --- Caso 3: Impacto climático en categoría Hogar ---
    print("\n[CASO 3] Impacto del clima en demanda de calefacción")
    result3 = pipeline.query(
        "Dado el pronóstico climático actual para Puerto Montt, "
        "¿cómo afecta al inventario de la categoría Hogar? "
        "¿Debo ajustar las órdenes de compra de estufas?"
    )

    # --- Caso 4: Crear orden de compra ---
    print("\n[CASO 4] Creación de orden de compra para SKU ELEC-001")
    order_result = erp.create_purchase_order(
        sku="ELEC-001",
        cantidad=45,
        proveedor="TechDistrib Ltda.",
        justificacion=(
            "Stock actual: 8 unidades (bajo mínimo de 15). "
            "Tendencia de búsqueda +120%. Cyber Monday en 2 semanas. "
            "Recomendación del agente RAG basada en historial + contexto externo."
        )
    )
    print(f"\nOrden creada en ERP:")
    print(json.dumps(order_result, indent=2, ensure_ascii=False))

    # --- Caso 5: Consulta de política de compras ---
    print("\n[CASO 5] Consulta de política interna de aprobación")
    result5 = pipeline.query(
        "¿Qué productos requieren aprobación del gerente de operaciones? "
        "¿Cuál es el proceso para pedidos de alto valor?"
    )

    print("\n" + "="*60)
    print("  DEMO COMPLETADO")
    print(f"  Órdenes de compra generadas: {len(erp.get_purchase_orders())}")
    print("="*60)


def interactive_mode(pipeline: RetailSurRAGPipeline, erp: OdooMockClient):
    """
    Interfaz de chat interactiva en terminal.
    Comandos especiales:
      /alertas  → Muestra alertas automáticas de reorden
      /erp      → Muestra resumen del inventario actual
      /pedido   → Crea una orden de compra manualmente
      /salir    → Termina la sesión
    """
    print("\n[Chat iniciado] Escribe tu consulta o usa un comando especial.")
    print("Comandos: /alertas  /erp  /pedido  /salir\n")

    while True:
        try:
            user_input = input("🏪 RetailSur > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n[Sesión terminada]")
            break

        if not user_input:
            continue

        # Comandos especiales
        if user_input.lower() == "/salir":
            print("[Sesión terminada]")
            break

        elif user_input.lower() == "/alertas":
            alerts = erp.get_reorder_alerts()
            if not alerts:
                print("✅ No hay alertas de reorden activas.")
            else:
                print(f"\n⚠️  {len(alerts)} alertas detectadas:\n")
                for a in alerts:
                    icon = "🔴" if a["urgencia"] == "CRÍTICA" else "🟡"
                    print(f"  {icon} {a['sku']} | {a['nombre']}")
                    print(f"     Stock: {a['stock_actual']} | Sugerido pedir: {a['cantidad_sugerida_pedido']} | "
                          f"Costo: ${a['costo_total_estimado_clp']:,} CLP")
            print()

        elif user_input.lower() == "/erp":
            inventory = erp.get_inventory()
            print("\n📦 Inventario actual:\n")
            for item in inventory:
                print(f"  {item['sku']} | Stock: {item['stock_actual']} | "
                      f"Mínimo: {item['stock_minimo']} | Lead time: {item['lead_time_dias']}d")
            print()

        elif user_input.lower() == "/pedido":
            print("Crear orden de compra:")
            sku = input("  SKU: ").strip().upper()
            try:
                cantidad = int(input("  Cantidad: ").strip())
            except ValueError:
                print("  Error: cantidad debe ser un número entero")
                continue
            inv = next((i for i in erp.get_inventory() if i["sku"] == sku), None)
            if not inv:
                print(f"  Error: SKU {sku} no encontrado")
                continue
            result = erp.create_purchase_order(
                sku=sku,
                cantidad=cantidad,
                proveedor=inv["proveedor"],
                justificacion="Creada manualmente desde interfaz de agente"
            )
            if result.get("success"):
                order = result["order"]
                print(f"\n  ✅ Orden {order['id']} creada")
                print(f"     Entrega estimada: {order['fecha_entrega_estimada']}")
                print(f"     Total: ${order['total_clp']:,} CLP")
                if order["requiere_aprobacion"]:
                    print("     ⚠️  REQUIERE APROBACIÓN DEL GERENTE")
            print()

        else:
            # Consulta normal al agente RAG
            print()
            pipeline.query(user_input)


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Agente de gestión de inventario RetailSur S.A."
    )
    parser.add_argument("--demo", action="store_true",
                        help="Ejecutar modo demo con casos de uso predefinidos")
    parser.add_argument("--rebuild", action="store_true",
                        help="Reconstruir el índice vectorial ChromaDB desde cero")
    args = parser.parse_args()

    print_banner()

    # Verificar API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ Error: OPENAI_API_KEY no configurada.")
        print("   Crea un archivo .env con: OPENAI_API_KEY=sk-...")
        sys.exit(1)

    # Inicializar ERP mock
    print("[Init] Conectando al ERP (modo simulación)...")
    erp = OdooMockClient()

    # Inicializar pipeline RAG
    print("[Init] Inicializando pipeline RAG...")
    pipeline = RetailSurRAGPipeline(openai_api_key=api_key)
    pipeline.build(force_rebuild=args.rebuild)

    print(f"\n✅ Sistema listo | {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    if args.demo:
        demo_mode(pipeline, erp)
    else:
        interactive_mode(pipeline, erp)


if __name__ == "__main__":
    main()
