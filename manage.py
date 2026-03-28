from app import app, init_db_command

with app.app_context():
    init_db_command.callback()
