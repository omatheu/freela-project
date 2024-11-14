import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [conciergeFile, setConciergeFile] = useState(null);
  const [sanusFile, setSanusFile] = useState(null);
  const [beneficiariosFile, setBeneficiariosFile] = useState(null);
  const [resultados, setResultados] = useState([]);
  const [fileName, setFileName] = useState('comparacao_resultados'); // Nome do arquivo Excel

  // Envia os arquivos para o backend e obtém os resultados da comparação
  const handleSubmit = async (event) => {
    event.preventDefault();
    const formData = new FormData();

    formData.append('concierge_file', conciergeFile);
    formData.append('sanus_file', sanusFile);
    formData.append('beneficiarios_file', beneficiariosFile);

    try {
      const response = await axios.post('http://127.0.0.1:5000/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      setResultados(response.data); // Define os resultados recebidos do backend
    } catch (error) {
      console.error('Erro ao enviar arquivos:', error);
    }
  };

  // Função para baixar o arquivo Excel gerado no backend
  const handleDownload = async () => {
    try {
      const response = await axios.post('http://127.0.0.1:5000/download_excel', {
        data: resultados,
        file_name: fileName,
      }, {
        responseType: 'blob', // Garantir que o download seja tratado como um arquivo
      });

      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `${fileName}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      console.error('Erro ao baixar o Excel:', error);
    }
  };

  // Definir a cor da linha de acordo com a presença em diferentes tabelas
  const getRowClass = (item) => {
    // Verifica quantos "✔️" existem nas colunas
    const countChecks = [item.concierge === '✔️', item.sanus === '✔️', item.beneficiarios === '✔️'].filter(Boolean).length;
    if (countChecks === 3) return 'table-success'; // Verde se todas as 3 planilhas têm o CPF
    if (countChecks === 2) return 'table-warning'; // Amarelo se 2 planilhas têm o CPF
    return 'table-danger'; // Vermelho se apenas 1 ou nenhuma planilha tem o CPF
  };

  // Renderizar uma tabela única com todos os dados comparados
  const renderTabela = (data) => (
    <div className="table-responsive mb-5">
      <h3>Resultados da Comparação</h3>
      <table className="table table-bordered">
        <thead>
          <tr>
            <th>CPF</th>
            <th>Nome</th>
            <th>Concierge</th>
            <th>Sanus</th>
            <th>Beneficiários</th>
          </tr>
        </thead>
        <tbody>
          {data.map((item, index) => (
            <tr key={index} className={getRowClass(item)}>
              <td>{item.cpf}</td>
              <td>{item.nome}</td>
              <td>{item.concierge}</td>
              <td>{item.sanus}</td>
              <td>{item.beneficiarios}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );

  return (
    <div className="container mt-5">
      <h1 className="text-center">Comparar CPFs entre Planilhas</h1>
      <form onSubmit={handleSubmit} className="mt-4">
        <div className="row mb-3">
          <div className="col-md-4">
            <label>Arquivo Concierge:</label>
            <input type="file" className="form-control" onChange={(e) => setConciergeFile(e.target.files[0])} />
          </div>
          <div className="col-md-4">
            <label>Arquivo Sanus:</label>
            <input type="file" className="form-control" onChange={(e) => setSanusFile(e.target.files[0])} />
          </div>
          <div className="col-md-4">
            <label>Arquivo Beneficiários:</label>
            <input type="file" className="form-control" onChange={(e) => setBeneficiariosFile(e.target.files[0])} />
          </div>
        </div>
        <button type="submit" className="btn btn-primary btn-block">Comparar</button>
      </form>

      {resultados.length > 0 && (
        <div className="mt-5">
          <h2 className="text-center">Resultados da Comparação</h2>
          {renderTabela(resultados)}

          <div className="mt-4">
            <label htmlFor="fileName">Nome do Arquivo Excel:</label>
            <input
              type="text"
              id="fileName"
              className="form-control mb-3"
              value={fileName}
              onChange={(e) => setFileName(e.target.value)}
            />
            <button className="btn btn-success btn-block" onClick={handleDownload}>Baixar Excel</button>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;