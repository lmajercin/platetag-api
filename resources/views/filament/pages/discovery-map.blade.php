<x-filament-panels::page>
    <style>
        .pt-map-shell {
            border-radius: 1rem; overflow: hidden;
            border: 1px solid rgba(17,24,39,0.08);
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
            background: #f8fafc;
            position: relative;
        }
        .dark .pt-map-shell { border-color: rgba(255,255,255,0.1); background: #111827; }
        .pt-map-shell.is-fullscreen {
            position: fixed; inset: 0; z-index: 100;
            border-radius: 0; border: none;
            display: flex; flex-direction: column;
            width: 100vw; height: 100vh;
        }
        .pt-map-header {
            display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center;
            gap: 0.75rem; padding: 1rem 1.25rem;
            background: linear-gradient(90deg, #78350f, #92400e 40%, #1f2937);
            color: #fff;
            flex-shrink: 0;
        }
        .pt-map-header h2 { font-size: 1.05rem; font-weight: 700; margin: 0; }
        .pt-map-header p { margin: 0.15rem 0 0; font-size: 0.8rem; opacity: 0.85; }
        .pt-map-header-actions { display: flex; align-items: center; gap: 0.6rem; }
        .pt-map-badge {
            font-size: 0.75rem; font-weight: 700; padding: 0.35rem 0.75rem;
            border-radius: 999px; background: rgba(251,191,36,0.2); border: 1px solid rgba(251,191,36,0.45);
        }
        .pt-map-fs-btn {
            font-size: 0.75rem; font-weight: 700; padding: 0.4rem 0.85rem;
            border-radius: 999px; cursor: pointer;
            background: rgba(255,255,255,0.12); border: 1px solid rgba(255,255,255,0.35);
            color: #fff; transition: background 0.15s;
        }
        .pt-map-fs-btn:hover { background: rgba(251,191,36,0.25); border-color: rgba(251,191,36,0.55); }
        #pt-discovery-map { height: 70vh; min-height: 420px; width: 100%; }
        .pt-map-shell.is-fullscreen #pt-discovery-map {
            height: auto; min-height: 0; flex: 1;
        }
        .pt-map-note { font-size: 0.8rem; color: #6b7280; margin-top: 0.75rem; }
        .dark .pt-map-note { color: #9ca3af; }
        body.pt-map-fs-lock { overflow: hidden; }
    </style>

    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
          integrity="sha256-p4NxAoJBhIIN+hmNHrzRCf9tD/miZyoHS5obTRR9BMY=" crossorigin="" />

    <div class="pt-map-shell" id="pt-map-shell">
        <div class="pt-map-header">
            <div>
                <h2>Discovery heat map</h2>
                <p>All plate discoveries that include latitude &amp; longitude. No personal labels shown.</p>
            </div>
            <div class="pt-map-header-actions">
                <div class="pt-map-badge">{{ number_format($this->pointCount) }} points plotted</div>
                <button type="button" class="pt-map-fs-btn" id="pt-map-fs-btn" aria-pressed="false">
                    Full screen
                </button>
            </div>
        </div>
        <div id="pt-discovery-map"
             wire:ignore
             data-points='@json($this->heatPoints)'></div>
    </div>
    <p class="pt-map-note">
        Uses Leaflet + heat layer (CDN). Limited to the 8,000 most recent geo-tagged discoveries for performance.
        Press <kbd>Esc</kbd> to exit full screen.
        Open <a href="{{ \App\Filament\Pages\DiscoveryInsights::getUrl() }}" class="text-amber-600 dark:text-amber-400 underline">Discovery Insights</a> for rates, time patterns, and hotspot tables.
    </p>

    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"
            integrity="sha256-20nQCchB9co0qIjJZRGuk2/Z9VM+kNiyxNV1lvTlZBo=" crossorigin=""></script>
    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
    <script>
        (function () {
            const el = document.getElementById('pt-discovery-map');
            const shell = document.getElementById('pt-map-shell');
            const fsBtn = document.getElementById('pt-map-fs-btn');
            if (!el || !shell || typeof L === 'undefined') return;

            let points = [];
            try { points = JSON.parse(el.getAttribute('data-points') || '[]'); } catch (e) { points = []; }

            const map = L.map(el, { scrollWheelZoom: true }).setView([39.5, -98.35], 4);
            L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
                maxZoom: 19,
            }).addTo(map);

            if (points.length && L.heatLayer) {
                L.heatLayer(points, {
                    radius: 22,
                    blur: 18,
                    maxZoom: 10,
                    gradient: {
                        0.2: '#1e3a8a',
                        0.4: '#0ea5e9',
                        0.6: '#fbbf24',
                        0.8: '#f97316',
                        1.0: '#ef4444',
                    },
                }).addTo(map);

                const bounds = L.latLngBounds(points.map(p => [p[0], p[1]]));
                if (bounds.isValid()) map.fitBounds(bounds.pad(0.15));
            }

            function refreshMapSize() {
                map.invalidateSize();
                setTimeout(() => map.invalidateSize(), 50);
                setTimeout(() => map.invalidateSize(), 200);
            }

            function setFullscreen(on) {
                shell.classList.toggle('is-fullscreen', on);
                document.body.classList.toggle('pt-map-fs-lock', on);
                fsBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
                fsBtn.textContent = on ? 'Exit full screen' : 'Full screen';
                refreshMapSize();
            }

            fsBtn.addEventListener('click', function () {
                setFullscreen(!shell.classList.contains('is-fullscreen'));
            });

            document.addEventListener('keydown', function (e) {
                if (e.key === 'Escape' && shell.classList.contains('is-fullscreen')) {
                    setFullscreen(false);
                }
            });

            setTimeout(() => map.invalidateSize(), 200);
        })();
    </script>
</x-filament-panels::page>
