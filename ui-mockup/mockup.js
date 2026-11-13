// Concept mockup logic. Mirrors the behaviour of daemon/ddns.py so the two agree.
(function () {
  var $ = function (s) { return document.querySelector(s); };
  var $$ = function (s) { return Array.prototype.slice.call(document.querySelectorAll(s)); };

  /* ---------- Provider dropdown: same show/hide idea as Peplink's ddns.js ---------- */
  var legacyUser = { changeip: 'User ID', noip: 'Email' };
  function onProvider() {
    var p = $('#provider').value;
    var cf = p === 'cloudflare';
    $$('.cf-row').forEach(function (r) { r.classList.toggle('hide', !cf); });
    $$('.legacy').forEach(function (r) { r.classList.toggle('hide', cf || p === 'disable'); });
    $('#legacyUserLbl').textContent = legacyUser[p] || 'Username';
    $('#newbadge').style.display = cf ? '' : 'none';
  }
  $('#provider').addEventListener('change', onProvider);

  /* ---------- Proxied: grey out TTL, show Auto ---------- */
  var lastTtl = '60';
  function onProxied() {
    var on = $('#cfProxied').checked, ttl = $('#cfTtl');
    if (on) { lastTtl = ttl.value; ttl.value = '1'; } else { ttl.value = lastTtl === '1' ? '60' : lastTtl; }
    ttl.disabled = on;
    $('#proxyNote').textContent = on
      ? 'Only HTTP/HTTPS on Cloudflare’s supported ports is proxied. VPN, SSH, SpeedFusion and game traffic will NOT work through this record. TTL is Auto.'
      : 'DNS only. Works for any protocol (VPN, SSH, SpeedFusion, game servers).';
    render();
  }
  $('#cfProxied').addEventListener('change', onProxied);

  /* ---------- Verify: three steps, each reporting its own result ---------- */
  function step(text, cls, hint) { var li = document.createElement('li'); li.className = cls; li.textContent = text; if (hint) { var h = document.createElement('span'); h.className = 'hint'; h.textContent = hint; li.appendChild(h); } $('#steps').appendChild(li); return li; }
  function sleep(ms) { return new Promise(function (r) { setTimeout(r, ms); }); }
  $('#verifyBtn').addEventListener('click', async function () {
    var sc = $('#scenario').value, zone = $('#cfZone').value.trim(), zid = $('#cfZoneId').value.trim();
    var hosts = $('#cfHosts').value.split(/\s+/).filter(Boolean);
    $('#steps').innerHTML = ''; this.disabled = true;
    var p1 = step('1. Token active  (GET /user/tokens/verify)…', 'pend'); await sleep(450);
    if (sc === 'revoked') { p1.className = 'bad'; p1.textContent = '✗ 1. Token is invalid or has been revoked.'; this.disabled = false; return; }
    p1.className = 'ok'; p1.textContent = '✓ 1. Token is active';
    var p2 = step('2. Zone visible  (GET /zones?name=' + zone + ')…', 'pend'); await sleep(450);
    if (zid) { p2.className = 'ok'; p2.textContent = '✓ 2. Skipped, using the Zone ID you entered'; }
    else if (sc === 'template') { p2.className = 'bad'; p2.textContent = '✗ 2. Token cannot look up zones (HTTP 403)'; var h = document.createElement('span'); h.className = 'hint'; h.textContent = 'Probably missing Zone → Zone → Read. Add it, or fill in the optional Zone ID field to skip this lookup.'; p2.appendChild(h); this.disabled = false; return; }
    else if (sc === 'wrongzone') { p2.className = 'bad'; p2.textContent = '✗ 2. No zone named ' + zone + ' is visible to this token'; var h2 = document.createElement('span'); h2.className = 'hint'; h2.textContent = 'The token is probably scoped to a different zone, or the zone name is misspelled.'; p2.appendChild(h2); this.disabled = false; return; }
    else { p2.className = 'ok'; p2.textContent = '✓ 2. Zone found, ID cached (7c1e…a9f2)'; }
    var p3 = step('3. Records readable  (GET /zones/<id>/dns_records?name=…)…', 'pend'); await sleep(500);
    if (sc === 'wrongzone') { p3.className = 'bad'; p3.textContent = '✗ 3. Access denied to this zone’s DNS records (HTTP 403)'; var h3 = document.createElement('span'); h3.className = 'hint'; h3.textContent = 'Probably missing Zone → DNS → Edit for this zone.'; p3.appendChild(h3); this.disabled = false; return; }
    p3.className = 'ok'; p3.textContent = '✓ 3. Records readable';
    hosts.forEach(function (h, i) { step('    ' + h + (i === 0 ? '  A → ' + (rec.ip || '198.51.100.7') + ' (will be updated)' : '  not found (will be created)'), 'ok'); });
    this.disabled = false;
  });

  /* ---------- Simulated router + provider behaviour ---------- */
  var wans = [
    { id: 1, name: 'WAN 1 (fibre)', pri: 1, up: true, ip: '203.0.113.10' },
    { id: 2, name: 'WAN 2 (cable)', pri: 1, up: true, ip: '198.51.100.20' },
    { id: 3, name: 'WAN 3 (cellular)', pri: 2, up: true, ip: '100.64.7.7' }
  ];
  var rec = { ip: '203.0.113.10', at: new Date() };
  var ttlLeft = 0, ttlTimer = null;

  function isPublic(ip) {
    var o = ip.split('.').map(Number);
    if (o[0] === 10 || o[0] === 127 || (o[0] === 192 && o[1] === 168) || (o[0] === 172 && o[1] >= 16 && o[1] <= 31) || (o[0] === 169 && o[1] === 254)) return false;
    if (o[0] === 100 && o[1] >= 64 && o[1] <= 127) return false; // CGNAT
    return true;
  }
  function bestPri() { var u = wans.filter(function (w) { return w.up; }); return u.length ? Math.min.apply(null, u.map(function (w) { return w.pri; })) : null; }
  function status(w) { if (!w.up) return 'red'; return w.pri === bestPri() ? 'green' : 'yellow'; }
  function log(msg) { var l = $('#log'); l.innerHTML += '[' + new Date().toLocaleTimeString() + '] ' + msg + '<br>'; l.scrollTop = l.scrollHeight; }

  function desired() {
    var mode = ($$('input[name=mode]').filter(function (r) { return r.checked; })[0] || {}).value;
    if (mode === 'this') { var w1 = wans[0]; return w1.up && isPublic(w1.ip) ? w1.ip : null; }
    var act = wans.filter(function (w) { return status(w) === 'green' && isPublic(w.ip); }).sort(function (a, b) { return a.pri - b.pri || a.id - b.id; })[0];
    if (act) return act.ip;
    if (mode === 'standby') { var s = $('#cfStandby').value.trim(); return s && isPublic(s) ? s : null; }
    return null;
  }
  function evaluate(why) {
    var d = desired();
    if (!d) { log('No publishable address (' + why + '); record left unchanged.'); return; }
    if (d === rec.ip) return;
    log('PUT ' + $('#cfHosts').value.split(/\s+/)[0] + ' ' + rec.ip + ' → ' + d + '  (' + why + ')');
    rec = { ip: d, at: new Date() };
    startTtl();
  }
  function startTtl() {
    clearInterval(ttlTimer);
    ttlLeft = $('#cfProxied').checked ? 0 : parseInt($('#cfTtl').value, 10) || 0;
    if (ttlLeft > 1) ttlTimer = setInterval(function () { ttlLeft--; if (ttlLeft <= 0) clearInterval(ttlTimer); render(); }, 1000);
    render();
  }
  function render() {
    $('#wanRows').innerHTML = '';
    wans.forEach(function (w) {
      var tr = document.createElement('tr'), st = status(w);
      var label = { green: 'Connected', yellow: 'Standby', red: 'Disconnected' }[st];
      var note = (w.up && !isPublic(w.ip)) ? ' <span title="never published">(not public)</span>' : '';
      tr.innerHTML = '<td>' + w.name + '</td><td>' + w.pri + '</td><td><span class="led ' + st + '"></span>' + label + '</td><td>' + (w.up ? w.ip : '—') + note + '</td><td></td>';
      var b = document.createElement('button'); b.textContent = w.up ? 'Unplug' : 'Plug in'; b.onclick = function () { w.up = !w.up; log(w.name + (w.up ? ' connected' : ' went down')); evaluate(w.name + (w.up ? ' up' : ' down')); render(); };
      tr.lastChild.appendChild(b); $('#wanRows').appendChild(tr);
    });
    var prox = $('#cfProxied').checked;
    var stale = prox ? 'Proxied: the change takes effect at Cloudflare’s edge almost immediately.' : (ttlLeft > 0 ? 'DNS-only: resolvers may still serve the old IP for up to <b>' + ttlLeft + 's</b> (TTL).' : 'DNS-only: record has propagated (TTL expired).');
    $('#rec').innerHTML = '<b>' + $('#cfHosts').value.split(/\s+/)[0] + '</b> &rarr; <code>' + rec.ip + '</code> ' + (prox ? '<span class="new-badge">proxied</span>' : '') + '<br>' + stale;
  }
  $$('input[name=mode], #cfStandby, #cfTtl').forEach(function (e) { e.addEventListener('change', function () { evaluate('settings changed'); render(); }); });

  document.getElementById('cfToken').value = 'demo-token-not-real';
  onProvider(); onProxied(); log('Provider started (mockup). Unplug a WAN to watch the record follow the active one.');
})();
