from flask import Flask, render_template, request, send_file, after_this_request, jsonify
import os
import sys
import secrets
import threading
import webbrowser
import time
from src.converter import converter_pdf_para_dxf


def resource_path(relative_path):
    """Obtém o caminho absoluto para recursos, compatível com PyInstaller."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


import shutil
import tkinter as tk
from tkinter import filedialog
import tempfile
import atexit

app = Flask(__name__, 
            template_folder=resource_path('templates'),
            static_folder=resource_path('static'))

# Cria um diretório temporário fantasma (auto-destruído ao fechar)
SESSION_TEMP_DIR = tempfile.mkdtemp(prefix="pdf2dwg_")

def cleanup_temp_dir():
    try:
        shutil.rmtree(SESSION_TEMP_DIR, ignore_errors=True)
    except:
        pass

atexit.register(cleanup_temp_dir)

app.config['UPLOAD_FOLDER'] = SESSION_TEMP_DIR
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB


@app.route('/')
def index():
    return render_template('index.html', version=int(time.time()))


@app.route('/convert', methods=['POST'])
def convert():
    print(">>> Recebida requisição de conversão")
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "Nenhum arquivo enviado."}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "Arquivo sem nome."}), 400
    
    # Lê o toggle da interface
    converter_blocos = request.form.get('converter_blocos') == 'true'
    print(f"Converter símbolos em blocos: {converter_blocos}")
    
    if file and file.filename.lower().endswith('.pdf'):
        base_name = secrets.token_hex(4) + "_" + file.filename
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], base_name)
        dwg_name = base_name.rsplit('.', 1)[0] + ".dwg"
        dwg_path = os.path.join(app.config['UPLOAD_FOLDER'], dwg_name)
        
        try:
            print(f"Salvando PDF temporário em: {pdf_path}")
            file.save(pdf_path)
            
            print(f"Iniciando conversão para: {file.filename}")
            resultado = converter_pdf_para_dxf(pdf_path, dwg_path, converter_blocos=converter_blocos)
            
            if not os.path.exists(dwg_path):
                print("ERRO: O conversor não gerou o arquivo DWG.")
                return jsonify({"status": "error", "message": "Falha interna: DWG não gerado."}), 500

            print(f"Conversão concluída com sucesso: {dwg_name}")

            @after_this_request
            def cleanup(response):
                try:
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)
                        print(f"PDF temporário removido: {pdf_path}")
                except Exception as e:
                    print(f"Aviso no cleanup: {e}")
                return response

            return jsonify({
                "status": "success", 
                "file_id": dwg_name, 
                "original_name": file.filename.rsplit('.', 1)[0],
                "escala_detectada": str(resultado.get("escala_detectada", "N/A")),
                "total_elementos": resultado.get("total_elementos", 0),
                "tamanho_kb": round(resultado.get("tamanho_kb", 0), 1),
                "blocos_criados": resultado.get("blocos_criados", 0) if converter_blocos else None
            })
            
        except Exception as e:
            print(f"ERRO NO FLASK: {str(e)}")
            import traceback
            traceback.print_exc()
            return jsonify({"status": "error", "message": f"Erro no servidor: {str(e)}"}), 500
    
    return jsonify({"status": "error", "message": "Formato inválido. Use PDF."}), 400


@app.route('/download/<file_id>')
def download(file_id):
    path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
    if os.path.exists(path):
        parts = file_id.split('_', 1)
        original_name = parts[1] if len(parts) > 1 else "projeto.dwg"
        
        # Encontra a pasta Downloads do usuário atual
        downloads_folder = os.path.join(os.path.expanduser('~'), 'Downloads')
        dest_path = os.path.join(downloads_folder, original_name)
        
        try:
            # Copia o arquivo diretamente para a pasta Downloads do Windows
            shutil.copy2(path, dest_path)
            return jsonify({"status": "success", "path": dest_path})
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
            
    return jsonify({"status": "error", "message": "Arquivo expirado ou não encontrado"}), 404


@app.route('/save_as', methods=['POST'])
def save_as():
    try:
        data = request.json
        file_id = data.get('file_id')
        original_name = data.get('original_name', 'desenho')
        
        source_path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
        if not os.path.exists(source_path):
            return jsonify({"status": "error", "message": "Arquivo não encontrado"}), 404

        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        
        target_path = filedialog.asksaveasfilename(
            title="Salvar arquivo DWG",
            initialfile=f"{original_name}.dwg",
            defaultextension=".dwg",
            filetypes=[("AutoCAD DWG", "*.dwg"), ("Todos os arquivos", "*.*")]
        )
        root.destroy()

        if target_path:
            shutil.copy(source_path, target_path)
            return jsonify({"status": "success", "path": target_path})
        
        return jsonify({"status": "cancelled"})
    except Exception as e:
        print(f"Erro no Save As: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


# A inicialização via '__main__' não é mais necessária, 
# pois o main.py cuidará de rodar tudo via PyWebView.
