import React, { useState, useEffect, useMemo } from 'react';
import {
  ShieldCheck,
  Search,
  RefreshCw,
  ExternalLink,
  AlertTriangle,
  Info,
  MapPin,
  Clock,
  Car,
  CloudRain,
  Radio,
  CheckCircle2,
  XCircle,
  HelpCircle,
  FileText,
  Database,
  Layers,
  SlidersHorizontal,
  ChevronRight,
  X
} from 'lucide-react';
import { getReports, getReportById } from '../services/api';

export default function EvidenceAnalysis() {
  const [reports, setReports] = useState([]);
  const [selectedReportId, setSelectedReportId] = useState(null);
  const [selectedReportDetail, setSelectedReportDetail] = useState(null);
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [error, setError] = useState(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('ALL');
  const [tierFilter, setTierFilter] = useState('ALL');

  // Fetch reports on mount
  const fetchAllReports = async () => {
    setLoadingList(true);
    setError(null);
    try {
      const data = await getReports();
      setReports(Array.isArray(data) ? data : []);
      if (Array.isArray(data) && data.length > 0) {
        // Keep currently selected report if still in list, or select first
        if (!selectedReportId || !data.some((r) => r.id === selectedReportId)) {
          setSelectedReportId(data[0].id);
        }
      } else {
        setSelectedReportId(null);
        setSelectedReportDetail(null);
      }
    } catch (err) {
      console.error('EvidenceAnalysis fetch reports error:', err);
      setError(err.message || 'Failed to load civic reports from backend.');
    } finally {
      setLoadingList(false);
    }
  };

  useEffect(() => {
    fetchAllReports();
  }, []);

  // Fetch report details when selection changes
  useEffect(() => {
    if (!selectedReportId) {
      setSelectedReportDetail(null);
      return;
    }

    let isMounted = true;
    const fetchDetail = async () => {
      setLoadingDetail(true);
      try {
        const detail = await getReportById(selectedReportId);
        if (isMounted) {
          setSelectedReportDetail(detail);
        }
      } catch (err) {
        console.warn('Failed to fetch detailed report by ID, falling back to list item:', err);
        if (isMounted) {
          // Fall back to the report object already in the list
          const fallback = reports.find((r) => r.id === selectedReportId);
          setSelectedReportDetail(fallback || null);
        }
      } finally {
        if (isMounted) {
          setLoadingDetail(false);
        }
      }
    };

    fetchDetail();
    return () => {
      isMounted = false;
    };
  }, [selectedReportId, reports]);

  // Filtered reports for the selector
  const filteredReports = useMemo(() => {
    return reports.filter((report) => {
      if (categoryFilter !== 'ALL' && report.category !== categoryFilter) {
        return false;
      }
      if (tierFilter !== 'ALL') {
        const tier = (report.confidence_tier || 'UNASSESSED').toUpperCase();
        if (tierFilter === 'UNASSESSED') {
          if (report.confidence !== null && report.confidence !== undefined && tier !== 'UNASSESSED' && tier !== 'NONE') {
            return false;
          }
        } else if (tier !== tierFilter) {
          return false;
        }
      }
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const matchesTitle = report.title?.toLowerCase().includes(q);
        const matchesText = report.raw_text?.toLowerCase().includes(q);
        const matchesLoc = report.location?.toLowerCase().includes(q);
        const matchesSource = report.source?.toLowerCase().includes(q);
        const matchesId = report.id?.toLowerCase().includes(q);
        if (!matchesTitle && !matchesText && !matchesLoc && !matchesSource && !matchesId) {
          return false;
        }
      }
      return true;
    });
  }, [reports, categoryFilter, tierFilter, searchQuery]);

  const activeReport = selectedReportDetail || reports.find((r) => r.id === selectedReportId);

  // Helper: check if confidence assessment exists
  const hasConfidenceAssessment =
    activeReport &&
    typeof activeReport.confidence === 'number' &&
    !isNaN(activeReport.confidence) &&
    activeReport.confidence_tier &&
    activeReport.confidence_tier.toUpperCase() !== 'NONE';

  // Helper: calculate completeness audit
  const completenessItems = useMemo(() => {
    if (!activeReport) return [];

    const hasSource = Boolean(activeReport.source && activeReport.source.trim());
    const hasSourceType = Boolean(activeReport.source_type && activeReport.source_type.trim());
    const hasUrl = Boolean(activeReport.url && activeReport.url.trim());
    const hasText = Boolean(activeReport.raw_text && activeReport.raw_text.trim());
    const hasLocName = Boolean(activeReport.location && activeReport.location.trim());
    const hasCoords =
      activeReport.latitude !== null &&
      activeReport.latitude !== undefined &&
      !isNaN(parseFloat(activeReport.latitude)) &&
      activeReport.longitude !== null &&
      activeReport.longitude !== undefined &&
      !isNaN(parseFloat(activeReport.longitude));
    const hasEventTime = Boolean(activeReport.event_time && activeReport.event_time.trim());
    const hasIngestedTime = Boolean(activeReport.ingested_at && activeReport.ingested_at.trim());
    const hasConfidence =
      typeof activeReport.confidence === 'number' && !isNaN(activeReport.confidence);
    const hasTier = Boolean(
      activeReport.confidence_tier && activeReport.confidence_tier.toUpperCase() !== 'NONE'
    );
    const hasChef = Boolean(
      activeReport.chef_factors &&
      typeof activeReport.chef_factors === 'object' &&
      !Array.isArray(activeReport.chef_factors) &&
      Object.keys(activeReport.chef_factors).length > 0
    );

    return [
      { label: 'Source Agency', available: hasSource, value: activeReport.source || 'Missing' },
      { label: 'Source Type', available: hasSourceType, value: activeReport.source_type || 'Missing' },
      { label: 'Source URL', available: hasUrl, value: activeReport.url ? 'Provided' : 'Missing' },
      { label: 'Raw Evidence Text', available: hasText, value: hasText ? `${activeReport.raw_text.length} chars` : 'Missing' },
      { label: 'Location Name', available: hasLocName, value: activeReport.location || 'Missing' },
      { label: 'Geographic Coordinates', available: hasCoords, value: hasCoords ? `${activeReport.latitude}, ${activeReport.longitude}` : 'Missing' },
      { label: 'Event Timestamp', available: hasEventTime, value: activeReport.event_time || 'Missing' },
      { label: 'Ingestion Timestamp', available: hasIngestedTime, value: activeReport.ingested_at || 'Missing' },
      { label: 'Confidence Score', available: hasConfidence, value: hasConfidence ? `${(activeReport.confidence * 100).toFixed(0)}%` : 'Not Assessed' },
      { label: 'Confidence Tier', available: hasTier, value: activeReport.confidence_tier || 'Not Assessed' },
      { label: 'CHEF Factors Object', available: hasChef, value: hasChef ? `${Object.keys(activeReport.chef_factors).length} factors` : 'Missing' }
    ];
  }, [activeReport]);

  const presentCount = completenessItems.filter((item) => item.available).length;
  const totalCount = completenessItems.length;

  return (
    <div className="evidence-analysis-container">
      {/* Page Header */}
      <div className="page-header-card">
        <div className="page-header-content">
          <div className="page-header-badge">
            <ShieldCheck size={26} color="#0f62fe" />
          </div>
          <div>
            <h1 className="page-title">Evidence Analysis</h1>
            <p className="page-subtitle">
              Inspect report evidence, inspect raw source text, and examine CHEF confidence factor breakdowns.
            </p>
          </div>
        </div>

        <div className="page-header-meta">
          <div className="header-stat-box">
            <span className="stat-label">REPORTS LOADED</span>
            <span className="stat-value">{reports.length}</span>
          </div>
          <button
            className="btn-sync"
            onClick={fetchAllReports}
            disabled={loadingList}
            title="Reload reports from backend"
          >
            <RefreshCw size={15} className={loadingList ? 'animate-spin' : ''} />
            <span>Refresh</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="evidence-error-banner">
          <AlertTriangle size={18} color="#dc2626" />
          <span>{error}</span>
        </div>
      )}

      {/* Main Two-Column Layout */}
      <div className="evidence-workspace-grid">
        {/* Left Column: Report Selector */}
        <div className="evidence-selector-panel">
          <div className="selector-panel-header">
            <div className="panel-title-wrap">
              <FileText size={18} color="#0f62fe" />
              <h2 className="panel-title">Select Civic Report</h2>
            </div>
            <span className="count-pill">
              {filteredReports.length} of {reports.length}
            </span>
          </div>

          {/* Search bar */}
          <div className="evidence-search-box">
            <Search size={15} color="#64748b" />
            <input
              type="text"
              placeholder="Search title, text, area, source..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="evidence-search-input"
            />
            {searchQuery && (
              <button className="evidence-search-clear" onClick={() => setSearchQuery('')}>
                <X size={13} />
              </button>
            )}
          </div>

          {/* Category Filter Pills */}
          <div className="evidence-filter-row">
            <span className="filter-row-label">Category:</span>
            <div className="filter-pills-scroll">
              {['ALL', 'TRAFFIC', 'WEATHER', 'OTHER'].map((cat) => (
                <button
                  key={cat}
                  className={`evidence-pill ${categoryFilter === cat ? 'active' : ''}`}
                  onClick={() => setCategoryFilter(cat)}
                >
                  {cat}
                </button>
              ))}
            </div>
          </div>

          {/* Confidence Tier Filter Pills */}
          <div className="evidence-filter-row">
            <span className="filter-row-label">Tier:</span>
            <div className="filter-pills-scroll">
              {['ALL', 'HIGH', 'MODERATE', 'LOW', 'UNASSESSED'].map((tier) => (
                <button
                  key={tier}
                  className={`evidence-pill ${tierFilter === tier ? 'active' : ''}`}
                  onClick={() => setTierFilter(tier)}
                >
                  {tier}
                </button>
              ))}
            </div>
          </div>

          {/* Report List */}
          <div className="evidence-report-list">
            {loadingList ? (
              <div className="evidence-loading-state">
                <RefreshCw size={24} className="animate-spin" color="#0f62fe" />
                <span>Loading civic reports...</span>
              </div>
            ) : filteredReports.length === 0 ? (
              <div className="evidence-empty-list">
                <Info size={28} color="#94a3b8" />
                <p>No reports match your filters.</p>
                <button
                  className="btn-sync"
                  style={{ marginTop: '8px', fontSize: '0.8rem', padding: '6px 12px' }}
                  onClick={() => {
                    setSearchQuery('');
                    setCategoryFilter('ALL');
                    setTierFilter('ALL');
                  }}
                >
                  Reset Filters
                </button>
              </div>
            ) : (
              filteredReports.map((report) => {
                const isSelected = report.id === selectedReportId;
                const tier = (report.confidence_tier || 'UNASSESSED').toLowerCase();
                const isAssessed =
                  typeof report.confidence === 'number' && !isNaN(report.confidence);

                return (
                  <div
                    key={report.id}
                    className={`evidence-report-card ${isSelected ? 'selected' : ''}`}
                    onClick={() => setSelectedReportId(report.id)}
                  >
                    <div className="report-card-header">
                      <span className={`category-tag cat-${(report.category || 'other').toLowerCase()}`}>
                        {report.category === 'TRAFFIC' && <Car size={11} />}
                        {report.category === 'WEATHER' && <CloudRain size={11} />}
                        {report.category !== 'TRAFFIC' && report.category !== 'WEATHER' && (
                          <AlertTriangle size={11} />
                        )}
                        <span>{report.category}</span>
                      </span>

                      {isAssessed ? (
                        <span className={`confidence-pill tier-${tier}`} style={{ fontSize: '0.72rem', padding: '2px 8px' }}>
                          <ShieldCheck size={12} />
                          <span>{(report.confidence * 100).toFixed(0)}%</span>
                        </span>
                      ) : (
                        <span className="confidence-pill tier-unassessed" style={{ fontSize: '0.72rem', padding: '2px 8px' }}>
                          <HelpCircle size={12} />
                          <span>Unassessed</span>
                        </span>
                      )}
                    </div>

                    <h4 className="report-card-title">{report.title}</h4>

                    <div className="report-card-footer">
                      <span className="source-pill" style={{ fontSize: '0.7rem' }}>
                        {report.source || 'Unknown Source'}
                      </span>
                      {report.event_time && (
                        <span className="card-time-text">
                          <Clock size={11} />
                          <span>{report.event_time.slice(0, 16).replace('T', ' ')}</span>
                        </span>
                      )}
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Right Column: Detailed Evidence Inspection */}
        <div className="evidence-detail-panel">
          {loadingDetail && (
            <div className="detail-loading-overlay">
              <RefreshCw size={24} className="animate-spin" color="#0f62fe" />
              <span>Loading report details...</span>
            </div>
          )}

          {!activeReport ? (
            <div className="detail-placeholder">
              <ShieldCheck size={48} color="#cbd5e1" />
              <h3>No Report Selected</h3>
              <p>Select a civic report from the left panel to inspect its supporting evidence and confidence factors.</p>
            </div>
          ) : (
            <div className="evidence-detail-scrollable">
              {/* Report Header Card */}
              <div className="detail-header-card">
                <div className="detail-header-top">
                  <div className="detail-header-tags">
                    <span className={`category-tag cat-${(activeReport.category || 'other').toLowerCase()}`}>
                      {activeReport.category === 'TRAFFIC' && <Car size={13} />}
                      {activeReport.category === 'WEATHER' && <CloudRain size={13} />}
                      {activeReport.category !== 'TRAFFIC' && activeReport.category !== 'WEATHER' && (
                        <AlertTriangle size={13} />
                      )}
                      <span>{activeReport.category}</span>
                    </span>
                    <span className="source-pill">{activeReport.source}</span>
                    {activeReport.source_type && (
                      <span className="source-type-chip">Type: {activeReport.source_type}</span>
                    )}
                  </div>
                  <div className="report-id-code">ID: {activeReport.id}</div>
                </div>

                <h2 className="detail-report-title">{activeReport.title}</h2>

                <div className="detail-meta-grid">
                  <div className="meta-grid-item">
                    <MapPin size={14} color="#0f62fe" />
                    <div>
                      <div className="meta-item-label">Reported Location</div>
                      <div className="meta-item-val">{activeReport.location || 'Bengaluru (General)'}</div>
                    </div>
                  </div>

                  <div className="meta-grid-item">
                    <Clock size={14} color="#0f62fe" />
                    <div>
                      <div className="meta-item-label">Incident Event Time</div>
                      <div className="meta-item-val">{activeReport.event_time || 'Not specified'}</div>
                    </div>
                  </div>

                  <div className="meta-grid-item">
                    <Database size={14} color="#0f62fe" />
                    <div>
                      <div className="meta-item-label">Ingested In Database</div>
                      <div className="meta-item-val">{activeReport.ingested_at || 'Not recorded'}</div>
                    </div>
                  </div>

                  <div className="meta-grid-item">
                    <Layers size={14} color="#0f62fe" />
                    <div>
                      <div className="meta-item-label">GPS Coordinates</div>
                      <div className="meta-item-val">
                        {activeReport.latitude !== null && activeReport.latitude !== undefined && activeReport.longitude !== null && activeReport.longitude !== undefined
                          ? `${activeReport.latitude}, ${activeReport.longitude}`
                          : 'Coordinates unavailable'}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* Confidence Assessment Panel */}
              <div className="detail-section-card">
                <div className="section-card-header">
                  <div className="section-title-wrap">
                    <ShieldCheck size={18} color="#0f62fe" />
                    <h3 className="section-title">Confidence Assessment</h3>
                  </div>
                  <span className="scientific-disclaimer-pill" title="Heuristic verification assessment, not calibrated probabilities">
                    Heuristic Assessment
                  </span>
                </div>

                <div className="confidence-assessment-body">
                  {hasConfidenceAssessment ? (
                    <div className="confidence-display-row">
                      <div className="confidence-primary-score">
                        <div className="score-number">
                          {(activeReport.confidence * 100).toFixed(0)}%
                        </div>
                        <div className="score-caption">
                          Stored Score: <code>{activeReport.confidence.toFixed(4)}</code>
                        </div>
                      </div>

                      <div className="confidence-tier-info">
                        <div className="tier-badge-row">
                          <span className="tier-badge-label">CONFIDENCE TIER:</span>
                          <span className={`confidence-pill tier-${(activeReport.confidence_tier || '').toLowerCase()}`}>
                            {activeReport.confidence_tier}
                          </span>
                        </div>
                        <p className="tier-description">
                          {activeReport.confidence_tier === 'HIGH' &&
                            'High verification assessment based on multi-source confirmation and authoritative feeds.'}
                          {activeReport.confidence_tier === 'MODERATE' &&
                            'Moderate verification assessment with partial corroboration or standard single-feed source.'}
                          {activeReport.confidence_tier === 'LOW' &&
                            'Low confidence heuristic rating; single unverified source or uncorroborated report.'}
                        </p>
                      </div>
                    </div>
                  ) : (
                    <div className="unassessed-banner">
                      <HelpCircle size={24} color="#64748b" />
                      <div>
                        <div className="unassessed-title">Assessment Not Available</div>
                        <p className="unassessed-desc">
                          This report has no recorded confidence score or tier in the database.
                          This indicates the report was ingested without running the verification scoring algorithm, rather than receiving a low-confidence score.
                        </p>
                      </div>
                    </div>
                  )}

                  <div className="confidence-note-box">
                    <Info size={14} color="#64748b" />
                    <span>
                      <strong>Important Limitation:</strong> Confidence scores reflect stored heuristic verification metrics computed by the ingestion pipeline. They represent comparative rule-based indicators and are not calibrated statistical probabilities.
                    </span>
                  </div>
                </div>
              </div>

              {/* CHEF Factor Breakdown Panel */}
              <div className="detail-section-card">
                <div className="section-card-header">
                  <div className="section-title-wrap">
                    <SlidersHorizontal size={18} color="#0f62fe" />
                    <h3 className="section-title">CHEF Factor Analysis</h3>
                  </div>
                  <span className="factors-count-chip">
                    {activeReport.chef_factors && typeof activeReport.chef_factors === 'object'
                      ? `${Object.keys(activeReport.chef_factors).length} Factors Recorded`
                      : '0 Factors'}
                  </span>
                </div>

                <div className="chef-factors-body">
                  {!activeReport.chef_factors ||
                  typeof activeReport.chef_factors !== 'object' ||
                  Array.isArray(activeReport.chef_factors) ||
                  Object.keys(activeReport.chef_factors).length === 0 ? (
                    <div className="no-factors-notice">
                      <Info size={20} color="#64748b" />
                      <div>
                        <strong>No CHEF factors available for this report.</strong>
                        <p>The report record does not contain individual factor breakdown attributes.</p>
                      </div>
                    </div>
                  ) : (
                    <div className="factors-grid">
                      {Object.entries(activeReport.chef_factors).map(([key, value]) => {
                        const isNumber = typeof value === 'number' && !isNaN(value);
                        const numVal = isNumber ? value : 0;
                        const formattedTitle = key
                          .replace(/_/g, ' ')
                          .replace(/\b\w/g, (c) => c.toUpperCase());

                        return (
                          <div key={key} className="factor-metric-card">
                            <div className="factor-metric-top">
                              <div className="factor-name-wrap">
                                <span className="factor-readable-name">{formattedTitle}</span>
                                <code className="factor-raw-key">{key}</code>
                              </div>
                              <div className="factor-value-pill">
                                {isNumber ? `${(numVal * 100).toFixed(0)}%` : String(value)}
                              </div>
                            </div>

                            {isNumber && (
                              <div className="factor-bar-track">
                                <div
                                  className="factor-bar-fill"
                                  style={{
                                    width: `${Math.min(100, Math.max(0, numVal * 100))}%`,
                                    backgroundColor:
                                      numVal >= 0.75
                                        ? '#059669'
                                        : numVal >= 0.4
                                        ? '#d97706'
                                        : '#dc2626'
                                  }}
                                />
                              </div>
                            )}

                            <div className="factor-metric-meta">
                              <span>Actual stored value:</span>
                              <code>{isNumber ? numVal.toFixed(4) : JSON.stringify(value)}</code>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              </div>

              {/* Source Evidence & Verbatim Text Panel */}
              <div className="detail-section-card">
                <div className="section-card-header">
                  <div className="section-title-wrap">
                    <Database size={18} color="#0f62fe" />
                    <h3 className="section-title">Source Evidence & Verbatim Text</h3>
                  </div>
                  {activeReport.url && (
                    <a
                      href={activeReport.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="source-external-link"
                    >
                      <span>Visit Source URL</span>
                      <ExternalLink size={13} />
                    </a>
                  )}
                </div>

                <div className="source-evidence-body">
                  <div className="evidence-meta-row">
                    <div className="evidence-meta-cell">
                      <span className="meta-cell-label">SOURCE PROVIDER:</span>
                      <span className="meta-cell-value">{activeReport.source || 'Unavailable'}</span>
                    </div>
                    <div className="evidence-meta-cell">
                      <span className="meta-cell-label">FEED TYPE:</span>
                      <span className="meta-cell-value">{activeReport.source_type || 'Unavailable'}</span>
                    </div>
                    <div className="evidence-meta-cell">
                      <span className="meta-cell-label">SOURCE URL:</span>
                      <span className="meta-cell-value">
                        {activeReport.url ? (
                          <a
                            href={activeReport.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="url-link"
                          >
                            {activeReport.url}
                          </a>
                        ) : (
                          <span className="missing-text">Not provided by source feed</span>
                        )}
                      </span>
                    </div>
                  </div>

                  <div className="raw-text-wrapper">
                    <div className="raw-text-header">
                      <span>Verbatim Report Body / Ingested Content:</span>
                      <span className="char-count">
                        {(activeReport.raw_text || '').length} characters
                      </span>
                    </div>
                    <div className="raw-text-box">
                      {activeReport.raw_text || <span className="missing-text">No raw text recorded</span>}
                    </div>
                  </div>
                </div>
              </div>

              {/* Evidence Completeness Audit Panel */}
              <div className="detail-section-card">
                <div className="section-card-header">
                  <div className="section-title-wrap">
                    <CheckCircle2 size={18} color="#0f62fe" />
                    <h3 className="section-title">Evidence Completeness Audit</h3>
                  </div>
                  <div className="completeness-summary-badge">
                    <strong>{presentCount}</strong> of <strong>{totalCount}</strong> Attributes Present
                  </div>
                </div>

                <div className="completeness-body">
                  <p className="completeness-intro">
                    Audit of stored attributes verifying presence of geographic coordinates, timestamps, raw text, and verification metrics:
                  </p>

                  <div className="completeness-grid">
                    {completenessItems.map((item, idx) => (
                      <div
                        key={idx}
                        className={`completeness-item-card ${item.available ? 'item-present' : 'item-missing'}`}
                      >
                        <div className="item-icon-col">
                          {item.available ? (
                            <CheckCircle2 size={17} color="#059669" />
                          ) : (
                            <XCircle size={17} color="#94a3b8" />
                          )}
                        </div>
                        <div className="item-content-col">
                          <div className="item-label">{item.label}</div>
                          <div className="item-val">{item.value}</div>
                        </div>
                        <div className="item-status-col">
                          <span className={`status-pill ${item.available ? 'pill-present' : 'pill-missing'}`}>
                            {item.available ? 'Present' : 'Missing'}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>

                  <div className="completeness-footer-note">
                    <Info size={13} color="#64748b" />
                    <span>Completeness reflects the physical availability of schema fields in the database record and does not calculate a composite score.</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
