/* Cookie and storage notice for karawene112.github.io and Layover Logbook.
   The site uses no advertising or tracking cookies. It only keeps data in the browser
   (localStorage) that the app needs to work, which doesn't require consent, so this is
   an information banner with a single "Got it" button. Shown once per browser. */
(function () {
  var KEY = "cookie-notice-v1";
  try { if (localStorage.getItem(KEY)) return; } catch (e) { /* storage blocked: show each visit */ }

  var fr = /^fr\b/i.test(navigator.language || "");
  var t = fr ? {
    title: "Cookies et stockage",
    body: "Aucun cookie publicitaire ni de suivi. Seulement ce dont l'app a besoin.",
    link: "Politique de confidentialité", href: "/layover/politique-de-confidentialite.html", ok: "J'ai compris"
  } : {
    title: "Cookies and storage",
    body: "No ads, no tracking. Only what the app needs to work.",
    link: "Privacy policy", href: "/layover/privacy-policy.html", ok: "Got it"
  };

  function show() {
    if (document.getElementById("cookieNotice")) return;
    var tabbar = document.querySelector(".tabbar");
    var bottom = tabbar ? (tabbar.getBoundingClientRect().height + 12) + "px" : "16px";

    var css = document.createElement("style");
    css.textContent =
      "#cookieNotice{position:fixed;left:12px;right:12px;bottom:calc(" + bottom + " + env(safe-area-inset-bottom,0px));z-index:55;" +
      "max-width:560px;margin:0 auto;background:#14223A;color:#F3F5FA;border-radius:16px;padding:16px 18px;" +
      "box-shadow:0 10px 30px rgba(0,0,0,.28);font:15px/1.45 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;" +
      "display:grid;gap:10px;animation:cnIn .25s ease-out}" +
      "#cookieNotice b{font-size:16px}" +
      "#cookieNotice p{margin:0;color:#C9D1E3}" +
      "#cookieNotice .cn-row{display:flex;gap:12px;align-items:center;justify-content:space-between;flex-wrap:wrap}" +
      "#cookieNotice a{color:#F6B26B;font-weight:600}" +
      "#cookieNotice button{border:0;border-radius:999px;padding:10px 20px;font:600 15px/1 inherit;font-family:inherit;" +
      "background:#F28C38;color:#14223A;cursor:pointer;min-height:44px}" +
      "#cookieNotice button:focus-visible,#cookieNotice a:focus-visible{outline:3px solid #F6B26B;outline-offset:2px}" +
      "@keyframes cnIn{from{transform:translateY(12px);opacity:0}to{transform:none;opacity:1}}" +
      "@media (prefers-reduced-motion:reduce){#cookieNotice{animation:none}}";
    document.head.appendChild(css);

    var box = document.createElement("section");
    box.id = "cookieNotice";
    box.setAttribute("role", "region");
    box.setAttribute("aria-label", t.title);
    box.lang = fr ? "fr" : "en";
    box.innerHTML = "<b></b><p></p><div class='cn-row'><a></a><button type='button'></button></div>";
    box.querySelector("b").textContent = t.title;
    box.querySelector("p").textContent = t.body;
    var a = box.querySelector("a"); a.textContent = t.link; a.href = t.href;
    var btn = box.querySelector("button"); btn.textContent = t.ok;
    btn.addEventListener("click", function () {
      try { localStorage.setItem(KEY, new Date().toISOString()); } catch (e) {}
      box.remove();
    });
    document.body.appendChild(box);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", show);
  else show();
})();
