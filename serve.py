import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("DTACH_PORT", app.user_settings.port))
    app.run(host="127.0.0.1", port=port, debug=False)
