import sys
import os

# Adiciona o diretório atual ao path para garantir que src seja encontrado
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.app import app
import threading
from web.app import open_browser

if __name__ == '__main__':
    is_exe = getattr(sys, 'frozen', False)
    
    if not is_exe:
        if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
            threading.Thread(target=open_browser, daemon=True).start()
        app.run(host='127.0.0.1', port=5077, debug=True)
    else:
        threading.Thread(target=open_browser, daemon=True).start()
        app.run(host='127.0.0.1', port=5077, debug=False)
