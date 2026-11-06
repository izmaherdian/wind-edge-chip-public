"""Presentation-only rotor calibration and concise turbine specifications."""

MARKER = '<!-- wec-twin-presentation-v1 -->'
SPECS = '''        <!-- wec-twin-presentation-v1 -->
        <section class="relative-z mt-4" aria-labelledby="wecSpecsTitle">
            <div class="section-divider">
                <h3 id="wecSpecsTitle" class="dash-title" style="text-align:left;font-size:1.4rem;padding-left:5px;">Spesifikasi</h3>
            </div>
            <div class="dashboard-grid about-grid">
                <div class="card glass-panel spec-card">
                    <div class="card-header">Generator</div>
                    <div class="glass-inner" style="padding:10px;">
                        <table class="spec-table">
                            <tr><td>Tipe generator</td><td class="val">3 fase · 1 kW</td></tr>
                            <tr><td>Daya maksimum</td><td class="val highlight">1 kW</td></tr>
                        </table>
                    </div>
                </div>
                <div class="card glass-panel spec-card">
                    <div class="card-header">Turbin</div>
                    <div class="glass-inner" style="padding:10px;">
                        <table class="spec-table">
                            <tr><td>Tinggi menara</td><td class="val">7,5 m di atas atap Gedung CRIMSE</td></tr>
                            <tr><td>Diameter rotor</td><td class="val">2,5 m</td></tr>
                            <tr><td>Radius rotor</td><td class="val">1,25 m</td></tr>
                        </table>
                    </div>
                </div>
            </div>
        </section>

        '''


def patch_twin_presentation(s):
    if MARKER in s:
        return s
    start = s.index('        <!-- SECTION: Spesifikasi dan teori sistem -->')
    end = s.index('<div class="project-footer', start)
    s = s[:start] + SPECS + s[end:]
    old = 'R.angle += R.rpmNow / 60 * 2 * Math.PI * dt * 0.25;               // diperlambat 4x agar terbaca mata'
    new = '''// Acuan visual pengguna: live 3,7 m/s setara demo 7 m/s; bukan kalibrasi RPM terukur.
                    const visualGain = this.twin.mode === 'live' ? 7 / 3.7 : 1;
                    R.angle += R.rpmNow / 60 * 2 * Math.PI * dt * 0.25 * visualGain;'''
    assert s.count(old) == 1, 'Anchor animasi berubah'
    s = s.replace(old, new)
    old_note = 'Putaran rotor dihitung dari angin (perkiraan tip-speed), bukan diukur.'
    assert s.count(old_note) == 1, 'Anchor catatan putaran berubah'
    return s.replace(old_note, old_note + ' Kecepatan animasi live disesuaikan secara visual: angin 3,7 m/s setara putaran demo 7 m/s; bukan pembacaan RPM.')
