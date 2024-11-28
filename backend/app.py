from flask import Flask, request, jsonify, send_file
import os
import pandas as pd
from io import BytesIO
from flask_cors import CORS
import re
import spacy

app = Flask(__name__)
CORS(app)

app.config['UPLOAD_FOLDER'] = 'uploads'

nlp = spacy.load('en_core_web_sm')

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

# Função para encontrar a coluna de Nome com validação adicional usando spaCy
def encontrar_coluna_nome(df, tabela, colunas_esperadas):
    # Verificar as colunas com base nos nomes esperados
    for col in df.columns:
        if any(nc in col.lower() for nc in colunas_esperadas):
            return col

    # Caso não encontre pelo nome da coluna, usar spaCy para validar o conteúdo
    for col in df.columns:
        valores = df[col].dropna().astype(str).tolist()  # Obter valores não nulos da coluna
        contagem_nomes = 0

        for valor in valores:
            doc = nlp(valor)  # Processar o valor com spaCy
            if any(ent.label_ == "PERSON" for ent in doc.ents):  # Verificar se é um nome de pessoa
                contagem_nomes += 1

        # Considerar a coluna como contendo nomes se um número significativo de valores for identificado como nomes
        if contagem_nomes > len(valores) * 0.5:  # Ajuste o limite conforme necessário
            return col

    # Se nenhuma coluna for identificada como contendo nomes
    raise ValueError(f"Coluna de Nome não encontrada na tabela {tabela}")


# Função para processar os arquivos e comparar os CPFs e Nomes
def comparar_cpfs(concierge_file, sanus_file, beneficiarios_file):
    concierge = pd.read_excel(concierge_file)
    sanus = pd.read_excel(sanus_file)
    beneficiarios = pd.read_excel(beneficiarios_file)

    try:
        coluna_cpf_concierge = encontrar_coluna_cpf(concierge)
        coluna_nome_concierge = encontrar_coluna_nome(concierge, 'concierge', ['funcionario', 'nome'])
        coluna_cpf_sanus = encontrar_coluna_cpf(sanus)
        coluna_nome_sanus = encontrar_coluna_nome(sanus, 'sanus', ['nome do beneficiário', 'nome'])
        coluna_cpf_beneficiarios = encontrar_coluna_cpf(beneficiarios)
        coluna_nome_beneficiarios = encontrar_coluna_nome(beneficiarios, 'beneficiarios', ['nome do beneficiário', 'nome'])
    except ValueError as e:
        return {"error": str(e)}

    # Formatando CPFs
    concierge[coluna_cpf_concierge] = concierge[coluna_cpf_concierge].astype(str).apply(formatar_cpf)
    sanus[coluna_cpf_sanus] = sanus[coluna_cpf_sanus].astype(str).apply(formatar_cpf)
    beneficiarios[coluna_cpf_beneficiarios] = beneficiarios[coluna_cpf_beneficiarios].astype(str).apply(formatar_cpf)

    # Combine todos os CPFs em um único conjunto
    all_cpfs = set(concierge[coluna_cpf_concierge]).union(set(sanus[coluna_cpf_sanus])).union(set(beneficiarios[coluna_cpf_beneficiarios]))

    # Preparar o resultado para cada CPF
    result = []
    for cpf in all_cpfs:
        # Buscar o nome nas três tabelas: Sanus, Concierge, Beneficiários (nesta ordem de prioridade)
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
        # Verifica se algum arquivo foi enviado
        if not request.files:
            return jsonify({'error': 'Nenhum arquivo foi enviado.'}), 400

        # Cria um dicionário para armazenar os arquivos carregados
        uploaded_files = {}

        # Itera sobre todos os arquivos enviados e salva no diretório
        for file_field, uploaded_file in request.files.items():
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], uploaded_file.filename)
            uploaded_file.save(file_path)
            uploaded_files[file_field] = file_path

        # Verifica se todos os arquivos necessários foram enviados
        if len(uploaded_files) < 3:
            return jsonify({'error': 'Arquivos insuficientes. Certifique-se de enviar 3 arquivos.'}), 400

        # Assumindo que os arquivos são os 3 esperados (independentemente da ordem)
        file_paths = list(uploaded_files.values())

        # Chama a função para comparar os arquivos
        resultados = comparar_cpfs(*file_paths)

        if "error" in resultados:
            return jsonify(resultados), 400

        return jsonify(resultados)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

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

    return send_file(output, download_name=f"{file_name}.xlsx", as_attachment=True)

if __name__ == "__main__":
    if not os.path.exists('uploads'):
        os.makedirs('uploads')
    app.run(debug=True)
