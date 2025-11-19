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

    from datetime import datetime, date

    try:
        cursor = db.connection.cursor()
        
        # Obtener viajes programados del chofer actual (pendientes y en curso)
        sql_viajes = """
            SELECT 
                v.id_viaje,
                DATE_FORMAT(v.fecha_salida, '%d/%m/%Y') as fecha,
                DATE_FORMAT(v.fecha_salida, '%H:%i') as hora,
                t_origen.nombre as origen,
                t_destino.nombre as destino,
                a.identificador as bus,
                (SELECT COUNT(*) FROM Boleto b WHERE b.id_viaje = v.id_viaje AND b.estado = 'Activo') as pasajeros,
                a.capacidad,
                v.estado
            FROM Viaje v
            INNER JOIN Ruta r ON v.id_ruta = r.id_ruta
            INNER JOIN Ruta_Terminal rt_origen ON r.id_ruta = rt_origen.id_ruta AND rt_origen.orden_parada = 1
            INNER JOIN Ruta_Terminal rt_destino ON r.id_ruta = rt_destino.id_ruta 
                AND rt_destino.orden_parada = (SELECT MAX(orden_parada) FROM Ruta_Terminal WHERE id_ruta = r.id_ruta)
            INNER JOIN Terminal t_origen ON rt_origen.id_terminal = t_origen.id_terminal
            INNER JOIN Terminal t_destino ON rt_destino.id_terminal = t_destino.id_terminal
            INNER JOIN Autobus a ON v.id_autobus = a.id_autobus
            WHERE v.id_chofer = %s
            AND v.estado IN ('Programado', 'En Curso')
            ORDER BY v.fecha_salida ASC
        """
        cursor.execute(sql_viajes, (current_user.id_usuario,))
        rows_viajes = cursor.fetchall()
        
        viajes_programados = []
        for row in rows_viajes:
            viajes_programados.append({
                'id_viaje': row[0],
                'fecha': row[1],
                'hora': row[2],
                'origen': row[3],
                'destino': row[4],
                'bus': row[5],
                'pasajeros': row[6] or 0,
                'capacidad': row[7] or 0,
                'estado': row[8]
            })
        
        # Obtener historial de viajes completados (últimos 10)
        sql_historial = """
            SELECT 
                DATE_FORMAT(v.fecha_salida, '%d/%m/%Y') as fecha,
                t_origen.nombre as origen,
                t_destino.nombre as destino
            FROM Viaje v
            INNER JOIN Ruta r ON v.id_ruta = r.id_ruta
            INNER JOIN Ruta_Terminal rt_origen ON r.id_ruta = rt_origen.id_ruta AND rt_origen.orden_parada = 1
            INNER JOIN Ruta_Terminal rt_destino ON r.id_ruta = rt_destino.id_ruta 
                AND rt_destino.orden_parada = (SELECT MAX(orden_parada) FROM Ruta_Terminal WHERE id_ruta = r.id_ruta)
            INNER JOIN Terminal t_origen ON rt_origen.id_terminal = t_origen.id_terminal
            INNER JOIN Terminal t_destino ON rt_destino.id_terminal = t_destino.id_terminal
            WHERE v.id_chofer = %s
            AND v.estado = 'Completado'
            ORDER BY v.fecha_salida DESC
            LIMIT 10
        """
        cursor.execute(sql_historial, (current_user.id_usuario,))
        rows_historial = cursor.fetchall()
        
        historial_viajes = []
        for row in rows_historial:
            historial_viajes.append({
                'fecha': row[0],
                'origen': row[1],
                'destino': row[2]
            })
        
        # Contar viajes completados hoy
        sql_hoy = """
            SELECT COUNT(*) 
            FROM Viaje 
            WHERE id_chofer = %s 
            AND DATE(fecha_salida) = CURDATE() 
            AND estado = 'Completado'
        """
        cursor.execute(sql_hoy, (current_user.id_usuario,))
        viajes_completados_hoy = cursor.fetchone()[0] or 0
        
        # Próximo viaje es el primero de la lista
        proximo = viajes_programados[0] if viajes_programados else None
        
        # Contar viajes pendientes
        viajes_pendientes_count = len([v for v in viajes_programados if v['estado'] == 'Programado'])
        
        cursor.close()
        
    except Exception as ex:
        app.logger.error(f"Error en ruta /chofer: {ex}")
        viajes_programados = []
        historial_viajes = []
        viajes_completados_hoy = 0
        viajes_pendientes_count = 0
        proximo = None

    fecha_actual = datetime.now().strftime('%d/%m/%Y')

    return render_template('chofer/chofer.html', 
                            user=current_user,
                            viajes=viajes_programados,
                            viajes_hoy=viajes_completados_hoy,
                            viajes_pendientes=viajes_pendientes_count,
                            proximo_viaje=proximo,
                            historial=historial_viajes,
                            fecha_hoy=fecha_actual)

@app.route('/ventas/nueva', methods=['GET', 'POST'])
@login_required
def nueva_venta():
    # Restringimos a Empleado / Admin
    if current_user.rol not in ('Empleado', 'Admin'):
        flash('Acceso restringido a personal de taquilla y administradores.', 'danger')
        return redirect(url_for('home'))

    if request.method == 'POST':
        # Aquí después implementaremos:
        # 1) Validar datos del pasajero
        # 2) Validar viaje y asiento
        # 3) Crear pasajero (si aplica)
        # 4) Insertar boleto + venta
        flash('Funcionalidad de registro de venta aún en desarrollo.', 'info')
        return redirect(url_for('nueva_venta'))

    # Por ahora, solo armamos el contexto básico para la vista
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    # TODO: más adelante rellenaremos esto con un SELECT real de viajes
    viajes_disponibles = []  # lista de diccionarios con viajes

    return render_template(
        'nueva_venta.html',
        user=current_user,
        fecha_hoy=fecha_hoy,
        viajes=viajes_disponibles
    )


if __name__ == '__main__':
    app.register_error_handler(401, status_401)
    app.register_error_handler(404, status_404)
    app.run(debug=True)
