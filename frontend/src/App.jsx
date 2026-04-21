import React, { useState } from 'react';
import Analytics from './pages/Analytics';
import Dashboard from './pages/Dashboard';
import Report from './pages/Report';

function App() {
  const [page, setPage] = useState('dashboard');

  return (
    <div id="root">
      {/* Navigation */}
      <nav className="nav-container">
        <button 
          className={`nav-button ${page === 'dashboard' ? 'active' : ''}`}
          onClick={() => setPage('dashboard')}
        >
          Telemetry Dashboard
        </button>
        <button 
          className={`nav-button ${page === 'analytics' ? 'active' : ''}`}
          onClick={() => setPage('analytics')}
        >
          Deep Analytics
        </button>
        <button 
          className={`nav-button ${page === 'report' ? 'active' : ''}`}
          onClick={() => setPage('report')}
        >
          Report
        </button>
      </nav>

      {/* Main Content Area */}
      <main>
        {page === 'dashboard' && <Dashboard />}
        {page === 'analytics' && <Analytics />}
        {page === 'report'    && <Report />}
      </main>
    </div>
  );
}

export default App;