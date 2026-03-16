import React from 'react';
import '../styles/App.css';

const ActionButtons = ({ 
  onTestSelection, 
  isSelectionRunning,
  disabled = false
}) => {
  return (
    <div className="details-section">
      <div className="section-title">Actions</div>
      <div className="action-buttons">
        <button
          className="action-button primary"
          onClick={onTestSelection}
          disabled={isSelectionRunning || disabled}
          title={disabled ? 'Test selection is disabled due to risk threshold being exceeded' : ''}
        >
          {isSelectionRunning ? 'Selecting Tests...' : disabled ? 'Selection Disabled' : 'Select Tests'}
        </button>
      </div>
    </div>
  );
};

export default ActionButtons;
