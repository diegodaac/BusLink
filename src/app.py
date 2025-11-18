from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_mysqldb import MySQL
from flask_wtf import CSRFProtect
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from functools import wraps
from config import config
from Models.ModelUser import ModelUser
from Models.entities.User import User

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
    return render_template('home.html', user=current_user)

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
    
    if not nombre_completo or not email or not password:
        flash('Todos los campos son obligatorios.', 'danger')
        return redirect(url_for('admin'))
    
    if ModelUser.create_user(db, nombre_completo, email, password, rol):
        flash(f'Usuario {nombre_completo} creado exitosamente.', 'success')
    else:
        flash('Error al crear el usuario. Verifique que el email no esté duplicado.', 'danger')
    
    return redirect(url_for('admin'))

@app.route('/admin/update_user/<int:id_usuario>', methods=['POST'])
@login_required
@admin_required
def update_user(id_usuario):
    nombre_completo = request.form.get('nombre_completo', '').strip()
    email = request.form.get('email', '').strip()
    rol = request.form.get('rol', 'Empleado')
    activo = int(request.form.get('activo', 1))
    
    if not nombre_completo or not email:
        flash('Nombre y email son obligatorios.', 'danger')
        return redirect(url_for('admin'))
    
    if ModelUser.update_user(db, id_usuario, nombre_completo, email, rol, activo):
        flash('Usuario actualizado exitosamente.', 'success')
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


if __name__ == '__main__':
    app.register_error_handler(401, status_401)
    app.register_error_handler(404, status_404)
    app.run(debug=True)
