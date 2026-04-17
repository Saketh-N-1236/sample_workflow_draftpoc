import React, { useState } from 'react';
import '../styles/App.css';

/* ─── tiny helpers ──────────────────────────────────────────────────── */
const MATCH_COLORS = {
  Semantic: { bg: '#f3e5f5', color: '#7b1fa2' },
  AST:      { bg: '#e8f5e9', color: '#2e7d32' },
  Both:     { bg: '#e1bee7', color: '#6a1b9a' },
};

function MatchBadge({ matchType }) {
  const c = MATCH_COLORS[matchType] || { bg: '#e0e0e0', color: '#666' };
  return (
    <span style={{
      display: 'inline-block', padding: '2px 8px', borderRadius: '4px',
      fontSize: '11px', background: c.bg, color: c.color,
    }}>
      {matchType || 'Unknown'}
    </span>
  );
}

/* ─── collapsible test list ─────────────────────────────────────────── */
function TestSection({ title, badge, badgeBg, badgeColor, borderColor, tests, defaultOpen = true }) {
  const [open, setOpen] = useState(defaultOpen);
  if (!tests.length) return null;
  return (
    <div style={{ marginBottom: '16px', border: `1px solid ${borderColor}`, borderRadius: '8px', overflow: 'hidden' }}>
      {/* header */}
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          width: '100%', display: 'flex', justifyContent: 'space-between',
          alignItems: 'center', padding: '12px 16px',
          background: badgeBg, border: 'none', cursor: 'pointer',
          fontSize: '14px', fontWeight: '600', color: badgeColor,
        }}
      >
        <span>{title}</span>
        <span style={{
          display: 'flex', alignItems: 'center', gap: '10px',
        }}>
          <span style={{
            background: badgeColor, color: '#fff', borderRadius: '12px',
            padding: '2px 10px', fontSize: '12px', fontWeight: '700',
          }}>
            {badge}
          </span>
          <span style={{ fontSize: '16px' }}>{open ? '▲' : '▼'}</span>
        </span>
      </button>

      {/* body */}
      {open && (
        <div style={{ maxHeight: '340px', overflowY: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '12px' }}>
            <thead>
              <tr style={{ background: '#f9f9f9', borderBottom: '2px solid #e0e0e0', position: 'sticky', top: 0, zIndex: 10 }}>
                <th style={{ padding: '8px 10px', textAlign: 'left', fontWeight: '600', color: '#555', width: '90px' }}>Test ID</th>
                <th style={{ padding: '8px 10px', textAlign: 'left', fontWeight: '600', color: '#555' }}>Test Name</th>
                <th style={{ padding: '8px 10px', textAlign: 'left', fontWeight: '600', color: '#555', width: '160px' }}>Class</th>
                <th style={{ padding: '8px 10px', textAlign: 'left', fontWeight: '600', color: '#555', width: '80px' }}>Match</th>
                <th style={{ padding: '8px 10px', textAlign: 'left', fontWeight: '600', color: '#555' }}>LLM Reason</th>
              </tr>
            </thead>
            <tbody>
              {tests.map((t, i) => {
                const depConf   = t.dependency_confidence;
                const depReason = t.dependency_reason;
                const depSrc    = t.dependency_source;
                const tooltip   = [
                  depReason && `Reason: ${depReason}`,
                  depConf   && `Confidence: ${depConf}`,
                  depSrc    && `Source: ${depSrc}`,
                ].filter(Boolean).join(' | ');
                return (
                  <tr key={i} style={{ borderBottom: '1px solid #f0f0f0', background: i % 2 === 0 ? '#fff' : '#fafafa' }}>
                    <td style={{ padding: '7px 10px', fontFamily: 'monospace', color: '#666', fontSize: '11px' }}>{t.test_id}</td>
                    <td style={{ padding: '7px 10px', color: '#333' }}>{t.method_name || 'N/A'}</td>
                    <td style={{ padding: '7px 10px', color: '#555', fontSize: '11px', maxWidth: '160px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{t.class_name || '—'}</td>
                    <td style={{ padding: '7px 10px' }}><MatchBadge matchType={t.match_type} /></td>
                    <td style={{ padding: '7px 10px' }}>
                      {depReason && (
                        <span
                          title={tooltip}
                          style={{
                            fontSize: '11px', color: '#555', cursor: 'help',
                            borderBottom: '1px dashed #999',
                            display: 'inline-block', maxWidth: '200px',
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                          }}
                        >
                          {depReason}
                        </span>
                      )}
                      {depConf && (
                        <span style={{
                          marginLeft: '6px', fontSize: '10px', padding: '1px 5px',
                          borderRadius: '3px',
                          background: depConf === 'high' ? '#e8f5e9' : depConf === 'medium' ? '#fff8e1' : '#fce4ec',
                          color:      depConf === 'high' ? '#2e7d32' : depConf === 'medium' ? '#f57f17' : '#b71c1c',
                        }}>
                          {depConf}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

/* ─── main modal ────────────────────────────────────────────────────── */
const TestSummaryModal = ({ isOpen, onClose, selectionResults, totalTestsInDb }) => {
  if (!isOpen) return null;

  const selectedTests = selectionResults?.tests || [];
  const selectedCount = selectedTests.length;

  const totalTests =
    selectionResults?.totalTestsInDb ||
    selectionResults?.total_tests_in_db ||
    totalTestsInDb || 0;

  const notSelectedCount = Math.max(0, totalTests - selectedCount);

  /* split by dependency_type */
  const independentTests    = selectedTests.filter(t => t.dependency_type === 'independent');
  const crossDependentTests = selectedTests.filter(t => t.dependency_type !== 'independent');

  /* use backend counts when available (more accurate) */
  const indCount   = selectionResults?.independentCount   ?? independentTests.length;
  const crossCount = selectionResults?.crossDependentCount ?? crossDependentTests.length;

  /* did LLM classify at least one test? */
  const llmClassified = selectedTests.filter(t => t.dependency_source === 'llm').length;
  const classSource   = llmClassified > 0
    ? `LLM (${llmClassified}/${selectedCount})`
    : 'Rule-based';

  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, backgroundColor: 'rgba(0,0,0,0.5)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000, padding: '20px',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        style={{
          backgroundColor: 'white', borderRadius: '10px', padding: '28px',
          maxWidth: '860px', width: '100%', maxHeight: '92vh', overflow: 'auto',
          boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
        }}
      >
        {/* ── Title bar ── */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '24px' }}>
          <div>
            <h2 style={{ margin: 0, fontSize: '22px', fontWeight: '700', color: '#222' }}>Test Selection Summary</h2>
            <span style={{
              fontSize: '11px', color: '#888', marginTop: '4px', display: 'inline-block',
            }}>
              Classification source: <strong style={{ color: llmClassified > 0 ? '#1976d2' : '#888' }}>{classSource}</strong>
            </span>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: '24px', cursor: 'pointer', color: '#888', lineHeight: 1 }}>×</button>
        </div>

        {/* ── Top stats row ── */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '14px', marginBottom: '24px' }}>
          {[
            { label: 'Total Tests',   val: totalTests,       bg: '#f5f5f5',  border: '#e0e0e0', color: '#333' },
            { label: 'Selected',      val: selectedCount,    bg: '#e8f5e9',  border: '#4caf50', color: '#2e7d32' },
            { label: 'Not Selected',  val: notSelectedCount, bg: '#ffebee',  border: '#f44336', color: '#c62828' },
          ].map(({ label, val, bg, border, color }) => (
            <div key={label} style={{ padding: '18px', background: bg, borderRadius: '8px', textAlign: 'center', border: `2px solid ${border}` }}>
              <div style={{ fontSize: '30px', fontWeight: 'bold', color, marginBottom: '6px' }}>{val}</div>
              <div style={{ fontSize: '13px', color }}>{label}</div>
              {label !== 'Total Tests' && totalTests > 0 && (
                <div style={{ fontSize: '11px', color: '#888', marginTop: '2px' }}>
                  {((val / totalTests) * 100).toFixed(1)}%
                </div>
              )}
            </div>
          ))}
        </div>

        {/* ── Match type breakdown ── */}
        {selectionResults && (
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px', marginBottom: '24px' }}>
            <div style={{ padding: '12px', background: '#e3f2fd', borderRadius: '6px', border: '1px solid #90caf9' }}>
              <div style={{ fontSize: '13px', color: '#666', marginBottom: '4px' }}>AST Matches</div>
              <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#1976d2' }}>{selectionResults.astMatches || 0}</div>
            </div>
            <div style={{ padding: '12px', background: '#f3e5f5', borderRadius: '6px', border: '1px solid #ce93d8' }}>
              <div style={{ fontSize: '13px', color: '#666', marginBottom: '4px' }}>Semantic Matches</div>
              <div style={{ fontSize: '20px', fontWeight: 'bold', color: '#7b1fa2' }}>{selectionResults.semanticMatches || 0}</div>
            </div>
          </div>
        )}

        {/* ── Dependency classification summary cards ── */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '14px', marginBottom: '24px' }}>
          <div style={{
            padding: '16px 18px', background: '#e8f5e9', borderRadius: '8px',
            border: '2px solid #4caf50', display: 'flex', alignItems: 'center', gap: '14px',
          }}>
            <span style={{ fontSize: '28px' }}>🎯</span>
            <div>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#2e7d32' }}>{indCount}</div>
              <div style={{ fontSize: '13px', color: '#2e7d32', fontWeight: '600' }}>Independent</div>
              <div style={{ fontSize: '11px', color: '#666', marginTop: '2px' }}>
                Directly test the changed code
              </div>
            </div>
          </div>
          <div style={{
            padding: '16px 18px', background: '#fff3e0', borderRadius: '8px',
            border: '2px solid #ff9800', display: 'flex', alignItems: 'center', gap: '14px',
          }}>
            <span style={{ fontSize: '28px' }}>🔗</span>
            <div>
              <div style={{ fontSize: '24px', fontWeight: 'bold', color: '#e65100' }}>{crossCount}</div>
              <div style={{ fontSize: '13px', color: '#e65100', fontWeight: '600' }}>Cross-dependent</div>
              <div style={{ fontSize: '11px', color: '#666', marginTop: '2px' }}>
                Indirectly affected via import chain or semantic match
              </div>
            </div>
          </div>
        </div>

        {/* ── Classified test lists ── */}
        {selectedTests.length > 0 ? (
          <>
            <TestSection
              title="Independent Tests"
              badge={independentTests.length}
              badgeBg="#e8f5e9"
              badgeColor="#2e7d32"
              borderColor="#4caf50"
              tests={independentTests}
              defaultOpen={true}
            />
            <TestSection
              title="Cross-dependent Tests"
              badge={crossDependentTests.length}
              badgeBg="#fff3e0"
              badgeColor="#e65100"
              borderColor="#ff9800"
              tests={crossDependentTests}
              defaultOpen={crossDependentTests.length <= 20}
            />
          </>
        ) : (
          <div style={{ padding: '24px', textAlign: 'center', color: '#999', background: '#f9f9f9', borderRadius: '8px', marginBottom: '16px' }}>
            No tests were selected for this diff.
          </div>
        )}

        {/* ── Close button ── */}
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginTop: '20px' }}>
          <button
            onClick={onClose}
            style={{
              padding: '10px 28px', background: '#1976d2', color: 'white',
              border: 'none', borderRadius: '6px', cursor: 'pointer',
              fontSize: '14px', fontWeight: '600',
            }}
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default TestSummaryModal;
