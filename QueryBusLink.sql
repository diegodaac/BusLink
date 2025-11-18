-- =========================
-- Base y modo estricto
-- =========================
DROP DATABASE IF EXISTS central_autobuses;
CREATE DATABASE central_autobuses
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_0900_ai_ci;
USE central_autobuses;

SET NAMES utf8mb4;
SET sql_mode = CONCAT(@@sql_mode, ',STRICT_TRANS_TABLES');

-- =========================
-- Tabla Usuarios (Login)
-- =========================


CREATE TABLE Usuario (
  id_usuario INT AUTO_INCREMENT PRIMARY KEY,
  nombre_completo VARCHAR(120) NOT NULL,
  email VARCHAR(120) NOT NULL,
  password_hash VARCHAR(255) NOT NULL,  -- almacenar hash bcrypt/argon2, no texto plano
  rol ENUM('Admin','Empleado','Cliente','Mecanico','Chofer') DEFAULT 'Empleado',
  activo TINYINT(1) NOT NULL DEFAULT 1,
  creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ultimo_login DATETIME NULL,
  CONSTRAINT uq_usuario_email UNIQUE (email),
  CONSTRAINT ck_email_buslink CHECK (email LIKE '%@buslink.com')
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;

INSERT INTO Usuario (nombre_completo, email, password_hash, rol, activo)
VALUES ('Diego Alvarado', 'diego.alvarado@buslink.com',
        'scrypt:32768:8:1$8rmNsbDsWtSRovtT$988e200661e064c56c22b0aa2628c2eb114bc0040efef390455d09b3390c5c1ba630d172086f3adbe6399fee14e3cf61a631eecb829439762a96739b496bd4a6',
        'Admin', 1);
        
SELECT * from Usuario;


-- =========================
-- Catálogos base
-- =========================
CREATE TABLE Ciudad (
  id_ciudad INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(100) NOT NULL,
  estado VARCHAR(100),
  pais VARCHAR(100) NOT NULL DEFAULT 'México',
  CONSTRAINT uq_ciudad UNIQUE (nombre, estado, pais)
) ENGINE=InnoDB;

CREATE TABLE Terminal (
  id_terminal INT AUTO_INCREMENT PRIMARY KEY,
  id_ciudad INT NOT NULL,
  nombre VARCHAR(120) NOT NULL,
  direccion VARCHAR(200),
  CONSTRAINT fk_terminal_ciudad FOREIGN KEY (id_ciudad)
    REFERENCES Ciudad(id_ciudad) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT uq_terminal UNIQUE (id_ciudad, nombre)
) ENGINE=InnoDB;

-- =========================
-- Rutas (plantilla de trayecto)
-- =========================
CREATE TABLE Ruta (
  id_ruta INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(120) NOT NULL,              -- Ej: "Mty - GDL (Directo)"
  distancia_km DECIMAL(7,2),
  CONSTRAINT uq_ruta_nombre UNIQUE (nombre),
  CONSTRAINT ck_ruta_distancia CHECK (distancia_km IS NULL OR distancia_km >= 0)
) ENGINE=InnoDB;

CREATE TABLE Ruta_Terminal (
  id_ruta INT NOT NULL,
  id_terminal INT NOT NULL,
  orden_parada INT NOT NULL,
  minutos_desde_origen INT,
  km_desde_origen DECIMAL(7,2),
  PRIMARY KEY (id_ruta, id_terminal),
  CONSTRAINT fk_rt_ruta FOREIGN KEY (id_ruta) REFERENCES Ruta(id_ruta)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_rt_terminal FOREIGN KEY (id_terminal) REFERENCES Terminal(id_terminal)
    ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT ck_rt_orden CHECK (orden_parada >= 1)
) ENGINE=InnoDB;

CREATE INDEX idx_rt_orden ON Ruta_Terminal (id_ruta, orden_parada);

-- =========================
-- Clase de servicio con modificadores de precio
-- =========================
CREATE TABLE ClaseServicio (
  id_clase INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(60) NOT NULL,               -- Económica / Plus / Lujo
  descripcion VARCHAR(200),
  recargo_fijo DECIMAL(10,2) DEFAULT 0.00,   -- +$ fijo sobre la tarifa base
  recargo_pct  DECIMAL(5,2)  DEFAULT 0.00,   -- +% sobre la tarifa base (ej. 15.00 = 15%)
  CONSTRAINT uq_clase_nombre UNIQUE (nombre),
  CONSTRAINT ck_recargo_pct CHECK (recargo_pct >= 0)
) ENGINE=InnoDB;

-- =========================
-- Autobuses
-- =========================
CREATE TABLE Autobus (
  id_autobus INT AUTO_INCREMENT PRIMARY KEY,
  numero_placa VARCHAR(20) NOT NULL,
  numero_fisico VARCHAR(20),                 -- identificador interno de flota
  modelo VARCHAR(60),
  capacidad INT NOT NULL,
  id_clase INT,
  CONSTRAINT uq_autobus_placa UNIQUE (numero_placa),
  CONSTRAINT uq_autobus_fisico UNIQUE (numero_fisico),
  CONSTRAINT ck_autobus_cap CHECK (capacidad > 0),
  CONSTRAINT fk_autobus_clase FOREIGN KEY (id_clase)
    REFERENCES ClaseServicio(id_clase) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- =========================
-- Choferes (operación de flota)
-- =========================
CREATE TABLE Chofer (
  id_chofer INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(120) NOT NULL,
  telefono VARCHAR(25),
  correo VARCHAR(120),
  rfc VARCHAR(13),
  curp VARCHAR(18),
  nss  VARCHAR(15),
  direccion VARCHAR(200),
  fecha_ingreso DATE,
  activo TINYINT(1) NOT NULL DEFAULT 1,
  licencia VARCHAR(50) NOT NULL,             -- número
  licencia_tipo VARCHAR(20),                 -- A, B, C, etc.
  licencia_expira DATE,
  anios_experiencia INT NOT NULL DEFAULT 0,
  notas VARCHAR(250),
  CONSTRAINT uq_chofer_lic UNIQUE (licencia),
  CONSTRAINT ck_chofer_exp CHECK (anios_experiencia >= 0)
) ENGINE=InnoDB;

-- =========================
-- Pasajeros (boletaje)
-- =========================
CREATE TABLE Pasajero (
  id_pasajero INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(120) NOT NULL,
  telefono VARCHAR(25),
  correo VARCHAR(120),
  creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT uq_pasajero_correo UNIQUE (correo)
) ENGINE=InnoDB;

-- =========================
-- Empleados (trazabilidad de ventas)
-- =========================
CREATE TABLE Empleado (
  id_empleado INT AUTO_INCREMENT PRIMARY KEY,
  nombre VARCHAR(120) NOT NULL,
  correo VARCHAR(120),
  telefono VARCHAR(25),
  rol ENUM('Ventanilla','Supervisor','Admin','Chofer','Mecanico') NOT NULL DEFAULT 'Ventanilla',
  activo TINYINT(1) NOT NULL DEFAULT 1,
  CONSTRAINT uq_empleado_correo UNIQUE (correo)
) ENGINE=InnoDB;

-- =========================
-- Tarifas por ruta/clase con vigencias
-- =========================
CREATE TABLE Tarifa (
  id_tarifa INT AUTO_INCREMENT PRIMARY KEY,
  id_ruta INT NOT NULL,
  id_clase INT,                              -- NULL = tarifa válida para cualquier clase
  precio_base DECIMAL(10,2) NOT NULL,
  impuesto    DECIMAL(10,2) NOT NULL DEFAULT 0.00,
  vigencia_inicio DATE NOT NULL,
  vigencia_fin    DATE,
  CONSTRAINT fk_tarifa_ruta FOREIGN KEY (id_ruta)
    REFERENCES Ruta(id_ruta) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_tarifa_clase FOREIGN KEY (id_clase)
    REFERENCES ClaseServicio(id_clase) ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB;

-- =========================
-- Viajes programados
-- =========================
CREATE TABLE Viaje (
  id_viaje INT AUTO_INCREMENT PRIMARY KEY,
  id_ruta INT NOT NULL,
  id_autobus INT NOT NULL,
  id_chofer INT NOT NULL,
  fecha_salida DATETIME NOT NULL,
  fecha_llegada DATETIME NOT NULL,
  estado ENUM('Programado','EnRuta','Finalizado','Cancelado') NOT NULL DEFAULT 'Programado',
  observaciones VARCHAR(250),
  KEY idx_viaje_ruta (id_ruta),
  KEY idx_viaje_autobus (id_autobus),
  KEY idx_viaje_chofer (id_chofer),
  CONSTRAINT fk_viaje_ruta   FOREIGN KEY (id_ruta)   REFERENCES Ruta(id_ruta)     ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_viaje_autobus FOREIGN KEY (id_autobus) REFERENCES Autobus(id_autobus) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_viaje_chofer FOREIGN KEY (id_chofer) REFERENCES Chofer(id_chofer) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT ck_viaje_fechas CHECK (fecha_llegada > fecha_salida)
) ENGINE=InnoDB;

CREATE TABLE Viaje_Escala (
  id_viaje INT NOT NULL,
  id_terminal INT NOT NULL,
  orden_parada INT NOT NULL,
  hora_estimada DATETIME NOT NULL,
  hora_real DATETIME,
  PRIMARY KEY (id_viaje, id_terminal),
  CONSTRAINT fk_ve_viaje   FOREIGN KEY (id_viaje)   REFERENCES Viaje(id_viaje)     ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_ve_terminal FOREIGN KEY (id_terminal) REFERENCES Terminal(id_terminal) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

-- =========================
-- Boletos y ventas
-- =========================
CREATE TABLE Boleto (
  id_boleto INT AUTO_INCREMENT PRIMARY KEY,
  id_viaje INT NOT NULL,
  id_pasajero INT NOT NULL,
  id_tarifa INT,
  numero_asiento INT NOT NULL,
  estado ENUM('Reservado','Pagado','Cancelado','Abordado','NoShow') NOT NULL DEFAULT 'Reservado',
  precio_total DECIMAL(10,2),
  creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en DATETIME NULL ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT uq_boleto_asiento UNIQUE (id_viaje, numero_asiento),
  CONSTRAINT fk_boleto_viaje    FOREIGN KEY (id_viaje)    REFERENCES Viaje(id_viaje)         ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_boleto_pasajero FOREIGN KEY (id_pasajero) REFERENCES Pasajero(id_pasajero)   ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT fk_boleto_tarifa   FOREIGN KEY (id_tarifa)   REFERENCES Tarifa(id_tarifa)       ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_boleto_asiento CHECK (numero_asiento > 0)
) ENGINE=InnoDB;

CREATE TABLE Cliente (
  id_cliente INT AUTO_INCREMENT PRIMARY KEY,
  nombre   VARCHAR(120) NOT NULL,
  correo   VARCHAR(120),
  telefono VARCHAR(25),
  tipo     ENUM('Particular','Empresa') NOT NULL DEFAULT 'Particular',
  CONSTRAINT uq_cliente_correo UNIQUE (correo)
) ENGINE=InnoDB;

CREATE TABLE Venta (
  id_venta INT AUTO_INCREMENT PRIMARY KEY,
  id_boleto INT NOT NULL,
  id_empleado INT,
  id_cliente INT,
  fecha_venta DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  metodo_pago ENUM('Efectivo','Tarjeta','Transferencia') NOT NULL,
  monto DECIMAL(10,2) NOT NULL,
  nota VARCHAR(200),
  CONSTRAINT fk_venta_boleto   FOREIGN KEY (id_boleto)  REFERENCES Boleto(id_boleto)   ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_venta_empleado FOREIGN KEY (id_empleado) REFERENCES Empleado(id_empleado) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT fk_venta_cliente  FOREIGN KEY (id_cliente)  REFERENCES Cliente(id_cliente) ON DELETE SET NULL ON UPDATE CASCADE,
  CONSTRAINT ck_venta_monto CHECK (monto >= 0)
) ENGINE=InnoDB;

-- =========================
-- Mantenimientos
-- =========================
CREATE TABLE Mantenimiento (
  id_mantenimiento INT AUTO_INCREMENT PRIMARY KEY,
  id_autobus INT NOT NULL,
  descripcion VARCHAR(250),
  fecha DATE NOT NULL,
  costo DECIMAL(10,2),
  CONSTRAINT fk_mant_autobus FOREIGN KEY (id_autobus)
    REFERENCES Autobus(id_autobus) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT ck_mant_costo CHECK (costo IS NULL OR costo >= 0)
) ENGINE=InnoDB;

-- =========================
-- Triggers clave
-- =========================
DELIMITER //
CREATE TRIGGER tr_boleto_capacidad
BEFORE INSERT ON Boleto
FOR EACH ROW
BEGIN
  DECLARE v_cap INT;
  SELECT a.capacidad INTO v_cap
  FROM Viaje v JOIN Autobus a ON a.id_autobus = v.id_autobus
  WHERE v.id_viaje = NEW.id_viaje;
  IF NEW.numero_asiento > v_cap OR NEW.numero_asiento <= 0 THEN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'El número de asiento excede la capacidad del autobús.';
  END IF;
END//

CREATE TRIGGER tr_viaje_no_overlap_bus
BEFORE INSERT ON Viaje
FOR EACH ROW
BEGIN
  IF EXISTS (
    SELECT 1 FROM Viaje v
    WHERE v.id_autobus = NEW.id_autobus
      AND v.estado <> 'Cancelado'
      AND NEW.fecha_salida < v.fecha_llegada
      AND NEW.fecha_llegada > v.fecha_salida
  ) THEN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Conflicto: el autobús ya tiene un viaje en ese horario.';
  END IF;
END//

CREATE TRIGGER tr_viaje_no_overlap_chofer
BEFORE INSERT ON Viaje
FOR EACH ROW
BEGIN
  IF EXISTS (
    SELECT 1 FROM Viaje v
    WHERE v.id_chofer = NEW.id_chofer
      AND v.estado <> 'Cancelado'
      AND NEW.fecha_salida < v.fecha_llegada
      AND NEW.fecha_llegada > v.fecha_salida
  ) THEN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Conflicto: el chofer ya tiene un viaje en ese horario.';
  END IF;
END//
DELIMITER ;

-- =========================
-- Detalle inmutable de la venta (ticket histórico)
-- =========================
CREATE TABLE Venta_Detalle (
  id_venta_detalle INT AUTO_INCREMENT PRIMARY KEY,
  id_venta  INT NOT NULL,
  id_boleto INT NOT NULL,

  -- Snapshot del comprador (cliente)
  cliente_nombre   VARCHAR(120),
  cliente_correo   VARCHAR(120),
  cliente_telefono VARCHAR(25),

  -- Snapshot del pasajero (quien viaja)
  pasajero_nombre VARCHAR(120),
  pasajero_correo VARCHAR(120),

  -- Snapshot del viaje
  ruta_nombre      VARCHAR(120),
  origen_ciudad    VARCHAR(100),
  origen_terminal  VARCHAR(120),
  destino_ciudad   VARCHAR(100),
  destino_terminal VARCHAR(120),
  fecha_salida     DATETIME,
  fecha_llegada    DATETIME,
  numero_asiento   INT,

  -- Snapshot de clase/tarifa/importes
  clase_nombre   VARCHAR(60),
  precio_base    DECIMAL(10,2),
  recargo_fijo   DECIMAL(10,2),
  recargo_pct    DECIMAL(5,2),
  impuesto       DECIMAL(10,2),
  precio_total   DECIMAL(10,2),
  metodo_pago    ENUM('Efectivo','Tarjeta','Transferencia'),
  moneda         CHAR(3) NOT NULL DEFAULT 'MXN',

  creado_en DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

  CONSTRAINT uq_vd_venta UNIQUE (id_venta),
  CONSTRAINT fk_vd_venta  FOREIGN KEY (id_venta)  REFERENCES Venta(id_venta)   ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_vd_boleto FOREIGN KEY (id_boleto) REFERENCES Boleto(id_boleto) ON DELETE RESTRICT ON UPDATE CASCADE
) ENGINE=InnoDB;

DELIMITER //
CREATE TRIGGER tr_venta_snapshot
AFTER INSERT ON Venta
FOR EACH ROW
BEGIN
  -- Comprador (cliente) si existe
  DECLARE v_cliente_nombre   VARCHAR(120);
  DECLARE v_cliente_correo   VARCHAR(120);
  DECLARE v_cliente_telefono VARCHAR(25);

  -- Pasajero y viaje
  DECLARE v_pasajero_nombre VARCHAR(120);
  DECLARE v_pasajero_correo VARCHAR(120);
  DECLARE v_ruta_nombre     VARCHAR(120);
  DECLARE v_fecha_salida    DATETIME;
  DECLARE v_fecha_llegada   DATETIME;
  DECLARE v_asiento         INT;
  DECLARE v_clase_nombre    VARCHAR(60);
  DECLARE v_precio_base     DECIMAL(10,2);
  DECLARE v_recargo_fijo    DECIMAL(10,2);
  DECLARE v_recargo_pct     DECIMAL(5,2);
  DECLARE v_impuesto        DECIMAL(10,2);
  DECLARE v_precio_total    DECIMAL(10,2);
  DECLARE v_origen_ciudad   VARCHAR(100);
  DECLARE v_origen_terminal VARCHAR(120);
  DECLARE v_dest_ciudad     VARCHAR(100);
  DECLARE v_dest_terminal   VARCHAR(120);

  -- Datos base (venta, boleto, pasajero, viaje, ruta, clase/tarifa)
  SELECT 
      p.nombre, p.correo,
      r.nombre,
      v.fecha_salida, v.fecha_llegada,
      b.numero_asiento,
      cs.nombre,
      COALESCE(t.precio_base, 0.00),
      COALESCE(cs.recargo_fijo, 0.00),
      COALESCE(cs.recargo_pct, 0.00),
      COALESCE(t.impuesto, 0.00),
      COALESCE(b.precio_total,
               COALESCE(t.precio_base,0.00) + COALESCE(cs.recargo_fijo,0.00)
               + (COALESCE(t.precio_base,0.00) * COALESCE(cs.recargo_pct,0.00) / 100.00)
               + COALESCE(t.impuesto,0.00))
  INTO
      v_pasajero_nombre, v_pasajero_correo,
      v_ruta_nombre,
      v_fecha_salida, v_fecha_llegada,
      v_asiento,
      v_clase_nombre,
      v_precio_base, v_recargo_fijo, v_recargo_pct, v_impuesto, v_precio_total
  FROM Venta ve
  JOIN Boleto b     ON b.id_boleto = ve.id_boleto
  JOIN Pasajero p   ON p.id_pasajero = b.id_pasajero
  JOIN Viaje v      ON v.id_viaje   = b.id_viaje
  JOIN Ruta  r      ON r.id_ruta    = v.id_ruta
  LEFT JOIN Tarifa t      ON t.id_tarifa = b.id_tarifa
  LEFT JOIN Autobus a     ON a.id_autobus = v.id_autobus
  LEFT JOIN ClaseServicio cs ON cs.id_clase = a.id_clase
  WHERE ve.id_venta = NEW.id_venta;

  -- Comprador (si Venta.id_cliente no es NULL)
  IF NEW.id_cliente IS NOT NULL THEN
    SELECT c.nombre, c.correo, c.telefono
    INTO   v_cliente_nombre, v_cliente_correo, v_cliente_telefono
    FROM Cliente c
    WHERE c.id_cliente = NEW.id_cliente;
  ELSE
    -- Si no hay cliente explícito, asumimos que el comprador = pasajero
    SET v_cliente_nombre   = v_pasajero_nombre;
    SET v_cliente_correo   = v_pasajero_correo;
    SET v_cliente_telefono = NULL;
  END IF;

  -- Origen y destino (si existen escalas)
  SELECT c.nombre, t.nombre
  INTO   v_origen_ciudad, v_origen_terminal
  FROM Viaje_Escala ve
  JOIN Terminal t ON t.id_terminal = ve.id_terminal
  JOIN Ciudad   c ON c.id_ciudad   = t.id_ciudad
  WHERE ve.id_viaje = (SELECT b2.id_viaje FROM Boleto b2 WHERE b2.id_boleto = NEW.id_boleto)
  ORDER BY ve.orden_parada ASC
  LIMIT 1;

  SELECT c.nombre, t.nombre
  INTO   v_dest_ciudad, v_dest_terminal
  FROM Viaje_Escala ve
  JOIN Terminal t ON t.id_terminal = ve.id_terminal
  JOIN Ciudad   c ON c.id_ciudad   = t.id_ciudad
  WHERE ve.id_viaje = (SELECT b3.id_viaje FROM Boleto b3 WHERE b3.id_boleto = NEW.id_boleto)
  ORDER BY ve.orden_parada DESC
  LIMIT 1;

  -- Inserta snapshot
  INSERT INTO Venta_Detalle(
    id_venta, id_boleto,
    cliente_nombre, cliente_correo, cliente_telefono,
    pasajero_nombre, pasajero_correo,
    ruta_nombre, origen_ciudad, origen_terminal, destino_ciudad, destino_terminal,
    fecha_salida, fecha_llegada, numero_asiento,
    clase_nombre, precio_base, recargo_fijo, recargo_pct, impuesto, precio_total,
    metodo_pago, moneda
  ) VALUES (
    NEW.id_venta, NEW.id_boleto,
    v_cliente_nombre, v_cliente_correo, v_cliente_telefono,
    v_pasajero_nombre, v_pasajero_correo,
    v_ruta_nombre, v_origen_ciudad, v_origen_terminal, v_dest_ciudad, v_dest_terminal,
    v_fecha_salida, v_fecha_llegada, v_asiento,
    v_clase_nombre, v_precio_base, v_recargo_fijo, v_recargo_pct, v_impuesto, v_precio_total,
    NEW.metodo_pago, 'MXN'
  );
END//
DELIMITER ;

-- =========================
-- Vistas útiles
-- =========================
CREATE OR REPLACE VIEW vw_tarifa_vigente AS
SELECT * FROM Tarifa
WHERE vigencia_inicio <= CURRENT_DATE()
  AND (vigencia_fin IS NULL OR vigencia_fin >= CURRENT_DATE());

CREATE OR REPLACE VIEW vw_asientos_disponibilidad AS
SELECT v.id_viaje, a.capacidad,
       SUM(CASE WHEN b.estado IN ('Pagado','Reservado') THEN 1 ELSE 0 END) AS asientos_ocupados,
       a.capacidad - SUM(CASE WHEN b.estado IN ('Pagado','Reservado') THEN 1 ELSE 0 END) AS asientos_disponibles
FROM Viaje v
JOIN Autobus a ON a.id_autobus = v.id_autobus
LEFT JOIN Boleto b ON b.id_viaje = v.id_viaje
GROUP BY v.id_viaje, a.capacidad;

CREATE OR REPLACE VIEW vw_itinerario_viaje AS
SELECT v.id_viaje, v.id_ruta, ve.orden_parada,
       c.nombre AS ciudad, t.nombre AS terminal,
       ve.hora_estimada, ve.hora_real
FROM Viaje v
JOIN Viaje_Escala ve ON ve.id_viaje = v.id_viaje
JOIN Terminal t ON t.id_terminal = ve.id_terminal
JOIN Ciudad c ON c.id_ciudad = t.id_ciudad
ORDER BY v.id_viaje, ve.orden_parada;
