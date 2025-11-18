from .entities.User import User
from werkzeug.security import generate_password_hash

class ModelUser():
    @classmethod
    def login(cls, db, user):
        try:
            cursor = db.connection.cursor()
            sql = "SELECT id_usuario, nombre_completo, email, password_hash, rol, activo FROM Usuario WHERE email = %s"
            cursor.execute(sql, (user.email,))
            row = cursor.fetchone()
            if row:
                user_data = User(*row[:5])  # mapea columnas principales
                if User.check_password(row[3], user.password) and row[5] == 1:
                    return user_data
            return None
        except Exception as ex:
            print("ERROR ModelUser.login:", ex)
            return None

    @classmethod
    def get_by_id(cls, db, id):
        try:
            cursor = db.connection.cursor()
            sql = "SELECT id_usuario, nombre_completo, email, password_hash, rol, activo FROM Usuario WHERE id_usuario = %s"
            cursor.execute(sql, (id,))
            row = cursor.fetchone()
            if row:
                return User(*row[:5])
            return None
        except Exception as ex:
            print("ERROR ModelUser.get_by_id:", ex)
            return None

    @classmethod
    def get_all_users(cls, db):
        """Obtener todos los usuarios del sistema"""
        try:
            cursor = db.connection.cursor()
            sql = "SELECT id_usuario, nombre_completo, email, rol, activo FROM Usuario ORDER BY nombre_completo"
            cursor.execute(sql)
            rows = cursor.fetchall()
            users = []
            for row in rows:
                user = {
                    'id_usuario': row[0],
                    'nombre_completo': row[1],
                    'email': row[2],
                    'rol': row[3],
                    'activo': row[4]
                }
                users.append(user)
            return users
        except Exception as ex:
            print("ERROR ModelUser.get_all_users:", ex)
            return []

    @classmethod
    def create_user(cls, db, nombre_completo, email, password, rol='Empleado'):
        """Crear un nuevo usuario"""
        try:
            cursor = db.connection.cursor()
            password_hash = generate_password_hash(password)
            sql = "INSERT INTO Usuario (nombre_completo, email, password_hash, rol, activo) VALUES (%s, %s, %s, %s, 1)"
            cursor.execute(sql, (nombre_completo, email, password_hash, rol))
            db.connection.commit()
            return True
        except Exception as ex:
            print("ERROR ModelUser.create_user:", ex)
            db.connection.rollback()
            return False

    @classmethod
    def update_user(cls, db, id_usuario, nombre_completo, email, rol, activo):
        """Actualizar información de un usuario"""
        try:
            cursor = db.connection.cursor()
            sql = "UPDATE Usuario SET nombre_completo = %s, email = %s, rol = %s, activo = %s WHERE id_usuario = %s"
            cursor.execute(sql, (nombre_completo, email, rol, activo, id_usuario))
            db.connection.commit()
            return True
        except Exception as ex:
            print("ERROR ModelUser.update_user:", ex)
            db.connection.rollback()
            return False

    @classmethod
    def toggle_user_status(cls, db, id_usuario):
        """Activar/Desactivar un usuario"""
        try:
            cursor = db.connection.cursor()
            sql = "UPDATE Usuario SET activo = NOT activo WHERE id_usuario = %s"
            cursor.execute(sql, (id_usuario,))
            db.connection.commit()
            return True
        except Exception as ex:
            print("ERROR ModelUser.toggle_user_status:", ex)
            db.connection.rollback()
            return False

    @classmethod
    def change_password(cls, db, id_usuario, new_password):
        """Cambiar la contraseña de un usuario"""
        try:
            cursor = db.connection.cursor()
            password_hash = generate_password_hash(new_password)
            sql = "UPDATE Usuario SET password_hash = %s WHERE id_usuario = %s"
            cursor.execute(sql, (password_hash, id_usuario))
            db.connection.commit()
            return True
        except Exception as ex:
            print("ERROR ModelUser.change_password:", ex)
            db.connection.rollback()
            return False
