USE central_autobuses;

-- 1) Crear roles
DROP ROLE IF EXISTS 'r_admin_app';
DROP ROLE IF EXISTS 'r_empleado_app';
DROP ROLE IF EXISTS 'r_chofer_app';

CREATE ROLE 'r_admin_app';
CREATE ROLE 'r_empleado_app';
CREATE ROLE 'r_chofer_app';

-- 2) Crear usuarios de BD (uno por perfil de conexión de la app)
CREATE USER 'buslink_admin'@'localhost' IDENTIFIED BY 'Fuerte#Admin2025';
CREATE USER 'buslink_empleado'@'localhost' IDENTIFIED BY 'Fuerte#Empleado2025';
CREATE USER 'buslink_chofer'@'localhost' IDENTIFIED BY 'Fuerte#Chofer2025';


GRANT ALL PRIVILEGES ON central_autobuses.* TO r_admin_app;
GRANT r_admin_app TO 'buslink_admin'@'localhost';
SET DEFAULT ROLE r_admin_app TO 'buslink_admin'@'localhost';

-- SELECT a catálogos y consultas
GRANT SELECT ON central_autobuses.Ciudad           TO r_empleado_app;
GRANT SELECT ON central_autobuses.Terminal         TO r_empleado_app;
GRANT SELECT ON central_autobuses.Ruta             TO r_empleado_app;
GRANT SELECT ON central_autobuses.Ruta_Terminal    TO r_empleado_app;
GRANT SELECT ON central_autobuses.ClaseServicio    TO r_empleado_app;
GRANT SELECT ON central_autobuses.Autobus          TO r_empleado_app;
GRANT SELECT ON central_autobuses.Chofer           TO r_empleado_app;
GRANT SELECT ON central_autobuses.Tarifa           TO r_empleado_app;
GRANT SELECT ON central_autobuses.Viaje            TO r_empleado_app;
GRANT SELECT ON central_autobuses.Viaje_Escala     TO r_empleado_app;
GRANT SELECT ON central_autobuses.Pasajero         TO r_empleado_app;
GRANT SELECT ON central_autobuses.vw_asientos_disponibilidad TO r_empleado_app;
GRANT SELECT ON central_autobuses.vw_itinerario_viaje        TO r_empleado_app;

-- No DML directo sobre Boleto/Venta/Pasajero (lo bloqueamos)
-- En su lugar, solo EXECUTE de SPs de negocio:
GRANT EXECUTE ON PROCEDURE central_autobuses.sp_registrar_venta    TO r_empleado_app;
GRANT EXECUTE ON PROCEDURE central_autobuses.sp_cancelar_boleto    TO r_empleado_app;
GRANT EXECUTE ON PROCEDURE central_autobuses.sp_registrar_pasajero TO r_empleado_app;

GRANT r_empleado_app TO 'buslink_empleado'@'localhost';
SET DEFAULT ROLE r_empleado_app TO 'buslink_empleado'@'localhost';

-- Lectura a vistas (no tablas de ventas)
GRANT SELECT ON central_autobuses.Viaje            TO r_chofer_app;
GRANT SELECT ON central_autobuses.Viaje_Escala     TO r_chofer_app;
GRANT SELECT ON central_autobuses.Ruta             TO r_chofer_app;
GRANT SELECT ON central_autobuses.Terminal         TO r_chofer_app;
GRANT SELECT ON central_autobuses.Ciudad           TO r_chofer_app;

-- Si usas vistas específicas:
-- GRANT SELECT ON central_autobuses.vw_viajes_programados TO r_chofer_app;

GRANT r_chofer_app TO 'buslink_chofer'@'localhost';
SET DEFAULT ROLE r_chofer_app TO 'buslink_chofer'@'localhost';
