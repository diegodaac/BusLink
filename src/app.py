from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_mysqldb import MySQL
from flask_wtf import CSRFProtect
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from config import config
from Models.ModelUser import ModelUser
from Models.entities.User import User
from datetime import datetime
import MySQLdb.cursors

app = Flask(__name__)
csrf = CSRFProtect(app)
app.config.from_object(config['development'])
app.secret_key = app.config.get('SECRET_KEY', 'dev_secret')
db = MySQL(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return ModelUser.get_by_id(db, user_id)

# Decorador para verificar que el usuario sea admin
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol != 'Admin':
            flash('Acceso denegado. Se requieren permisos de administrador.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    return redirect(url_for('home'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        user = User(id_usuario=0, email=email, password=password)
        logged_user = ModelUser.login(db, user)
        app.logger.info(logged_user)

        if logged_user:
            login_user(logged_user)
            flash(f'Bienvenido, {logged_user.nombre_completo}', 'success')

            # Redirección según rol
            if logged_user.rol == 'Chofer':
                return redirect(url_for('chofer'))
            else:
                return redirect(url_for('home'))
        else:
            flash('Credenciales inválidas o usuario inactivo.', 'danger')
            return render_template('auth/login.html')

    return render_template('auth/login.html')


@app.route('/home')
@login_required
def home():
    try:
        cursor = db.connection.cursor(MySQLdb.cursors.DictCursor)
        # 1) KPIs del día (boletos y monto)
        cursor.execute("""
            SELECT 
                COUNT(*) AS boletos_hoy,
                COALESCE(SUM(monto), 0) AS monto_hoy
            FROM Venta
            WHERE DATE(fecha_venta) = CURDATE();
        """)
        kpi = cursor.fetchone() or {'boletos_hoy': 0, 'monto_hoy': 0}

        # 2) Viajes programados para HOY
        cursor.execute("""
            SELECT
              v.id_viaje,
              v.fecha_salida,
              v.fecha_llegada,

              r.nombre  AS ruta_nombre,
              cs.nombre AS clase_nombre,  -- ← NUEVO

              ch.nombre AS chofer_nombre,
              CONCAT_WS(' ', a.numero_placa, a.numero_fisico) AS autobus_identificador,

              oc.nombre  AS origen_ciudad,
              ot.nombre  AS origen_terminal,
              dc.nombre  AS destino_ciudad,
              dt.nombre  AS destino_terminal,

              COALESCE(ad.asientos_disponibles, a.capacidad) AS asientos_disponibles

            FROM Viaje v
            JOIN Ruta   r  ON r.id_ruta     = v.id_ruta
            JOIN Autobus a ON a.id_autobus  = v.id_autobus
            JOIN ClaseServicio cs ON cs.id_clase = a.id_clase   -- ← NUEVO JOIN
            JOIN Chofer ch  ON ch.id_chofer = v.id_chofer

            -- Origen: menor orden_parada
            JOIN Viaje_Escala ve_o
              ON ve_o.id_viaje = v.id_viaje
             AND ve_o.orden_parada = (
                 SELECT MIN(orden_parada)
                 FROM Viaje_Escala
                 WHERE id_viaje = v.id_viaje
             )
            JOIN Terminal ot   ON ot.id_terminal = ve_o.id_terminal
            JOIN Ciudad  oc    ON oc.id_ciudad   = ot.id_ciudad

            -- Destino: mayor orden_parada
            JOIN Viaje_Escala ve_d
              ON ve_d.id_viaje = v.id_viaje
             AND ve_d.orden_parada = (
                 SELECT MAX(orden_parada)
                 FROM Viaje_Escala
                 WHERE id_viaje = v.id_viaje
             )
            JOIN Terminal dt   ON dt.id_terminal = ve_d.id_terminal
            JOIN Ciudad  dc    ON dc.id_ciudad   = dt.id_ciudad

            -- Asientos disponibles desde la vista
            LEFT JOIN vw_asientos_disponibilidad ad
                   ON ad.id_viaje = v.id_viaje

            WHERE DATE(v.fecha_salida) = CURDATE()
              AND v.estado <> 'Cancelado'
            ORDER BY v.fecha_salida;
        """)

        viajes_hoy = cursor.fetchall()  # lista de diccionarios
        cursor.close()

        viajes_hoy_count = len(viajes_hoy)
        boletos_hoy = kpi['boletos_hoy']
        monto_hoy = float(kpi['monto_hoy'])

    except Exception as e:
        app.logger.error(f"Error cargando /home: {e}")
        flash('Ocurrió un error al cargar la información del día.', 'danger')
        viajes_hoy = []
        viajes_hoy_count = 0
        boletos_hoy = 0
        monto_hoy = 0.0

    # Fecha formateada para el encabezado del dashboard
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    return render_template(
        'home.html',
        user=current_user,
        fecha_hoy=fecha_hoy,
        boletos_hoy=boletos_hoy,
        monto_hoy=f"{monto_hoy:.2f}",
        viajes_hoy=viajes_hoy,
        viajes_hoy_count=viajes_hoy_count
    )


@app.route('/protected')
@login_required
def protected():
    return "<h1>Vista protegida para usuarios autenticados</h1>"

def status_401(error):
    return redirect(url_for('login'))

def status_404(error):
    return "<h1>Pagina no encontarada</h1>", 404

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('Sesión cerrada correctamente.', 'info')
    return redirect(url_for('login'))


# ========== RUTAS DE ADMINISTRACIÓN ==========
@app.route('/admin')
@login_required
@admin_required
def admin():
    users = ModelUser.get_all_users(db)
    return render_template('admin/admin.html', users=users, user=current_user)

@app.route('/admin/create_user', methods=['POST'])
@login_required
@admin_required
def create_user():
    nombre_completo = request.form.get('nombre_completo', '').strip()
    email = request.form.get('email', '').strip()
    password = request.form.get('password', '')
    rol = request.form.get('rol', 'Empleado')
    telefono = request.form.get('telefono_empleado', None)

    if not nombre_completo or not email or not password:
        flash('Nombre, email y contraseña son obligatorios.', 'danger')
        return redirect(url_for('admin'))

    chofer_data = None
    if rol == 'Chofer':
        chofer_data = {
            'rfc': request.form.get('rfc', None),
            'curp': request.form.get('curp', None),
            'nss': request.form.get('nss', None),
            'direccion': request.form.get('direccion', None),
            'fecha_ingreso': request.form.get('fecha_ingreso', None),
            'licencia': request.form.get('licencia', '').strip(),
            'licencia_tipo': request.form.get('licencia_tipo', None),
            'licencia_expira': request.form.get('licencia_expira', None),
            'anios_experiencia': request.form.get('anios_experiencia', 0),
            'notas': request.form.get('notas', None)
        }

    ok = ModelUser.create_user(
        db,
        nombre_completo=nombre_completo,
        email=email,
        password=password,
        rol=rol,
        telefono=telefono,
        chofer_data=chofer_data
    )

    if ok:
        flash(f'Usuario {nombre_completo} creado exitosamente.', 'success')
    else:
        flash('Error al crear el usuario. Revisa los datos e intenta de nuevo.', 'danger')

    return redirect(url_for('admin'))



@app.route('/admin/update_user/<int:id_usuario>', methods=['POST'])
@login_required
@admin_required
def update_user(id_usuario):
    # Datos básicos
    nombre_completo = request.form.get('nombre_completo', '').strip()
    email = request.form.get('email', '').strip()
    rol = request.form.get('rol', 'Empleado')
    activo = int(request.form.get('activo', 1))

    # Teléfono (Empleado)
    telefono_empleado = request.form.get('telefono_empleado', '').strip() or None

    if not nombre_completo or not email:
        flash('Nombre y email son obligatorios.', 'danger')
        return redirect(url_for('admin'))

    # Si el rol es Chofer, recogemos los campos extra
    chofer_data = None
    if rol == 'Chofer':
        chofer_data = {
            'rfc':               request.form.get('rfc', '').strip() or None,
            'curp':              request.form.get('curp', '').strip() or None,
            'nss':               request.form.get('nss', '').strip() or None,
            'direccion':         request.form.get('direccion', '').strip() or None,
            'fecha_ingreso':     request.form.get('fecha_ingreso') or None,
            'licencia':          request.form.get('licencia', '').strip() or None,
            'licencia_tipo':     request.form.get('licencia_tipo', '').strip() or None,
            'licencia_expira':   request.form.get('licencia_expira') or None,
            'anios_experiencia': request.form.get('anios_experiencia', '').strip() or 0,
            'notas':             request.form.get('notas', '').strip() or None
        }

        # Normalizar años de experiencia a int
        try:
            chofer_data['anios_experiencia'] = int(chofer_data['anios_experiencia'])
        except (ValueError, TypeError):
            chofer_data['anios_experiencia'] = 0

    # Llamamos al modelo para hacer el UPDATE en cascada
    ok = ModelUser.update_user_full(
        db,
        id_usuario=id_usuario,
        nombre_completo=nombre_completo,
        email=email,
        rol=rol,
        activo=activo,
        telefono_empleado=telefono_empleado,
        chofer_data=chofer_data
    )

    if ok:
        flash('Usuario actualizado correctamente.', 'success')
    else:
        flash('Error al actualizar el usuario.', 'danger')

    return redirect(url_for('admin'))


@app.route('/admin/toggle_user/<int:id_usuario>', methods=['POST'])
@login_required
@admin_required
def toggle_user(id_usuario):
    if ModelUser.toggle_user_status(db, id_usuario):
        flash('Estado del usuario actualizado.', 'success')
    else:
        flash('Error al cambiar el estado del usuario.', 'danger')
    
    return redirect(url_for('admin'))

@app.route('/admin/change_password/<int:id_usuario>', methods=['POST'])
@login_required
@admin_required
def change_password(id_usuario):
    new_password = request.form.get('new_password', '')
    
    if not new_password or len(new_password) < 6:
        flash('La contraseña debe tener al menos 6 caracteres.', 'danger')
        return redirect(url_for('admin'))
    
    if ModelUser.change_password(db, id_usuario, new_password):
        flash('Contraseña actualizada exitosamente.', 'success')
    else:
        flash('Error al cambiar la contraseña.', 'danger')
    
    return redirect(url_for('admin'))


# ========== RUTAS DEL CHOFER ==========
@app.route('/chofer')
@login_required
def chofer():
    if current_user.rol != 'Chofer':
        flash('Acceso denegado. Esta sección es solo para choferes.', 'danger')
        return redirect(url_for('home'))

    try:
        cursor = db.connection.cursor(MySQLdb.cursors.DictCursor)

        # 1) Obtener el id_chofer real a partir del usuario logueado
        cursor.execute("""
            SELECT ch.id_chofer
            FROM Usuario u
            JOIN Empleado e ON e.id_empleado = u.id_empleado
            JOIN Chofer  ch ON ch.id_empleado = e.id_empleado
            WHERE u.id_usuario = %s
        """, (current_user.id_usuario,))
        row = cursor.fetchone()

        if not row:
            flash('No se encontró un chofer asociado a este usuario.', 'danger')
            cursor.close()
            return redirect(url_for('home'))

        id_chofer = row['id_chofer']

        # 2) Viajes programados / en ruta para este chofer
        cursor.execute("""
            SELECT 
                v.id_viaje,
                DATE_FORMAT(v.fecha_salida, '%%d/%%m/%%Y') AS fecha,
                DATE_FORMAT(v.fecha_salida, '%%H:%%i')     AS hora,
                t_origen.nombre  AS origen,
                t_destino.nombre AS destino,
                CONCAT_WS(' ', a.numero_placa, a.numero_fisico) AS bus,

                (
                  SELECT COUNT(*)
                  FROM Boleto b
                  WHERE b.id_viaje = v.id_viaje
                    AND b.estado IN ('Pagado','Reservado','Abordado')
                ) AS pasajeros,

                a.capacidad,

                CASE 
                  WHEN v.estado = 'Programado' THEN 'Pendiente'
                  WHEN v.estado = 'EnRuta'     THEN 'En Curso'
                  WHEN v.estado = 'Finalizado' THEN 'Completado'
                  ELSE v.estado
                END AS estado_mostrar

            FROM Viaje v
            JOIN Ruta r ON v.id_ruta = r.id_ruta

            -- ORIGEN (primer terminal de la ruta)
            JOIN Ruta_Terminal rt_o
              ON rt_o.id_ruta = r.id_ruta
             AND rt_o.orden_parada = 1
            JOIN Terminal t_origen ON t_origen.id_terminal = rt_o.id_terminal

            -- DESTINO (último terminal de la ruta)
            JOIN Ruta_Terminal rt_d
              ON rt_d.id_ruta = r.id_ruta
             AND rt_d.orden_parada = (
                 SELECT MAX(orden_parada)
                 FROM Ruta_Terminal
                 WHERE id_ruta = r.id_ruta
              )
            JOIN Terminal t_destino ON t_destino.id_terminal = rt_d.id_terminal

            JOIN Autobus a ON a.id_autobus = v.id_autobus

            WHERE v.id_chofer = %s
              AND v.estado IN ('Programado','EnRuta')
            ORDER BY v.fecha_salida ASC;
        """, (id_chofer,))
        rows_viajes = cursor.fetchall()

        viajes_programados = []
        for row in rows_viajes:
            viajes_programados.append({
                'id_viaje':  row['id_viaje'],
                'fecha':     row['fecha'],
                'hora':      row['hora'],
                'origen':    row['origen'],
                'destino':   row['destino'],
                'bus':       row['bus'],
                'pasajeros': row['pasajeros'] or 0,
                'capacidad': row['capacidad'] or 0,
                'estado':    row['estado_mostrar']
            })

        # 3) Historial de viajes finalizados (últimos 10)
        cursor.execute("""
            SELECT 
                DATE_FORMAT(v.fecha_salida, '%%d/%%m/%%Y') AS fecha,
                t_origen.nombre  AS origen,
                t_destino.nombre AS destino
            FROM Viaje v
            JOIN Ruta r ON v.id_ruta = r.id_ruta

            JOIN Ruta_Terminal rt_o
              ON rt_o.id_ruta = r.id_ruta
             AND rt_o.orden_parada = 1
            JOIN Terminal t_origen ON t_origen.id_terminal = rt_o.id_terminal

            JOIN Ruta_Terminal rt_d
              ON rt_d.id_ruta = r.id_ruta
             AND rt_d.orden_parada = (
                 SELECT MAX(orden_parada)
                 FROM Ruta_Terminal
                 WHERE id_ruta = r.id_ruta
              )
            JOIN Terminal t_destino ON t_destino.id_terminal = rt_d.id_terminal

            WHERE v.id_chofer = %s
              AND v.estado = 'Finalizado'
            ORDER BY v.fecha_salida DESC
            LIMIT 10;
        """, (id_chofer,))
        rows_hist = cursor.fetchall()

        historial_viajes = [
            {
                'fecha':   r['fecha'],
                'origen':  r['origen'],
                'destino': r['destino']
            }
            for r in rows_hist
        ]

        # 4) Viajes completados hoy
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM Viaje
            WHERE id_chofer = %s
              AND DATE(fecha_salida) = CURDATE()
              AND estado = 'Finalizado';
        """, (id_chofer,))
        row_cnt = cursor.fetchone()
        viajes_completados_hoy = row_cnt['total'] if row_cnt else 0

        cursor.close()

        # 5) Próximo viaje y pendientes (para las cards del template)
        proximo = viajes_programados[0] if viajes_programados else None
        viajes_pendientes_count = len([v for v in viajes_programados if v['estado'] == 'Pendiente'])

    except Exception as ex:
        app.logger.error(f"Error en ruta /chofer: {ex}")
        viajes_programados = []
        historial_viajes = []
        viajes_completados_hoy = 0
        viajes_pendientes_count = 0
        proximo = None

    fecha_actual = datetime.now().strftime('%d/%m/%Y')

    return render_template(
        'chofer/chofer.html',
        user=current_user,
        viajes=viajes_programados,
        viajes_hoy=viajes_completados_hoy,
        viajes_pendientes=viajes_pendientes_count,
        proximo_viaje=proximo,
        historial=historial_viajes,
        fecha_hoy=fecha_actual
    )


@app.route('/api/viajes/<int:id_viaje>/asientos', methods=['GET'])
@login_required
def api_asientos_viaje(id_viaje):
    """
    Devuelve en JSON los asientos disponibles para un viaje dado.
    Solo accesible para Admin y Empleado (taquilla).
    """
    if current_user.rol not in ('Admin', 'Empleado'):
        # 403 semántico, pero devolvemos JSON sencillo
        return jsonify({'error': 'No autorizado'}), 403

    try:
        cursor = db.connection.cursor(MySQLdb.cursors.DictCursor)

        # 1) Obtener capacidad del autobús para ese viaje
        sql_cap = """
            SELECT a.capacidad
            FROM Viaje v
            JOIN Autobus a ON a.id_autobus = v.id_autobus
            WHERE v.id_viaje = %s
            LIMIT 1;
        """
        cursor.execute(sql_cap, (id_viaje,))
        row_cap = cursor.fetchone()

        if not row_cap:
            cursor.close()
            return jsonify({'error': 'Viaje no encontrado'}), 404

        capacidad = row_cap['capacidad']

        # 2) Obtener asientos ya ocupados (Reservado, Pagado, Abordado)
        sql_ocupados = """
            SELECT numero_asiento
            FROM Boleto
            WHERE id_viaje = %s
              AND estado IN ('Reservado','Pagado','Abordado');
        """
        cursor.execute(sql_ocupados, (id_viaje,))
        rows_oc = cursor.fetchall()
        cursor.close()

        ocupados = {r['numero_asiento'] for r in rows_oc}

        # 3) Construir lista de asientos libres
        asientos_libres = [n for n in range(1, capacidad + 1) if n not in ocupados]

        return jsonify({
            'id_viaje': id_viaje,
            'capacidad': capacidad,
            'ocupados': sorted(list(ocupados)),
            'asientos_libres': asientos_libres
        })

    except Exception as e:
        app.logger.error(f"Error en /api/viajes/{id_viaje}/asientos: {e}")
        return jsonify({'error': 'Error interno al calcular asientos'}), 500


@app.route('/ventas/confirmacion/<int:id_boleto>')
@login_required
def confirmacion_venta(id_boleto):
    """
    Muestra la información detallada de un boleto recién comprado.
    """
    if current_user.rol not in ('Admin', 'Empleado'):
        flash('No tienes permiso para ver esta venta.', 'danger')
        return redirect(url_for('home'))

    try:
        cursor = db.connection.cursor(MySQLdb.cursors.DictCursor)

        sql = """
        SELECT
            b.id_boleto,
            b.numero_asiento,
            b.precio_total,
            DATE_FORMAT(b.creado_en, '%%Y-%%m-%%d %%H:%%i') AS fecha_emision,

            p.nombre AS pasajero_nombre,
            p.correo AS pasajero_correo,
            p.telefono AS pasajero_telefono,

            v.id_viaje,
            DATE_FORMAT(v.fecha_salida, '%%Y-%%m-%%d %%H:%%i') AS salida,
            DATE_FORMAT(v.fecha_llegada, '%%Y-%%m-%%d %%H:%%i') AS llegada,

            oc.nombre AS origen_ciudad,
            ot.nombre AS origen_terminal,

            dc.nombre AS destino_ciudad,
            dt.nombre AS destino_terminal,

            a.numero_placa,
            a.numero_fisico,
            CONCAT_WS(' ', a.numero_placa, a.numero_fisico) AS autobus_identificador,
            cs.nombre AS clase_nombre

        FROM Boleto b
        JOIN Pasajero p ON p.id_pasajero = b.id_pasajero
        JOIN Viaje v ON v.id_viaje = b.id_viaje
        JOIN Autobus a ON a.id_autobus = v.id_autobus
        LEFT JOIN ClaseServicio cs ON cs.id_clase = a.id_clase

        JOIN Viaje_Escala ve_o
               ON ve_o.id_viaje = v.id_viaje
              AND ve_o.orden_parada = (
                  SELECT MIN(orden_parada)
                  FROM Viaje_Escala
                  WHERE id_viaje = v.id_viaje
              )
        JOIN Terminal ot ON ot.id_terminal = ve_o.id_terminal
        JOIN Ciudad oc ON oc.id_ciudad = ot.id_ciudad

        JOIN Viaje_Escala ve_d
               ON ve_d.id_viaje = v.id_viaje
              AND ve_d.orden_parada = (
                  SELECT MAX(orden_parada)
                  FROM Viaje_Escala
                  WHERE id_viaje = v.id_viaje
              )
        JOIN Terminal dt ON dt.id_terminal = ve_d.id_terminal
        JOIN Ciudad dc ON dc.id_ciudad = dt.id_ciudad

        WHERE b.id_boleto = %s;
        """

        cursor.execute(sql, (id_boleto,))
        boleto = cursor.fetchone()
        cursor.close()

        if not boleto:
            flash("El boleto solicitado no existe.", "danger")
            return redirect(url_for('home'))

        return render_template(
            "confirmacion_venta.html",
            boleto=boleto,
            fecha_hoy=datetime.now().strftime("%d/%m/%Y"),
            user=current_user
        )

    except Exception as e:
        print("ERROR confirmacion_venta:", e)
        flash("No se pudo cargar la información del boleto.", "danger")
        return redirect(url_for('home'))


@app.route('/ventas/nueva', methods=['GET', 'POST'])
@login_required
def nueva_venta():
    # Solo Admin y Empleado pueden usar taquilla
    if current_user.rol not in ('Admin', 'Empleado'):
        flash('Esta sección es solo para personal de taquilla o administradores.', 'danger')
        return redirect(url_for('home'))

    # ================== GET: mostrar formulario ==================
    if request.method == 'GET':
        try:
            cursor = db.connection.cursor(MySQLdb.cursors.DictCursor)

            sql = """
                SELECT 
                    v.id_viaje,
                    DATE_FORMAT(v.fecha_salida, '%d/%m/%Y %H:%i') AS salida_label,

                    -- ORIGEN (primera parada)
                    oc.nombre AS origen,

                    -- DESTINO (última parada)
                    dc.nombre AS destino,

                    -- Autobús y clase
                    CONCAT_WS(' ', a.numero_placa, a.numero_fisico) AS autobus,
                    cs.nombre AS clase_nombre

                FROM Viaje v
                JOIN Ruta   r  ON r.id_ruta    = v.id_ruta
                JOIN Autobus a ON a.id_autobus = v.id_autobus
                LEFT JOIN ClaseServicio cs ON cs.id_clase = a.id_clase

                -- ORIGEN: menor orden_parada
                JOIN Viaje_Escala ve_o
                       ON ve_o.id_viaje = v.id_viaje
                      AND ve_o.orden_parada = (
                          SELECT MIN(orden_parada)
                          FROM Viaje_Escala
                          WHERE id_viaje = v.id_viaje
                      )
                JOIN Terminal ot ON ot.id_terminal = ve_o.id_terminal
                JOIN Ciudad  oc  ON oc.id_ciudad   = ot.id_ciudad

                -- DESTINO: mayor orden_parada
                JOIN Viaje_Escala ve_d
                       ON ve_d.id_viaje = v.id_viaje
                      AND ve_d.orden_parada = (
                          SELECT MAX(orden_parada)
                          FROM Viaje_Escala
                          WHERE id_viaje = v.id_viaje
                      )
                JOIN Terminal dt ON dt.id_terminal = ve_d.id_terminal
                JOIN Ciudad  dc  ON dc.id_ciudad   = dt.id_ciudad

                WHERE DATE(v.fecha_salida) = CURDATE()
                  AND v.estado <> 'Cancelado'
                ORDER BY v.fecha_salida ASC;
            """

            cursor.execute(sql)
            rows = cursor.fetchall()
            cursor.close()

            viajes = []
            for row in rows:
                viajes.append({
                    'id_viaje': row['id_viaje'],
                    'salida_label': row['salida_label'],   # ya viene bonito: 19/11/2025 08:30
                    'origen': row['origen'],
                    'destino': row['destino'],
                    'autobus': row['autobus'],
                    'clase_nombre': row.get('clase_nombre')
                })

        except Exception as e:
            app.logger.error(f"Error cargando /ventas/nueva (GET): {e}")
            flash('Ocurrió un error al cargar los viajes disponibles.', 'danger')
            viajes = []

        fecha_hoy = datetime.now().strftime("%d/%m/%Y")
        return render_template(
            'nueva_venta.html',
            user=current_user,
            fecha_hoy=fecha_hoy,
            viajes=viajes
        )

    # ================== POST: registrar venta ==================
    try:
        # 1) Datos del formulario
        nombre_pasajero   = request.form.get('nombre_pasajero', '').strip()
        correo_pasajero   = request.form.get('correo_pasajero', '').strip() or None
        telefono_pasajero = request.form.get('telefono_pasajero', '').strip() or None
        metodo_pago       = request.form.get('metodo_pago', '')
        id_viaje          = request.form.get('id_viaje', '')
        numero_asiento    = request.form.get('numero_asiento', '')

        if not nombre_pasajero or not id_viaje or not numero_asiento or not metodo_pago:
            flash('Faltan datos obligatorios para registrar la venta.', 'danger')
            return redirect(url_for('nueva_venta'))

        id_viaje = int(id_viaje)
        numero_asiento = int(numero_asiento)

        # 2) Simulación de pago con tarjeta (solo log en consola)
        if metodo_pago == 'Tarjeta':
            tarjeta_numero = request.form.get('tarjeta_numero', '')
            tarjeta_nombre = request.form.get('tarjeta_nombre', '')
            tarjeta_expira = request.form.get('tarjeta_expira', '')
            tarjeta_cvv    = request.form.get('tarjeta_cvv', '')

            pago_payload = {
                "monto": 0,  # se actualiza después
                "pasajero": nombre_pasajero,
                "asiento": numero_asiento,
                "id_viaje": id_viaje,
                "tarjeta": {
                    "numero": tarjeta_numero[-4:],  # solo últimos 4
                    "nombre": tarjeta_nombre,
                    "expira": tarjeta_expira,
                }
            }
            print("=== PAGO TARJETA (SIMULACIÓN) ===")
            print(pago_payload)
            print("===================================")

        cursor = db.connection.cursor()

        # 3) Buscar o crear PASAJERO
        id_pasajero = None
        if correo_pasajero:
            cursor.execute("""
                SELECT id_pasajero 
                FROM Pasajero 
                WHERE correo = %s 
                LIMIT 1
            """, (correo_pasajero,))
            row = cursor.fetchone()
            if row:
                id_pasajero = row[0]

        if not id_pasajero:
            cursor.execute("""
                INSERT INTO Pasajero (nombre, correo, telefono)
                VALUES (%s, %s, %s)
            """, (nombre_pasajero, correo_pasajero, telefono_pasajero))
            id_pasajero = cursor.lastrowid

        # 4) Calcular monto del boleto (lógico provisional)
        precio_base = 600.00
        impuesto = round(precio_base * 0.05, 2)
        precio_total = precio_base + impuesto

        if metodo_pago == 'Tarjeta':
            pago_payload["monto"] = float(precio_total)
            print("=== PAGO TARJETA (SIMULACIÓN) ===")
            print(pago_payload)
            print("===================================")

        # 5) Insertar BOLETO primero (porque Venta referencia a Boleto)
        cursor.execute("""
            INSERT INTO Boleto (id_viaje, id_pasajero, numero_asiento, estado, precio_total)
            VALUES (%s, %s, %s, 'Pagado', %s)
        """, (id_viaje, id_pasajero, numero_asiento, precio_total))
        id_boleto = cursor.lastrowid

        # 6) Obtener id_empleado del usuario actual (si existe)
        cursor.execute("""
            SELECT id_empleado
            FROM Usuario
            WHERE id_usuario = %s
        """, (current_user.id_usuario,))
        row_emp = cursor.fetchone()
        id_empleado = row_emp[0] if row_emp and row_emp[0] is not None else None

        # 7) Insertar VENTA (nota: NO va id_viaje, va id_boleto)
        cursor.execute("""
            INSERT INTO Venta (id_boleto, id_empleado, id_cliente, metodo_pago, monto, nota)
            VALUES (%s, %s, NULL, %s, %s, %s)
        """, (
            id_boleto,
            id_empleado,
            metodo_pago,
            precio_total,
            'Venta registrada desde módulo de taquilla'
        ))
        id_venta = cursor.lastrowid

        # 8) NO insertes Venta_Detalle aquí: el trigger tr_venta_snapshot lo hace AUTOMÁTICAMENTE

        db.connection.commit()
        cursor.close()

        flash('Venta registrada correctamente.', 'success')
        return redirect(url_for('confirmacion_venta', id_boleto=id_boleto))

    except Exception as e:
        db.connection.rollback()
        app.logger.error(f"Error registrando venta /ventas/nueva (POST): {e}")
        flash('Ocurrió un error al registrar la venta. Intente de nuevo.', 'danger')
        return redirect(url_for('nueva_venta'))


@app.route('/admin/ventas_hoy')
@login_required
@admin_required
def ventas_hoy():
    """
    Reporte de ventas del día, agrupadas por empleado (taquilla).
    Solo visible para Admin.
    """
    try:
        cursor = db.connection.cursor(MySQLdb.cursors.DictCursor)

        # Ventas del día actual agrupadas por empleado
        sql = """
            SELECT 
                e.id_empleado,
                e.nombre AS empleado_nombre,

                COUNT(v.id_venta)                       AS num_ventas,
                COALESCE(SUM(v.monto), 0)              AS total_ventas,

                -- Desglose por método de pago
                COALESCE(SUM(CASE WHEN v.metodo_pago = 'Efectivo'     THEN v.monto ELSE 0 END), 0) AS total_efectivo,
                COALESCE(SUM(CASE WHEN v.metodo_pago = 'Tarjeta'      THEN v.monto ELSE 0 END), 0) AS total_tarjeta,
                COALESCE(SUM(CASE WHEN v.metodo_pago = 'Transferencia' THEN v.monto ELSE 0 END), 0) AS total_transferencia

            FROM Venta v
            LEFT JOIN Empleado e ON e.id_empleado = v.id_empleado

            WHERE DATE(v.fecha_venta) = CURDATE()
            GROUP BY e.id_empleado, e.nombre
            ORDER BY total_ventas DESC, empleado_nombre;
        """

        cursor.execute(sql)
        resumen = cursor.fetchall()
        cursor.close()

        # Totales generales del día
        total_general = sum(f['total_ventas'] for f in resumen) if resumen else 0
        total_boletos = sum(f['num_ventas'] for f in resumen) if resumen else 0

    except Exception as e:
        app.logger.error(f"Error en /admin/ventas_hoy: {e}")
        flash("Ocurrió un error al cargar el reporte de ventas del día.", "danger")
        resumen = []
        total_general = 0
        total_boletos = 0

    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    return render_template(
        'ventas_hoy.html',
        user=current_user,
        fecha_hoy=fecha_hoy,
        resumen=resumen,
        total_general=total_general,
        total_boletos=total_boletos
    )


@app.route('/viajes/proximos')
@login_required
def viajes_proximos():
    """
    Vista rápida con todos los viajes próximos (de todos los choferes),
    ordenados por fecha de salida.
    Solo para Admin y Empleado (taquilla).
    """
    if current_user.rol not in ('Admin', 'Empleado'):
        flash('Acceso denegado. Solo el personal de taquilla o administradores pueden ver esta sección.', 'danger')
        return redirect(url_for('home'))

    try:
        cursor = db.connection.cursor(MySQLdb.cursors.DictCursor)

        sql = """
            SELECT
                v.id_viaje,
                DATE_FORMAT(v.fecha_salida, '%d/%m/%Y %H:%i') AS fecha_salida,
                DATE_FORMAT(v.fecha_llegada, '%d/%m/%Y %H:%i') AS fecha_llegada,

                r.nombre AS ruta_nombre,

                -- ORIGEN
                oc.nombre AS origen_ciudad,
                ot.nombre AS origen_terminal,

                -- DESTINO
                dc.nombre AS destino_ciudad,
                dt.nombre AS destino_terminal,

                -- AUTOBÚS Y CLASE
                CONCAT_WS(' ', a.numero_placa, a.numero_fisico) AS autobus_identificador,
                cs.nombre AS clase_nombre,

                -- CHOFER
                ch.nombre AS chofer_nombre,

                v.estado,
                COALESCE(ad.asientos_disponibles, a.capacidad) AS asientos_disponibles

            FROM Viaje v
            JOIN Ruta   r  ON r.id_ruta    = v.id_ruta
            JOIN Autobus a ON a.id_autobus = v.id_autobus
            LEFT JOIN ClaseServicio cs ON cs.id_clase = a.id_clase
            JOIN Chofer ch  ON ch.id_chofer = v.id_chofer

            -- ORIGEN: mínima orden_parada
            JOIN Viaje_Escala ve_o
                   ON ve_o.id_viaje = v.id_viaje
                  AND ve_o.orden_parada = (
                      SELECT MIN(orden_parada)
                      FROM Viaje_Escala
                      WHERE id_viaje = v.id_viaje
                  )
            JOIN Terminal ot ON ot.id_terminal = ve_o.id_terminal
            JOIN Ciudad  oc  ON oc.id_ciudad   = ot.id_ciudad

            -- DESTINO: máxima orden_parada
            JOIN Viaje_Escala ve_d
                   ON ve_d.id_viaje = v.id_viaje
                  AND ve_d.orden_parada = (
                      SELECT MAX(orden_parada)
                      FROM Viaje_Escala
                      WHERE id_viaje = v.id_viaje
                  )
            JOIN Terminal dt ON dt.id_terminal = ve_d.id_terminal
            JOIN Ciudad  dc  ON dc.id_ciudad   = dt.id_ciudad

            -- Asientos disponibles (vista)
            LEFT JOIN vw_asientos_disponibilidad ad
                   ON ad.id_viaje = v.id_viaje

            WHERE v.fecha_salida >= NOW()
              AND v.estado <> 'Cancelado'
            ORDER BY v.fecha_salida ASC;
        """

        cursor.execute(sql)
        viajes = cursor.fetchall()
        cursor.close()

    except Exception as e:
        app.logger.error(f"Error cargando /viajes/proximos: {e}")
        flash('Ocurrió un error al cargar los viajes próximos.', 'danger')
        viajes = []

    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    return render_template(
        'viajes_proximos.html',
        user=current_user,
        fecha_hoy=fecha_hoy,
        viajes=viajes
    )



if __name__ == '__main__':
    app.register_error_handler(401, status_401)
    app.register_error_handler(404, status_404)
    app.run(debug=True)
