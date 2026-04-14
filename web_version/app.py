from flask import Flask, render_template, request, send_file, after_this_request, jsonify
import os
import secrets
import time
from pdf_para_dxf import converter_pdf_para_dxf

app = Flask(__name__)

# Configurações de pastas
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])

@app.route('/')
def index():
    return render_template('index.html', version=int(time.time()))

@app.route('/convert', methods=['POST'])
def convert():
    if 'file' not in request.files:
        return jsonify({"status": "error", "message": "Nenhum arquivo enviado."}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"status": "error", "message": "Arquivo sem nome."}), 400
    
    if file and file.filename.lower().endswith('.pdf'):
        base_name = secrets.token_hex(4) + "_" + file.filename
        pdf_path = os.path.join(app.config['UPLOAD_FOLDER'], base_name)
        dwg_name = base_name.rsplit('.', 1)[0] + ".dwg"
        dwg_path = os.path.join(app.config['UPLOAD_FOLDER'], dwg_name)
        
        try:
            file.save(pdf_path)
            
            # Chama o motor de conversão
            resultado = converter_pdf_para_dxf(pdf_path, dwg_path)
            
            if not os.path.exists(dwg_path):
                return jsonify({"status": "error", "message": "Falha na conversão: Arquivo não gerado."}), 500

            @after_this_request
            def cleanup(response):
                try:
                    if os.path.exists(pdf_path):
                        os.remove(pdf_path)
                except Exception as e:
                    print(f"Erro no cleanup: {e}")
                return response

            return jsonify({
                "status": "success", 
                "file_id": dwg_name, 
                "original_name": file.filename.rsplit('.', 1)[0],
                "escala_detectada": str(resultado.get("escala_detectada", "N/A")),
                "total_elementos": resultado.get("total_elementos", 0),
                "tamanho_kb": round(resultado.get("tamanho_kb", 0), 1),
            })
            
        except Exception as e:
            return jsonify({"status": "error", "message": f"Erro no servidor: {str(e)}"}), 500
    
    return jsonify({"status": "error", "message": "Formato inválido. Use PDF."}), 400

@app.route('/download/<file_id>')
def download(file_id):
    path = os.path.join(app.config['UPLOAD_FOLDER'], file_id)
    if os.path.exists(path):
        return send_file(os.path.abspath(path), as_attachment=True)
    return "Arquivo expirado ou não encontrado", 404

if __name__ == '__main__':
    # Modo desenvolvimento local
    app.run(host='0.0.0.0', port=5000, debug=True)
