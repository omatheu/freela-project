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
        'beneficiarios': ['nome do beneficiário', 'nome do beneficiario', 'nome']
    }
    for col in df.columns:
        if any(nc in col.lower() for nc in nome_colunas[tabela]):
            return col
    raise ValueError(f"Coluna de Nome não encontrada na tabela {tabela}")

# Função para identificar o tipo de tabela com base nas colunas
def identificar_tabela(df):
    colunas = df.columns.str.lower().tolist()

    if any(cpf_col in colunas for cpf_col in ['cpf', 'funcionario']):
        return 'concierge'
    elif any(nome_col in colunas for nome_col in ['nome do beneficiário', 'nome']):
        return 'sanus'
    elif any(nome_col in colunas for nome_col in ['nome do beneficiário', 'nome do beneficiario']):
        return 'beneficiarios'
    else:
        raise ValueError("Tipo de tabela não identificado. Verifique o conteúdo dos arquivos.")

# Função para processar os arquivos e comparar os CPFs e Nomes
def comparar_cpfs(arquivos):
    tabelas = {}
    for arquivo in arquivos:
        df = pd.read_excel(arquivo)
        tipo_tabela = identificar_tabela(df)
        tabelas[tipo_tabela] = df

    # Garantir que todas as tabelas foram carregadas
    if not all(tipo in tabelas for tipo in ['concierge', 'sanus', 'beneficiarios']):
        raise ValueError("Algumas tabelas estão faltando ou não foram identificadas corretamente.")

    concierge = tabelas['concierge']
    sanus = tabelas['sanus']
    beneficiarios = tabelas['beneficiarios']

    coluna_cpf_concierge = encontrar_coluna_cpf(concierge)
    coluna_nome_concierge = encontrar_coluna_nome(concierge, 'concierge')
    coluna_cpf_sanus = encontrar_coluna_cpf(sanus)
    coluna_nome_sanus = encontrar_coluna_nome(sanus, 'sanus')
    coluna_cpf_beneficiarios = encontrar_coluna_cpf(beneficiarios)
    coluna_nome_beneficiarios = encontrar_coluna_nome(beneficiarios, 'beneficiarios')

    concierge[coluna_cpf_concierge] = concierge[coluna_cpf_concierge].astype(str).apply(formatar_cpf)
    sanus[coluna_cpf_sanus] = sanus[coluna_cpf_sanus].astype(str).apply(formatar_cpf)
    beneficiarios[coluna_cpf_beneficiarios] = beneficiarios[coluna_cpf_beneficiarios].astype(str).apply(formatar_cpf)

    # Combine todos os CPFs em um único conjunto
    all_cpfs = set(concierge[coluna_cpf_concierge]).union(set(sanus[coluna_cpf_sanus])).union(set(beneficiarios[coluna_cpf_beneficiarios]))

    # Preparar o resultado para cada CPF
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

# Rota para processar e retornar os resultados
@app.route("/upload", methods=["POST"])
def upload_files():
    if 'files' not in request.files:
        return jsonify({'error': 'Arquivos não enviados corretamente.'}), 400

    arquivos = request.files.getlist('files')
    if len(arquivos) < 3:
        return jsonify({'error': 'Envie pelo menos três arquivos.'}), 400

    caminhos = []
    for arquivo in arquivos:
        caminho = os.path.join(app.config['UPLOAD_FOLDER'], arquivo.filename)
        arquivo.save(caminho)
        caminhos.append(caminho)

    try:
        resultados = comparar_cpfs(caminhos)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400

    return jsonify(resultados)

if __name__ == "__main__":
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    app.run(debug=True)
