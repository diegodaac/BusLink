from .entities.User import User
from werkzeug.security import generate_password_hash

class ModelUser:

    @classmethod
    def login(cls, db, user):
        try:
            cursor = db.connection.cursor()
            sql = """
                SELECT id_usuario, nombre_completo, email, password_hash, rol, activo
                FROM Usuario
                WHERE email = %s
            """
            cursor.execute(sql, (user.email,))
            row = cursor.fetchone()
            if row:
                user_data = User(*row[:5])  # id_usuario, nombre_completo, email, password_hash, rol
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
            sql = """
                SELECT id_usuario, nombre_completo, email, password_hash, rol, activo
                FROM Usuario
                WHERE id_usuario = %s
            """
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
        try:
            cursor = db.connection.cursor()
            sql = """
                SELECT 
                    u.id_usuario,
                    u.nombre_completo,
                    u.email,
                    u.rol,
                    u.activo,
                    e.id_empleado,
                    e.telefono,
                    ch.rfc,
                    ch.curp,
                    ch.nss,
                    ch.direccion,
                    ch.fecha_ingreso,
                    ch.licencia,
                    ch.licencia_tipo,
                    ch.licencia_expira,
                    ch.anios_experiencia,
                    ch.notas
                FROM Usuario u
                LEFT JOIN Empleado e ON u.id_empleado = e.id_empleado
                LEFT JOIN Chofer ch ON ch.id_empleado = e.id_empleado
                ORDER BY u.nombre_completo;
            """
            cursor.execute(sql)
            rows = cursor.fetchall()
            users = []
            for row in rows:
                user = {
                    'id_usuario': row[0],
                    'nombre_completo': row[1],
                    'email': row[2],
                    'rol': row[3],
                    'activo': row[4],
                    'id_empleado': row[5],
                    'telefono': row[6],
                    'rfc': row[7],
                    'curp': row[8],
                    'nss': row[9],
                    'direccion': row[10],
                    'fecha_ingreso': row[11],
                    'licencia': row[12],
                    'licencia_tipo': row[13],
                    'licencia_expira': row[14],
                    'anios_experiencia': row[15],
                    'notas': row[16]
                }
                users.append(user)
            return users
        except Exception as ex:
            print("ERROR ModelUser.get_all_users:", ex)
            return []

    @classmethod
    def create_user(cls, db, nombre_completo, email, password, rol='Empleado',
                    telefono=None, chofer_data=None):
        """
        Crea:
          1) Empleado
          2) (opcional) Chofer si rol == 'Chofer'
          3) Usuario (login), enlazado con id_empleado
        """
        try:
            cursor = db.connection.cursor()

            # Mapear rol lógico del sistema al rol de la tabla Empleado
            map_rol_empleado = {
                'Empleado': 'Ventanilla',
                'Admin': 'Admin',
                'Chofer': 'Chofer',
                'Mecanico': 'Mecanico'
            }
            rol_empleado = map_rol_empleado.get(rol, 'Ventanilla')

            # 1) Insertar en EMPLEADO
            sql_emp = """
                INSERT INTO Empleado (nombre, correo, telefono, rol, activo)
                VALUES (%s, %s, %s, %s, 1)
            """
            cursor.execute(sql_emp, (nombre_completo, email, telefono, rol_empleado))
            id_empleado = cursor.lastrowid

            # 2) Si es CHOFER, insertar en CHOFER
            if rol == 'Chofer':
                if chofer_data is None or not chofer_data.get('licencia'):
                    raise ValueError("La licencia es obligatoria para registrar un chofer.")

                sql_ch = """
                    INSERT INTO Chofer (
                        id_empleado,
                        nombre, telefono, correo,
                        rfc, curp, nss,
                        direccion, fecha_ingreso,
                        activo,
                        licencia, licencia_tipo, licencia_expira,
                        anios_experiencia, notas
                    )
                    VALUES (
                        %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s,
                        1,
                        %s, %s, %s,
                        %s, %s
                    )
                """
                cursor.execute(sql_ch, (
                    id_empleado,
                    nombre_completo,
                    telefono,
                    email,
                    chofer_data.get('rfc'),
                    chofer_data.get('curp'),
                    chofer_data.get('nss'),
                    chofer_data.get('direccion'),
                    chofer_data.get('fecha_ingreso'),
                    chofer_data.get('licencia'),
                    chofer_data.get('licencia_tipo'),
                    chofer_data.get('licencia_expira'),
                    chofer_data.get('anios_experiencia', 0),
                    chofer_data.get('notas')
                ))

            # 3) Insertar en USUARIO (para login), enlazando id_empleado
            password_hash = generate_password_hash(password)
            sql_usr = """
                INSERT INTO Usuario (id_empleado, nombre_completo, email, password_hash, rol, activo)
                VALUES (%s, %s, %s, %s, %s, 1)
            """
            cursor.execute(sql_usr, (id_empleado, nombre_completo, email, password_hash, rol))

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
            sql = """
                UPDATE Usuario
                SET nombre_completo = %s,
                    email = %s,
                    rol = %s,
                    activo = %s
                WHERE id_usuario = %s
            """
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

    @classmethod
    def update_user_full(cls, db, id_usuario,
                         nombre_completo, email, rol, activo,
                         telefono_empleado=None,
                         chofer_data=None):
        """
        Actualiza:
          - Usuario
          - Empleado vinculado
          - (Opcional) Chofer, si el rol es 'Chofer'

        chofer_data es un diccionario con claves:
          rfc, curp, nss, direccion, fecha_ingreso,
          licencia, licencia_tipo, licencia_expira,
          anios_experiencia, notas
        """
        try:
            conn = db.connection
            cursor = conn.cursor()

            # 1) Obtener id_empleado actual y rol previo del usuario
            cursor.execute("""
                SELECT id_empleado, rol
                FROM Usuario
                WHERE id_usuario = %s
            """, (id_usuario,))
            row = cursor.fetchone()
            if not row:
                raise ValueError("Usuario no encontrado")

            id_empleado_actual = row[0]  # puede ser None en datos viejos
            rol_anterior = row[1]

            # 2) Si no hay empleado vinculado, lo creamos ahora
            if id_empleado_actual is None:
                # mapear rol del sistema a rol de Empleado
                map_rol_empleado = {
                    'Empleado': 'Ventanilla',
                    'Admin': 'Admin',
                    'Chofer': 'Chofer',
                    'Mecanico': 'Mecanico',
                    'Cliente': 'Ventanilla'
                }
                rol_empleado = map_rol_empleado.get(rol, 'Ventanilla')

                sql_emp = """
                    INSERT INTO Empleado (nombre, correo, telefono, rol, activo)
                    VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(sql_emp, (
                    nombre_completo,
                    email,
                    telefono_empleado,
                    rol_empleado,
                    activo
                ))
                id_empleado = cursor.lastrowid

                # actualizar Usuario.id_empleado
                cursor.execute("""
                    UPDATE Usuario
                    SET id_empleado = %s
                    WHERE id_usuario = %s
                """, (id_empleado, id_usuario))
            else:
                id_empleado = id_empleado_actual

            # 3) Actualizar tabla Usuario
            cursor.execute("""
                UPDATE Usuario
                SET nombre_completo = %s,
                    email           = %s,
                    rol             = %s,
                    activo          = %s
                WHERE id_usuario   = %s
            """, (nombre_completo, email, rol, activo, id_usuario))

            # 4) Actualizar tabla Empleado (nombre, correo, telefono, rol, activo)
            map_rol_empleado = {
                'Empleado': 'Ventanilla',
                'Admin': 'Admin',
                'Chofer': 'Chofer',
                'Mecanico': 'Mecanico',
                'Cliente': 'Ventanilla'
            }
            rol_empleado = map_rol_empleado.get(rol, 'Ventanilla')

            cursor.execute("""
                UPDATE Empleado
                SET nombre  = %s,
                    correo  = %s,
                    telefono= %s,
                    rol     = %s,
                    activo  = %s
                WHERE id_empleado = %s
            """, (nombre_completo, email, telefono_empleado, rol_empleado, activo, id_empleado))

            # 5) Manejo de tabla Chofer según el rol
            if rol == 'Chofer':
                # si no hay chofer_data, usamos dict vacío
                if chofer_data is None:
                    chofer_data = {}

                # verificar si ya existe registro en Chofer para ese empleado
                cursor.execute("""
                    SELECT id_chofer
                    FROM Chofer
                    WHERE id_empleado = %s
                """, (id_empleado,))
                row_ch = cursor.fetchone()

                if row_ch:
                    # UPDATE existente
                    cursor.execute("""
                        UPDATE Chofer
                        SET nombre            = %s,
                            telefono          = %s,
                            correo            = %s,
                            rfc               = %s,
                            curp              = %s,
                            nss               = %s,
                            direccion         = %s,
                            fecha_ingreso     = %s,
                            licencia          = %s,
                            licencia_tipo     = %s,
                            licencia_expira   = %s,
                            anios_experiencia = %s,
                            notas             = %s,
                            activo            = %s
                        WHERE id_empleado = %s
                    """, (
                        nombre_completo,
                        telefono_empleado,
                        email,
                        chofer_data.get('rfc'),
                        chofer_data.get('curp'),
                        chofer_data.get('nss'),
                        chofer_data.get('direccion'),
                        chofer_data.get('fecha_ingreso'),
                        chofer_data.get('licencia'),
                        chofer_data.get('licencia_tipo'),
                        chofer_data.get('licencia_expira'),
                        chofer_data.get('anios_experiencia', 0),
                        chofer_data.get('notas'),
                        1 if activo else 0,
                        id_empleado
                    ))
                else:
                    # INSERT nuevo chofer
                    cursor.execute("""
                        INSERT INTO Chofer (
                            id_empleado,
                            nombre, telefono, correo,
                            rfc, curp, nss,
                            direccion, fecha_ingreso,
                            activo,
                            licencia, licencia_tipo, licencia_expira,
                            anios_experiencia, notas
                        )
                        VALUES (
                            %s,
                            %s, %s, %s,
                            %s, %s, %s,
                            %s, %s,
                            %s,
                            %s, %s, %s,
                            %s, %s
                        )
                    """, (
                        id_empleado,
                        nombre_completo,
                        telefono_empleado,
                        email,
                        chofer_data.get('rfc'),
                        chofer_data.get('curp'),
                        chofer_data.get('nss'),
                        chofer_data.get('direccion'),
                        chofer_data.get('fecha_ingreso'),
                        1 if activo else 0,
                        chofer_data.get('licencia'),
                        chofer_data.get('licencia_tipo'),
                        chofer_data.get('licencia_expira'),
                        chofer_data.get('anios_experiencia', 0),
                        chofer_data.get('notas')
                    ))

            else:
                # Si ya no es chofer, opcionalmente lo marcamos inactivo en Chofer
                cursor.execute("""
                    UPDATE Chofer
                    SET activo = 0
                    WHERE id_empleado = %s
                """, (id_empleado,))

            conn.commit()
            return True

        except Exception as ex:
            print("ERROR ModelUser.update_user_full:", ex)
            try:
                db.connection.rollback()
            except:
                pass
            return False

