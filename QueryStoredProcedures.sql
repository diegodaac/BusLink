USE central_autobuses;

DELIMITER //

-- =========================================
-- 1) Registrar pasajero
-- =========================================
DROP PROCEDURE IF EXISTS sp_registrar_pasajero;
CREATE DEFINER = `buslink_admin`@`localhost`
PROCEDURE sp_registrar_pasajero (
    IN p_nombre   VARCHAR(120),
    IN p_correo   VARCHAR(120),
    IN p_telefono VARCHAR(25)
)
SQL SECURITY DEFINER
BEGIN
    INSERT INTO Pasajero(nombre, correo, telefono)
    VALUES (p_nombre, p_correo, p_telefono);
END//
 

-- =========================================
-- 2) Registrar venta
-- =========================================
DROP PROCEDURE IF EXISTS sp_registrar_venta;
CREATE DEFINER = `buslink_admin`@`localhost`
PROCEDURE sp_registrar_venta (
    IN p_id_viaje     INT,
    IN p_id_pasajero  INT,
    IN p_num_asiento  INT,
    IN p_metodo_pago  VARCHAR(20),  -- 'Efectivo','Tarjeta','Transferencia'
    IN p_id_cliente   INT           -- puede ser NULL
)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_id_boleto INT;

    -- Aquí podrías validar capacidad o asiento duplicado, de momento lo dejamos simple

    -- 1) Crear boleto (asumimos venta inmediata: estado 'Pagado')
    INSERT INTO Boleto(
        id_viaje, id_pasajero, id_tarifa,
        numero_asiento, estado, precio_total
    ) VALUES (
        p_id_viaje, p_id_pasajero, NULL,
        p_num_asiento, 'Pagado', NULL   -- precio_total se puede calcular luego o venir de app
    );

    SET v_id_boleto = LAST_INSERT_ID();

    -- 2) Crear venta (monto 0 por ahora, luego puedes pasarlo como parámetro o calcularlo)
    INSERT INTO Venta(
        id_boleto, id_empleado, id_cliente,
        metodo_pago, monto, nota
    ) VALUES (
        v_id_boleto, NULL, p_id_cliente,
        p_metodo_pago, 0.00, NULL
    );

    -- El trigger tr_venta_snapshot se ejecuta después del INSERT en Venta
END//


-- =========================================
-- 3) Cancelar boleto
--    - Marca el boleto como 'Cancelado'
--    - Añade nota a la venta asociada (si existe)
-- =========================================
DROP PROCEDURE IF EXISTS sp_cancelar_boleto;
CREATE DEFINER = `buslink_admin`@`localhost`
PROCEDURE sp_cancelar_boleto (
    IN p_id_boleto INT,
    IN p_motivo    VARCHAR(200)
)
SQL SECURITY DEFINER
BEGIN
    DECLARE v_id_venta INT;

    -- Verificar que el boleto exista
    IF NOT EXISTS (SELECT 1 FROM Boleto WHERE id_boleto = p_id_boleto) THEN
        SIGNAL SQLSTATE '45000'
            SET MESSAGE_TEXT = 'El boleto no existe.';
    END IF;

    -- Cambiar estado del boleto
    UPDATE Boleto
    SET estado = 'Cancelado'
    WHERE id_boleto = p_id_boleto;

    -- Buscar la venta asociada, si la hay
    SELECT id_venta
    INTO v_id_venta
    FROM Venta
    WHERE id_boleto = p_id_boleto
    LIMIT 1;

    -- Actualizar la nota de la venta para dejar rastro
    IF v_id_venta IS NOT NULL THEN
        UPDATE Venta
        SET nota = CONCAT(
                COALESCE(nota, ''),
                CASE WHEN nota IS NULL OR nota = '' THEN '' ELSE ' | ' END,
                'CANCELADO: ', p_motivo
            )
        WHERE id_venta = v_id_venta;
    END IF;
END//

DELIMITER ;

DELIMITER //
CREATE FUNCTION fn_total_ventas_dia_empleado(
    p_id_empleado INT,
    p_fecha DATE
)
RETURNS DECIMAL(10,2)
DETERMINISTIC
BEGIN
    DECLARE v_total DECIMAL(10,2);

    SELECT COALESCE(SUM(monto),0) INTO v_total
    FROM   Venta
    WHERE  id_empleado = p_id_empleado
      AND  DATE(fecha_venta) = p_fecha;

    RETURN v_total;
END//
DELIMITER ;
