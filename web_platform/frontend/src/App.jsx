import React from 'react';
import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import Header from './components/Header';
import Sidebar from './components/Sidebar';
import AddRepository from './pages/AddRepository';
import RepositoryList from './pages/RepositoryList';
import RepositoryDetail from './pages/RepositoryDetail';
import AnalysisResults from './pages/AnalysisResults';
import './styles/App.css';

function App() {
  return (
    <Router>
      <div className="app-container">
        <Header />
        <div className="main-layout">
          <Sidebar />
          <div className="content-area">
            <Routes>
              <Route path="/" element={<AddRepository />} />
              <Route path="/repositories" element={<RepositoryList />} />
              <Route path="/repositories/:repoId" element={<RepositoryDetail />} />
              <Route path="/analysis-results" element={<AnalysisResults />} />
            </Routes>
          </div>
        </div>
      </div>
    </Router>
  );
}

export default App;
