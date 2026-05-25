/* =====================================================
   Calculadora de Cableado — Datacenter ZAZ
   Frontend Orchestrator (Backend API Integration)
   ===================================================== */

// UX Helper for Inter-Hall Auto-fill
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

function toExcelNum(value) {
  return parseFloat(value).toFixed(2).replace('.', ',');
}

function formatTotal(n) {
  return Number.isInteger(n) ? `${n} m` : `${n.toFixed(2)} m`;
}

// ─── DOM Controller ──────────────────────────────────

document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const inputTextarea = document.getElementById('rack-input');
  const parseBtn = document.getElementById('btn-parse');
  const clearBtn = document.getElementById('btn-clear');
  const parsedSection = document.getElementById('parsed-section');
  const parsedBody = document.getElementById('parsed-body');
  const calcBtn = document.getElementById('btn-calculate');
  const alertsContainer = document.getElementById('alerts-container');
  const resultsSection = document.getElementById('results-section');
  const resultsBody = document.getElementById('results-body');
  const copyBtn = document.getElementById('btn-copy');
  const exportBtn = document.getElementById('btn-export');
  const summaryBar = document.getElementById('summary-bar');
  const summTotal = document.getElementById('summ-total');
  const summPairs = document.getElementById('summ-pairs');
  const summAvg = document.getElementById('summ-avg');

  // Helper to animate hiding a section
  const animateHide = (el) => {
    if (!el || el.classList.contains('hidden') || el.classList.contains('fade-out')) return;
    el.classList.remove('fade-in');
    el.classList.add('fade-out');
    setTimeout(() => {
      if (el.classList.contains('fade-out')) {
        el.classList.add('hidden');
        el.classList.remove('fade-out');
      }
    }, 250);
  };

  const hideResults = () => {
    animateHide(resultsSection);
  };

  const hideConfigAndResults = () => {
    animateHide(parsedSection);
    animateHide(bulkBar);
    hideResults();
  };

  const bulkBar = document.getElementById('bulk-bar');
  const bulkDropdowns = document.getElementById('bulk-dropdowns');
  const bulkApplyBtn = document.getElementById('btn-bulk-apply');
  const bulkCounter = document.getElementById('bulk-counter');
  const checkAllBtn = document.getElementById('check-all');

  function autoResizeTextarea() {
    if (inputTextarea) {
      inputTextarea.style.height = 'auto';
      inputTextarea.style.height = inputTextarea.scrollHeight + 'px';
    }
  }

  if (inputTextarea) {
    inputTextarea.addEventListener('input', () => {
      autoResizeTextarea();
      hideConfigAndResults();
    });
    autoResizeTextarea();
  }

  if (parsedBody) {
    parsedBody.addEventListener('input', (e) => {
      if (e.target.classList.contains('interhall-input')) {
        hideResults();
      }
    });
  }

  if (bulkDropdowns) {
    const pathOptions = [
      { value: '', label: '— sin cambio —' },
      { value: 'A', label: 'Path A' },
      { value: 'B', label: 'Path B' },
      { value: 'C', label: 'Path C' },
      { value: 'D', label: 'Path D' }
    ];
    const tierOptions = [
      { value: '', label: '— sin cambio —' },
      { value: '3', label: 'Tier 3 (10m)' },
      { value: '4', label: 'Tier 4 (15m)' },
      { value: '5', label: 'Tier 5 (15m)' }
    ];
    const roundingOptions = [
      { value: '', label: '— sin cambio —' },
      { value: '2', label: 'Cada 2m' },
      { value: '5', label: 'Cada 5m' },
      { value: '0', label: 'Sin redondeo' }
    ];
    bulkDropdowns.innerHTML =
      buildDropdownHtml('bulk-path', pathOptions, '', 'bulk') +
      buildDropdownHtml('bulk-tier', tierOptions, '', 'bulk') +
      buildDropdownHtml('bulk-rounding', roundingOptions, '', 'bulk');
  }

  let parsedPairs = [];
  let results = [];

  // ── Parse Input (API Call) ──
  parseBtn.addEventListener('click', async () => {
    const text = inputTextarea.value.trim();
    if (!text) {
      showAlert('Introduce al menos un binomio de racks.', 'error');
      return;
    }

    clearAlerts();
    
    try {
      const response = await fetch('/api/parse', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text })
      });
      
      if (!response.ok) throw new Error('Error en la conexión con el servidor');
      
      const data = await response.json();
      parsedPairs = data.pairs || [];
    } catch (err) {
      showAlert(`Error de API: ${err.message}`, 'error');
      return;
    }

    if (parsedPairs.length === 0) {
      showAlert('No se han detectado binomios válidos.', 'error');
      return;
    }

    const pairsWithErrors = parsedPairs.filter(p => p.error);
    if (pairsWithErrors.length > 0) {
      pairsWithErrors.forEach(p => {
        const offendingText = (p.originRaw && p.destRaw) 
          ? `${p.originRaw} / ${p.destRaw}` 
          : p.rawLine;
        showAlert(`"${offendingText.trim()}" tiene un formato de entrada incorrecto.`, 'error');
      });
      hideConfigAndResults();
      return;
    }

    const hasInterHall = parsedPairs.some(p => p.interHall === true);
    const container = document.querySelector('.app-container');
    if (container) {
      container.classList.toggle('hide-interhall', !hasInterHall);
    }

    renderParsedTable();
    parsedSection.classList.remove('hidden', 'fade-out');
    if (bulkBar) bulkBar.classList.remove('hidden', 'fade-out');
    parsedSection.classList.add('fade-in');
    hideResults(); 

    parsedSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
  });

  // ── Clear ──
  clearBtn.addEventListener('click', () => {
    inputTextarea.value = '';
    parsedPairs = [];
    results = [];
    [parsedSection, bulkBar, resultsSection].forEach(el => {
      if (el) {
        el.classList.add('hidden');
        el.classList.remove('fade-in', 'fade-out');
      }
    });
    clearAlerts();
  });

  // ── Render Parsed Table ──
  function renderParsedTable() {
    parsedBody.innerHTML = '';

    parsedPairs.forEach((pair, idx) => {
      const tr = document.createElement('tr');

      if (pair.error) {
        let raw1 = '';
        let raw2 = '';
        if (pair.originRaw && pair.destRaw) {
          const highlighted = highlightDifferences(pair.originRaw, pair.destRaw);
          raw1 = highlighted.h1;
          raw2 = highlighted.h2;
        } else {
          raw1 = pair.originRaw ? escapeHtml(pair.originRaw) : '';
          raw2 = pair.destRaw ? escapeHtml(pair.destRaw) : '';
        }

        tr.className = 'row-unselected';
        tr.innerHTML = `
          <td></td>
          <td>${pair.lineNum}</td>
          <td><code>${raw1}</code></td>
          <td><code>${raw2}</code></td>
          <td colspan="5">
            <span class="tag tag--error">Error</span>
            ${escapeHtml(pair.error)}
          </td>
          <td>
            <button class="row-remove-btn" data-idx="${idx}" title="Eliminar">✕</button>
          </td>
        `;
      } else {
        const config = pair.origin.config; // Config sent from backend
        const isDirect = pair.directConnection;
        const isInterHall = pair.interHall;

        let statusHtml = '';
        if (isDirect) {
          statusHtml = `<span class="tag tag--ok">${config.label}</span>`;
        } else if (isInterHall) {
          statusHtml = `<span class="tag tag--interhall">${config.label} / Inter-Hall</span>`;
        } else {
          statusHtml = `<span class="tag tag--ok">${config.label}</span>`;
        }

        let pathHtml;
        if (isDirect) {
          pathHtml = '<span class="tag tag--direct">Directo</span>';
        } else {
          const pathOptions = config.paths.map(p => ({
            value: p,
            label: `Path ${p}`
          }));
          pathHtml = buildDropdownHtml(`path-${idx}`, pathOptions, pathOptions[0].value, idx);
        }

        const tierOptions = [
          { value: '3', label: 'Tier 3 (10m)' },
          { value: '4', label: 'Tier 4 (15m)' },
          { value: '5', label: 'Tier 5 (15m)' }
        ];
        const tierHtml = buildDropdownHtml(`tier-${idx}`, tierOptions, '3', idx);

        const roundingOptions = [
          { value: '2', label: 'Cada 2m' },
          { value: '5', label: 'Cada 5m' },
          { value: '0', label: 'Sin redondeo' }
        ];
        const roundingHtml = buildDropdownHtml(`rounding-${idx}`, roundingOptions, '2', idx);

        let interHallHtml = '<span class="text-muted">—</span>';
        if (isInterHall) {
          const defaultPath = config.paths[0];
          const knownDist = getKnownInterHallDistance(pair.origin.seriesNum, defaultPath);
          const valueAttr = knownDist !== null ? ` value="${knownDist}"` : '';
          const autoClass = knownDist !== null ? ' auto-filled' : '';
          interHallHtml = `
            <input type="number" class="interhall-input${autoClass}" data-idx="${idx}"
                   data-series-num="${pair.origin.seriesNum}"
                   id="interhall-${idx}"
                   placeholder="m" min="0" step="0.1"${valueAttr}
                   title="Distancia Inter-Hall en metros">
          `;
        }

        tr.className = 'row-selected';
        tr.innerHTML = `
          <td><input type="checkbox" class="neu-checkbox row-checkbox" id="check-${idx}" data-idx="${idx}" checked></td>
          <td>${pair.lineNum}</td>
          <td><code>${escapeHtml(pair.origin.raw)}</code></td>
          <td><code>${escapeHtml(pair.dest.raw)}</code></td>
          <td>${statusHtml}</td>
          <td>${pathHtml}</td>
          <td class="interhall-col">${interHallHtml}</td>
          <td>${tierHtml}</td>
          <td>${roundingHtml}</td>
          <td>
            <button class="row-remove-btn" data-idx="${idx}" title="Eliminar">✕</button>
          </td>
        `;
      }

      parsedBody.appendChild(tr);
    });

    initDropdowns();

    document.querySelectorAll('.row-checkbox').forEach(cb => {
      cb.addEventListener('change', (e) => {
        const tr = e.target.closest('tr');
        if (e.target.checked) {
          tr.classList.add('row-selected');
          tr.classList.remove('row-unselected');
        } else {
          tr.classList.add('row-unselected');
          tr.classList.remove('row-selected');
        }
        updateBulkState();
        hideResults();
      });
    });

    updateBulkState();

    document.querySelectorAll('.row-remove-btn').forEach(btn => {
      btn.addEventListener('click', (e) => {
        const idx = parseInt(e.target.dataset.idx, 10);
        parsedPairs.splice(idx, 1);
        if (parsedPairs.length === 0) {
          parsedSection.classList.add('hidden');
        } else {
          renderParsedTable();
        }
        resultsSection.classList.add('hidden');
      });
    });
  }

  function buildDropdownHtml(id, options, selectedValue, idx) {
    const selectedOption = options.find(o => o.value === selectedValue) || options[0];
    const optionsHtml = options.map(o => {
      const isSelected = o.value === selectedValue;
      return `<div class="neu-dropdown__option${isSelected ? ' is-selected' : ''}" data-value="${o.value}">
        <span class="neu-dropdown__option-check"></span>
        <span>${o.label}</span>
      </div>`;
    }).join('');

    return `<div class="neu-dropdown neu-dropdown--sm" data-dropdown-id="${id}">
      <select class="neu-dropdown__native" id="${id}" data-idx="${idx}">
        ${options.map(o => `<option value="${o.value}"${o.value === selectedValue ? ' selected' : ''}>${o.label}</option>`).join('')}
      </select>
      <button type="button" class="neu-dropdown__trigger">
        <span class="neu-dropdown__label">${selectedOption.label}</span>
        <span class="neu-dropdown__arrow">▾</span>
      </button>
      <div class="neu-dropdown__panel">
        ${optionsHtml}
      </div>
    </div>`;
  }

  function initDropdowns() {
    document.querySelectorAll('.neu-dropdown:not([data-initialized])').forEach(dropdown => {
      dropdown.setAttribute('data-initialized', 'true');
      const trigger = dropdown.querySelector('.neu-dropdown__trigger');
      const panel = dropdown.querySelector('.neu-dropdown__panel');
      const label = dropdown.querySelector('.neu-dropdown__label');
      const nativeSelect = dropdown.querySelector('.neu-dropdown__native');
      const options = dropdown.querySelectorAll('.neu-dropdown__option');

      trigger.addEventListener('click', (e) => {
        e.stopPropagation();
        document.querySelectorAll('.neu-dropdown.is-open').forEach(d => {
          if (d !== dropdown) d.classList.remove('is-open');
        });

        if (!dropdown.classList.contains('is-open')) {
          const rect = trigger.getBoundingClientRect();
          panel.style.top = (rect.bottom + 8) + 'px';
          panel.style.left = rect.left + 'px';
          panel.style.minWidth = rect.width + 'px';
          panel.style.width = 'auto'; 
        }

        dropdown.classList.toggle('is-open');
      });

      options.forEach(opt => {
        opt.addEventListener('click', (e) => {
          e.stopPropagation();
          const value = opt.dataset.value;

          nativeSelect.value = value;
          options.forEach(o => o.classList.remove('is-selected'));
          opt.classList.add('is-selected');
          label.textContent = opt.querySelector('span:last-child').textContent;
          dropdown.classList.remove('is-open');
          hideResults();

          const dropdownId = nativeSelect.id;
          if (dropdownId && dropdownId.startsWith('path-')) {
            const pairIdx = parseInt(nativeSelect.dataset.idx, 10);
            updateInterHallAutoFill(pairIdx, value);
          }
        });
      });
    });

    document.addEventListener('click', () => {
      document.querySelectorAll('.neu-dropdown.is-open').forEach(d => {
        d.classList.remove('is-open');
      });
    });
  }

  function updateInterHallAutoFill(idx, newPath) {
    const pair = parsedPairs[idx];
    if (!pair || !pair.interHall) return;

    const interHallInput = document.getElementById(`interhall-${idx}`);
    if (!interHallInput) return;

    const knownDist = getKnownInterHallDistance(pair.origin.seriesNum, newPath);
    if (knownDist !== null) {
      interHallInput.value = knownDist;
      interHallInput.classList.add('auto-filled');
      interHallInput.title = `Distancia predefinida para ZAZ${pair.origin.seriesNum} Path ${newPath}`;
    } else {
      interHallInput.value = '';
      interHallInput.classList.remove('auto-filled');
      interHallInput.title = 'Introduce los metros de distancia Inter-Hall manualmente';
    }
  }

  // ── Calculate (API Call) ──
  calcBtn.addEventListener('click', async () => {
    clearAlerts();
    results = [];

    const pairsWithErrors = parsedPairs.filter(p => p.error);
    if (pairsWithErrors.length > 0) {
      pairsWithErrors.forEach(p => showAlert(p.error, 'error'));
      showAlert('Corrige los errores antes de calcular.', 'warning');
      resultsSection.classList.add('hidden');
      return;
    }

    const items = [];
    let hasLocalErrors = false;

    parsedPairs.forEach((pair, idx) => {
      const tierEl = document.getElementById(`tier-${idx}`);
      const tier = tierEl ? parseInt(tierEl.value, 10) : 3;
      const roundingEl = document.getElementById(`rounding-${idx}`);
      const roundingMode = roundingEl ? roundingEl.value : '2';

      let path = null;
      let interHallMeters = null;

      if (!pair.directConnection) {
        const pathEl = document.getElementById(`path-${idx}`);
        path = pathEl ? pathEl.value : 'A';
      }

      if (pair.interHall) {
        const interHallInput = document.getElementById(`interhall-${idx}`);
        interHallMeters = interHallInput ? parseFloat(interHallInput.value) : NaN;

        if (isNaN(interHallMeters) || interHallMeters < 0) {
          showAlert(`Error en ${pair.origin.raw} → ${pair.dest.raw}: Introduce la distancia Inter-Hall.`, 'error');
          hasLocalErrors = true;
        }
      }

      items.push({
        pair,
        tier,
        path,
        interHallMeters,
        roundingMode
      });
    });

    if (hasLocalErrors) {
      showAlert('Corrige los errores antes de calcular.', 'warning');
      resultsSection.classList.add('hidden');
      return;
    }

    // Call API
    try {
      const response = await fetch('/api/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items })
      });
      
      if (!response.ok) throw new Error('Error en la conexión con el servidor');
      
      const data = await response.json();
      results = data.results || [];
      
      if (data.hasErrors) {
        results.filter(r => r.error).forEach(r => {
          showAlert(r.error, 'error');
        });
        showAlert('Corrige los errores antes de calcular.', 'warning');
        resultsSection.classList.add('hidden');
        return;
      }

    } catch (err) {
      showAlert(`Error de API: ${err.message}`, 'error');
      return;
    }

    const validResults = results.filter(r => r.calc);
    if (validResults.length > 0) {
      renderResults(validResults);
      resultsSection.classList.remove('hidden', 'fade-out');
      resultsSection.classList.add('fade-in');
      resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else {
      showAlert('No hay resultados para mostrar.', 'warning');
    }
  });

  // ── Render Results ──
  function renderResults(validResults) {
    resultsBody.innerHTML = '';

    let totalSum = 0;
    validResults.forEach(r => {
      const p = r.pair;
      const c = r.calc;
      totalSum += c.total;

      let typeLabel = '';

      const hasRounding = r.roundingMode && r.roundingMode !== '0';
      const totalDisplay = (hasRounding && c.totalRaw !== undefined && c.totalRaw !== null)
        ? `<div class="total-raw">${c.totalRaw.toFixed(2)} m</div><div class="total-rounded">${formatTotal(c.total)}</div>`
        : formatTotal(c.total);

      const interHallCell = c.interHallDist > 0
        ? `${c.interHallDist.toFixed(2)} m`
        : '<span class="text-muted">—</span>';

      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>${escapeHtml(p.origin.raw)} → ${escapeHtml(p.dest.raw)}${typeLabel}</td>
        <td>${r.pathLabel}</td>
        <td>${c.verticalInicial.toFixed(2)} m</td>
        <td>${c.horizontal.toFixed(2)} m</td>
        <td class="interhall-col">${interHallCell}</td>
        <td>${c.verticalFinal.toFixed(2)} m</td>
        <td>${c.bandeja.toFixed(2)} m</td>
        <td>${c.margen.toFixed(2)} m</td>
        <td class="total-col">${totalDisplay}</td>
      `;
      resultsBody.appendChild(tr);
    });

    summPairs.textContent = validResults.length;
    summTotal.textContent = roundTo2(totalSum).toFixed(2) + ' m';
    summAvg.textContent = roundTo2(totalSum / validResults.length).toFixed(2) + ' m';
    summaryBar.classList.remove('hidden');
  }

  copyBtn.addEventListener('click', () => {
    const validResults = results.filter(r => r.calc);

    if (validResults.length === 0) {
      showAlert('❌ No hay datos para copiar. Calcula primero.', 'warning');
      return;
    }

    try {
      const hasAnyRounding = validResults.some(r => r.roundingMode && r.roundingMode !== '0');
      const header = hasAnyRounding
        ? ['Rack Origen', 'Rack Destino', 'Path', 'Vertical Inicial (m)', 'Horizontal (m)', 'Inter-Hall (m)', 'Vertical Final (m)', 'Bandeja (m)', 'Margen (m)', 'Total Exacto (m)', 'Total Redondeado (m)']
        : ['Rack Origen', 'Rack Destino', 'Path', 'Vertical Inicial (m)', 'Horizontal (m)', 'Inter-Hall (m)', 'Vertical Final (m)', 'Bandeja (m)', 'Margen (m)', 'Total (m)'];
      const rows = validResults.map(r => {
        const p = r.pair;
        const c = r.calc;
        const ihVal = c.interHallDist > 0 ? toExcelNum(c.interHallDist) : '0,00';
        const base = [
          p.origin.raw,
          p.dest.raw,
          r.pathLabel,
          toExcelNum(c.verticalInicial),
          toExcelNum(c.horizontal),
          ihVal,
          toExcelNum(c.verticalFinal),
          toExcelNum(c.bandeja),
          toExcelNum(c.margen)
        ];
        if (hasAnyRounding) {
          const rawVal = c.totalRaw !== undefined && c.totalRaw !== null ? c.totalRaw : c.total;
          base.push(toExcelNum(rawVal), toExcelNum(c.total));
        } else {
          base.push(toExcelNum(c.total));
        }
        return base.join('\t');
      });

      const totalMeters = validResults.reduce((sum, r) => sum + r.calc.total, 0);
      const totalRawSum = validResults.reduce((sum, r) => sum + (r.calc.totalRaw !== undefined && r.calc.totalRaw !== null ? r.calc.totalRaw : r.calc.total), 0);
      if (hasAnyRounding) {
        rows.push(['TOTAL', '', '', '', '', '', '', '', '', toExcelNum(totalRawSum), toExcelNum(totalMeters)].join('\t'));
      } else {
        rows.push(['TOTAL', '', '', '', '', '', '', '', '', toExcelNum(totalMeters)].join('\t'));
      }

      const tsv = [header.join('\t'), ...rows].join('\n');

      navigator.clipboard.writeText(tsv).then(() => {
        showToast(`✓ Copiado al portapapeles (${validResults.length} binomios)`);
      }).catch((err) => {
        showAlert(`No se pudo copiar: ${err.message}`, 'error');
        console.error('Clipboard error:', err);
      });
    } catch (error) {
      showAlert(`Error: ${error.message}`, 'error');
    }
  });

  exportBtn.addEventListener('click', async () => {
    const validResults = results.filter(r => r.calc);
    if (validResults.length === 0) {
      showAlert('❌ No hay datos para exportar. Calcula primero.', 'warning');
      return;
    }

    try {
      const response = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ results: validResults })
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
      
      showToast('✓ Archivo Excel descargado');
    } catch (err) {
      console.error('Error al exportar:', err);
      showAlert(`Error al exportar: ${err.message}`, 'error');
    }
  });

  function showAlert(msg, type = 'info') {
    const existingAlerts = Array.from(alertsContainer.children);
    const duplicate = existingAlerts.find(a => a.dataset.msg === msg && a.dataset.type === type);

    if (duplicate) {
      duplicate.classList.remove('shake');
      void duplicate.offsetWidth; 
      duplicate.classList.add('shake');
      return;
    }

    const div = document.createElement('div');
    div.className = `alert alert--${type}`;
    div.dataset.msg = msg;
    div.dataset.type = type;
    div.innerHTML = escapeHtml(msg);
    alertsContainer.appendChild(div);

    setTimeout(() => {
      div.classList.add('alert-fade-out');
      div.addEventListener('animationend', () => {
        div.remove();
      }, { once: true });
    }, 5000);

    alertsContainer.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  function clearAlerts() {
    alertsContainer.innerHTML = '';
  }

  function showToast(msg) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = msg;
    document.body.appendChild(toast);

    setTimeout(() => toast.remove(), 3000);
  }

  function escapeHtml(str) {
    const escapeMap = {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
      '/': '&#x2F;'
    };
    return String(str).replace(/[&<>"'\/]/g, char => escapeMap[char]);
  }

  function highlightDifferences(str1, str2) {
    const len = Math.max((str1 || '').length, (str2 || '').length);
    let h1 = '';
    let h2 = '';
    for (let i = 0; i < len; i++) {
      const c1 = str1 ? str1[i] : undefined;
      const c2 = str2 ? str2[i] : undefined;

      if (c1 === c2 && c1 !== undefined) {
        h1 += escapeHtml(c1);
        h2 += escapeHtml(c2);
      } else {
        if (c1 !== undefined) h1 += `<span style="color:var(--danger);font-weight:bold">${escapeHtml(c1)}</span>`;
        if (c2 !== undefined) h2 += `<span style="color:var(--danger);font-weight:bold">${escapeHtml(c2)}</span>`;
      }
    }
    return { h1, h2 };
  }

  function getSelectedIndexes() {
    const indexes = [];
    document.querySelectorAll('.row-checkbox:checked').forEach(cb => {
      indexes.push(parseInt(cb.dataset.idx, 10));
    });
    return indexes;
  }

  function updateBulkState() {
    const checkboxes = document.querySelectorAll('.row-checkbox');
    if (checkboxes.length === 0) return;
    const checked = document.querySelectorAll('.row-checkbox:checked');

    if (checkAllBtn) {
      if (checked.length === 0) {
        checkAllBtn.checked = false;
        checkAllBtn.indeterminate = false;
      } else if (checked.length === checkboxes.length) {
        checkAllBtn.checked = true;
        checkAllBtn.indeterminate = false;
      } else {
        checkAllBtn.checked = false;
        checkAllBtn.indeterminate = true;
      }
    }

    updateBulkCounter(checked.length, checkboxes.length);
  }

  function updateBulkCounter(selected = 0, total = 0) {
    if (!bulkCounter) return;

    bulkCounter.textContent = `${selected} ${selected === 1 ? 'fila' : 'filas'} seleccionada${selected === 1 ? '' : 's'}`;
    if (selected > 0) {
      bulkCounter.classList.add('bulk-counter--active');
      if (bulkApplyBtn) bulkApplyBtn.disabled = false;
    } else {
      bulkCounter.classList.remove('bulk-counter--active');
      if (bulkApplyBtn) bulkApplyBtn.disabled = true;
    }
  }

  if (checkAllBtn) {
    checkAllBtn.addEventListener('change', (e) => {
      const isChecked = e.target.checked;
      document.querySelectorAll('.row-checkbox').forEach(cb => {
        cb.checked = isChecked;
        const tr = cb.closest('tr');
        if (isChecked) {
          tr.classList.add('row-selected');
          tr.classList.remove('row-unselected');
        } else {
          tr.classList.add('row-unselected');
          tr.classList.remove('row-selected');
        }
      });
      updateBulkState();
      hideResults();
    });
  }

  if (bulkApplyBtn) {
    bulkApplyBtn.addEventListener('click', () => {
      const indexes = getSelectedIndexes();
      if (indexes.length === 0) return;

      const pathVal = document.getElementById('bulk-path').value;
      const tierVal = document.getElementById('bulk-tier').value;
      const roundingVal = document.getElementById('bulk-rounding').value;

      if (!pathVal && !tierVal && !roundingVal) {
        showAlert('Selecciona al menos un valor en la barra de acciones masivas.', 'warning');
        return;
      }

      let affectedCount = 0;
      let pathsIgnored = 0;

      indexes.forEach(idx => {
        const pair = parsedPairs[idx];
        let updated = false;

        if (pathVal) {
          if (!pair.directConnection && !pair.interHall) {
            if (updateDropdownVisuals(`path-${idx}`, pathVal)) updated = true;
          } else {
            pathsIgnored++;
          }
        }

        if (tierVal) {
          if (updateDropdownVisuals(`tier-${idx}`, tierVal)) updated = true;
        }

        if (roundingVal) {
          if (updateDropdownVisuals(`rounding-${idx}`, roundingVal)) updated = true;
        }

        if (updated) affectedCount++;
      });

      if (affectedCount > 0) {
        hideResults();
        let msg = `✓ Aplicado a ${affectedCount} filas`;
        if (pathsIgnored > 0) {
          msg += ` (${pathsIgnored} paths ignorados por ser directas/inter-hall)`;
        }
        showToast(msg);
      }
    });
  }

  function updateDropdownVisuals(id, newValue) {
    const select = document.getElementById(id);
    if (!select) return false;

    const optionExists = Array.from(select.options).some(o => o.value === newValue);
    if (!optionExists) return false;

    if (select.value === newValue) return false;

    select.value = newValue;

    const dropdown = select.closest('.neu-dropdown');
    if (dropdown) {
      const options = dropdown.querySelectorAll('.neu-dropdown__option');
      const label = dropdown.querySelector('.neu-dropdown__label');

      options.forEach(opt => {
        if (opt.dataset.value === newValue) {
          opt.classList.add('is-selected');
          if (label) label.textContent = opt.querySelector('span:last-child').textContent;
        } else {
          opt.classList.remove('is-selected');
        }
      });
    }
    return true;
  }

  const exampleBtn = document.getElementById('btn-example');
  if (exampleBtn) {
    exampleBtn.addEventListener('click', () => {
      inputTextarea.value = `ZAZ61.01-01-006-74\tZAZ61.01-01-012-45\nZAZ61.01-01-003-20\tZAZ61.01-01-008-80\nZAZ61.01-01-025-50\tZAZ61.01-01-025-30\nZAZ71.01-01-010-25\tZAZ71.01-01-020-60\nZAZ60.01-01-006-74\tZAZ60.02-01-012-45`;
      inputTextarea.focus();
      autoResizeTextarea();
      hideConfigAndResults();
    });
  }

  document.querySelectorAll('.card-arrow').forEach(arrow => {
    arrow.addEventListener('click', () => {
      const container = document.querySelector('.app-container');
      if (container) {
        container.classList.toggle('is-collapsed');
      }
    });
  });

  window.addEventListener('scroll', () => {
    const nav = document.querySelector('.top-nav');
    if (nav) {
      if (window.scrollY > 20) {
        nav.classList.add('shrink');
      } else {
        nav.classList.remove('shrink');
      }
    }
  });
});
