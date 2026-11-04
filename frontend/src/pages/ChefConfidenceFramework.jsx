import React, { useState, useEffect, useMemo } from 'react';
import { Info, ShieldCheck, AlertTriangle, X } from 'lucide-react';
import { getReports, getReportById } from '../services/api';

// Extracted from backend source (static strings to avoid importing Python)
const CHEF_FULL_FORM = 'CHEF (Confidence Heuristic via Evidential Factors)';
const CHEF_DESCRIPTION = 'Provides an evidence‑based confidence score for civic reports.';

// Deterministic partial CHEF factor weights (single‑report assessment)
const PARTIAL_WEIGHTS = {
  source_reliability: 0.30,
  temporal_consistency: 0.25,
  corroboration: 0.25,
  source_agreement: 0.10,
  geographic_consistency: 0.10,
};

// Full‑agency CHEF weights (used for canonical events – shown for reference)
const FULL_WEIGHTS = {
  source_diversity: 0.30,
  source_reliability: 0.20,
  source_agreement: 0.20,
  geographic_consistency: 0.15,
  temporal_freshness: 0.15,
};

// Tier thresholds (exactly as implemented in backend/app/chef/calculator.py)
const TIER_THRESHOLDS = {
  HIGH: 0.80,
  MODERATE: 0.60,
  LOW: 0.0,
};

export default function ChefConfidenceFramework() {
  const [reports, setReports] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [search, setSearch] = useState('');

  // Load reports list on mount
  useEffect(() => {
    async function fetch() {
      try {
        const data = await getReports();
        setReports(Array.isArray(data) ? data : []);
      } catch (e) {
        setError(e.message || 'Failed to load reports');
      } finally {
        setLoading(false);
      }
    }
    fetch();
  }, []);

  // Load selected report detail when ID changes
  useEffect(() => {
    if (!selectedId) return;
    async function fetchDetail() {
      try {
        const d = await getReportById(selectedId);
        setDetail(d);
      } catch (e) {
        setError(e.message || `Failed to load report ${selectedId}`);
        setDetail(null);
      }
    }
    fetchDetail();
  }, [selectedId]);

  const filtered = useMemo(() => {
    if (!search) return reports;
    const q = search.toLowerCase();
    return reports.filter(r =>
      (r.title && r.title.toLowerCase().includes(q)) ||
      (r.id && r.id.toLowerCase().includes(q)) ||
      (r.source && r.source.toLowerCase().includes(q))
    );
  }, [reports, search]);

  const renderFactorRow = (name, value) => (
    <tr key={name}>
      <td>{name.replace('_', ' ')}</td>
      <td>{value !== undefined && value !== null ? value : 'Missing'}</td>
    </tr>
  );

  return (
    <div className="chef-framework-container">
      {/* Header */}
      <section className="page-header-card">
        <div className="page-header-content">
          <div className="page-header-badge"><Info size={26} color="#0f62fe" /></div>
          <div>
            <h1 className="page-title">CHEF Confidence Framework</h1>
            <p>{CHEF_DESCRIPTION}</p>
            <p><strong>{CHEF_FULL_FORM}</strong></p>
          </div>
        </div>
      </section>

      {/* Methodology */}
      <section className="methodology-card card">
        <h2>Scoring Methodology (partial CHEF)</h2>
        <p>The backend computes confidence as a weighted sum of five deterministic factors. The exact formula (see <code>backend/app/chef/calculator.py</code>) is:</p>
        <pre style={{background:'#111',color:'#0f0',padding:'1rem'}}>
confidence = max(0.0, min(1.0,
  {PARTIAL_WEIGHTS.source_reliability} * sourceReliability +
  {PARTIAL_WEIGHTS.temporal_consistency} * temporalConsistency +
  {PARTIAL_WEIGHTS.corroboration} * corroboration +
  {PARTIAL_WEIGHTS.source_agreement} * sourceAgreement +
  {PARTIAL_WEIGHTS.geographic_consistency} * geographicConsistency
));
        </pre>
        <p>Tier thresholds (backend <code>get_confidence_tier</code>) are:</p>
        <ul>
          <li>HIGH  ≥ {TIER_THRESHOLDS.HIGH * 100}%</li>
          <li>MODERATE ≥ {TIER_THRESHOLDS.MODERATE * 100}%</li>
          <li>LOW   < {TIER_THRESHOLDS.MODERATE * 100}%</li>
        </ul>
      </section>

      {/* Live Assessment */}
      <section className="live-assessment card">
        <h2>Live Assessment</h2>
        <div className="search-bar">
          <input
            type="text"
            placeholder="Search reports by title, ID, or source"
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
        </div>
        {loading && <p>Loading reports…</p>}
        {error && <p className="error">{error}</p>}
        <div className="report-list">
          <ul>
            {filtered.map(r => (
              <li key={r.id} onClick={() => setSelectedId(r.id)} className={selectedId===r.id?'selected':''}>
                {r.title || r.id}
                {r.confidence !== undefined && r.confidence !== null && (
                  <span className={`confidence-pill tier-${(r.confidence_tier||'').toLowerCase()}`}> {(r.confidence*100).toFixed(0)}% </span>
                )}
              </li>
            ))}
          </ul>
        </div>
        {detail && (
          <div className="detail-card card">
            <button className="close-btn" onClick={() => setDetail(null)}><X size={16} /></button>
            <h3>{detail.title || detail.id}</h3>
            <p><strong>Category:</strong> {detail.category || 'N/A'}</p>
            <p><strong>Source:</strong> {detail.source || 'N/A'}</p>
            <p><strong>Event Time:</strong> {detail.event_time || 'N/A'}</p>
            <hr />
            <h4>Confidence</h4>
            <p>
              Score: {detail.confidence !== undefined && detail.confidence !== null ? `${(detail.confidence*100).toFixed(0)}%` : <span className="missing">Not assessed</span>}
            </p>
            <p>Tier: {detail.confidence_tier || <span className="missing">Not assessed</span>}</p>
            <hr />
            <h4>CHEF Factors (partial)</h4>
            {detail.chef_factors && Object.keys(detail.chef_factors).length ? (
              <table className="factor-table">
                <thead><tr><th>Factor</th><th>Value</th></tr></thead>
                <tbody>
                  {Object.entries(detail.chef_factors).map(([k,v]) => renderFactorRow(k, v))}
                </tbody>
              </table>
            ) : (
              <p>No CHEF factor data available for this report.</p>
            )}
            <hr />
            <h4>Source Evidence</h4>
            <p><strong>URL:</strong> {detail.url ? <a href={detail.url} target="_blank" rel="noreferrer">{detail.url}</a> : 'Missing'}</p>
            <p><strong>Raw Text:</strong> {detail.raw_text ? detail.raw_text.slice(0,200) + (detail.raw_text.length>200? '…' : '') : 'Missing'}</p>
          </div>
        )}
      </section>

      {/* Explainability & Limitations */}
      <section className="limitations card">
        <h2>Explainability & Limitations</h2>
        <p>The current implementation uses deterministic heuristics (source reliability, temporal consistency, corroboration, source agreement, geographic consistency) to produce a confidence score. It does not incorporate machine‑learning models or probabilistic calibration.</p>
        <p>Missing fields (e.g., no source, no location, or missing timestamps) lead to the corresponding factor being omitted and the overall score reflecting the available evidence only.</p>
        <p>Future research may extend CHEF with additional signals, weighting adjustments, or learned models, but those are not part of the present system.</p>
      </section>
    </div>
  );
}
