"""
erp/odoo_mock.py
----------------
Simula la API REST de Odoo 17 para RetailSur S.A.
En producción, reemplazar las funciones con llamadas reales a:
  POST /web/dataset/call_kw  (método JSON-RPC de Odoo)
  o usar la librería oficial: odoorpc

Endpoints simulados:
  - get_inventory()       → stock.quant
  - get_sales_history()   → sale.order.line (agrupado por producto)
  - get_purchase_orders() → purchase.order
  - create_purchase_order() → purchase.order (escritura)
"""

import json
from datetime import datetime, timedelta
from typing import Optional
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data.sample_data import SALES_HISTORY, CURRENT_INVENTORY


class OdooMockClient:
    """
    Cliente simulado de la API REST de Odoo.
    Imita el comportamiento de odoorpc.ODOO o requests hacia /web/dataset/call_kw
    """

    BASE_URL = "https://retailsur.odoo.com"  # URL de producción (no activa en mock)

    def __init__(self, db: str = "retailsur_prod", user: str = "api_user"):
        self.db = db
        self.user = user
        self.connected = True
        self._purchase_orders = []
        print(f"[OdooMock] Conectado a {self.db} como {self.user} (modo simulación)")

    # ------------------------------------------------------------------
    # LECTURA
    # ------------------------------------------------------------------

    def get_inventory(self, sku: Optional[str] = None) -> list[dict]:
        """
        Simula stock.quant.search_read()
        Retorna stock actual por producto, con datos de reorden.
        """
        data = CURRENT_INVENTORY
        if sku:
            data = [item for item in data if item["sku"] == sku]
        return self._format_response("stock.quant", data)

    def get_sales_history(self, days: int = 90, sku: Optional[str] = None) -> list[dict]:
        """
        Simula sale.order.line agrupado por product_id.
        Retorna ventas de los últimos `days` días.
        """
        data = SALES_HISTORY
        if sku:
            data = [item for item in data if item["sku"] == sku]

        # Enriquecer con fecha de consulta
        enriched = []
        for item in data:
            total = item["ventas_oct"] + item["ventas_nov"] + item["ventas_dic"]
            enriched.append({
                **item,
                "total_vendido_90d": total,
                "promedio_mensual": round(total / 3, 1),
                "fecha_consulta": datetime.now().strftime("%Y-%m-%d"),
                "periodo": f"{(datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')} → {datetime.now().strftime('%Y-%m-%d')}"
            })
        return self._format_response("sale.order.line", enriched)

    def get_purchase_orders(self, status: str = "all") -> list[dict]:
        """
        Simula purchase.order.search_read()
        Retorna órdenes de compra existentes.
        """
        orders = self._purchase_orders
        if status == "pending":
            orders = [o for o in orders if o["estado"] == "borrador"]
        return self._format_response("purchase.order", orders)

    def get_reorder_alerts(self) -> list[dict]:
        """
        Calcula SKUs que están bajo el punto de reorden.
        Lógica: stock_actual < stock_minimo + (promedio_diario * lead_time)
        """
        alerts = []
        sales = {s["sku"]: s for s in SALES_HISTORY}

        for inv in CURRENT_INVENTORY:
            sku = inv["sku"]
            sale_data = sales.get(sku, {})
            total_90d = (sale_data.get("ventas_oct", 0) +
                         sale_data.get("ventas_nov", 0) +
                         sale_data.get("ventas_dic", 0))
            promedio_diario = total_90d / 90
            consumo_lead_time = promedio_diario * inv["lead_time_dias"]
            punto_reorden = inv["stock_minimo"] + consumo_lead_time

            if inv["stock_actual"] < punto_reorden:
                cantidad_sugerida = round(
                    (promedio_diario * 30 * 1.2) - inv["stock_actual"]  # 30 días + 20% buffer
                )
                alerts.append({
                    "sku": sku,
                    "nombre": sale_data.get("nombre", "N/A"),
                    "stock_actual": inv["stock_actual"],
                    "punto_reorden": round(punto_reorden, 1),
                    "deficit": round(punto_reorden - inv["stock_actual"], 1),
                    "cantidad_sugerida_pedido": max(cantidad_sugerida, 1),
                    "proveedor": inv["proveedor"],
                    "lead_time_dias": inv["lead_time_dias"],
                    "costo_unitario_clp": inv["costo_unitario"],
                    "costo_total_estimado_clp": max(cantidad_sugerida, 1) * inv["costo_unitario"],
                    "urgencia": "CRÍTICA" if inv["stock_actual"] < inv["stock_minimo"] else "MODERADA"
                })

        return self._format_response("reorder.alert", alerts)

    # ------------------------------------------------------------------
    # ESCRITURA
    # ------------------------------------------------------------------

    def create_purchase_order(self, sku: str, cantidad: int, proveedor: str,
                               justificacion: str = "") -> dict:
        """
        Simula purchase.order.create()
        En producción: POST /web/dataset/call_kw con model=purchase.order, method=create
        """
        inv = next((i for i in CURRENT_INVENTORY if i["sku"] == sku), None)
        if not inv:
            return {"error": f"SKU {sku} no encontrado en el sistema"}

        order = {
            "id": f"PO-{len(self._purchase_orders) + 1001}",
            "sku": sku,
            "proveedor": proveedor,
            "cantidad": cantidad,
            "costo_unitario": inv["costo_unitario"],
            "total_clp": cantidad * inv["costo_unitario"],
            "estado": "borrador",
            "fecha_creacion": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "fecha_entrega_estimada": (
                datetime.now() + timedelta(days=inv["lead_time_dias"])
            ).strftime("%Y-%m-%d"),
            "justificacion_agente": justificacion,
            "requiere_aprobacion": (cantidad * inv["costo_unitario"]) > 5_000_000
        }

        self._purchase_orders.append(order)
        aprobacion = " ⚠️  REQUIERE APROBACIÓN GERENTE" if order["requiere_aprobacion"] else ""
        print(f"[OdooMock] Orden creada: {order['id']} | {sku} x{cantidad} | "
              f"${order['total_clp']:,} CLP{aprobacion}")
        return {"success": True, "order": order}

    # ------------------------------------------------------------------
    # UTILIDADES
    # ------------------------------------------------------------------

    def _format_response(self, model: str, records: list) -> list[dict]:
        """Imita el envelope de respuesta de Odoo JSON-RPC"""
        return records  # En mock retornamos directo; en prod vendría dentro de result{}

    def __repr__(self):
        return f"OdooMockClient(db='{self.db}', user='{self.user}', mode='simulation')"


# --- Test rápido ---
if __name__ == "__main__":
    client = OdooMockClient()

    print("\n=== ALERTAS DE REORDEN ===")
    alerts = client.get_reorder_alerts()
    for a in alerts:
        print(f"  [{a['urgencia']}] {a['sku']} | Stock: {a['stock_actual']} | "
              f"Sugerido pedir: {a['cantidad_sugerida_pedido']} unidades | "
              f"Total: ${a['costo_total_estimado_clp']:,} CLP")

    print("\n=== CREANDO ORDEN DE COMPRA ===")
    result = client.create_purchase_order(
        sku="ELEC-001",
        cantidad=40,
        proveedor="TechDistrib Ltda.",
        justificacion="Stock crítico + Cyber Monday próximo + tendencia de búsqueda +120%"
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
