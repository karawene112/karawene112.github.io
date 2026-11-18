/* 3D route globe for the Today card and the sign-in screen.
   Loads three.js from cdnjs (cached offline by sw.js). If WebGL or the library is missing,
   the canvas hides itself and the rest of the app carries on. */
(function () {
  "use strict";
  var REDUCE = false;
  try { REDUCE = matchMedia("(prefers-reduced-motion: reduce)").matches; } catch (e) {}
  var threeP = null;
  function loadThree() {
    if (window.THREE) return Promise.resolve(window.THREE);
    if (threeP) return threeP;
    threeP = new Promise(function (ok, fail) {
      var s = document.createElement("script");
      s.src = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js";
      s.async = true;
      s.onload = function () { window.THREE ? ok(window.THREE) : fail(); };
      s.onerror = function () { threeP = null; fail(); };
      document.head.appendChild(s);
    });
    return threeP;
  }

  function Globe(canvas, opt) {
    var T = window.THREE, self = this;
    opt = opt || {};
    var renderer;
    try { renderer = new T.WebGLRenderer({ canvas: canvas, antialias: true, alpha: true, powerPreference: "low-power" }); }
    catch (e) { canvas.hidden = true; this.ok = false; return; }
    this.ok = true;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    var scene = new T.Scene(), camera = new T.PerspectiveCamera(30, 1, 0.1, 100);
    var world = new T.Group(); scene.add(world);
    var R = 1, dist = opt.dist || 4.4;
    camera.position.set(0, 0, dist);

    function ll(lat, lon, r) {
      var p = (90 - lat) * Math.PI / 180, t = (lon + 180) * Math.PI / 180;
      return new T.Vector3(-r * Math.sin(p) * Math.cos(t), r * Math.cos(p), r * Math.sin(p) * Math.sin(t));
    }
    this.ll = ll;

    /* night-chart sphere */
    world.add(new T.Mesh(new T.SphereGeometry(R, 56, 40), new T.ShaderMaterial({
      uniforms: { a: { value: new T.Color("#2A4470") }, b: { value: new T.Color("#0E1B33") }, rim: { value: new T.Color("#E2589F") } },
      vertexShader: "varying vec3 vN; void main(){ vN=normalize(normalMatrix*normal); gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }",
      fragmentShader: "uniform vec3 a; uniform vec3 b; uniform vec3 rim; varying vec3 vN; void main(){ float f=clamp(dot(vN,normalize(vec3(-.4,.5,1.))),0.,1.); vec3 c=mix(b,a,pow(f,1.4)); float r=pow(1.-max(vN.z,0.),2.5); c=mix(c,rim,r*.35); gl_FragColor=vec4(c,1.); }"
    })));
    /* atmosphere glow */
    world.add(new T.Mesh(new T.SphereGeometry(R * 1.16, 48, 32), new T.ShaderMaterial({
      side: T.BackSide, transparent: true, depthWrite: false, blending: T.AdditiveBlending,
      vertexShader: "varying vec3 vN; void main(){ vN=normalize(normalMatrix*normal); gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.0); }",
      fragmentShader: "varying vec3 vN; void main(){ float i=pow(clamp(-vN.z*1.6,0.,1.),2.); gl_FragColor=vec4(mix(vec3(.31,.49,.84),vec3(.89,.35,.62),.35)*i*1.1,1.); }"
    })));
    /* a few stars behind it */
    (function () {
      var st = [], n = 260;
      for (var k = 0; k < n; k++) {
        var u = Math.random() * 2 - 1, a = Math.random() * Math.PI * 2, rr = 9 + Math.random() * 6, q = Math.sqrt(1 - u * u);
        st.push(rr * q * Math.cos(a), rr * u, -Math.abs(rr * q * Math.sin(a)) - 2);
      }
      var sg = new T.BufferGeometry(); sg.setAttribute("position", new T.Float32BufferAttribute(st, 3));
      scene.add(new T.Points(sg, new T.PointsMaterial({ color: 0xC9D7E6, size: 0.05, transparent: true, opacity: 0.55, depthWrite: false })));
    })();
    var g = [];
    for (var la = -75; la <= 75; la += 15) for (var lo = -180; lo < 180; lo += 4) g.push(ll(la, lo, R * 1.001), ll(la, lo + 4, R * 1.001));
    for (var lo2 = -180; lo2 < 180; lo2 += 15) for (var la2 = -86; la2 < 86; la2 += 4) g.push(ll(la2, lo2, R * 1.001), ll(la2 + 4, lo2, R * 1.001));
    world.add(new T.LineSegments(new T.BufferGeometry().setFromPoints(g), new T.LineBasicMaterial({ color: 0x9FB2C6, transparent: true, opacity: 0.12 })));

    function tex(fill, ring) {
      var c = document.createElement("canvas"); c.width = c.height = 64; var x = c.getContext("2d");
      x.beginPath(); x.arc(32, 32, ring ? 24 : 28, 0, Math.PI * 2); x.fillStyle = fill; x.fill();
      if (ring) { x.lineWidth = 9; x.strokeStyle = "#13233F"; x.stroke(); }
      return new T.CanvasTexture(c);
    }
    var dotT = tex("#9FB2C6"), endT = tex("#F0B429", true), planeT = tex("#FFFFFF", true);
    if (opt.points && opt.points.length) {
      var arr = [];
      opt.points.forEach(function (p) { var v = ll(p[0], p[1], R * 1.004); arr.push(v.x, v.y, v.z); });
      var pg = new T.BufferGeometry(); pg.setAttribute("position", new T.Float32BufferAttribute(arr, 3));
      world.add(new T.Points(pg, new T.PointsMaterial({ size: 0.03, map: dotT, transparent: true, alphaTest: 0.4, depthWrite: false, opacity: 0.8 })));
    }

    var routeGroup = new T.Group(); world.add(routeGroup);
    var arcs = [], arcMat = new T.LineBasicMaterial({ color: 0xE2589F, transparent: true, opacity: 0.95 });
    function clearRoutes() {
      while (routeGroup.children.length) {
        var o = routeGroup.children.pop();
        if (o.geometry) o.geometry.dispose();
      }
      arcs = [];
    }
    function addArc(a, b, i) {
      var A = ll(a[0], a[1], R), B = ll(b[0], b[1], R), d = A.angleTo(B);
      if (d < 0.002) return;
      var h = R + 0.08 + d * 0.2, mid = A.clone().add(B).normalize().multiplyScalar(h);
      var cA = A.clone().lerp(mid, 0.55).normalize().multiplyScalar(h), cB = B.clone().lerp(mid, 0.55).normalize().multiplyScalar(h);
      var curve = new T.CubicBezierCurve3(A, cA, cB, B), N = 90;
      var geo = new T.BufferGeometry().setFromPoints(curve.getPoints(N)); geo.setDrawRange(0, 0);
      routeGroup.add(new T.Line(geo, arcMat));
      var plg = new T.BufferGeometry(); plg.setAttribute("position", new T.Float32BufferAttribute([0, 0, 0], 3));
      var plane = new T.Points(plg, new T.PointsMaterial({ size: 0.075, map: planeT, transparent: true, alphaTest: 0.4, depthWrite: false }));
      plane.visible = false; routeGroup.add(plane);
      arcs.push({ geo: geo, N: N, curve: curve, plane: plane, born: clock.elapsedTime + (i || 0) * 0.08, t: 0, speed: 0.09 / Math.max(0.6, d) });
    }
    function ends(list) {
      var arr = [];
      list.forEach(function (p) { var v = ll(p[0], p[1], R * 1.006); arr.push(v.x, v.y, v.z); });
      if (!arr.length) return;
      var eg = new T.BufferGeometry(); eg.setAttribute("position", new T.Float32BufferAttribute(arr, 3));
      routeGroup.add(new T.Points(eg, new T.PointsMaterial({ size: 0.085, map: endT, transparent: true, alphaTest: 0.4, depthWrite: false })));
    }

    /* rotation, drag and focus */
    var rotY = 0, rotX = 0.3, tY = 0, tX = 0.3, vel = 0, dragging = false, lx = 0, idle = 99, back = true, focus = null, home = null;
    function aim(lat, lon) {
      var target = -Math.PI / 2 - lon * Math.PI / 180, d = target - tY;
      d = Math.atan2(Math.sin(d), Math.cos(d));
      return { y: tY + d, x: Math.max(-1.1, Math.min(1.1, lat * Math.PI / 180)) };
    }
    this.setRoutes = function (list, focusAt, endpoints) {
      clearRoutes();
      (list || []).forEach(function (r, i) { addArc(r[0], r[1], i); });
      ends(endpoints || []);
      home = focusAt ? aim(focusAt[0], focusAt[1]) : null;
      if (home) { focus = home; if (!self.started) { tY = rotY = home.y; tX = rotX = home.x; } }
      self.started = true;
      kick();
    };

    var lock = null, sx = 0, sy = 0;
    function down(x) { dragging = true; lx = x; vel = 0; focus = null; idle = 0; back = false; }
    function move(x) { if (!dragging) return; var dx = x - lx; lx = x; tY += dx * 0.008; vel = dx * 0.008; idle = 0; }
    function up() { dragging = false; }
    canvas.addEventListener("pointerdown", function (e) { if (e.pointerType === "touch") return; down(e.clientX); try { canvas.setPointerCapture(e.pointerId); } catch (er) {} kick(); });
    canvas.addEventListener("pointermove", function (e) { if (e.pointerType !== "touch") move(e.clientX); });
    canvas.addEventListener("pointerup", up); canvas.addEventListener("pointercancel", up);
    canvas.addEventListener("touchstart", function (e) { var t = e.touches[0]; sx = t.clientX; sy = t.clientY; lock = null; down(t.clientX); kick(); }, { passive: true });
    canvas.addEventListener("touchmove", function (e) {
      var t = e.touches[0];
      if (lock === null) lock = Math.abs(t.clientX - sx) > Math.abs(t.clientY - sy) ? "x" : "y";
      if (lock === "x") { e.preventDefault(); move(t.clientX); } else up();
    }, { passive: false });
    canvas.addEventListener("touchend", up);

    function size() {
      var w = canvas.clientWidth, h = canvas.clientHeight; if (!w || !h) return false;
      renderer.setSize(w, h, false); camera.aspect = w / h;
      camera.position.z = dist / Math.min(1, w / h);
      camera.updateProjectionMatrix(); return true;
    }
    window.addEventListener("resize", function () { size(); kick(); });

    var clock = new T.Clock(), running = false, visible = true;
    if ("IntersectionObserver" in window) new IntersectionObserver(function (en) { visible = en[0].isIntersecting; if (visible) { size(); kick(); } }).observe(canvas);
    document.addEventListener("visibilitychange", kick);

    function frame(dt) {
      var t = clock.elapsedTime, busy = dragging || Math.abs(vel) > 1e-4 || !!focus;
      if (focus) { tY += (focus.y - tY) * 0.07; tX += (focus.x - tX) * 0.07; if (Math.abs(focus.y - tY) < 0.0005 && Math.abs(focus.x - tX) < 0.0005) focus = null; }
      else if (!dragging) {
        vel *= 0.93; tY += vel; idle += dt;
        if (home && !back && idle > 3.5) { focus = home; back = true; }                 /* drift back to the route */
        if (!home && opt.autoSpin && !REDUCE) { tY += dt * 0.08; busy = true; }
      }
      rotY += (tY - rotY) * 0.2; rotX += (tX - rotX) * 0.15;
      world.rotation.set(rotX, rotY, 0);
      arcs.forEach(function (a) {
        var p = REDUCE ? 1 : Math.max(0, Math.min(1, (t - a.born) / 1.2));
        a.geo.setDrawRange(0, Math.floor(p * (a.N + 1)));
        if (p < 1) { busy = true; return; }
        a.plane.visible = true;
        if (!REDUCE) { a.t = (a.t + dt * a.speed) % 1; busy = true; }
        var q = a.curve.getPoint(REDUCE ? 0.5 : a.t), at = a.plane.geometry.attributes.position;
        at.setXYZ(0, q.x, q.y, q.z); at.needsUpdate = true;
      });
      renderer.render(scene, camera);
      return busy || Math.abs(tY - rotY) > 1e-4 || Math.abs(tX - rotX) > 1e-4;
    }
    function kick() {
      if (running) return;
      running = true; clock.getDelta();
      (function go() {
        if (!visible || document.hidden) { running = false; return; }
        var dt = Math.min(clock.getDelta(), 0.05);
        if (!frame(dt)) { running = false; return; }   /* nothing moving: stop drawing to save battery */
        requestAnimationFrame(go);
      })();
    }
    size();
    this.kick = kick;
  }

  /* ---------- wiring to the app ---------- */
  var today = null, login = null;
  function coordsFor(p) {
    if (!p) return null;
    if (isFinite(p.lat) && isFinite(p.lon) && (p.lat || p.lon)) return [p.lat, p.lon];
    var D = window.LAYOVER_DESTS || [];
    var m = p.code && D.find(function (d) { return d.code === p.code; });
    if (!m && p.name) m = D.find(function (d) { return d.name === p.name; });
    if (!m && p.tz) m = D.find(function (d) { return d.tz === p.tz; });
    return m ? [m.lat, m.lon] : null;
  }
  function update() {
    if (!today || !today.ok) return;
    var st = window.LAYOVER_STATE && window.LAYOVER_STATE();
    if (!st) return;
    var h = coordsFor(st.home), d = coordsFor(st.dest);
    if (h && d) {
      var mid = [(h[0] + d[0]) / 2, h[1] + (((d[1] - h[1] + 540) % 360) - 180) / 2];
      today.setRoutes([[h, d]], mid, [h, d]);
    } else if (d) today.setRoutes([], d, [d]);
    else today.setRoutes([], h, h ? [h] : []);
  }
  function loginRoutes() {
    if (!login || !login.ok) return;
    var D = window.LAYOVER_DESTS || [], by = function (c) { var m = D.find(function (d) { return d.code === c; }); return m ? [m.lat, m.lon] : null; };
    var pairs = [["DOH", "LHR"], ["DXB", "JFK"], ["SIN", "SYD"], ["CDG", "GRU"], ["DOH", "NRT"], ["FRA", "JNB"], ["IST", "BKK"], ["LHR", "LAX"]]
      .map(function (p) { return [by(p[0]), by(p[1])]; }).filter(function (p) { return p[0] && p[1]; });
    login.setRoutes(pairs, null, []);
  }
  function boot() {
    var tc = document.getElementById("passGlobe"), lc = document.getElementById("loginGlobe");
    if (!tc && !lc) return;
    loadThree().then(function () {
      var pts = (window.LAYOVER_DESTS || []).map(function (d) { return [d.lat, d.lon]; });
      if (tc) { today = new Globe(tc, { points: pts, dist: 3.35 }); update(); }
      if (lc) { login = new Globe(lc, { points: pts, dist: 3.6, autoSpin: true }); loginRoutes(); }
      document.documentElement.classList.add("has-globe");
    }).catch(function () {
      if (tc) tc.hidden = true; if (lc) lc.hidden = true;
    });
  }
  window.LGlobe = { update: update, kickLogin: function () { if (login && login.ok) login.kick(); } };
  if (document.readyState === "complete") boot(); else window.addEventListener("load", boot);
})();
