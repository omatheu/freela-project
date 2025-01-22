from flask import Flask, request, jsonify, send_file
import os
import pandas as pd
from io import BytesIO
from flask_cors import CORS
import re
import spacy

app = Flask(__name__)
CORS(app, resources={
    r"*": {
        "origins": [
            "http://localhost:3000", 
            "http://172.17.0.2:3000", 
            "https://freela-project-brown.vercel.app"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

app.config['UPLOAD_FOLDER'] = 'uploads'
nlp = spacy.load('en_core_web_sm')

# Middleware para tratamento global de erros
@app.errorhandler(Exception)
def handle_exception(e):
    response = {
        "error": "Ocorreu um erro inesperado.",
        "details": str(e)
    }
    return jsonify(response), 500

# Função auxiliar para respostas padronizadas de erro
def error_response(message, status_code=400):
    return jsonify({"error": message}), status_code

# Função para formatar CPFs
def formatar_cpf(cpf):
    cpf_str = re.sub(r'\D', '', str(cpf))
    return cpf_str.zfill(11)

# Função para processar arquivo Excel
def process_excel(file_path):
    try:
        df = pd.read_excel(file_path, header=None)
        if df.empty:
            raise ValueError("O arquivo está vazio.")
        start_row = df[df.isin(['CPF']).any(axis=1)].index[0]
        df = pd.read_excel(file_path, skiprows=start_row)
        if df is None or not hasattr(df, 'columns'):
            raise ValueError("Erro ao processar o arquivo. Nenhuma tabela válida encontrada.")
        return df
    except Exception as e:
        raise ValueError(f"Erro ao processar o arquivo {file_path}: {e}")

# Função para encontrar coluna de CPF
def encontrar_coluna_cpf(df):
    for col in df.columns:
        if 'cpf' in col.lower():
            return col
    raise ValueError("Coluna de CPF não encontrada")

# Função para encontrar coluna de Nome
def encontrar_coluna_nome(df, tabela, colunas_esperadas):
    for col in df.columns:
        if any(nc in col.lower() for nc in colunas_esperadas):
            return col

    for col in df.columns:
        valores = df[col].dropna().astype(str).tolist()
        contagem_nomes = sum(any(ent.label_ == "PERSON" for ent in nlp(valor).ents) for valor in valores)
        if contagem_nomes > len(valores) * 0.5:
            return col

    raise ValueError(f"Coluna de Nome não encontrada na tabela {tabela}")

# Função para comparar CPFs entre tabelas
def comparar_cpfs(concierge, sanus, beneficiarios):
    try:
        coluna_cpf_concierge = encontrar_coluna_cpf(concierge)
        coluna_nome_concierge = encontrar_coluna_nome(concierge, 'concierge', ['funcionario', 'nome'])
        coluna_cpf_sanus = encontrar_coluna_cpf(sanus)
        coluna_nome_sanus = encontrar_coluna_nome(sanus, 'sanus', ['nome do beneficiário', 'nome'])
        coluna_cpf_beneficiarios = encontrar_coluna_cpf(beneficiarios)
        coluna_nome_beneficiarios = encontrar_coluna_nome(beneficiarios, 'beneficiarios', ['nome do beneficiário', 'nome'])
    except ValueError as e:
        return {"error": str(e)}

    concierge[coluna_cpf_concierge] = concierge[coluna_cpf_concierge].astype(str).apply(formatar_cpf)
    sanus[coluna_cpf_sanus] = sanus[coluna_cpf_sanus].astype(str).apply(formatar_cpf)
    beneficiarios[coluna_cpf_beneficiarios] = beneficiarios[coluna_cpf_beneficiarios].astype(str).apply(formatar_cpf)

    all_cpfs = set(concierge[coluna_cpf_concierge]).union(set(sanus[coluna_cpf_sanus])).union(set(beneficiarios[coluna_cpf_beneficiarios]))

    result = []
    for cpf in all_cpfs:
        nome = '❌'
        if cpf in sanus[coluna_cpf_sanus].values:
            nome = sanus[sanus[coluna_cpf_sanus] == cpf][coluna_nome_sanus].values[0]
        elif cpf in concierge[coluna_cpf_concierge].values:
            nome = concierge[concierge[coluna_cpf_concierge] == cpf][coluna_nome_concierge].values[0]
        elif cpf in beneficiarios[coluna_cpf_beneficiarios].values:
            nome = beneficiarios[beneficiarios[coluna_cpf_beneficiarios] == cpf][coluna_nome_beneficiarios].values[0]

        result.append({
            'cpf': cpf,
            'nome': nome,
            'concierge': '✔️' if cpf in concierge[coluna_cpf_concierge].values else '❌',
            'sanus': '✔️' if cpf in sanus[coluna_cpf_sanus].values else '❌',
            'beneficiarios': '✔️' if cpf in beneficiarios[coluna_cpf_beneficiarios].values else '❌'
        })

    return result

@app.route("/", methods=["GET"])
def get():
    return "Hello world!"

@app.route("/upload", methods=["POST"])
def upload_files():
    try:
        if not request.files:
            return error_response('Nenhum arquivo foi enviado.')

        required_files = ['concierge_file', 'sanus_file', 'beneficiarios_file']
        processed_files = {}

        for file_field in required_files:
            uploaded_file = request.files.get(file_field)
            if not uploaded_file:
                return error_response(f"O arquivo '{file_field}' está ausente.")

            file_path = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
            uploaded_file.save(file_path)
            processed_files[file_field] = process_excel(file_path)

        if len(processed_files) < len(required_files):
            return error_response('Arquivos insuficientes. Certifique-se de enviar todos os arquivos obrigatórios.')

        concierge_df = processed_files['concierge_file']
        sanus_df = processed_files['sanus_file']
        beneficiarios_df = processed_files['beneficiarios_file']

        resultados = comparar_cpfs(concierge_df, sanus_df, beneficiarios_df)

        if "error" in resultados:
            return error_response(resultados["error"], 400)

        return jsonify(resultados)
    except Exception as e:
        return handle_exception(e)

@app.route("/download_excel", methods=["POST"])
def download_excel():
    try:
        data = request.json.get('data')
        file_name = request.json.get('file_name', 'comparacao_resultados')

        for item in data:
            item['concierge'] = 'Sim' if item['concierge'] == '✔️' else 'Não'
            item['sanus'] = 'Sim' if item['sanus'] == '✔️' else 'Não'
            item['beneficiarios'] = 'Sim' if item['beneficiarios'] == '✔️' else 'Não'

        df = pd.DataFrame(data)
        output = BytesIO()
        df.to_excel(output, index=False)
        output.seek(0)

        return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                         as_attachment=True, download_name=f"{file_name}.xlsx")
    except Exception as e:
        return handle_exception(e)

if __name__ == "__main__":
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
