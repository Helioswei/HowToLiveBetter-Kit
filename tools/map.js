/* 性价比分布图（/map.html）—— canvas 交互层。
   构建时被 build_site.py 内联进页面的一个 script 块，所以：
   · 不引外部脚本（白名单只认 map.json 这个数据文件）
   · 关掉 JS 时页面靠 <noscript> 里的静态 SVG 兜底
   数据：/map.json = [[url, 节, 条, 标题, 投入分, 收益, 档, 证据, 说人话], ...] */
(function () {
  var cv = document.getElementById("hltb-map");
  if (!cv || !cv.getContext) return;
  var ctx = cv.getContext("2d");
  var wrap = cv.parentNode;
  var card = wrap.querySelector(".b-mapcard");
  var bar = document.querySelector(".b-mapbar");
  var COL = { "极高": "#b3402f", "高": "#5b6069", "一般": "#a9adb5" };
  var R = { "极高": 3.6, "高": 2.6, "一般": 2.0 };
  var YS = { "大": 0, "中": 1, "小": 2 };
  var PAD = { l: 54, r: 26, t: 30, b: 46 };
  var pts = [], sel = -1, hov = -1, filter = "all", k = 1, tx = 0, ty = 0, W = 0, H = 0;


  function jit(i, salt) {  /* 确定性抖动：重绘不跳，同一格里的点散开成云 */
    var h = Math.sin(i * 12.9898 + salt * 78.233) * 43758.5453;
    return (h - Math.floor(h)) * 2 - 1;
  }

  function layout() {
    var dpr = Math.min(2, window.devicePixelRatio || 1);
    var r = cv.getBoundingClientRect();
    W = r.width; H = r.height || 460;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function iw() { return W - PAD.l - PAD.r; }
  function ih() { return H - PAD.t - PAD.b; }

  function project(p, i) {           /* 数据坐标 → 屏幕坐标（含抖动与缩放） */
    var x = PAD.l + (p[4] / 6) * iw() + jit(i, 1) * (iw() / 6) * 0.30;
    var y = PAD.t + ((YS[p[5]] || 1) + 0.5) / 3 * ih() + jit(i, 2) * (ih() / 3) * 0.26;
    return { x: x * k + tx, y: y * k + ty };
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    ctx.font = "12px -apple-system,PingFang SC,sans-serif";
    ctx.lineWidth = 1;
    // 网格 + 刻度
    for (var c = 0; c <= 6; c++) {
      var x = PAD.l + (c / 6) * iw();
      ctx.strokeStyle = c === 0 ? "#ddd6c6" : "#ece7dc";
      ctx.beginPath(); ctx.moveTo(x * k + tx, PAD.t * k + ty);
      ctx.lineTo(x * k + tx, (PAD.t + ih()) * k + ty); ctx.stroke();
      ctx.fillStyle = "#8b8f97"; ctx.textAlign = "center";
      ctx.fillText(String(c), x * k + tx, (PAD.t + ih()) * k + ty + 20);
    }
    var names = ["大", "中", "小"];
    for (var r0 = 0; r0 < 3; r0++) {
      var y = PAD.t + (r0 + 0.5) / 3 * ih();
      ctx.strokeStyle = "#ece7dc";
      ctx.beginPath(); ctx.moveTo(PAD.l * k + tx, y * k + ty);
      ctx.lineTo((PAD.l + iw()) * k + tx, y * k + ty); ctx.stroke();
      ctx.fillStyle = "#5b6069"; ctx.textAlign = "right";
      ctx.fillText("收益 " + names[r0], PAD.l * k + tx - 10, y * k + ty + 4);
    }
    ctx.fillStyle = "#8b8f97"; ctx.textAlign = "center";
    ctx.fillText("投入（钱 / 时间 / 毅力 按书里的权重相加） →", (PAD.l + iw() / 2) * k + tx, H - 8);
    // 点
    for (var i = 0; i < pts.length; i++) {
      var p = pts[i], q = project(p, i);
      if (q.x < -20 || q.x > W + 20 || q.y < -20 || q.y > H + 20) continue;
      var dim = (filter !== "all" && p[6] !== filter) || (sel >= 0 && i !== sel);
      ctx.globalAlpha = dim ? 0.10 : 0.72;
      ctx.fillStyle = COL[p[6]] || "#a9adb5";
      ctx.beginPath(); ctx.arc(q.x, q.y, (R[p[6]] || 2) * Math.sqrt(k), 0, 6.2832); ctx.fill();
    }
    ctx.globalAlpha = 1;
    var hi = hov >= 0 ? hov : sel;
    if (hi >= 0 && hi < pts.length) {   /* 选中/悬停的点描一圈 */
      var h = project(pts[hi], hi);
      var rr = (R[pts[hi][6]] || 2) * Math.sqrt(k);
      ctx.fillStyle = COL[pts[hi][6]] || "#26292f";
      ctx.globalAlpha = 0.18;
      ctx.beginPath(); ctx.arc(h.x, h.y, rr + 7, 0, 6.2832); ctx.fill();
      ctx.globalAlpha = 1; ctx.lineWidth = 2; ctx.strokeStyle = COL[pts[hi][6]] || "#26292f";
      ctx.beginPath(); ctx.arc(h.x, h.y, rr + 4, 0, 6.2832); ctx.stroke();
    }
  }

  function showCard(i, mx, my) {          /* 悬停卡：说明这个圆点代表哪一条 */
    var p = pts[i];
    card.innerHTML = "<b>" + p[3] + "</b>" +
      '<span class="k">第 ' + p[1] + " 节第 " + p[2] + " 条 · 书里算「" + p[6] + "」 · " +
      "投入 " + p[4] + " · 收益" + p[5] + (p[7] ? " · 证据 " + p[7] : "") + "</span>" +
      '<p class="t">' + p[8] + "…</p>" +
      '<span class="hint">点这个圆点就能打开这一条</span>';
    card.hidden = false;
    var cw = card.offsetWidth, ch = card.offsetHeight;
    var x = mx + 16, y = my + 16;
    if (x + cw > W - 8) x = mx - 16 - cw;      /* 右边放不下 → 翻到左边 */
    if (y + ch > H - 8) y = my - 16 - ch;      /* 下边放不下 → 翻到上边 */
    x = Math.max(8, Math.min(x, W - cw - 8));
    y = Math.max(8, Math.min(y, H - ch - 8));
    card.style.transform = "translate(" + x + "px," + y + "px)";
  }

  function hideCard() { card.hidden = true; }

  function nearest(mx, my) {
    var best = -1, bd = 14 * 14;
    for (var i = 0; i < pts.length; i++) {
      if (filter !== "all" && pts[i][6] !== filter) continue;
      var q = project(pts[i], i), dx = q.x - mx, dy = q.y - my, d = dx * dx + dy * dy;
      if (d < bd) { bd = d; best = i; }
    }
    return best;
  }

  function toLocal(ev) {   /* 一律用画布坐标：卡片的 pointermove 不经过这里 */
    var r = cv.getBoundingClientRect();
    var t = ev.touches && ev.touches[0] ? ev.touches[0] : ev;
    return { x: t.clientX - r.left, y: t.clientY - r.top };
  }

  /* 拖拽平移 + 滚轮缩放（在触屏上单指拖 = 平移，点上点 = 选择） */
  var drag = null;
  cv.addEventListener("pointerdown", function (ev) {
    drag = { x: ev.clientX, y: ev.clientY, tx: tx, ty: ty, moved: 0, down: toLocal(ev) };
    cv.setPointerCapture(ev.pointerId); cv.classList.add("grabbing");
  });
  cv.addEventListener("pointermove", function (ev) {
    var m = toLocal(ev);
    if (drag) {
      drag.moved = Math.max(drag.moved, Math.abs(ev.clientX - drag.x) + Math.abs(ev.clientY - drag.y));
      tx = drag.tx + (ev.clientX - drag.x); ty = drag.ty + (ev.clientY - drag.y);
      draw(); return;
    }
    var i = nearest(m.x, m.y);       /* 换点才重画/换卡（正常 tooltip；不做粘滞） */
    if (i !== hov) {
      hov = i; draw();
      if (i >= 0) showCard(i, m.x, m.y); else hideCard();
    }
    cv.style.cursor = i >= 0 ? "pointer" : "grab";
  });
  cv.addEventListener("pointerup", function (ev) {
    cv.classList.remove("grabbing");
    var m = toLocal(ev), wasDrag = drag && drag.moved > 6;
    drag = null;
    if (wasDrag) return;                       /* 拖动结束不算点击 */
    var i = nearest(m.x, m.y);
    if (i < 0) { sel = -1; hideCard(); draw(); return; }
    location.href = pts[i][0];       /* 点圆点 = 打开这一条 */
  });
  wrap.addEventListener("pointerleave", function () { hov = -1; hideCard(); draw(); });
  cv.addEventListener("wheel", function (ev) {
    ev.preventDefault();
    var m = toLocal(ev);
    var nk = Math.min(6, Math.max(1, k * (ev.deltaY < 0 ? 1.12 : 0.89)));
    tx = m.x - (m.x - tx) * (nk / k); ty = m.y - (m.y - ty) * (nk / k);
    k = nk; draw();
  }, { passive: false });

  if (bar) {
    bar.addEventListener("click", function (ev) {
      var b = ev.target.closest("button");
      if (!b) return;
      if (b.dataset.reset) { k = 1; tx = 0; ty = 0; sel = -1; hideCard(); draw(); return; }
      filter = b.dataset.ratio || "all";
      var bs = bar.querySelectorAll("button[data-ratio]");
      for (var i = 0; i < bs.length; i++) bs[i].classList.toggle("on", bs[i] === b);
      draw();
    });
  }
  window.addEventListener("resize", function () { layout(); draw(); });

  fetch("map.json").then(function (r) { return r.json(); }).then(function (d) {
    pts = d;
    /* 数据到位才把 canvas 换上来：之前一直显示静态图（秒出，不再有空白画布） */
    var st = document.querySelector(".b-mapstatic");
    if (st) st.style.display = "none";
    if (bar) bar.hidden = false;
    wrap.hidden = false;
    layout(); draw();
  }).catch(function () { /* 拿不到数据：静态图还在页面上，页面不会空 */ });
})();
