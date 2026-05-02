"""
rag/loader.py
-------------
Convierte los datos internos (ERP mock) y externos (clima, feriados, tendencias)
en documentos LangChain listos para indexar en ChromaDB.

Fuentes manejadas:
  - Interna: historial de ventas (sale.order.line)
  - Interna: inventario actual (stock.quant)
  - Interna: alertas de reorden calculadas
  - Interna: políticas de compra
  - Externa: clima, feriados, tendencias de mercado
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_core.documents import Document
from data.sample_data import (
    SALES_HISTORY, CURRENT_INVENTORY,
    EXTERNAL_CONTEXT, PURCHASE_POLICIES
)


def load_sales_documents() -> list[Document]:
    """
    Convierte el historial de ventas del ERP en documentos LangChain.
    Cada documento representa un SKU con su tendencia de demanda.
    """
    docs = []
    for item in SALES_HISTORY:
        total = item["ventas_oct"] + item["ventas_nov"] + item["ventas_dic"]
        promedio = round(total / 3, 1)

        # Determinar tendencia
        if item["ventas_dic"] > item["ventas_nov"] > item["ventas_oct"]:
            tendencia = "CRECIENTE"
        elif item["ventas_dic"] < item["ventas_nov"] < item["ventas_oct"]:
            tendencia = "DECRECIENTE"
        else:
            tendencia = "VARIABLE"

        content = (
            f"Historial de ventas | SKU: {item['sku']} | Producto: {item['nombre']} | "
            f"Categoría: {item['categoria']} | "
            f"Ventas octubre: {item['ventas_oct']} unidades | "
            f"Ventas noviembre: {item['ventas_nov']} unidades | "
            f"Ventas diciembre: {item['ventas_dic']} unidades | "
            f"Total 90 días: {total} unidades | "
            f"Promedio mensual: {promedio} unidades | "
            f"Tendencia: {tendencia}"
        )

        docs.append(Document(
            page_content=content,
            metadata={
                "source": "ERP_Odoo_sales",
                "sku": item["sku"],
                "categoria": item["categoria"],
                "tipo": "ventas_historicas",
                "tendencia": tendencia
            }
        ))
    return docs


def load_inventory_documents() -> list[Document]:
    """
    Convierte el stock actual del ERP en documentos LangChain.
    Incluye cálculo del punto de reorden y estado de alerta.
    """
    docs = []
    sales_map = {s["sku"]: s for s in SALES_HISTORY}

    for item in CURRENT_INVENTORY:
        sale = sales_map.get(item["sku"], {})
        total_90d = (sale.get("ventas_oct", 0) +
                     sale.get("ventas_nov", 0) +
                     sale.get("ventas_dic", 0))
        promedio_diario = round(total_90d / 90, 2)
        punto_reorden = item["stock_minimo"] + (promedio_diario * item["lead_time_dias"])
        estado = "CRÍTICO" if item["stock_actual"] < item["stock_minimo"] else \
                 "ALERTA" if item["stock_actual"] < punto_reorden else "NORMAL"

        content = (
            f"Inventario actual | SKU: {item['sku']} | Producto: {sale.get('nombre', 'N/A')} | "
            f"Stock actual: {item['stock_actual']} unidades | "
            f"Stock mínimo: {item['stock_minimo']} unidades | "
            f"Punto de reorden calculado: {round(punto_reorden, 1)} unidades | "
            f"Estado: {estado} | "
            f"Lead time proveedor: {item['lead_time_dias']} días | "
            f"Proveedor: {item['proveedor']} | "
            f"Costo unitario: ${item['costo_unitario']:,} CLP | "
            f"Consumo diario promedio: {promedio_diario} unidades/día"
        )

        docs.append(Document(
            page_content=content,
            metadata={
                "source": "ERP_Odoo_inventory",
                "sku": item["sku"],
                "tipo": "inventario_actual",
                "estado": estado,
                "proveedor": item["proveedor"]
            }
        ))
    return docs


def load_external_documents() -> list[Document]:
    """
    Carga el contexto externo (clima, feriados, tendencias, mercado)
    como documentos LangChain.
    """
    docs = []
    for item in EXTERNAL_CONTEXT:
        docs.append(Document(
            page_content=f"Contexto externo [{item['tipo'].upper()}]: {item['descripcion']}",
            metadata={
                "source": f"external_{item['tipo']}",
                "tipo": item["tipo"],
                "categoria": "contexto_externo"
            }
        ))
    return docs


def load_policy_documents() -> list[Document]:
    """
    Carga las políticas internas de compra como documentos LangChain.
    """
    docs = []
    for i, item in enumerate(PURCHASE_POLICIES):
        docs.append(Document(
            page_content=f"Política interna [{item['tipo'].upper()}]: {item['descripcion']}",
            metadata={
                "source": "internal_policy",
                "tipo": item["tipo"],
                "categoria": "politica_interna",
                "id_politica": f"POL-{i+1:03d}"
            }
        ))
    return docs


def load_all_documents() -> list[Document]:
    """
    Carga y combina todos los documentos de todas las fuentes.
    Punto de entrada principal para el pipeline RAG.
    """
    all_docs = []
    all_docs.extend(load_sales_documents())
    all_docs.extend(load_inventory_documents())
    all_docs.extend(load_external_documents())
    all_docs.extend(load_policy_documents())

    print(f"[Loader] Documentos cargados: {len(all_docs)} total")
    print(f"  - Ventas históricas: {len(SALES_HISTORY)}")
    print(f"  - Inventario actual: {len(CURRENT_INVENTORY)}")
    print(f"  - Contexto externo:  {len(EXTERNAL_CONTEXT)}")
    print(f"  - Políticas internas: {len(PURCHASE_POLICIES)}")

    return all_docs


# --- Test rápido ---
if __name__ == "__main__":
    docs = load_all_documents()
    print(f"\nEjemplo de documento generado:\n{docs[0].page_content}")
    print(f"Metadata: {docs[0].metadata}")
