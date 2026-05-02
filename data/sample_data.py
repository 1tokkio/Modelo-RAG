"""
Datos de ejemplo simulados para RetailSur S.A.
Representan lo que vendría del ERP Odoo y fuentes externas.
"""

# Histórico de ventas por SKU (últimos 3 meses)
SALES_HISTORY = [
    {"sku": "ELEC-001", "nombre": "Smart TV 55 pulgadas", "categoria": "Electrónica",
     "ventas_oct": 45, "ventas_nov": 62, "ventas_dic": 130, "unidad": "unidades"},
    {"sku": "ELEC-002", "nombre": "Notebook Core i5", "categoria": "Electrónica",
     "ventas_oct": 28, "ventas_nov": 35, "ventas_dic": 89, "unidad": "unidades"},
    {"sku": "HOGAR-001", "nombre": "Estufa a Pellet 15kW", "categoria": "Hogar",
     "ventas_oct": 92, "ventas_nov": 78, "ventas_dic": 41, "unidad": "unidades"},
    {"sku": "HOGAR-002", "nombre": "Refrigerador 350L No Frost", "categoria": "Hogar",
     "ventas_oct": 19, "ventas_nov": 22, "ventas_dic": 51, "unidad": "unidades"},
    {"sku": "VEST-001", "nombre": "Parka Impermeable Hombre", "categoria": "Vestuario",
     "ventas_oct": 67, "ventas_nov": 55, "ventas_dic": 30, "unidad": "unidades"},
    {"sku": "FERR-001", "nombre": "Generador Gasolina 2500W", "categoria": "Ferretería",
     "ventas_oct": 14, "ventas_nov": 18, "ventas_dic": 12, "unidad": "unidades"},
]

# Estado actual del inventario
CURRENT_INVENTORY = [
    {"sku": "ELEC-001", "stock_actual": 8,  "stock_minimo": 15, "lead_time_dias": 12,
     "proveedor": "TechDistrib Ltda.", "costo_unitario": 389000},
    {"sku": "ELEC-002", "stock_actual": 3,  "stock_minimo": 10, "lead_time_dias": 15,
     "proveedor": "TechDistrib Ltda.", "costo_unitario": 429000},
    {"sku": "HOGAR-001", "stock_actual": 24, "stock_minimo": 20, "lead_time_dias": 21,
     "proveedor": "Calefacción Sur S.A.", "costo_unitario": 289000},
    {"sku": "HOGAR-002", "stock_actual": 11, "stock_minimo": 8,  "lead_time_dias": 18,
     "proveedor": "ElectroHogar Ltda.", "costo_unitario": 449000},
    {"sku": "VEST-001", "stock_actual": 34, "stock_minimo": 25, "lead_time_dias": 10,
     "proveedor": "TextilSur SpA", "costo_unitario": 39000},
    {"sku": "FERR-001", "stock_actual": 6,  "stock_minimo": 5,  "lead_time_dias": 14,
     "proveedor": "HerramientasPro", "costo_unitario": 189000},
]

# Datos externos simulados (clima, feriados, tendencias)
EXTERNAL_CONTEXT = [
    {
        "tipo": "clima",
        "descripcion": "Pronóstico próximas 4 semanas Puerto Montt y región: temperaturas mínimas "
                       "entre 4°C y 8°C, con precipitaciones frecuentes. Se proyecta frente de frío "
                       "intenso para la segunda quincena. Condiciones favorables para mayor demanda "
                       "de calefacción, prendas de abrigo y equipos de emergencia."
    },
    {
        "tipo": "feriados",
        "descripcion": "Próximos eventos comerciales: Cyber Monday (primer lunes de diciembre, alta "
                       "demanda proyectada en electrónica +85% sobre promedio). Navidad (25 diciembre, "
                       "pico en electrónica, hogar y vestuario). Año Nuevo (1 enero, menor impacto)."
    },
    {
        "tipo": "tendencias",
        "descripcion": "Google Trends semana actual (región Los Lagos): búsquedas 'Smart TV oferta' "
                       "+120% vs mes anterior. 'Notebook estudiante' +95%. 'Estufa pellet' -30% "
                       "(fin temporada). 'Parka invierno' -45% (fin temporada). 'Generador luz' +60% "
                       "por cortes eléctricos recientes en zona rural."
    },
    {
        "tipo": "mercado",
        "descripcion": "Análisis competitivo: competidor principal (MegaRetail) lanzó promoción "
                       "'2x1 en electrónica' vigente hasta fin de mes. RetailSur debe anticipar "
                       "posible caída de demanda en electrónica en tiendas físicas y compensar "
                       "con canal e-commerce donde el precio es más competitivo."
    }
]

# Políticas internas de compra
PURCHASE_POLICIES = [
    {
        "tipo": "política",
        "descripcion": "Política de reabastecimiento RetailSur S.A.: el punto de reorden se activa "
                       "cuando el stock actual cae por debajo del stock mínimo más el consumo "
                       "proyectado durante el lead time del proveedor. La cantidad a pedir debe "
                       "cubrir al menos 30 días de demanda proyectada más un buffer de seguridad "
                       "del 20%. Pedidos superiores a $5.000.000 CLP requieren aprobación del "
                       "gerente de operaciones."
    },
    {
        "tipo": "política",
        "descripcion": "Categorías prioritarias en temporada alta (noviembre-enero): Electrónica y "
                       "Hogar tienen prioridad de reabastecimiento sobre Vestuario y Ferretería. "
                       "En caso de presupuesto limitado, se priorizan los SKU con mayor margen "
                       "bruto y mayor rotación histórica."
    }
]
