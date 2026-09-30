/* Campo de puntos ondulado del hero (canvas 2D, sin dependencias).
   Una malla de puntos cuya altura sigue la suma de varias ondas; el tamaño y
   el brillo de cada punto dependen de su altura y de la inclinación de la
   superficie, lo que da el efecto de relieve. Respeta prefers-reduced-motion
   (un solo cuadro) y se pausa cuando la pestaña o el hero no se ven. */
(function () {
  var canvas = document.getElementById("ondas");
  if (!canvas || !canvas.getContext) return;
  var ctx = canvas.getContext("2d");
  var quieto = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  var ancho = 0, alto = 0, dpr = 1, visible = true, raf = 0;
  var PASO_X = 11, PASO_Y = 8;   // separación entre puntos, en px CSS
  var CUBOS = 9;                 // niveles de opacidad (un trazo por nivel)

  function medir() {
    var r = canvas.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    ancho = r.width; alto = r.height;
    canvas.width = Math.round(ancho * dpr);
    canvas.height = Math.round(alto * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  // Altura de la superficie en (u, v): crestas diagonales que se desplazan.
  function altura(u, v, t) {
    return (
      Math.sin(u * 1.15 + v * 1.7 + t * 0.5) * 0.6 +
      Math.sin(u * 2.3 - v * 1.2 + t * 0.34) * 0.28 +
      Math.sin(v * 3.1 + u * 0.4 + t * 0.22) * 0.16
    );
  }

  function dibujar(t) {
    ctx.clearRect(0, 0, ancho, alto);
    var cols = Math.ceil(ancho / PASO_X) + 2;
    var filas = Math.ceil(alto / PASO_Y) + 6;
    var amp = Math.max(alto * 0.12, 40);
    var cubos = [];
    for (var b = 0; b < CUBOS; b++) cubos.push([]);

    for (var j = -3; j < filas; j++) {
      var y = j * PASO_Y;
      var v = (y / alto) * 2.6;
      for (var i = -1; i < cols; i++) {
        var x = i * PASO_X + (j & 1 ? PASO_X / 2 : 0);
        var u = (x / ancho) * 4.2;
        var h = altura(u, v, t);
        // La cara de la cresta que mira a la "luz" brilla; la opuesta se apaga.
        var luz = (h - altura(u + 0.06, v - 0.05, t)) * 9 + 0.55;
        luz = luz < 0 ? 0 : luz > 1 ? 1 : luz;
        var py = y - h * amp;
        var r = 0.45 + luz * 1.5;
        var a = 0.03 + luz * luz * 0.82;
        var k = Math.min(CUBOS - 1, (a * CUBOS) | 0);
        cubos[k].push(x, py, r);
      }
    }

    for (var k2 = 0; k2 < CUBOS; k2++) {
      var pts = cubos[k2];
      if (!pts.length) continue;
      ctx.fillStyle = "rgba(255,255,255," + ((k2 + 0.5) / CUBOS).toFixed(3) + ")";
      ctx.beginPath();
      for (var n = 0; n < pts.length; n += 3) {
        ctx.moveTo(pts[n] + pts[n + 2], pts[n + 1]);
        ctx.arc(pts[n], pts[n + 1], pts[n + 2], 0, 6.2832);
      }
      ctx.fill();
    }
  }

  function cuadro(ms) {
    raf = 0;
    if (!visible || document.hidden) return;
    dibujar(ms / 1000);
    raf = requestAnimationFrame(cuadro);
  }

  function arrancar() {
    if (quieto) { dibujar(2.4); return; }
    if (!raf && visible) raf = requestAnimationFrame(cuadro);
  }

  medir();
  arrancar();
  window.addEventListener("resize", function () { medir(); if (quieto) dibujar(2.4); });
  document.addEventListener("visibilitychange", arrancar);
  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (e) {
      visible = e[0].isIntersecting;
      arrancar();
    }).observe(canvas);
  }
})();
