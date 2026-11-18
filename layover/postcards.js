/* Postcards: one photo per destination of something typical of that place.
   Photos come from Wikipedia (free licences) and are cached on the phone by sw.js.
   Places not in this list fall back to the city's own Wikipedia photo. */
(function () {
  "use strict";
  var SPOT = {
    DOH: "Museum of Islamic Art, Doha", DXB: "Burj Khalifa", LHR: "Tower Bridge", MAN: "Manchester Town Hall",
    BHX: "Selfridges Building, Birmingham", EDI: "Edinburgh Castle", DUB: "Ha'penny Bridge", CDG: "Eiffel Tower",
    NCE: "Promenade des Anglais", FRA: "Römerberg", MUC: "Marienplatz", BER: "Brandenburg Gate", DUS: "Rheinturm",
    AMS: "Canals of Amsterdam", BRU: "Grand-Place", ZRH: "Grossmünster", GVA: "Jet d'Eau", VIE: "Schönbrunn Palace",
    FCO: "Colosseum", MXP: "Milan Cathedral", VCE: "Grand Canal (Venice)", MAD: "Royal Palace of Madrid",
    BCN: "Sagrada Família", LIS: "Belém Tower", ATH: "Parthenon", IST: "Hagia Sophia", CPH: "Nyhavn",
    OSL: "Oslo Opera House", ARN: "Gamla stan", HEL: "Helsinki Cathedral", WAW: "Warsaw Old Town", PRG: "Charles Bridge",
    BUD: "Hungarian Parliament Building", OTP: "Palace of the Parliament", SOF: "Alexander Nevsky Cathedral, Sofia",
    TBS: "Narikala", GYD: "Flame Towers", EVN: "Yerevan Cascade", ALA: "Ascension Cathedral, Almaty", TAS: "Kukeldash Madrasa",
    JFK: "Statue of Liberty", BOS: "Faneuil Hall", IAD: "Lincoln Memorial", PHL: "Independence Hall", MIA: "South Beach",
    ATL: "Centennial Olympic Park", ORD: "Cloud Gate", DFW: "Reunion Tower", IAH: "Space Center Houston",
    LAX: "Hollywood Sign", SFO: "Golden Gate Bridge", SEA: "Space Needle", YUL: "Notre-Dame Basilica (Montreal)",
    YYZ: "CN Tower", GRU: "Avenida Paulista", EZE: "Caminito", BOG: "Monserrate", CAI: "Giza pyramid complex",
    CMN: "Hassan II Mosque", RAK: "Jemaa el-Fnaa", TUN: "Sidi Bou Said", ALG: "Notre-Dame d'Afrique",
    NBO: "Nairobi National Park", ADD: "Holy Trinity Cathedral (Addis Ababa)", ZNZ: "Stone Town", EBB: "Lake Victoria",
    KGL: "Kigali Convention Centre", LOS: "Lekki-Ikoyi Link Bridge", ABV: "Aso Rock", ACC: "Independence Arch",
    JNB: "Nelson Mandela Bridge", CPT: "Table Mountain", DUR: "Moses Mabhida Stadium", MPM: "Maputo railway station",
    WDH: "Christuskirche, Windhoek", SEZ: "Anse Source d'Argent", MRU: "Le Morne Brabant", RUH: "Kingdom Centre",
    JED: "King Fahd's Fountain", MED: "Al-Masjid an-Nabawi", KWI: "Kuwait Towers", BAH: "Bahrain World Trade Center",
    MCT: "Sultan Qaboos Grand Mosque", AMM: "Amman Citadel", BEY: "Pigeons' Rock", BGW: "Al-Shaheed Monument",
    EBL: "Erbil Citadel", IKA: "Azadi Tower", KHI: "Mazar-e-Quaid", LHE: "Badshahi Mosque", ISB: "Faisal Mosque",
    DEL: "India Gate", BOM: "Gateway of India", BLR: "Bangalore Palace", MAA: "Marina Beach", HYD: "Charminar",
    COK: "Chinese fishing nets", CCU: "Howrah Bridge", CMB: "Gangaramaya Temple", KTM: "Boudhanath", DAC: "Ahsan Manzil",
    BKK: "Wat Arun", HKT: "Big Buddha (Phuket)", KUL: "Petronas Towers", SIN: "Marina Bay Sands",
    CGK: "National Monument (Indonesia)", DPS: "Tanah Lot", MNL: "Intramuros",
    SGN: "Notre-Dame Cathedral Basilica of Saigon", HAN: "Hoàn Kiếm Lake", PNH: "Royal Palace, Phnom Penh",
    HKG: "Victoria Harbour", PVG: "The Bund", PEK: "Forbidden City", CAN: "Canton Tower", TPE: "Taipei 101",
    ICN: "Gyeongbokgung", NRT: "Sensō-ji", KIX: "Osaka Castle", SYD: "Sydney Opera House",
    MEL: "Flinders Street railway station", BNE: "Story Bridge", PER: "Kings Park", ADL: "Adelaide Oval",
    AKL: "Sky Tower (Auckland)", SVO: "Saint Basil's Cathedral", LED: "Winter Palace", KZN: "Kazan Kremlin",
    AER: "Sochi Olympic Park", SVX: "Church on the Blood", OVB: "Novosibirsk Opera and Ballet Theatre", VVO: "Russky Bridge",
    MEX: "Palacio de Bellas Artes", CUN: "Isla Mujeres", SCL: "Cerro San Cristóbal", LIM: "Plaza Mayor, Lima",
    LCA: "Church of Saint Lazarus, Larnaca", ZAG: "St. Mark's Church, Zagreb", KEF: "Hallgrímskirkja", BEG: "Belgrade Fortress"
  };
  var API = "https://en.wikipedia.org/api/rest_v1/page/summary/";
  var mem = {}, KEY = "lay.pc.", MONTH = 30 * 864e5;

  function big(url, w) { return url ? url.replace(/\/(\d+)px-/, "/" + w + "px-") : url; }
  function ask(title) {
    return fetch(API + encodeURIComponent(title.replace(/ /g, "_")), { headers: { "Accept": "application/json" } })
      .then(function (r) { if (!r.ok) throw 0; return r.json(); })
      .then(function (j) {
        var t = j.thumbnail || j.originalimage;
        if (!t || !t.source || j.type === "disambiguation") throw 0;
        return { img: big(t.source, 960), thumb: big(t.source, 240), title: j.title,
          link: (j.content_urls && j.content_urls.mobile && j.content_urls.mobile.page) || ("https://en.wikipedia.org/wiki/" + encodeURIComponent(j.title)) };
      });
  }
  function get(code, name) {
    var k = (code || name || "").trim(); if (!k) return Promise.reject();
    if (mem[k]) return mem[k];
    try {
      var c = JSON.parse(localStorage.getItem(KEY + k) || "null");
      if (c && Date.now() - c.at < MONTH) return (mem[k] = Promise.resolve(c));
    } catch (e) {}
    var first = SPOT[code] ? ask(SPOT[code]) : Promise.reject();
    mem[k] = first.catch(function () { return name ? ask(name) : Promise.reject(); }).then(function (p) {
      p.at = Date.now(); p.spot = !!SPOT[code] && p.title !== name;
      try { localStorage.setItem(KEY + k, JSON.stringify(p)); } catch (e) {}
      return p;
    });
    mem[k].catch(function () { delete mem[k]; });
    return mem[k];
  }

  /* Today: the big postcard under the boarding pass */
  var seq = 0;
  function today(d) {
    var box = document.getElementById("postcard"); if (!box || !d) return;
    var my = ++seq;
    box.classList.remove("in");
    get(d.code, d.name).then(function (p) {
      if (my !== seq) return;
      var img = box.querySelector("img");
      box.querySelector(".pc-from").textContent = "Postcard from " + d.name;
      box.querySelector(".pc-what").textContent = p.title;
      box.querySelector(".pc-stamp b").textContent = d.code || (d.cc || "").toUpperCase() || "★";
      var a = box.querySelector(".pc-credit"); a.href = p.link;
      img.onload = function () { if (my === seq) { box.hidden = false; requestAnimationFrame(function () { box.classList.add("in"); }); } };
      img.onerror = function () { if (my === seq) box.hidden = true; };
      img.alt = p.title + ", " + d.name;
      img.src = p.img;
    }).catch(function () { if (my === seq) box.hidden = true; });
  }

  /* Any element with data-pc="CODE" data-pcn="City" gets that place's photo as its background */
  function fill(root) {
    (root || document).querySelectorAll("[data-pc],[data-pcn]").forEach(function (el) {
      if (el.dataset.pcDone) return; el.dataset.pcDone = "1";
      get(el.dataset.pc, el.dataset.pcn).then(function (p) {
        var im = new Image();
        im.onload = function () { el.style.backgroundImage = "url(\"" + p.thumb.replace(/"/g, "%22") + "\")"; el.classList.add("in"); };
        im.src = p.thumb;
      }).catch(function () {});
    });
  }
  window.LayoverPostcard = { today: today, fill: fill, get: get };
})();
