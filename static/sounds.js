/* ═══════════════════════════════════════════════════════
   METROPOLIS CHESS CLUB — Audio Engine (Howler.js)
   ═══════════════════════════════════════════════════════ */

const Audio = (() => {
    let _ambient = null;
    let _ambientKey = null;

    // ── Lazy sound loader ────────────────────────────────────────────────────
    const _cache = {};
    function _sound(key, src, opts = {}) {
        if (!_cache[key]) {
            _cache[key] = new Howl({ src: [src], preload: true, ...opts });
        }
        return _cache[key];
    }

    // ── Game sounds ──────────────────────────────────────────────────────────

    function init() {
        // Howler handles AudioContext unlock automatically on first user gesture.
        // Preload all SFX so there's no latency on first play.
        _sound('move',      '/static/sounds/move.mp3',      { volume: 0.8 });
        _sound('capture',   '/static/sounds/capture.mp3',   { volume: 0.9 });
        _sound('check',     '/static/sounds/check.mp3',     { volume: 0.7 });
        _sound('game_over', '/static/sounds/game_over.mp3', { volume: 0.6 });
    }

    function playMove()    { _sound('move',    '/static/sounds/move.mp3',    { volume: 0.8 }).play(); }
    function playCapture() { _sound('capture', '/static/sounds/capture.mp3', { volume: 0.9 }).play(); }
    function playCheck()   { _sound('check',   '/static/sounds/check.mp3',   { volume: 0.7 }).play(); }

    function playGameStart() {
        // Short synthesized chord — keeps the atmospheric feel on game start
        const c = new (window.AudioContext || window.webkitAudioContext)();
        const t = c.currentTime;
        [110, 138, 165, 220].forEach((freq, i) => {
            const osc = c.createOscillator();
            const g   = c.createGain();
            osc.type = 'triangle';
            osc.frequency.value = freq;
            g.gain.setValueAtTime(0, t + i * 0.06);
            g.gain.linearRampToValueAtTime(0.07, t + i * 0.06 + 0.25);
            g.gain.exponentialRampToValueAtTime(0.0001, t + 2.8);
            osc.connect(g); g.connect(c.destination);
            osc.start(t + i * 0.06); osc.stop(t + 2.8);
        });
    }

    function playGameOver(outcome) {
        _sound('game_over', '/static/sounds/game_over.mp3', { volume: 0.6 }).play();
    }

    // ── Ambient ──────────────────────────────────────────────────────────────

    function startAmbient(isMenu) {
        const key = isMenu ? 'menu' : 'game';
        if (_ambientKey === key && _ambient) return; // already playing the right one
        stopAmbient();

        const src    = isMenu ? '/static/sounds/ambient_menu.mp3' : '/static/sounds/ambient_game.mp3';
        const volume = isMenu ? 0.28 : 0.18;

        _ambient = new Howl({
            src: [src],
            loop:   true,
            volume: 0,
        });
        _ambient.play();
        _ambient.fade(0, volume, 2500);
        _ambientKey = key;
    }

    function stopAmbient() {
        if (!_ambient) return;
        const a = _ambient;
        _ambient    = null;
        _ambientKey = null;
        a.fade(a.volume(), 0, 900);
        setTimeout(() => a.unload(), 1000);
    }

    // Dim ambient for in-game (stays alive, just quieter)
    function dimAmbient()   { if (_ambient) _ambient.fade(_ambient.volume(), 0.07, 1500); }
    function undimAmbient() { if (_ambient) _ambient.fade(_ambient.volume(), 0.28, 1500); }

    // Global mute toggle
    let _muted = false;
    function toggleMute() {
        _muted = !_muted;
        Howler.mute(_muted);
        return _muted;
    }

    // ── Public API ───────────────────────────────────────────────────────────
    return { init, playMove, playCapture, playCheck, playGameStart, playGameOver, startAmbient, stopAmbient, dimAmbient, undimAmbient, toggleMute };
})();
