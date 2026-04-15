import React, { useState } from 'react';
import Analytics from './pages/Analytics';
import Dashboard from './pages/Dashboard';

// Mocking "live" data for Dashboard
const mockLive = {
  water_level_pct: 65,
  distance_mm: 84.5,
  roc: { state: 'Stable', roc: 0.002, noise_floor: 0.001 },
  last_anomaly: false
};

function App() {
  const [page, setPage] = useState('dashboard');

  return (
    <div id="root">
      {/* Updated Navigation with specific UI classes */}
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
      </nav>

      {/* Main Content Area */}
      <main>
        {page === 'dashboard' ? (
          <Dashboard live={mockLive} />
        ) : (
          <Analytics />
        )}
      </main>
    </div>
  );
}

export default App;