/* SmartCAT embeddable chat widget
 * Usage: <script src="http://YOUR-SERVER:8000/widget.js"
 *                 data-api-url="http://YOUR-SERVER:8000"
 *                 data-api-key="sc-...">
 *        </script>
 */
(function () {
  'use strict';

  // ── read config from <script> tag ─────────────────────────────────────────
  var s = document.currentScript || document.querySelector('script[src*="widget.js"]');
  var API_URL  = (s && s.getAttribute('data-api-url'))  || window.location.origin;
  var API_KEY  = (s && s.getAttribute('data-api-key'))  || '';
  var BOT_NAME = (s && s.getAttribute('data-title'))    || 'SmartCAT';
  var POSITION = (s && s.getAttribute('data-position')) || 'bottom-right';

  var RIGHT = POSITION.includes('right') ? '24px' : 'auto';
  var LEFT  = POSITION.includes('left')  ? '24px' : 'auto';

  // ── state ─────────────────────────────────────────────────────────────────
  var sessionId = 'sc_' + Math.random().toString(36).slice(2);
  var history   = [];

  // ── styles ────────────────────────────────────────────────────────────────
  var css = '\
#sc-widget*{box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;margin:0;padding:0}\
#sc-fab{\
  position:fixed;bottom:24px;right:' + RIGHT + ';left:' + LEFT + ';z-index:2147483646;\
  width:56px;height:56px;border-radius:50%;\
  background:#E55B2D;color:#fff;border:none;cursor:pointer;\
  font-size:26px;box-shadow:0 4px 18px rgba(0,0,0,.28);\
  display:flex;align-items:center;justify-content:center;\
  transition:transform .18s;}\
#sc-fab:hover{transform:scale(1.09)}\
#sc-panel{\
  position:fixed;bottom:92px;right:' + RIGHT + ';left:' + LEFT + ';z-index:2147483647;\
  width:370px;height:530px;border-radius:16px;\
  background:#fff;box-shadow:0 8px 40px rgba(0,0,0,.22);\
  display:flex;flex-direction:column;overflow:hidden;\
  opacity:0;pointer-events:none;\
  transform:translateY(14px) scale(.97);\
  transition:opacity .2s,transform .2s;}\
#sc-panel.sc-open{opacity:1;pointer-events:all;transform:none}\
#sc-head{\
  background:#E55B2D;color:#fff;\
  padding:13px 14px;font-weight:700;font-size:14.5px;\
  display:flex;align-items:center;justify-content:space-between;flex-shrink:0}\
#sc-head-left{display:flex;align-items:center;gap:8px}\
#sc-status{width:8px;height:8px;border-radius:50%;background:#7FE57F;flex-shrink:0}\
#sc-x{background:none;border:none;color:rgba(255,255,255,.85);font-size:19px;cursor:pointer;line-height:1;padding:2px 4px}\
#sc-x:hover{color:#fff}\
#sc-msgs{\
  flex:1;overflow-y:auto;padding:14px 12px;\
  display:flex;flex-direction:column;gap:10px;background:#f6f6f6}\
#sc-msgs::-webkit-scrollbar{width:4px}\
#sc-msgs::-webkit-scrollbar-thumb{background:#ddd;border-radius:4px}\
.sc-msg{\
  max-width:86%;padding:9px 13px;border-radius:14px;\
  font-size:13.5px;line-height:1.55;word-break:break-word;white-space:pre-wrap}\
.sc-user{\
  align-self:flex-end;\
  background:#E55B2D;color:#fff;border-bottom-right-radius:3px}\
.sc-bot{\
  align-self:flex-start;\
  background:#fff;color:#1a1a1a;border-bottom-left-radius:3px;\
  box-shadow:0 1px 4px rgba(0,0,0,.09)}\
.sc-think{\
  align-self:flex-start;\
  background:#ebebeb;color:#888;font-style:italic;font-size:13px;\
  border-bottom-left-radius:3px;padding:8px 12px}\
#sc-foot{\
  display:flex;align-items:flex-end;gap:8px;padding:9px 10px;\
  border-top:1px solid #eee;background:#fff;flex-shrink:0}\
#sc-in{\
  flex:1;border:1.5px solid #ddd;border-radius:10px;\
  padding:8px 11px;font-size:13.5px;outline:none;\
  resize:none;min-height:38px;max-height:100px;overflow-y:auto;line-height:1.45}\
#sc-in:focus{border-color:#E55B2D}\
#sc-btn{\
  background:#E55B2D;border:none;color:#fff;\
  border-radius:10px;min-width:38px;height:38px;cursor:pointer;\
  font-size:15px;display:flex;align-items:center;justify-content:center;flex-shrink:0}\
#sc-btn:hover{background:#c94e25}\
#sc-btn:disabled{background:#ccc;cursor:not-allowed}\
#sc-credit{text-align:center;font-size:10px;color:#c0c0c0;padding:4px 0 6px;flex-shrink:0;background:#fff}\
';

  var el = document.createElement('style');
  el.textContent = css;
  document.head.appendChild(el);

  // ── HTML ──────────────────────────────────────────────────────────────────
  var wrap = document.createElement('div');
  wrap.id = 'sc-widget';
  wrap.innerHTML =
    '<button id="sc-fab" title="Ask ' + BOT_NAME + '">&#x1F4AC;</button>' +
    '<div id="sc-panel">' +
      '<div id="sc-head">' +
        '<div id="sc-head-left">' +
          '<span id="sc-status"></span>' +
          '<span>&#x1F916; ' + BOT_NAME + '</span>' +
        '</div>' +
        '<button id="sc-x" title="Close">&#x2715;</button>' +
      '</div>' +
      '<div id="sc-msgs">' +
        '<div class="sc-msg sc-bot">Hi! I\'m ' + BOT_NAME + ', your CAT modelling assistant.\nAsk me anything &#x1F44B;</div>' +
      '</div>' +
      '<div id="sc-foot">' +
        '<textarea id="sc-in" placeholder="Ask a question…" rows="1"></textarea>' +
        '<button id="sc-btn" title="Send">&#x27A4;</button>' +
      '</div>' +
      '<div id="sc-credit">Powered by SmartCAT</div>' +
    '</div>';
  document.body.appendChild(wrap);

  // ── refs ──────────────────────────────────────────────────────────────────
  var fab  = document.getElementById('sc-fab');
  var panel= document.getElementById('sc-panel');
  var msgs = document.getElementById('sc-msgs');
  var inp  = document.getElementById('sc-in');
  var btn  = document.getElementById('sc-btn');
  var xBtn = document.getElementById('sc-x');

  // ── toggle ────────────────────────────────────────────────────────────────
  fab.addEventListener('click', function () {
    panel.classList.add('sc-open');
    inp.focus();
  });
  xBtn.addEventListener('click', function () {
    panel.classList.remove('sc-open');
  });

  // ── helpers ───────────────────────────────────────────────────────────────
  function addMsg(text, cls) {
    var el = document.createElement('div');
    el.className = 'sc-msg ' + cls;
    el.textContent = text;
    msgs.appendChild(el);
    msgs.scrollTop = msgs.scrollHeight;
    return el;
  }

  // ── send ──────────────────────────────────────────────────────────────────
  function send() {
    var q = inp.value.trim();
    if (!q || btn.disabled) return;
    inp.value = '';
    inp.style.height = '';
    btn.disabled = true;

    addMsg(q, 'sc-user');
    var thinking = addMsg('Thinking…', 'sc-think');

    var headers = { 'Content-Type': 'application/json' };
    if (API_KEY) headers['X-API-Key'] = API_KEY;

    fetch(API_URL + '/chat', {
      method: 'POST',
      headers: headers,
      body: JSON.stringify({
        question: q,
        session_id: sessionId,
        history: history.slice(-10),
      }),
    })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        msgs.removeChild(thinking);
        var answer = (data && data.answer) || (data && data.detail) || 'Sorry, I could not get a response.';
        addMsg(answer, 'sc-bot');
        history.push({ role: 'user', content: q });
        history.push({ role: 'assistant', content: answer });
      })
      .catch(function () {
        msgs.removeChild(thinking);
        addMsg('Connection error — is the SmartCAT server running?', 'sc-bot');
      })
      .finally(function () {
        btn.disabled = false;
        inp.focus();
      });
  }

  btn.addEventListener('click', send);
  inp.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });
  inp.addEventListener('input', function () {
    this.style.height = '';
    this.style.height = Math.min(this.scrollHeight, 100) + 'px';
  });
})();
