import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import '../styles/App.css';

const Sidebar = () => {
  const navigate = useNavigate();
  const location = useLocation();

  const menuItems = [
    { id: 'add', label: 'Add Repository', path: '/', icon: '➕' },
    { id: 'list', label: 'View Repositories', path: '/repositories', icon: '📁' },
    { id: 'analysis', label: 'Analysis Results', path: '/analysis-results', icon: '📊' },
  ];

  const isActive = (path) => {
    if (path === '/') {
      return location.pathname === '/' || location.pathname === '';
    }
    return location.pathname.startsWith(path);
  };

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h2 className="sidebar-title">Navigation</h2>
      </div>
      <nav className="sidebar-nav">
        {menuItems.map(item => (
          <button
            key={item.id}
            className={`sidebar-item ${isActive(item.path) ? 'active' : ''}`}
            onClick={() => navigate(item.path)}
          >
            <span className="sidebar-icon">{item.icon}</span>
            <span className="sidebar-label">{item.label}</span>
          </button>
        ))}
      </nav>
    </div>
  );
};

export default Sidebar;
