import sys
import os

# Adiciona o diretório atual ao path para garantir que src seja encontrado
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from web.app import app
import webview

if __name__ == '__main__':
    # Configura a janela nativa do webview
    window = webview.create_window(
        title='CONVERSOR PDF DWG',
        url=app,
        width=800,
        height=680,
        min_size=(600, 500),
        background_color='#111319' # Fundo escuro padrão
    )
    
    # Inicia a aplicação (PyWebView lida com o Flask internamente)
    webview.start(
        debug=False,
        gui='edgehtml' if os.name == 'nt' else 'cef'
    )
