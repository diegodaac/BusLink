import MySQLdb
import MySQLdb.cursors
from datetime import datetime
from decimal import Decimal

class ModelTarifa:
    @classmethod
    def calcular_precio_boleto(cls, db, id_viaje: int):
        """
        Calcula el precio final de un boleto para un viaje dado.

        Regla de negocio:
        - Precio base desde Tarifa.precio_base
        - + recargo_fijo de ClaseServicio
        - + recargo_pct (porcentaje sobre precio_base)
        - + impuesto (monto fijo en Tarifa.impuesto)
        - +10% adicional si la fecha de salida es de Lunes a Viernes

        Retorna:
        - (id_tarifa, precio_final)  ó  (None, None) si no encuentra tarifa
        """
        try:
            cursor = db.connection.cursor(MySQLdb.cursors.DictCursor)

            sql = """
            SELECT 
                t.id_tarifa,
                t.precio_base,
                t.impuesto,
                cs.recargo_fijo,
                cs.recargo_pct,
                v.fecha_salida
            FROM Viaje v
            JOIN Ruta r       ON v.id_ruta    = r.id_ruta
            JOIN Autobus a    ON v.id_autobus = a.id_autobus
            LEFT JOIN ClaseServicio cs 
                   ON a.id_clase = cs.id_clase
            JOIN Tarifa t
              ON t.id_ruta = r.id_ruta
             AND (t.id_clase = a.id_clase OR t.id_clase IS NULL)
             AND DATE(v.fecha_salida) BETWEEN t.vigencia_inicio 
                                          AND IFNULL(t.vigencia_fin, DATE(v.fecha_salida))
            WHERE v.id_viaje = %s
            ORDER BY 
              (t.id_clase IS NULL) ASC,
              t.vigencia_inicio DESC
            LIMIT 1;
            """

            cursor.execute(sql, (id_viaje,))
            row = cursor.fetchone()
            cursor.close()

            if not row:
                # No hay tarifa definida para ese viaje
                return None, None

            # Extraemos valores y los convertimos a Decimal para evitar problemas de flotantes
            precio_base   = Decimal(row['precio_base']   or 0)
            impuesto      = Decimal(row['impuesto']      or 0)
            recargo_fijo  = Decimal(row.get('recargo_fijo') or 0)
            recargo_pct   = Decimal(row.get('recargo_pct')  or 0)

            # 1) Base + recargos por clase
            subtotal = precio_base + recargo_fijo
            subtotal += precio_base * (recargo_pct / Decimal('100'))

            # 2) Sumamos impuesto (lo tomamos como monto fijo)
            subtotal += impuesto

            # 3) Recargo del 10% si la salida es de lunes a viernes
            fecha_salida = row['fecha_salida']
            if isinstance(fecha_salida, str):
                # por si el driver devolviera string
                fecha_dt = datetime.fromisoformat(fecha_salida)
            else:
                fecha_dt = fecha_salida

            # weekday(): 0 = lunes, 6 = domingo
            if fecha_dt.weekday() < 5:  # 0..4 → lunes a viernes
                subtotal *= Decimal('1.10')

            # 4) Redondear a 2 decimales
            precio_final = subtotal.quantize(Decimal('0.01'))

            return row['id_tarifa'], float(precio_final)

        except Exception as ex:
            print("ERROR ModelTarifa.calcular_precio_boleto:", ex)
            return None, None
