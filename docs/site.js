/* Lightbox for every a[data-lightbox] — keyboard, swipe, grouped by the attribute value. */
(function () {
  var box = document.getElementById('lightbox');
  if (!box) return;
  var img = box.querySelector('img'), cap = box.querySelector('figcaption');
  var group = [], idx = 0, startX = 0;

  function show(i) {
    idx = (i + group.length) % group.length;
    var a = group[idx];
    img.src = a.getAttribute('href');
    img.alt = (a.querySelector('img') || {}).alt || '';
    cap.textContent = a.dataset.caption || '';
    box.hidden = false;
    document.body.style.overflow = 'hidden';
  }
  function close() { box.hidden = true; document.body.style.overflow = ''; img.src = ''; }

  document.addEventListener('click', function (e) {
    var a = e.target.closest('a[data-lightbox]');
    if (!a) return;
    e.preventDefault();
    group = Array.prototype.slice.call(document.querySelectorAll('a[data-lightbox="' + a.dataset.lightbox + '"]'));
    show(group.indexOf(a));
  });
  box.querySelector('.lb-close').addEventListener('click', close);
  box.querySelector('.lb-prev').addEventListener('click', function () { show(idx - 1); });
  box.querySelector('.lb-next').addEventListener('click', function () { show(idx + 1); });
  box.addEventListener('click', function (e) { if (e.target === box) close(); });
  document.addEventListener('keydown', function (e) {
    if (box.hidden) return;
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowRight') show(idx + 1);
    if (e.key === 'ArrowLeft') show(idx - 1);
  });
  box.addEventListener('touchstart', function (e) { startX = e.touches[0].clientX; }, { passive: true });
  box.addEventListener('touchend', function (e) {
    var dx = e.changedTouches[0].clientX - startX;
    if (Math.abs(dx) > 50) show(idx + (dx < 0 ? 1 : -1));
  });
})();

/* Category filter (episodes): the chosen category lives in the URL hash, so a reload
   or a shared link (/episodi/#musica) restores it. Hides the .ecard whose data-cat differs. */
(function () {
  var bar = document.getElementById('filters');
  if (!bar) return;
  var chips = Array.prototype.slice.call(bar.querySelectorAll('a[data-cat]'));
  var items = Array.prototype.slice.call(document.querySelectorAll('[data-cat]')).filter(function (el) { return !bar.contains(el); });
  var count = document.getElementById('ep-count');
  function apply() {
    var cat = decodeURIComponent(location.hash.replace(/^#/, ''));
    if (!chips.some(function (c) { return c.dataset.cat === cat; })) cat = '';
    var n = 0;
    items.forEach(function (el) { var on = !cat || el.dataset.cat === cat; el.hidden = !on; if (on) n++; });
    chips.forEach(function (c) {
      var on = c.dataset.cat === cat;
      c.setAttribute('aria-pressed', on ? 'true' : 'false');
      if (on && cat && c.scrollIntoView) c.scrollIntoView({ block: 'nearest', inline: 'center' });
    });
    if (count) count.textContent = n;
  }
  bar.addEventListener('click', function (e) {
    var a = e.target.closest('a[data-cat]');
    if (!a) return;
    e.preventDefault();
    var h = a.dataset.cat ? '#' + a.dataset.cat : '';
    if (h !== location.hash) history.replaceState(null, '', location.pathname + (h || ''));
    apply();
  });
  window.addEventListener('hashchange', apply);
  apply();
})();

/* Episode video: the still image with a play button becomes the YouTube embed only on click
   (no third-party request until the visitor asks for the video). */
(function () {
  var fig = document.querySelector('.ehero[data-yt]');
  if (!fig) return;
  fig.querySelector('.play').addEventListener('click', function () {
    var f = document.createElement('iframe');
    f.src = 'https://www.youtube-nocookie.com/embed/' + fig.dataset.yt + '?autoplay=1&rel=0';
    f.title = 'YouTube';
    f.allow = 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share';
    f.allowFullscreen = true;
    fig.replaceChildren(f);
  });
})();
