import React, { useState, useEffect, useRef, useMemo } from 'react';
import { Layers, MapPin, Filter, Eye, RefreshCw, AlertTriangle, Car, CloudRain, ShieldCheck, X } from 'lucide-react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';

// Fix default leaflet marker icon path in bundled applications
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

export default function BengaluruMap({
  reports = [],
  selectedLocality = 'ALL',
  activeCategory = 'ALL',
  onSelectReport,
  onSelectLocality
}) {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const geojsonLayerRef = useRef(null);
  const markersLayerRef = useRef(null);

  const [geoData, setGeoData] = useState(null);
  const [loadingGeo, setLoadingGeo] = useState(true);
  const [loadError, setLoadError] = useState(null);

  // Map controls & filters
  const [showChoropleth, setShowChoropleth] = useState(false);
  const [selectedAgency, setSelectedAgency] = useState('ALL');
  const [selectedConfidence, setSelectedConfidence] = useState('ALL');
  const [categoryFilter, setCategoryFilter] = useState(activeCategory);
  const [selectedWard, setSelectedWard] = useState(null);
  const [selectedIncident, setSelectedIncident] = useState(null);

  // Sync category filter with parent prop
  useEffect(() => {
    setCategoryFilter(activeCategory);
  }, [activeCategory]);

  // 1. Fetch Authoritative 225-Ward GeoJSON
  useEffect(() => {
    let isMounted = true;
    async function loadWards() {
      setLoadingGeo(true);
      try {
        // Try local static endpoint first, fallback to backend API
        let res = await fetch('/bengaluru_wards_225.geojson');
        if (!res.ok) {
          res = await fetch('http://localhost:8000/geo/wards/geojson');
        }
        if (!res.ok) throw new Error('Could not load Bengaluru 225-ward boundaries.');
        const data = await res.json();
        if (isMounted) {
          setGeoData(data);
          setLoadingGeo(false);
        }
      } catch (err) {
        if (isMounted) {
          console.warn('GeoJSON fetch error, falling back to backend API:', err);
          try {
            const apiRes = await fetch('http://localhost:8000/geo/wards/geojson');
            if (apiRes.ok) {
              const apiData = await apiRes.json();
              setGeoData(apiData);
            } else {
              setLoadError('Failed to load Bengaluru ward boundaries.');
            }
          } catch (e2) {
            setLoadError('Failed to load Bengaluru ward boundaries.');
          }
          setLoadingGeo(false);
        }
      }
    }
    loadWards();
    return () => {
      isMounted = false;
    };
  }, []);

  // Filter reports with valid coordinates
  const filteredReports = useMemo(() => {
    return reports.filter((r) => {
      if (!r.latitude || !r.longitude) return false;
      const lat = parseFloat(r.latitude);
      const lon = parseFloat(r.longitude);
      if (isNaN(lat) || isNaN(lon) || lat < 12.0 || lat > 14.0 || lon < 76.5 || lon > 78.5) return false;

      // Category filter
      if (categoryFilter !== 'ALL' && r.category !== categoryFilter) return false;

      // Agency filter
      if (selectedAgency !== 'ALL') {
        const agencyStr = (r.source || r.source_type || '').toUpperCase();
        if (!agencyStr.includes(selectedAgency.toUpperCase())) return false;
      }

      // Confidence tier
      if (selectedConfidence !== 'ALL' && r.confidence_tier !== selectedConfidence) return false;

      return true;
    });
  }, [reports, categoryFilter, selectedAgency, selectedConfidence]);

  // Aggregate incidents per ward for choropleth
  const wardIncidentCounts = useMemo(() => {
    const counts = {};
    filteredReports.forEach((r) => {
      const loc = (r.location || '').toLowerCase();
      if (loc) {
        counts[loc] = (counts[loc] || 0) + 1;
      }
    });
    return counts;
  }, [filteredReports]);

  // 2. Initialize Leaflet Map Instance
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // Center on Bengaluru [12.9716, 77.5946]
    const map = L.map(mapContainerRef.current, {
      center: [12.9716, 77.5946],
      zoom: 11,
      minZoom: 10,
      maxZoom: 18,
      zoomControl: false
    });

    // Clean civic carto tile layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | BBMP Bengaluru',
      
      maxZoom: 19
    }).addTo(map);

    L.control.zoom({ position: 'bottomright' }).addTo(map);

    markersLayerRef.current = L.layerGroup().addTo(map);
    mapInstanceRef.current = map;

    return () => {
      map.remove();
      mapInstanceRef.current = null;
    };
  }, []);

  // 3. Render 225 Ward Polygons on Map
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !geoData) return;

    if (geojsonLayerRef.current) {
      map.removeLayer(geojsonLayerRef.current);
    }

    const maxIncidents = Math.max(1, ...Object.values(wardIncidentCounts));

    function getWardColor(feature) {
      if (!showChoropleth) {
        return '#0f62fe';
      }
      const name = (feature.properties?.name_en || '').toLowerCase();
      const count = wardIncidentCounts[name] || 0;
      if (count === 0) return '#cbd5e1'; // No incidents: neutral slate
      const ratio = count / maxIncidents;
      if (ratio > 0.66) return '#ef4444'; // High incident density: red
      if (ratio > 0.33) return '#f97316'; // Moderate: orange
      return '#3b82f6'; // Low: blue
    }

    const geoLayer = L.geoJSON(geoData, {
      style: (feature) => {
        const isSelected = selectedWard && selectedWard.id === feature.properties.id;
        return {
          color: isSelected ? '#ea580c' : getWardColor(feature),
          weight: isSelected ? 3 : 1.2,
          opacity: isSelected ? 1.0 : 0.7,
          fillColor: isSelected ? '#fed7aa' : getWardColor(feature),
          fillOpacity: isSelected ? 0.45 : showChoropleth ? 0.35 : 0.08
        };
      },
      onEachFeature: (feature, layer) => {
        const p = feature.properties || {};
        const wardId = p.id;
        const nameEn = p.name_en || p.proposed_ward_name_en;
        const nameKa = p.name_ka || '';
        const acName = p.assembly_constituency_name_en || '';
        const pop = p.population ? Number(p.population).toLocaleString() : 'N/A';
        const area = p.ward_area ? `${parseFloat(p.ward_area).toFixed(2)} kmÂ²` : 'N/A';

        // Tooltip on hover
        layer.bindTooltip(
          `<strong>Ward ${wardId}: ${nameEn}</strong><br/>AC: ${acName}<br/>Pop: ${pop}`,
          { sticky: true, className: 'ward-map-tooltip' }
        );

        // Click ward
        layer.on('click', (e) => {
          L.DomEvent.stopPropagation(e);
          setSelectedWard(p);
          if (onSelectLocality) {
            onSelectLocality(nameEn);
          }
          if (layer.getBounds) {
            map.fitBounds(layer.getBounds(), { padding: [40, 40], maxZoom: 14 });
          }
        });

        // Hover highlight
        layer.on('mouseover', () => {
          if (!selectedWard || selectedWard.id !== p.id) {
            layer.setStyle({ weight: 2.2, fillOpacity: 0.25, color: '#0284c7' });
          }
        });
        layer.on('mouseout', () => {
          if (!selectedWard || selectedWard.id !== p.id) {
            geoLayer.resetStyle(layer);
          }
        });
      }
    });

    geoLayer.addTo(map);
    geojsonLayerRef.current = geoLayer;

    // Fit map bounds to full Bengaluru 225 ward bounds on initial load
    if (!selectedWard) {
      map.fitBounds(geoLayer.getBounds(), { padding: [15, 15] });
    }
  }, [geoData, showChoropleth, selectedWard, wardIncidentCounts, onSelectLocality]);

  // 4. Render Incident Markers
  useEffect(() => {
    const map = mapInstanceRef.current;
    const markersGroup = markersLayerRef.current;
    if (!map || !markersGroup) return;

    markersGroup.clearLayers();

    filteredReports.forEach((report) => {
      const lat = parseFloat(report.latitude);
      const lon = parseFloat(report.longitude);
      const isTraffic = report.category === 'TRAFFIC';
      const isWeather = report.category === 'WEATHER';
      const markerColor = isTraffic ? '#ea580c' : isWeather ? '#0284c7' : '#7c3aed';
      const confPct = report.confidence == null ? null : Math.round(report.confidence * 100);

      // Custom pulsing circle marker
      const marker = L.circleMarker([lat, lon], {
        radius: 7,
        fillColor: markerColor,
        color: '#ffffff',
        weight: 2,
        opacity: 1,
        fillOpacity: 0.9
      });

      marker.bindTooltip(
        `<strong>${report.title}</strong><br/>Category: ${report.category} (${confPct == null ? "N/A" : `${confPct}% confidence`})<br/>Location: ${report.location || 'Bengaluru'}`,
        { direction: 'top', className: 'ward-map-tooltip' }
      );

      marker.on('click', (e) => {
        L.DomEvent.stopPropagation(e);
        setSelectedIncident(report);
        if (onSelectReport) {
          onSelectReport(report);
        }
      });

      markersGroup.addLayer(marker);
    });
  }, [filteredReports, onSelectReport]);

  const handleResetView = () => {
    setSelectedWard(null);
    setSelectedIncident(null);
    if (onSelectLocality) onSelectLocality('ALL');
    if (mapInstanceRef.current && geojsonLayerRef.current) {
      mapInstanceRef.current.fitBounds(geojsonLayerRef.current.getBounds(), { padding: [15, 15] });
    }
  };

  return (
    <div className="bengaluru-radar-container">
      {/* Map Control Toolbar */}
      <div className="radar-header">
        <div className="radar-title-box">
          <Layers size={18} color="#0f62fe" />
          <span className="radar-title">BENGALURU 225-WARD CIVIC MAP</span>
          <span className="radar-badge">225 Verified Wards</span>
          <span className="radar-badge" style={{ background: '#dbeafe', color: '#1e40af' }}>
            {filteredReports.length} Geolocated Incidents
          </span>
          {selectedWard && (
            <span className="radar-active-locality-pill">
              Ward {selectedWard.id}: {selectedWard.name_en}
            </span>
          )}
        </div>

        {/* Filter Controls Bar */}
        <div className="map-toolbar-actions">
          {/* Category Filter */}
          <select
            className="map-filter-select"
            value={categoryFilter}
            onChange={(e) => setCategoryFilter(e.target.value)}
          >
            <option value="ALL">All Categories</option>
            <option value="TRAFFIC">Traffic Incidents</option>
            <option value="WEATHER">Weather Advisories</option>
            <option value="OTHER">Civic Complaints</option>
          </select>

          {/* Agency Filter */}
          <select
            className="map-filter-select"
            value={selectedAgency}
            onChange={(e) => setSelectedAgency(e.target.value)}
          >
            <option value="ALL">All Agencies</option>
            <option value="BBMP">BBMP</option>
            <option value="TRAFFIC POLICE">Traffic Police (BTP)</option>
            <option value="WEATHER">IMD / Weather</option>
          </select>

          {/* Choropleth Layer Toggle */}
          <button
            className={`map-toggle-btn ${showChoropleth ? 'active' : ''}`}
            onClick={() => setShowChoropleth(!showChoropleth)}
            title="Toggle Ward Incident Density Choropleth"
          >
            <Eye size={14} />
            <span>{showChoropleth ? 'Density: ON' : 'Choropleth'}</span>
          </button>

          {/* Reset Zoom Button */}
          <button className="map-toggle-btn" onClick={handleResetView} title="Reset to City View">
            <RefreshCw size={14} />
            <span>Reset View</span>
          </button>
        </div>
      </div>

      {/* Map Display Frame */}
      <div className="radar-svg-wrapper" style={{ height: '560px', position: 'relative' }}>
        {loadingGeo && (
          <div className="map-loading-overlay">
            <RefreshCw size={24} className="animate-spin" color="#0f62fe" />
            <span>Loading 225 Bengaluru Ward Boundaries...</span>
          </div>
        )}

        {loadError && (
          <div className="map-error-banner">
            <AlertTriangle size={18} color="#ef4444" />
            <span>{loadError}</span>
          </div>
        )}

        <div ref={mapContainerRef} style={{ width: '100%', height: '100%', zIndex: 1 }} />

        {/* Floating Ward Information Card */}
        {selectedWard && (
          <div className="ward-detail-card animate-fade-in">
            <div className="ward-detail-header">
              <div>
                <span className="ward-id-pill">Ward #{selectedWard.id}</span>
                <h4 className="ward-title">{selectedWard.name_en}</h4>
                {selectedWard.name_ka && (
                  <span className="ward-kannada-name">{selectedWard.name_ka}</span>
                )}
              </div>
              <button className="btn-close-card" onClick={() => setSelectedWard(null)}>
                <X size={14} />
              </button>
            </div>
            <div className="ward-detail-body">
              <div className="ward-stat-row">
                <span className="stat-label">Assembly Constituency:</span>
                <span className="stat-val">{selectedWard.assembly_constituency_name_en || 'Bengaluru'}</span>
              </div>
              <div className="ward-stat-row">
                <span className="stat-label">Parliamentary Seat:</span>
                <span className="stat-val">{selectedWard.parliamentary_constituency_name_en || 'Bengaluru'}</span>
              </div>
              <div className="ward-stat-row">
                <span className="stat-label">Population:</span>
                <span className="stat-val">
                  {selectedWard.population ? Number(selectedWard.population).toLocaleString() : 'N/A'}
                </span>
              </div>
              <div className="ward-stat-row">
                <span className="stat-label">Ward Area:</span>
                <span className="stat-val">
                  {selectedWard.ward_area ? `${parseFloat(selectedWard.ward_area).toFixed(2)} kmÂ²` : 'N/A'}
                </span>
              </div>
              <div className="ward-stat-row">
                <span className="stat-label">Active Incidents in Ward:</span>
                <span className="stat-val highlight">
                  {wardIncidentCounts[(selectedWard.name_en || '').toLowerCase()] || 0}
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Floating Selected Incident Card */}
        {selectedIncident && (
          <div className="incident-detail-card animate-fade-in">
            <div className="incident-card-top">
              <span className={`category-tag cat-${(selectedIncident.category || 'other').toLowerCase()}`}>
                {selectedIncident.category}
              </span>
              <span className="incident-conf-badge">
                                {selectedIncident.confidence == null ? 'N/A' : `${Math.round(selectedIncident.confidence * 100)}% Confidence`}
              </span>
              <button className="btn-close-card" onClick={() => setSelectedIncident(null)}>
                <X size={14} />
              </button>
            </div>
            <div className="incident-card-title">{selectedIncident.title}</div>
            <div className="incident-card-meta">
              <MapPin size={13} color="#0f62fe" />
              <span>{selectedIncident.location || 'Bengaluru'}</span>
            </div>
            {selectedIncident.source && (
              <div className="incident-card-agency">
                <ShieldCheck size={13} color="#16a34a" />
                <span>Source: {selectedIncident.source}</span>
              </div>
            )}
            <div className="incident-card-text">
              {selectedIncident.raw_text?.slice(0, 160)}
              {selectedIncident.raw_text?.length > 160 ? '...' : ''}
            </div>
          </div>
        )}

        {/* Map Legend */}
        <div className="map-legend-overlay">
          <div className="legend-title">INCIDENT TYPES</div>
          <div className="legend-item">
            <span className="legend-dot traffic" /> <span>Traffic (BTP)</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot weather" /> <span>Weather (IMD)</span>
          </div>
          <div className="legend-item">
            <span className="legend-dot other" /> <span>Civic / BBMP</span>
          </div>
          {showChoropleth && (
            <div className="choropleth-legend-block">
              <div className="legend-title" style={{ marginTop: '6px' }}>WARD INCIDENT DENSITY</div>
              <div className="density-scale">
                <span className="density-box" style={{ background: '#cbd5e1' }} title="0 Incidents" />
                <span className="density-box" style={{ background: '#3b82f6' }} title="Low Density" />
                <span className="density-box" style={{ background: '#f97316' }} title="Moderate Density" />
                <span className="density-box" style={{ background: '#ef4444' }} title="High Density" />
              </div>
              <div className="density-labels">
                <span>0</span>
                <span>Low</span>
                <span>High</span>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}


