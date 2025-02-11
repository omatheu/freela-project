import React, { useState } from 'react';
import axios from 'axios';
import './App.css';

function App() {
  const [conciergeFile, setConciergeFile] = useState(null);
  const [sanusFile, setSanusFile] = useState(null);
  const [beneficiariosFile, setBeneficiariosFile] = useState(null);
  const [resultados, setResultados] = useState([]);
  const [fileName, setFileName] = useState('comparacao_resultados');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const serverUrl = 'https://freela-project-72p2.onrender.com';

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    const formData = new FormData();
    if (conciergeFile) formData.append('concierge_file', conciergeFile);
    if (sanusFile) formData.append('sanus_file', sanusFile);
    if (beneficiariosFile) formData.append('beneficiarios_file', beneficiariosFile);

    try {
      const response = await axios.post(`${serverUrl}/upload`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResultados(response.data);
    } catch (error) {
      setError('Erro ao enviar arquivos. Tente novamente.');
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async () => {
    try {
      const response = await axios.post(`${serverUrl}/download_excel`, {
        data: resultados,
        file_name: fileName,
      }, {
        responseType: 'blob',
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

  const getRowClass = (item) => {
    const countChecks = [item.concierge === '✔️', item.sanus === '✔️', item.beneficiarios === '✔️'].filter(Boolean).length;
    if (countChecks === 3) return 'table-success';
    if (countChecks === 2) return 'table-warning';
    return 'table-danger';
  };

  return (
    <div className="container mt-5">
      <h1 className="text-center">Bate Cadastral Sanus</h1>
      <form onSubmit={handleSubmit} className="mt-4">
        <div className="row mb-3">
          {[{ label: 'Base Operadora', state: setConciergeFile },
            { label: 'Base Plataforma Sanus', state: setSanusFile },
            { label: 'Base Folha RH', state: setBeneficiariosFile }].map(({ label, state }, idx) => (
            <div key={idx} className="col-md-4">
              <label>{label}:</label>
              <input type="file" className="form-control" onChange={(e) => state(e.target.files[0])} />
            </div>
          ))}
        </div>
        <button type="submit" className="btn btn-primary btn-block" disabled={loading}>
          {loading ? 'Processando...' : 'Comparar'}
        </button>
      </form>

      {error && <div className="alert alert-danger mt-3">{error}</div>}

      {resultados.length > 0 && (
        <div className="mt-5">
          <h2 className="text-center">Resultados da Comparação</h2>
          <button className="btn btn-success btn-block" onClick={handleDownload}>Baixar Excel</button>
          <div className="table-responsive mb-5">
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
                {resultados.map((item, index) => (
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
          <div className="mt-4">
            <label htmlFor="fileName">Nome do Arquivo Excel:</label>
            <input
              type="text"
              id="fileName"
              className="form-control mb-3"
              value={fileName}
              onChange={(e) => setFileName(e.target.value)}
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
