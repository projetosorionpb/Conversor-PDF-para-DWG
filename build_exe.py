import PyInstaller.__main__
import os
import shutil

# Nome do executável final
EXE_NAME = "Conversor_PDF_para_DWG"

def build():
    print("Iniciando build do executável...")
    
    # Limpa pastas antigas
    for folder in ['build', 'dist']:
        if os.path.exists(folder):
            try:
                shutil.rmtree(folder)
            except Exception as e:
                print(f"Aviso: Não foi possível limpar a pasta {folder}. Se o app estiver aberto, feche-o. Erro: {e}")

    # Argumentos do PyInstaller
    args = [
        'app.py',                         # Script principal
        '--name=%s' % EXE_NAME,           # Nome do .exe
        '--onefile',                      # Arquivo único
        '--noconsole',                    # Não abre CMD ao rodar
        '--add-data=templates;templates', # Inclui a pasta de templates
        '--hidden-import=pdf_para_dxf',   # Garante que o conversor seja incluído
        '--collect-all=ezdxf',            # Dependências do ezdxf
        '--clean'
    ]

    PyInstaller.__main__.run(args)
    
    print("\n" + "="*30)
    print("Build concluído!")
    print("O executável está na pasta 'dist/%s.exe'" % EXE_NAME)
    print("="*30)

if __name__ == '__main__':
    build()
