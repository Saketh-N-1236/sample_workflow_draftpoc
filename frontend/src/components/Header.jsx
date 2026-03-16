import React from 'react';
import '../styles/App.css';
import companyLogo from '../../company_logo.png';

const Header = () => {
  return (
    <header className="header">
      <div className="header-left">
        <div className="logo-section">
          <img src={companyLogo} alt="Company Logo" className="company-logo" />
        </div>
      </div>
      <div className="header-right">
        <svg className="notification-icon" fill="currentColor" viewBox="0 0 24 24">
          <path d="M12 22c1.1 0 2-.9 2-2h-4c0 1.1.89 2 2 2zm6-6v-5c0-3.07-1.64-5.64-4.5-6.32V4c0-.83-.67-1.5-1.5-1.5s-1.5.67-1.5 1.5v.68C7.63 5.36 6 7.92 6 11v5l-2 2v1h16v-1l-2-2z"/>
        </svg>
        <div className="user-profile">
          <div className="user-avatar">DW</div>
          <div className="user-info">
            <div className="user-name">Diane Ward</div>
            <div className="user-email">diane.ward@ideyalabs.com</div>
          </div>
          <svg width="12" height="12" fill="currentColor" viewBox="0 0 24 24">
            <path d="M7 10l5 5 5-5z"/>
          </svg>
        </div>
      </div>
    </header>
  );
};

export default Header;
