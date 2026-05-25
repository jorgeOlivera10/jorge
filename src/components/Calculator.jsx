import React, { useState, useEffect, useRef } from 'react';
import * as XLSX from 'xlsx-js-style';

const UX_INTER_HALL_DISTANCES = {
  60: { A: 60, B: 70 },
  62: { A: 51, B: 77 },
  72: { A: 73, D: 74 }
};

function getKnownInterHallDistance(seriesNum, path) {
  const entry = UX_INTER_HALL_DISTANCES[seriesNum];
  if (entry && entry[path] !== undefined) return entry[path];
  return null;
}

function roundTo2(n) {
  return Math.round(n * 100) / 100;
}

function formatTotal(n) {
  return Number.isInteger(n) ? `${n} m` : `${n.toFixed(2)} m`;
}

export default function Calculator() {
  const [inputText, setInputText] = useState('');
  const [parsedPairs, setParsedPairs] = useState([]);
  const [results, setResults] = useState([]);
  const [alerts, setAlerts] = useState([]);

  // Selections & configs
  const [filterPath, setFilterPath] = useState('');
  const [filterTier, setFilterTier] = useState('');
  const [filterRounding, setFilterRounding] = useState('');
  const [selectedIndexes, setSelectedIndexes] = useState(new Set());

  const showAlert = (msg, type = 'info') => {
    const id = Date.now() + Math.random();
    setAlerts(prev => [...prev, { id, msg, type }]);
    setTimeout(() => {
      setAlerts(prev => prev.filter(a => a.id !== id));
    }, 5000);
  };

  const clearAlerts = () => setAlerts([]);

  const handleParse = async () => {
    if (!inputText.trim()) {
      showAlert('Introduce al menos un binomio de racks.', 'error');
      return;
    }
    clearAlerts();
    try {
      const response = await fetch('/api/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: inputText.trim() })
      });
      if (!response.ok) throw new Error('Error en la conexión con el servidor');
      const data = await response.json();
      
      const pairs = data.pairs || [];
      if (pairs.length === 0) {
        showAlert('No se han detectado binomios válidos.', 'error');
        return;
      }
      
      const pairsWithErrors = pairs.filter(p => p.error);
      if (pairsWithErrors.length > 0) {
        pairsWithErrors.forEach(p => {
          const offendingText = (p.originRaw && p.destRaw) 
            ? `${p.originRaw} / ${p.destRaw}` 
            : p.rawLine;
          showAlert(`"${offendingText.trim()}" tiene un formato de entrada incorrecto.`, 'error');
        });
        setParsedPairs([]);
        return;
      }
      
      // Initialize configs
      const initialConfigs = {};
      const initialSelected = new Set();
      pairs.forEach((pair, idx) => {
        initialSelected.add(idx);
        initialConfigs[idx] = {
          tier: '3',
          roundingMode: '2',
          path: !pair.directConnection && pair.origin && pair.origin.config && pair.origin.config.paths ? pair.origin.config.paths[0] : 'A',
          interHallMeters: ''
        };
        // Auto-fill inter-hall if applicable
        if (pair.interHall) {
          const knownDist = getKnownInterHallDistance(pair.origin.seriesNum, initialConfigs[idx].path);
          if (knownDist !== null) initialConfigs[idx].interHallMeters = knownDist;
        }
      });
      
      setConfigs(initialConfigs);
      setSelectedIndexes(initialSelected);
      setParsedPairs(pairs);
      setResults([]);
    } catch (err) {
      showAlert(`Error de API: ${err.message}`, 'error');
    }
  };

  const handleCalculate = async () => {
    clearAlerts();
    const items = [];
    let hasLocalErrors = false;
    
    parsedPairs.forEach((pair, idx) => {
      const config = configs[idx];
      let interHallMeters = null;
      
      if (pair.interHall) {
        interHallMeters = parseFloat(config.interHallMeters);
        if (isNaN(interHallMeters) || interHallMeters < 0) {
          showAlert(`Error en ${pair.origin.raw} → ${pair.dest.raw}: Introduce la distancia Inter-Hall.`, 'error');
          hasLocalErrors = true;
        }
      }
      
      items.push({
        pair,
        tier: parseInt(config.tier, 10) || 3,
        path: pair.directConnection ? null : config.path,
        interHallMeters,
        roundingMode: config.roundingMode
      });
    });
    
    if (hasLocalErrors) return;
    
    try {
      const response = await fetch('/api/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items })
      });
      if (!response.ok) throw new Error('Error en la conexión con el servidor');
      
      const data = await response.json();
      const validResults = (data.results || []).filter(r => r.calc);
      
      if (data.hasErrors) {
        (data.results || []).filter(r => r.error).forEach(r => showAlert(r.error, 'error'));
        return;
      }
      
      if (validResults.length > 0) {
        setResults(validResults);
      } else {
        showAlert('No hay resultados para mostrar.', 'warning');
      }
    } catch (err) {
      showAlert(`Error de API: ${err.message}`, 'error');
    }
  };

  const handleExport = async () => {
    if (results.length === 0) {
      showAlert('❌ No hay datos para exportar. Calcula primero.', 'warning');
      return;
    }
    
    try {
      const response = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ results })
      });

      if (!response.ok) throw new Error('Error al generar el archivo en el servidor');

      const buffer = await response.arrayBuffer();
      const blob = new Blob([buffer], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `Cableado_ZAZ_${new Date().toISOString().slice(0, 10)}.xlsx`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      showAlert(`Error al exportar: ${err.message}`, 'error');
    }
  };

  const handleLoadExample = () => {
    const example = `ZAZ61.01-01-006-74    ZAZ61.01-01-012-45\nZAZ61.02-02-010-33    ZAZ61.02-02-014-37`;
    setInputText(example);
  };

  const handleClear = () => {
    setInputText('');
    setParsedPairs([]);
    setResults([]);
    clearAlerts();
  };

  // Add more logic for rendering...
  
  return (
    <div className="app-container">
      {/* ═══ INPUT SECTION ═══ */}
      <div className="section-row" id="input-section">
        <div className="section-left fade-in">
          <div className="section-number-container">
            <div className="section-number">1</div>
            <div className="section-info">
              <h3 className="section-title">INTRODUCCIÓN DE BINOMIOS DE RACKS</h3>
              <p className="section-desc">Escribe o pega los binomios de racks del SOW. Un par por línea.</p>
            </div>
          </div>
        </div>
        <section className="neu-card">
          <div className="card-arrow"><i className="fas fa-chevron-left"></i></div>
          <h2 className="work-area-title">INTRODUCCIÓN DE BINOMIOS DE RACKS</h2>
          <textarea 
            className="neu-textarea" 
            value={inputText}
            onChange={e => setInputText(e.target.value)}
            placeholder="ZAZ61.01-01-006-74    ZAZ61.01-01-012-45"
          />
          <div className="btn-group" style={{marginTop: '20px'}}>
            <button className="neu-btn neu-btn--primary" onClick={handleParse}>Analizar Racks</button>
            <button className="neu-btn neu-btn--secondary" onClick={handleLoadExample}>Cargar ejemplo</button>
            <button className="neu-btn neu-btn--danger" onClick={handleClear}>Limpiar</button>
          </div>
        </section>
      </div>

      <div id="alerts-container">
        {alerts.map(a => (
          <div key={a.id} className={`alert alert--${a.type}`}>{a.msg}</div>
        ))}
      </div>

            {/* ═══ GLOBAL FILTERS ═══ */}
            <div className="filter-bar" style={{marginBottom: '20px', display: 'flex', gap: '10px', alignItems: 'center'}}>
              <label className="neu-label">Path:</label>
              <select value={filterPath} onChange={e => setFilterPath(e.target.value)} className="neu-dropdown__native">
                <option value="">-- Todos --</option>
                <option value="A">A</option>
                <option value="B">B</option>
                <option value="C">C</option>
                <option value="D">D</option>
              </select>
              <label className="neu-label">Tier:</label>
              <select value={filterTier} onChange={e => setFilterTier(e.target.value)} className="neu-dropdown__native">
                <option value="">-- Todos --</option>
                <option value="3">Tier 3 (10m)</option>
                <option value="4">Tier 4 (15m)</option>
                <option value="5">Tier 5 (15m)</option>
              </select>
              <label className="neu-label">Redondeo:</label>
              <select value={filterRounding} onChange={e => setFilterRounding(e.target.value)} className="neu-dropdown__native">
                <option value="">-- Todos --</option>
                <option value="2">Cada 2m</option>
                <option value="5">Cada 5m</option>
                <option value="0">Sin redondeo</option>
              </select>
              <button className="neu-btn neu-btn--primary" onClick={() => {
                setConfigs(prev => {
                  const newCfg = { ...prev };
                  selectedIndexes.forEach(idx => {
                    if (filterPath) newCfg[idx] = { ...newCfg[idx], path: filterPath };
                    if (filterTier) newCfg[idx] = { ...newCfg[idx], tier: filterTier };
                    if (filterRounding) newCfg[idx] = { ...newCfg[idx], roundingMode: filterRounding };
                  });
                  return newCfg;
                });
              }}>Aplicar a seleccionados</button>
            </div>
      {/* ═══ PARSED TABLE ═══ */}
      {parsedPairs.length > 0 && (
        <div className="section-row" id="parsed-section">
          <div className="section-left fade-in">
            <div className="section-number-container">
              <div className="section-number">2</div>
              <div className="section-info">
                <h3 className="section-title">CONFIGURACIÓN DE BINOMIOS</h3>
              </div>
            </div>
          </div>
          <section className="neu-card">
            <h2 className="work-area-title">CONFIGURACIÓN DE BINOMIOS</h2>
            
            <div className="parsed-table-wrap">
              <table className="parsed-table">
                <thead>
                  <tr>
                    <th><input type="checkbox" className="neu-checkbox" /></th>
                    <th>#</th>
                    <th>Rack Origen</th>
                    <th>Rack Destino</th>
                    <th>Tipo</th>
                    <th>Path</th>
                    <th className="interhall-col">Inter-Hall</th>
                    <th>Bandeja</th>
                    <th>Redondeo</th>
                  </tr>
                </thead>
                <tbody>
                  {parsedPairs.map((pair, idx) => {
                    const isDirect = pair.directConnection;
                    const config = configs[idx] || {};
                    return (
                      <tr key={idx} className={selectedIndexes.has(idx) ? 'row-selected' : 'row-unselected'}>
                        <td><input type="checkbox" className="neu-checkbox row-checkbox" checked={selectedIndexes.has(idx)} onChange={(e) => {
                          const newSet = new Set(selectedIndexes);
                          if (e.target.checked) newSet.add(idx);
                          else newSet.delete(idx);
                          setSelectedIndexes(newSet);
                        }}/></td>
                        <td>{pair.lineNum}</td>
                        <td><code>{pair.origin.raw}</code></td>
                        <td><code>{pair.dest.raw}</code></td>
                        <td><span className={isDirect ? 'tag tag--ok' : 'tag tag--ok'}>{pair.origin.config?.label || 'OK'}</span></td>
                        <td>
                          {isDirect ? <span className="tag tag--direct">Directo</span> : (
                            <select value={config.path} onChange={e => {
                          const newPath = e.target.value;
                          setConfigs(prev => ({
                            ...prev,
                            [idx]: { ...prev[idx], path: newPath }
                          }));
                        }} className="neu-dropdown__native" style={{opacity: 1, position: 'relative', width: 'auto'}}>
                          {(pair.origin.config?.paths?.length ? pair.origin.config?.paths : ['A','B','C','D']).map(p => (
                            <option key={p} value={p}>Path {p}</option>
                          ))}
                        </select>  )}
                        </td>
                        <td className="interhall-col">
                           {pair.interHall ? (
                             <input type="number" style={{width: '60px'}} value={config.interHallMeters} onChange={e => {
                               setConfigs(prev => ({
                                 ...prev,
                                 [idx]: { ...prev[idx], interHallMeters: e.target.value }
                               }));
                             }} />
                           ) : <span>—</span>}
                        </td>
                        <td>
                          <select value={config.tier} onChange={e => {
                            setConfigs(prev => ({
                                 ...prev,
                                 [idx]: { ...prev[idx], tier: e.target.value }
                               }));
                          }}>
                            <option value="3">Tier 3 (10m)</option>
                            <option value="4">Tier 4 (15m)</option>
                            <option value="5">Tier 5 (15m)</option>
                          </select>
                        </td>
                        <td>
                          <select value={config.roundingMode} onChange={e => {
                            setConfigs(prev => ({
                                 ...prev,
                                 [idx]: { ...prev[idx], roundingMode: e.target.value }
                               }));
                          }}>
                            <option value="2">Cada 2m</option>
                            <option value="5">Cada 5m</option>
                            <option value="0">Sin redondeo</option>
                          </select>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>

            <div className="btn-group">
              <button className="neu-btn neu-btn--primary" onClick={handleCalculate}>Calcular Metros de Cable</button>
            </div>
          </section>
        </div>
      )}

      {/* ═══ RESULTS ═══ */}
      {results.length > 0 && (
        <div className="section-row" id="results-section">
          <div className="section-left fade-in">
            <div className="section-number-container">
              <div className="section-number">3</div>
              <div className="section-info">
                <h3 className="section-title">RESULTADOS DEL CÁLCULO</h3>
              </div>
            </div>
          </div>
          <section className="neu-card">
            <h2 className="work-area-title">RESULTADOS DEL CÁLCULO</h2>

            <div className="results-table-wrap">
              <table className="results-table">
                <thead>
                  <tr>
                    <th>Binomio</th>
                    <th>Path</th>
                    <th>Vertical Inicial</th>
                    <th>Horizontal</th>
                    <th className="interhall-col">Inter-Hall</th>
                    <th>Vertical Final</th>
                    <th>Bandeja</th>
                    <th>Margen</th>
                    <th>Total</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((r, idx) => {
                     const p = r.pair;
                     const c = r.calc;
                     return (
                       <tr key={idx}>
                         <td>{p.origin.raw} → {p.dest.raw}</td>
                         <td>{r.pathLabel}</td>
                         <td>{c.verticalInicial.toFixed(2)} m</td>
                         <td>{c.horizontal.toFixed(2)} m</td>
                         <td className="interhall-col">{c.interHallDist > 0 ? c.interHallDist.toFixed(2) + ' m' : '—'}</td>
                         <td>{c.verticalFinal.toFixed(2)} m</td>
                         <td>{c.bandeja.toFixed(2)} m</td>
                         <td>{c.margen.toFixed(2)} m</td>
                         <td className="total-col">
                           {r.roundingMode && r.roundingMode !== '0' && c.totalRaw !== undefined ? (
                             <>
                               <div className="total-raw">{c.totalRaw.toFixed(2)} m</div>
                               <div className="total-rounded">{formatTotal(c.total)}</div>
                             </>
                           ) : formatTotal(c.total)}
                         </td>
                       </tr>
                     );
                  })}
                </tbody>
              </table>
            </div>

            <div className="btn-group">
              <button className="neu-btn neu-btn--primary" onClick={handleExport}>Exportar a Excel</button>
            </div>
          </section>
        </div>
      )}
      
    </div>
  );
}
