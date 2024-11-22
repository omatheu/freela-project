from flask import Flask, request, jsonify, send_file
import os
import pandas as pd
from io import BytesIO
from flask_cors import CORS
import re

app = Flask(__name__)
CORS(app)

app.config['UPLOAD_FOLDER'] = 'uploads'

# Função para garantir que todos os CPFs tenham apenas números e 11 caracteres
def formatar_cpf(cpf):
    cpf_str = re.sub(r'\D', '', str(cpf))  # Remove todos os caracteres não numéricos
    return cpf_str.zfill(11)

# Função para identificar qual tabela é qual com base nas colunas
def identificar_arquivo(df):
    if any('funcionario' in col.lower() or 'nome' in col.lower() for col in df.columns):
        return 'concierge'
    elif any('beneficiário' in col.lower() or 'nome' in col.lower() for col in df.columns):
        return 'beneficiarios'
    elif any('beneficiário' in col.lower() or 'sanus' in col.lower() for col in df.columns):
        return 'sanus'
    else:
        return None

# Função para encontrar a coluna de CPF
def encontrar_coluna_cpf(df):
    for col in df.columns:
        if 'cpf' in col.lower():
            return col
    raise ValueError("Coluna de CPF não encontrada")

# Função para encontrar a coluna de Nome com flexibilidade para diferentes formatos
def encontrar_coluna_nome(df, tabela):
    nome_colunas = {
        'concierge': ['funcionario', 'nome'],
        'sanus': ['nome do beneficiário', 'nome'],
        'beneficiarios': ['nome do beneficiário', 'nome']
    }
    for col in df.columns:
        if any(nc in col.lower() for nc in nome_colunas[tabela]):
            return col
    raise ValueError(f"Coluna de Nome não encontrada na tabela {tabela}")

# Função para processar os arquivos e comparar os CPFs e Nomes
def comparar_cpfs(files):
    dataframes = {}
    
    # Verificar e classificar os arquivos enviados
    for file_name, file_content in files.items():
        try:
            df = pd.read_excel(file_content)
            tabela = identificar_arquivo(df)
            if tabela:
                dataframes[tabela] = df
            else:
                return jsonify({'error': f"Não foi possível identificar o arquivo '{file_name}'."}), 400
        except Exception as e:
            return jsonify({'error': f"Erro ao processar o arquivo '{file_name}': {str(e)}"}), 400

    # Garantir que todas as tabelas necessárias foram encontradas
    required_tables = {'concierge', 'sanus', 'beneficiarios'}
    if not required_tables.issubset(dataframes.keys()):
        return jsonify({'error': "Nem todas as tabelas obrigatórias foram enviadas (concierge, sanus, beneficiarios)."}), 400

    concierge = dataframes['concierge']
    sanus = dataframes['sanus']
    beneficiarios = dataframes['beneficiarios']

    # Garantir formatação de CPFs
    concierge['cpf'] = concierge['cpf'].astype(str).apply(formatar_cpf)
    sanus['cpf'] = sanus['cpf'].astype(str).apply(formatar_cpf)
    beneficiarios['cpf'] = beneficiarios['cpf'].astype(str).apply(formatar_cpf)

    # Combine todos os CPFs em um único conjunto
    all_cpfs = set(concierge['cpf']).union(set(sanus['cpf'])).union(set(beneficiarios['cpf']))

    # Preparar o resultado para cada CPF
    result = []
    for cpf in all_cpfs:
        nome = '❌'
        if cpf in sanus['cpf'].values:
            nome = sanus[sanus['cpf'] == cpf]['nome'].values[0]
        elif cpf in concierge['cpf'].values:
            nome = concierge[concierge['cpf'] == cpf]['nome'].values[0]
        elif cpf in beneficiarios['cpf'].values:
            nome = beneficiarios[beneficiarios['cpf'] == cpf]['nome'].values[0]

        result.append({
            'cpf': cpf,
            'nome': nome,
            'concierge': '✔️' if cpf in concierge['cpf'].values else '❌',
            'sanus': '✔️' if cpf in sanus['cpf'].values else '❌',
            'beneficiarios': '✔️' if cpf in beneficiarios['cpf'].values else '❌'
        })

    return result

@app.route("/", methods=["GET"])
def get():
    return "Hello world!"

@app.route("/upload", methods=["POST"])
def upload_files():
    # Verificar se os arquivos foram enviados
    if not request.files:
        return jsonify({'error': 'Nenhum arquivo enviado.'}), 400

    files = request.files
    resultados = comparar_cpfs(files)

    if isinstance(resultados, tuple):  # Caso retorne erro na identificação
        return resultados

    return jsonify(resultados)

# Rota para processar e retornar os resultados
@app.route("/upload2", methods=["POST"])
def upload_filesw():
    if 'concierge_file' not in request.files or 'sanus_file' not in request.files or 'beneficiarios_file' not in request.files:
        return jsonify({'error': 'Arquivos não enviados corretamente.'}), 400

    concierge_file = request.files['concierge_file']
    sanus_file = request.files['sanus_file']
    beneficiarios_file = request.files['beneficiarios_file']

    concierge_path = os.path.join(app.config['UPLOAD_FOLDER'], concierge_file.filename)
    sanus_path = os.path.join(app.config['UPLOAD_FOLDER'], sanus_file.filename)
    beneficiarios_path = os.path.join(app.config['UPLOAD_FOLDER'], beneficiarios_file.filename)

    concierge_file.save(concierge_path)
    sanus_file.save(sanus_path)
    beneficiarios_file.save(beneficiarios_path)

    resultados = comparar_cpfs(concierge_path, sanus_path, beneficiarios_path)

    return jsonify(resultados)

# Rota para baixar o Excel
@app.route("/download_excel", methods=["POST"])
def download_excel():
    data = request.json.get('data')
    file_name = request.json.get('file_name', 'comparacao_resultados')

    # Converter os valores de ✔️ e ❌ para Sim e Não no arquivo Excel
    for item in data:
        item['concierge'] = 'Sim' if item['concierge'] == '✔️' else 'Não'
        item['sanus'] = 'Sim' if item['sanus'] == '✔️' else 'Não'
        item['beneficiarios'] = 'Sim' if item['beneficiarios'] == '✔️' else 'Não'

    # Criar o DataFrame a partir dos dados
    df = pd.DataFrame(data)

    # Reordenar as colunas para CPF, Nome e depois as planilhas
    df = df[['cpf', 'nome', 'concierge', 'sanus', 'beneficiarios']]

    # Criar um buffer de bytes para armazenar o Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Resultados')

    output.seek(0)

    return send_file(output, attachment_filename=f"{file_name}.xlsx", as_attachment=True)

if __name__ == "__main__":
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    app.run(debug=True)
