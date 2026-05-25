import React from 'react';
import './index.css';
import Calculator from './components/Calculator';

function App() {
  return (
    <>
      <header className="hero">
        <div className="hero-overlay"></div>
        <nav className="hero-nav">
          <img src="/Gotor Comunicaciones Blanco.png" alt="Gotor Comunicaciones" className="hero-logo" />
        </nav>
        <div className="hero-content">
          <h1 className="hero-title">CALCULADORA<br/><span>AWS</span></h1>
          <p className="hero-subtitle">Bienvenido a la calculadora automática de metros de cableado para los datacenter de Amazon</p>
        </div>
      </header>

      <Calculator />

      <footer className="app-footer">
        Calculadora de Cableado ZAZ — Datacenter AWS Zaragoza — PI, JO y MU | 2026
      </footer>
    </>
  );
}

export default App;
