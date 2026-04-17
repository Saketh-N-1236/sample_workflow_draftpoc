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
    </header>
  );
};

export default Header;
