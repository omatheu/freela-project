from flask import Flask, request, jsonify, send_file
import os
import pandas as pd
from io import BytesIO
from flask_cors import CORS
import re
import spacy
import tempfile

app = Flask(__name__)
CORS(app, resources={
    r"*": {
        "origins": [
            "https://freela-project-brown.vercel.app",
            "https://freela-project.vercel.app",
            "http://localhost:3000"
        ],
        "methods": ["GET", "POST", "PUT", "DELETE"],
        "allow_headers": ["Content-Type", "Authorization"],
        "supports_credentials": True
    }
})

app.config['UPLOAD_FOLDER'] = 'uploads'
nlp = spacy.load('en_core_web_sm')

def save_as_csv(df, filename):
    csv_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    df.to_csv(csv_path, index=False, encoding='utf-8')
    return csv_path

@app.errorhandler(Exception)
def handle_exception(e):
    return jsonify({"error": "Erro interno no servidor", "details": str(e)}), 500

def formatar_cpf(cpf):
    cpf_str = re.sub(r'\D', '', str(cpf))
    return cpf_str.zfill(11)

def process_excel_in_chunks(file_path):
    try:
        # Encontrar a linha do cabeçalho
        df_header = pd.read_excel(file_path, header=None, engine="openpyxl", nrows=100)
        start_row = df_header[df_header.isin(['CPF']).any(axis=1)].index[0]
        
        # Ler o DataFrame com os cabeçalhos corretos
        df = pd.read_excel(file_path, skiprows=start_row, engine="openpyxl")
        return df
    except Exception as e:
        raise ValueError(f"Erro ao processar o arquivo {file_path}: {e}")

def encontrar_coluna_cpf(df):
    for col in df.columns:
        if 'cpf' in col.lower():
            return col
    raise ValueError("Coluna de CPF não encontrada")

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

def comparar_cpfs(concierge, sanus, beneficiarios):
    try:
        # Encontrar colunas de CPF e Nome em cada DataFrame
        col_cpf_con = encontrar_coluna_cpf(concierge)
        col_nome_con = encontrar_coluna_nome(concierge, 'concierge', ['funcionario', 'nome'])
        
        col_cpf_sanus = encontrar_coluna_cpf(sanus)
        col_nome_sanus = encontrar_coluna_nome(sanus, 'sanus', ['nome do beneficiário', 'nome'])
        
        col_cpf_ben = encontrar_coluna_cpf(beneficiarios)
        col_nome_ben = encontrar_coluna_nome(beneficiarios, 'beneficiarios', ['nome do beneficiário', 'nome'])
    except ValueError as e:
        return {"error": str(e)}

    # Formatar CPFs
    concierge[col_cpf_con] = concierge[col_cpf_con].astype(str).apply(formatar_cpf)
    sanus[col_cpf_sanus] = sanus[col_cpf_sanus].astype(str).apply(formatar_cpf)
    beneficiarios[col_cpf_ben] = beneficiarios[col_cpf_ben].astype(str).apply(formatar_cpf)

    # Coletar todos os CPFs
    cpfs_con = set(concierge[col_cpf_con])
    cpfs_sanus = set(sanus[col_cpf_sanus])
    cpfs_ben = set(beneficiarios[col_cpf_ben])
    todos_cpfs = cpfs_con.union(cpfs_sanus).union(cpfs_ben)

    # Comparar cada CPF
    resultados = []
    for cpf in todos_cpfs:
        # Encontrar nome (prioridade Sanus > Concierge > Beneficiários)
        nome = '❌'
        if cpf in cpfs_sanus:
            nome = sanus[sanus[col_cpf_sanus] == cpf][col_nome_sanus].values[0]
        elif cpf in cpfs_con:
            nome = concierge[concierge[col_cpf_con] == cpf][col_nome_con].values[0]
        elif cpf in cpfs_ben:
            nome = beneficiarios[beneficiarios[col_cpf_ben] == cpf][col_nome_ben].values[0]

        resultados.append({
            'cpf': cpf,
            'nome': nome,
            'concierge': '✔️' if cpf in cpfs_con else '❌',
            'sanus': '✔️' if cpf in cpfs_sanus else '❌',
            'beneficiarios': '✔️' if cpf in cpfs_ben else '❌'
        })

    return resultados

@app.route("/upload", methods=["POST"])
def upload_files():
    try:
        if not request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400

        arquivos = ['concierge_file', 'sanus_file', 'beneficiarios_file']
        dataframes = {}
        
        for arquivo in arquivos:
            file = request.files.get(arquivo)
            if not file:
                return jsonify({'error': f'Arquivo {arquivo} ausente'}), 400
            
            caminho = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(caminho)
            
            df = process_excel_in_chunks(caminho)
            dataframes[arquivo] = df

        # Comparar CPFs
        resultado = comparar_cpfs(
            dataframes['concierge_file'],
            dataframes['sanus_file'],
            dataframes['beneficiarios_file']
        )

        if isinstance(resultado, dict) and 'error' in resultado:
            return jsonify(resultado), 400

        return jsonify(resultado)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route("/download_excel", methods=["POST"])
def download_excel():
    try:
        data = request.json.get('data')
        df = pd.DataFrame(data)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            df.to_excel(tmp.name, index=False)
            return send_file(
                tmp.name,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name='resultado_comparacao.xlsx'
            )
    except Exception as e:
        return handle_exception(e)

if __name__ == "__main__":
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    app.run(debug=True)
