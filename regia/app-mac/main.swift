// Regia.app — finestra macOS sulla Regia (server locale http://127.0.0.1:8765).
// Niente logica qui: la pagina resta quella del server. L'app aggiunge solo
// finestra propria, pagina «non risponde» con Riprova, notifiche native e numero sul Dock.
import AppKit
import WebKit
import UserNotifications

let INDIRIZZO = URL(string: ProcessInfo.processInfo.environment["REGIA_URL"] ?? "http://127.0.0.1:8765/")!

// Ponte JS → Swift: Notification e setAppBadge della pagina finiscono qui (app.js non cambia).
let PONTE_JS = """
(() => {
  const h = (m) => window.webkit.messageHandlers.regia.postMessage(m);
  addEventListener("error", (e) => h({ tipo: "log", testo: "errore JS: " + e.message + " @" + e.filename + ":" + e.lineno }));
  addEventListener("unhandledrejection", (e) => h({ tipo: "log", testo: "promessa rifiutata: " + String(e.reason) }));
  // Niente service worker nell'app: le notifiche passano dal ponte, la cache non serve.
  try { delete Navigator.prototype.serviceWorker; } catch (_) {}
  if ("serviceWorker" in navigator) try {
    Object.defineProperty(Navigator.prototype, "serviceWorker", { configurable: true,
      get: () => ({ controller: null, register: () => Promise.resolve(), ready: new Promise(() => {}) }) });
  } catch (_) {}
  let permesso = window.__regiaPermesso || "default";
  class N {
    constructor(titolo, o) { o = o || {}; h({ tipo: "notifica", titolo: String(titolo), testo: String(o.body || ""), tag: String(o.tag || "") }); }
    static get permission() { return permesso; }
    static requestPermission() {
      return window.webkit.messageHandlers.regiaRisposta.postMessage({ tipo: "permesso" }).then((p) => (permesso = p));
    }
    close() {}
  }
  window.Notification = N;
  Navigator.prototype.setAppBadge = function (n) { h({ tipo: "badge", n: Number(n) || 0 }); return Promise.resolve(); };
  Navigator.prototype.clearAppBadge = function () { h({ tipo: "badge", n: 0 }); return Promise.resolve(); };
})();
"""

func paginaErrore(_ motivo: String) -> String {
  let m = motivo.replacingOccurrences(of: "<", with: "&lt;")
  return """
  <!doctype html><html lang="it"><meta charset="utf-8"><title>Regia</title>
  <style>
  :root{color-scheme:light dark;--s:#16181b;--t:#e8e8ea;--d:#9a9ca3;--a:#a3b8ff}
  @media (prefers-color-scheme: light){:root{--s:#f6f6f7;--t:#1b1c1f;--d:#5d6068;--a:#3653c9}}
  body{margin:0;height:100vh;display:grid;place-items:center;background:var(--s);color:var(--t);font:16px -apple-system,system-ui,sans-serif}
  main{max-width:30rem;padding:2rem;text-align:center}
  h1{font-size:1.4rem;margin:0 0 .6rem}p{color:var(--d);line-height:1.5;margin:.4rem 0}
  button{margin-top:1.2rem;font:inherit;padding:.6rem 1.6rem;border-radius:8px;border:0;background:var(--a);color:var(--s);cursor:pointer}
  code{font-size:.85em}
  </style>
  <main>
  <h1>La Regia non risponde</h1>
  <p>Il programma che tiene i dati della Regia (server su questo Mac) non è acceso o si sta riavviando.</p>
  <p>Riprovo da solo ogni 5 secondi. <span id="c"></span></p>
  <button id="r" autofocus>Riprova adesso</button>
  <p style="margin-top:1.6rem;font-size:.85rem">Se non torna: nel Terminale<br><code>launchctl kickstart -k gui/$(id -u)/local.regia.server</code></p>
  <p style="font-size:.75rem;opacity:.7">Dettaglio: \(m)</p>
  </main>
  <script>
  const riprova = () => window.webkit.messageHandlers.regia.postMessage({tipo:"riprova"});
  document.getElementById("r").onclick = riprova;
  let n = 5; setInterval(() => { n--; document.getElementById("c").textContent = n > 0 ? "(tra " + n + " s)" : ""; if (n <= 0) { n = 5; riprova(); } }, 1000);
  </script></html>
  """
}

