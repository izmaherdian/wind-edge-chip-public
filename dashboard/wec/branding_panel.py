"""CITA footer and readable specification typography for the Hackathon page."""
import base64
from pathlib import Path

MARKER = '<!-- wec-cita-branding-v3 -->'
LEGACY_MARKERS = ('<!-- wec-cita-branding-v1 -->', '<!-- wec-cita-branding-v2 -->')
CSS = '''
    /* CITA identity and specification hierarchy */
    .wec-v2.wec-hk .wec-specs .about-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 24px; align-items: stretch;
    }
    .wec-v2.wec-hk .wec-specs .spec-card { display: flex; flex-direction: column; }
    .wec-v2.wec-hk .wec-specs .card-header {
        font-size: 20px !important; font-weight: 600; color: var(--k-ink) !important;
        margin-bottom: 18px; padding-bottom: 12px; border-bottom: 1px solid var(--k-rule);
    }
    .wec-v2.wec-hk .wec-specs .glass-inner {
        padding: 0 20px !important; flex: 1; display: flex; background: var(--k-deep) !important;
    }
    .wec-v2.wec-hk .wec-specs .spec-table { width: 100%; border-collapse: collapse; }
    .wec-v2.wec-hk .wec-specs .spec-table td {
        padding: 20px 0; font-family: var(--k-font); font-size: 16px;
        line-height: 1.5; color: var(--k-muted); vertical-align: middle;
        border-bottom: 1px solid var(--k-rule);
    }
    .wec-v2.wec-hk .wec-specs .spec-table tr:last-child td { border-bottom: 0; }
    .wec-v2.wec-hk .wec-specs .spec-table td.val {
        width: 58%; padding-left: 20px; font-size: clamp(22px, 2vw, 28px);
        font-family: var(--k-display); font-weight: 400; letter-spacing: -.02em;
        color: var(--k-ink) !important; text-align: right;
        font-variant-numeric: tabular-nums; line-height: 1.35; overflow-wrap: anywhere;
    }
    .wec-v2.wec-hk .wec-specs .spec-table .spec-location {
        display: block; margin-top: 6px; font-family: var(--k-font); letter-spacing: 0; font-size: 15px; font-weight: 400; color: var(--k-muted);
    }
    .wec-v2.wec-hk .project-footer.wec-cita-footer {
        display: flex; flex-direction: row; align-items: center; justify-content: center; gap: 24px;
        margin-top: 48px; padding: 32px 0 12px; text-align: left;
    }
    .wec-v2.wec-hk .wec-cita-logo {
        display: block; width: 180px; max-width: 100%; height: auto; flex: 0 0 auto;
        padding: 10px 12px; box-sizing: content-box; border-radius: 10px; background: #fff;
    }
    .wec-v2.wec-hk .wec-cita-identity { min-width: 0; }
    .wec-v2.wec-hk .wec-cita-name {
        display: block; font-family: var(--k-display); font-size: 28px; font-weight: 400;
        line-height: 1.3; letter-spacing: -.02em; color: var(--k-ink);
    }
    .wec-v2.wec-hk .wec-cita-footer .lab-name {
        margin-top: 6px; max-width: 44ch; font-family: var(--k-font); font-size: 15px;
        line-height: 1.5; font-weight: 400; letter-spacing: 0; color: var(--k-muted);
    }
    @media (max-width: 760px) {
        .wec-v2.wec-hk .project-footer.wec-cita-footer { gap: 14px; }
        .wec-v2.wec-hk .wec-cita-logo { width: 96px; padding: 8px; }
        .wec-v2.wec-hk .wec-cita-name { font-size: 24px; }
        .wec-v2.wec-hk .wec-cita-footer .lab-name { font-size: 13px; }
        .wec-v2.wec-hk .wec-specs .about-grid { grid-template-columns: minmax(0, 1fr); gap: 16px; }
        .wec-v2.wec-hk .wec-specs .glass-inner { padding: 0 16px !important; }
        .wec-v2.wec-hk .wec-specs .spec-table td { font-size: 15px; padding: 18px 0; }
        .wec-v2.wec-hk .wec-specs .spec-table td.val { font-size: 22px; padding-left: 12px; }
    }
'''


def patch_branding(s):
    if MARKER in s:
        return s
    legacy_marker = next((m for m in LEGACY_MARKERS if m in s), None)
    if legacy_marker:
        # The earlier presentation CSS was appended last; replace that bounded block.
        css_start = s.index('    /* CITA identity and specification hierarchy */')
        css_end = s.rindex('</style>')
        s = s[:css_start] + s[css_end:]
        start = s.index(legacy_marker)
    else:
        anchor = '<section class="relative-z mt-4" aria-labelledby="wecSpecsTitle">'
        assert s.count(anchor) == 1, 'Specification section changed'
        s = s.replace(anchor, '<section class="wec-specs relative-z mt-4" aria-labelledby="wecSpecsTitle">')
        s = s.replace('7,5 m di atas atap Gedung CRIMSE', '7,5 m<span class="spec-location">di atas atap Gedung CRIMSE</span>', 1)
        start = s.index('<div class="project-footer relative-z">')
    end = s.index('        <div class="toast-wrapper', start)
    logo = base64.b64encode((Path(__file__).parent / 'assets/logo-cita.png').read_bytes()).decode('ascii')
    footer = f'''{MARKER}
        <footer class="project-footer wec-cita-footer relative-z">
            <img class="wec-cita-logo" src="data:image/png;base64,{logo}" alt="CITA ITB" width="200" height="38">
            <div class="wec-cita-identity">
                <strong class="wec-cita-name">CITA-ITB</strong>
                <div class="lab-name">Center Instrumentation Technology and Automation</div>
            </div>
        </footer>

'''
    s = s[:start] + footer + s[end:]
    pos = s.rindex('</style>')
    return s[:pos] + CSS + s[pos:]
