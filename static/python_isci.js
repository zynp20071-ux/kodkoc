// KodKoç - Tarayıcıda Python çalıştıran "işçi" (Web Worker), 9. hafta
//
// Neden işçi? Sayfanın kendisinde çalıştırsaydık "while True:" gibi bitmeyen bir döngü
// sayfayı dondururdu. İşçi ayrı bir iş parçacığında çalışır; sayfa onu istediği an
// durdurabilir (worker.terminate()).
//
// Python nereden geliyor? Pyodide: Python'un WebAssembly'ye derlenmiş hali. Kod KodKoç'un
// sunucusunda değil, öğrencinin kendi tarayıcısında çalışır; sunucuya yük ve güvenlik riski yok.
//
// Sayfayla konuşma (postMessage):
//   gelen  : {kod: "...", girdi: "Ali\n12"}            (girdi: input() için satır satır)
//   giden  : {tur: "hazir"} | {tur: "cikti", metin} | {tur: "hata", metin} | {tur: "bitti"}

const PYODIDE = "https://cdn.jsdelivr.net/pyodide/v0.27.7/full/";
importScripts(PYODIDE + "pyodide.js");

const cozucu = new TextDecoder();
const hazir = loadPyodide({ indexURL: PYODIDE }).then(function (pyodide) {
  postMessage({ tur: "hazir" });
  return pyodide;
});

// Python'un hata mesajından Pyodide'nin kendi iç satırlarını temizle; öğrenci sadece
// kendi kodundaki satırı görsün ("File "<exec>", line 3").
function hatayiSadelestir(metin) {
  const satirlar = metin.split("\n");
  const temiz = [];
  for (let i = 0; i < satirlar.length; i++) {
    if (/File "\/lib\/python|_pyodide/.test(satirlar[i])) {
      i++;                       // Bir sonraki satır o iç dosyanın kod satırı; onu da atla
      continue;
    }
    temiz.push(satirlar[i].replace('File "<exec>"', "Senin kodun"));
  }
  return temiz.join("\n").trim();
}

onmessage = async function (olay) {
  const pyodide = await hazir;
  const kod = olay.data.kod;
  const girdiler = olay.data.girdi ? olay.data.girdi.split("\n") : [];
  let sira = 0;

  pyodide.setStdout({ write: function (b) { postMessage({ tur: "cikti", metin: cozucu.decode(b) }); return b.length; } });
  pyodide.setStderr({ write: function (b) { postMessage({ tur: "hata", metin: cozucu.decode(b) }); return b.length; } });
  // input(): "Girdiler" kutusundaki sıradaki satırı verir ve terminaldeki gibi ekrana da yazar
  pyodide.setStdin({
    stdin: function () {
      if (sira >= girdiler.length) return null;           // Girdi bitti: input() EOFError verir
      const satir = girdiler[sira++];
      postMessage({ tur: "girdi", metin: satir + "\n" });
      return satir;
    },
  });

  // Her çalıştırma temiz başlasın: önceki çalıştırmanın değişkenleri kalmasın
  const alan = pyodide.globals.get("dict")();
  try {
    await pyodide.loadPackagesFromImports(kod);           // Ör. "import numpy" varsa indir
    await pyodide.runPythonAsync(kod, { globals: alan });
  } catch (hata) {
    let mesaj = hatayiSadelestir(String(hata.message || hata));
    if (mesaj.includes("EOFError")) {
      mesaj += "\n\nİpucu: Kodun input() ile girdi bekliyor. Girdileri yukarıdaki \"Girdiler\" kutusuna her satıra bir tane yaz.";
    }
    postMessage({ tur: "hata", metin: mesaj + "\n" });
  } finally {
    alan.destroy();
    postMessage({ tur: "bitti" });
  }
};