final class Regia: NSObject, NSApplicationDelegate, NSWindowDelegate, WKNavigationDelegate, WKUIDelegate,
  WKScriptMessageHandler, WKScriptMessageHandlerWithReply, UNUserNotificationCenterDelegate {
  var finestra: NSWindow!
  var web: WKWebView!
  var inErrore = false
  var permesso = "default"
  var osservaTitolo: NSKeyValueObservation?

  func applicationDidFinishLaunching(_ n: Notification) {
    UNUserNotificationCenter.current().delegate = self
    menu()
    let cfg = WKWebViewConfiguration()
    let uc = cfg.userContentController
    uc.add(self, name: "regia")
    uc.addScriptMessageHandler(self, contentWorld: .page, name: "regiaRisposta")
    web = WKWebView(frame: .zero, configuration: cfg)
    web.navigationDelegate = self
    web.uiDelegate = self
    web.allowsBackForwardNavigationGestures = false
    if #available(macOS 13.3, *) { web.isInspectable = true }
    finestra = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1280, height: 860),
                        styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
    finestra.title = "Regia"
    finestra.minSize = NSSize(width: 380, height: 420)
    finestra.contentView = web
    // Titolo della finestra = titolo della pagina («PROVA Regia» sul server di prova).
    osservaTitolo = web.observe(\.title, options: [.new]) { [weak self] w, _ in
      if let t = w.title, !t.isEmpty { self?.finestra.title = t }
    }
    finestra.delegate = self
    finestra.isReleasedWhenClosed = false
    if !finestra.setFrameUsingName("RegiaFinestra") { finestra.center() }
    finestra.setFrameAutosaveName("RegiaFinestra")
    finestra.makeKeyAndOrderFront(nil)
    NSApp.activate(ignoringOtherApps: true)
    // Permesso notifiche già noto → la pagina parte col valore giusto.
    // Primo avvio vero: macOS chiede una volta il permesso (senza, niente numero sul Dock né avvisi).
    // Le prove con REGIA_URL non lo chiedono. Gli avvisi restano spenti finché l'utente non preme «Avvisi».
    let chiedi = ProcessInfo.processInfo.environment["REGIA_URL"] == nil
    UNUserNotificationCenter.current().getNotificationSettings { s0 in
      if s0.authorizationStatus == .notDetermined && chiedi {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in
          UNUserNotificationCenter.current().getNotificationSettings { s in
            DispatchQueue.main.async { self.permesso = Regia.nome(s.authorizationStatus); self.installaPonte(); self.web.reload() }
          }
        }
      }
      let s = s0
      DispatchQueue.main.async {
        self.permesso = Regia.nome(s.authorizationStatus)
        FileHandle.standardError.write("[Regia] permesso notifiche: \(self.permesso)\n".data(using: .utf8)!)
        self.installaPonte()
        self.carica()
      }
    }
  }

  static func log(_ t: String) { FileHandle.standardError.write("[Regia] \(t)\n".data(using: .utf8)!) }
  static func nome(_ st: UNAuthorizationStatus) -> String {
    switch st { case .authorized, .provisional: return "granted"; case .denied: return "denied"; default: return "default" }
  }

  func installaPonte() {
    let uc = web.configuration.userContentController
    uc.removeAllUserScripts()
    uc.addUserScript(WKUserScript(source: "window.__regiaPermesso = \"\(permesso)\";\n" + PONTE_JS,
                                  injectionTime: .atDocumentStart, forMainFrameOnly: true))
  }

  func carica() { inErrore = false; web.load(URLRequest(url: INDIRIZZO, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 8)) }

  // Chiudere la finestra = nasconderla; clic sul Dock la riapre. ⌘Q esce.
  func windowShouldClose(_ sender: NSWindow) -> Bool { sender.orderOut(nil); return false }
  func applicationShouldHandleReopen(_ s: NSApplication, hasVisibleWindows: Bool) -> Bool { finestra.makeKeyAndOrderFront(nil); return true }

  // --- navigazione
  func mostraErrore(_ e: Error) {
    let ns = e as NSError
    if ns.domain == NSURLErrorDomain && ns.code == NSURLErrorCancelled { return }
    inErrore = true
    web.loadHTMLString(paginaErrore(e.localizedDescription), baseURL: nil)
  }
  func webView(_ w: WKWebView, didFailProvisionalNavigation n: WKNavigation!, withError e: Error) { mostraErrore(e) }
  func webView(_ w: WKWebView, didFail n: WKNavigation!, withError e: Error) { mostraErrore(e) }
  func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationResponse, decisionHandler d: @escaping (WKNavigationResponsePolicy) -> Void) {
    if let r = a.response as? HTTPURLResponse, a.isForMainFrame, r.statusCode >= 500 {
      d(.cancel); mostraErrore(NSError(domain: "Regia", code: r.statusCode, userInfo: [NSLocalizedDescriptionKey: "il server risponde \(r.statusCode)"])); return
    }
    d(.allow)
  }
  func webView(_ w: WKWebView, didFinish n: WKNavigation!) {
    if !inErrore, ProcessInfo.processInfo.environment["REGIA_PROVA_NOTIFICA"] == "1" {
      w.evaluateJavaScript("new Notification('prova Regia', {body: 'notifica di prova', tag: 'prova'}); navigator.setAppBadge(3)")
    }
  }
  func webViewWebContentProcessDidTerminate(_ w: WKWebView) { carica() }
  // Link verso fuori dalla Regia → browser predefinito.
  func webView(_ w: WKWebView, decidePolicyFor a: WKNavigationAction, decisionHandler d: @escaping (WKNavigationActionPolicy) -> Void) {
    if let u = a.request.url, a.targetFrame?.isMainFrame ?? true, !Regia.interna(u) {
      NSWorkspace.shared.open(u); d(.cancel); return
    }
    d(.allow)
  }
  func webView(_ w: WKWebView, createWebViewWith c: WKWebViewConfiguration, for a: WKNavigationAction, windowFeatures f: WKWindowFeatures) -> WKWebView? {
    if let u = a.request.url { if Regia.interna(u) { w.load(a.request) } else { NSWorkspace.shared.open(u) } }
    return nil
  }
  static func interna(_ u: URL) -> Bool {
    if u.scheme == "about" || u.scheme == "data" || u.scheme == "blob" { return true }
    return u.host == INDIRIZZO.host && u.port == INDIRIZZO.port
  }
  func webView(_ w: WKWebView, runJavaScriptAlertPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo, completionHandler c: @escaping () -> Void) {
    let a = NSAlert(); a.messageText = m; a.runModal(); c()
  }
  func webView(_ w: WKWebView, runJavaScriptConfirmPanelWithMessage m: String, initiatedByFrame f: WKFrameInfo, completionHandler c: @escaping (Bool) -> Void) {
    let a = NSAlert(); a.messageText = m; a.addButton(withTitle: "OK"); a.addButton(withTitle: "Annulla"); c(a.runModal() == .alertFirstButtonReturn)
  }

  // --- ponte
  func userContentController(_ u: WKUserContentController, didReceive m: WKScriptMessage) {
    guard let d = m.body as? [String: Any], let tipo = d["tipo"] as? String else { return }
    switch tipo {
    case "riprova": carica()
    case "log": FileHandle.standardError.write(("[Regia] " + (d["testo"] as? String ?? "") + "\n").data(using: .utf8)!)
    case "badge":
      let n = (d["n"] as? NSNumber)?.intValue ?? 0
      NSApp.dockTile.badgeLabel = n > 0 ? String(n) : nil
      Regia.log("numero sul Dock: \(n)")
    case "notifica":
      let c = UNMutableNotificationContent()
      c.title = d["titolo"] as? String ?? "Regia"
      c.body = d["testo"] as? String ?? ""
      c.sound = .default
      let tag = (d["tag"] as? String).flatMap { $0.isEmpty ? nil : $0 } ?? UUID().uuidString
      UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: tag, content: c, trigger: nil)) { e in
        Regia.log("notifica «\(c.title)»: " + (e.map { "non mostrata (\($0.localizedDescription))" } ?? "mandata a macOS"))
      }
    default: break
    }
  }
  func userContentController(_ u: WKUserContentController, didReceive m: WKScriptMessage, replyHandler r: @escaping (Any?, String?) -> Void) {
    UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { _, _ in
      UNUserNotificationCenter.current().getNotificationSettings { s in
        DispatchQueue.main.async {
          self.permesso = Regia.nome(s.authorizationStatus)
          self.installaPonte()
          r(self.permesso, nil)
        }
      }
    }
  }
  // Notifica mostrata anche con l'app davanti solo se la finestra non è in primo piano (la pagina già filtra).
  func userNotificationCenter(_ c: UNUserNotificationCenter, willPresent n: UNNotification, withCompletionHandler h: @escaping (UNNotificationPresentationOptions) -> Void) {
    h([.banner, .sound])
  }
  func userNotificationCenter(_ c: UNUserNotificationCenter, didReceive r: UNNotificationResponse, withCompletionHandler h: @escaping () -> Void) {
    NSApp.activate(ignoringOtherApps: true); finestra.makeKeyAndOrderFront(nil); h()
  }

  // --- menu (serve anche per ⌘C/⌘V nelle caselle)
  @objc func ricarica() { if inErrore { carica() } else { web.reload() } }
  @objc func zoomPiu() { web.pageZoom = min(web.pageZoom + 0.1, 2) }
  @objc func zoomMeno() { web.pageZoom = max(web.pageZoom - 0.1, 0.6) }
  @objc func zoomNormale() { web.pageZoom = 1 }
  func menu() {
    let barra = NSMenu()
    func voce(_ m: NSMenu, _ t: String, _ s: Selector?, _ k: String, _ mod: NSEvent.ModifierFlags = .command, _ target: AnyObject? = nil) {
      let i = NSMenuItem(title: t, action: s, keyEquivalent: k); i.keyEquivalentModifierMask = mod; i.target = target; m.addItem(i)
    }
    func sotto(_ t: String) -> NSMenu { let i = NSMenuItem(); let m = NSMenu(title: t); i.submenu = m; barra.addItem(i); return m }
    let app = sotto("Regia")
    voce(app, "Nascondi Regia", #selector(NSApplication.hide(_:)), "h")
    voce(app, "Nascondi altre", #selector(NSApplication.hideOtherApplications(_:)), "h", [.command, .option])
    app.addItem(.separator())
    voce(app, "Esci da Regia", #selector(NSApplication.terminate(_:)), "q")
    let mod = sotto("Modifica")
    voce(mod, "Annulla", Selector(("undo:")), "z")
    voce(mod, "Ripeti", Selector(("redo:")), "z", [.command, .shift])
    mod.addItem(.separator())
    voce(mod, "Taglia", #selector(NSText.cut(_:)), "x")
    voce(mod, "Copia", #selector(NSText.copy(_:)), "c")
    voce(mod, "Incolla", #selector(NSText.paste(_:)), "v")
    voce(mod, "Seleziona tutto", #selector(NSText.selectAll(_:)), "a")
    let vista = sotto("Vista")
    voce(vista, "Ricarica", #selector(ricarica), "r", .command, self)
    voce(vista, "Ingrandisci", #selector(zoomPiu), "+", .command, self)
    voce(vista, "Riduci", #selector(zoomMeno), "-", .command, self)
    voce(vista, "Dimensione normale", #selector(zoomNormale), "0", .command, self)
    let fin = sotto("Finestra")
    voce(fin, "Chiudi", #selector(NSWindow.performClose(_:)), "w")
    voce(fin, "Riduci a icona", #selector(NSWindow.performMiniaturize(_:)), "m")
    voce(fin, "Ridimensiona", #selector(NSWindow.performZoom(_:)), "")
    NSApp.mainMenu = barra
    NSApp.windowsMenu = fin
  }
}

let app = NSApplication.shared
let delegato = Regia()
app.delegate = delegato
app.setActivationPolicy(.regular)
app.run()
