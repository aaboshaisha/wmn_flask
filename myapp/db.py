import sqlite3
from flask import current_app, g
import click

def get_db():
    if 'db' not in g: # if no existing connection, establish one
        g.db = sqlite3.connect(
            current_app.config['DATABASE'], # get it from the path u defined in configuration
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row # return rows that behave like dicts to acces cols by name
    return g.db


def close_db(e=None):
    db = g.pop('db', None) # check if g is storing an existing db
    if db is not None:
        db.close()

def init_db():
    db = get_db() # establish a database connection
    # open the app's schema file and run its commands
    with current_app.open_resource('schema.sql') as f: 
        db.executescript(f.read().decode('utf8'))
        

@click.command('init-db')
def init_db_command():
    """Clear the existing database and create new tables"""
    init_db()
    click.echo('Initialized the database.')
    
# when app instance is available, register the functions above with it
def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)

