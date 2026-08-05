import os
import sys
import mysql.connector

# Ensure current folder is in Python path
workspace_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, workspace_dir)

def init_all():
    # 1. Connect to MySQL
    print("Connecting to MySQL...")
    conn = mysql.connector.connect(host='localhost', user='root', password='')
    cur = conn.cursor()

    # 2. Drop and recreate database
    print("Recreating database url_safety...")
    cur.execute("DROP DATABASE IF EXISTS url_safety")
    cur.execute("CREATE DATABASE url_safety CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cur.execute("USE url_safety")
    conn.commit()

    # 3. Read and run php/setup.sql
    sql_file_path = os.path.join(workspace_dir, "php", "setup.sql")
    print(f"Reading SQL commands from {sql_file_path}...")
    with open(sql_file_path, 'r', encoding='utf-8') as f:
        sql_content = f.read()

    # Split by semicolon, filter out comments and empty commands
    commands = sql_content.split(';')
    for cmd in commands:
        cmd_clean = ""
        for line in cmd.split('\n'):
            line_stripped = line.strip()
            if line_stripped and not line_stripped.startswith('--') and not line_stripped.startswith('#'):
                cmd_clean += line + "\n"
        cmd_clean = cmd_clean.strip()
        if cmd_clean:
            print(f"Executing PHP setup SQL command: {cmd_clean[:60]}...")
            try:
                cur.execute(cmd_clean)
                conn.commit()
            except Exception as e:
                print(f"Error executing command: {e}")

    cur.close()
    conn.close()

    # 4. Run server.py's init functions
    print("Running server.py database initializers...")
    import server
    server.init_db()
    server.init_mysql_otp_tables()

    # 5. Run database.py's table creator
    print("Running database.py database initializers...")
    import database
    database.create_tables()

    # 6. Verify and list all tables
    print("\nVerifying all tables in url_safety...")
    conn = mysql.connector.connect(host='localhost', user='root', password='', database='url_safety')
    cur = conn.cursor()
    cur.execute("SHOW TABLES")
    tables = [r[0] for r in cur.fetchall()]
    print(f"Created {len(tables)} tables:")
    for t in tables:
        try:
            cur.execute(f"SELECT COUNT(*) FROM `{t}`")
            cnt = cur.fetchone()[0]
            print(f"  - {t} ({cnt} rows) - OK")
        except Exception as e:
            print(f"  - {t} - ERROR: {e}")
    cur.close()
    conn.close()

if __name__ == '__main__':
    init_all()
