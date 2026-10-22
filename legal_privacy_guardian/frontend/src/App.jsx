import { useEffect, useMemo, useRef, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowDownToLine,
  ArrowUpRight,
  Check,
  ChevronDown,
  Clock3,
  Download,
  Eye,
  FileCheck2,
  FileText,
  Fingerprint,
  FolderClosed,
  History,
  LoaderCircle,
  LockKeyhole,
  MessageCircle,
  Paperclip,
  Scale,
  Search,
  Send,
  ShieldCheck,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";

const SUPPORTED_EXTENSIONS = [
  ".txt", ".md", ".csv", ".json", ".xml", ".html", ".htm", ".rtf",
  ".pdf", ".docx", ".pptx", ".xlsx", ".xls",
];
const MAX_FILE_SIZE = 15 * 1024 * 1024;

function formatDate(value) {
  const date = new Date(`${value.replace(" ", "T")}Z`);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function countFindings(findings = {}) {
  return Object.values(findings).reduce((total, count) => total + count, 0);
}

function App() {
  const [scans, setScans] = useState([]);
  const [countries, setCountries] = useState({});
  const [geminiHealth, setGeminiHealth] = useState(null);
  const [countryCode, setCountryCode] = useState(() => localStorage.getItem("guardian-country") || "");
  const [onboardingCountry, setOnboardingCountry] = useState(() => localStorage.getItem("guardian-country") || "");
  const [activePage, setActivePage] = useState("assistant");
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState("");
  const [chatNotice, setChatNotice] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatFile, setChatFile] = useState(null);
  const [availableRedactedDocument, setAvailableRedactedDocument] = useState(null);
  const [file, setFile] = useState(null);
  const [notice, setNotice] = useState(null);
  const [lastResult, setLastResult] = useState(null);
  const [selectedReport, setSelectedReport] = useState(null);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);
  const chatDocumentRef = useRef(null);

  async function refreshScans() {
    const response = await fetch("/api/scans");
    if (!response.ok) throw new Error("Impossible de charger les analyses.");
    const payload = await response.json();
    setScans(payload.scans ?? []);
  }

  useEffect(() => {
    refreshScans().catch((error) => setNotice({ type: "error", text: error.message }));
    fetch("/api/countries")
      .then((response) => response.json())
      .then((payload) => setCountries(payload.countries || {}))
      .catch(() => setChatNotice("Impossible de charger la liste des pays."));
    fetch("/api/health")
      .then(async (response) => {
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.error || `Erreur HTTP ${response.status}.`);
        }
        if (
          !payload.gemini ||
          typeof payload.gemini.available !== "boolean" ||
          typeof payload.gemini.model_available !== "boolean"
        ) {
          throw new Error("La réponse de statut Gemini est invalide.");
        }
        setGeminiHealth(payload.gemini);
      })
      .catch((error) =>
        setGeminiHealth({
          available: false,
          model_available: false,
          error: error.message || "Impossible de vérifier l’état de Gemini.",
        }),
      );
    const updatePage = () => setActivePage("assistant");
    window.addEventListener("hashchange", updatePage);
    return () => window.removeEventListener("hashchange", updatePage);
  }, []);

  function selectCountry(value) {
    setCountryCode(value);
    localStorage.setItem("guardian-country", value);
    setChatMessages([]);
    setChatNotice("");
  }

  async function submitQuestion(event) {
    event.preventDefault();
    const question = chatInput.trim();
    if (!question || chatBusy) return;
    setChatBusy(true);
    setChatNotice("");
    try {
      const formData = new FormData();
      formData.append("country", countryCode);
      formData.append("message", question);
      formData.append("history", JSON.stringify(chatMessages.slice(-10).map(({ role, content }) => ({ role, content }))));
      if (chatFile) formData.append("document", chatFile);
      const response = await fetch("/api/chat", {
        method: "POST",
        body: formData,
      });
      const payload = await response.json();
      if (!response.ok) {
        if (payload.document) setAvailableRedactedDocument(payload.document);
        throw new Error(payload.error || "L’assistant n’a pas pu répondre.");
      }
      setAvailableRedactedDocument(null);
      setChatMessages((current) => [
        ...current,
        { role: "user", content: question, document: payload.document },
        { role: "assistant", content: payload.answer },
      ]);
      setChatInput("");
      setChatFile(null);
      if (chatDocumentRef.current) chatDocumentRef.current.value = "";
    } catch (error) {
      setChatNotice(error.message || "Le serveur est injoignable.");
    } finally {
      setChatBusy(false);
    }
  }

  function chooseChatDocument(candidate) {
    if (!candidate) return;
    if (!SUPPORTED_EXTENSIONS.some((extension) => candidate.name.toLowerCase().endsWith(extension))) {
      setChatNotice("Ce format de document n’est pas pris en charge.");
      return;
    }
    if (candidate.size > MAX_FILE_SIZE) {
      setChatNotice("Le document dépasse la limite de 15 Mo.");
      return;
    }
    setChatFile(candidate);
    setChatNotice("");
  }

  function downloadAssistantDocument(documentResult) {
    const blob = new Blob([documentResult.redacted_text], { type: "text/plain;charset=utf-8" });
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = documentResult.output_filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
  }

  const totalFindings = useMemo(
    () => scans.reduce((total, scan) => total + countFindings(scan.findings), 0),
    [scans],
  );
  const flaggedScans = useMemo(
    () => scans.filter((scan) => countFindings(scan.findings) > 0).length,
    [scans],
  );
  const visibleScans = scans.filter((scan) =>
    scan.filename.toLowerCase().includes(query.trim().toLowerCase()),
  );

  function chooseFile(candidate) {
    if (!candidate) return;
    if (!SUPPORTED_EXTENSIONS.some((extension) => candidate.name.toLowerCase().endsWith(extension))) {
      setFile(null);
      setNotice({ type: "error", text: "Ce format n’est pas pris en charge par l’extracteur local." });
      return;
    }
    if (candidate.size > MAX_FILE_SIZE) {
      setFile(null);
      setNotice({ type: "error", text: "Le fichier dépasse la limite de 15 Mo." });
      return;
    }
    setFile(candidate);
    setLastResult(null);
    setNotice(null);
  }

  async function submitScan(event) {
    event.preventDefault();
    if (!file || busy) return;

    setBusy(true);
    setNotice(null);
    const formData = new FormData();
    formData.append("document", file);

    try {
      const response = await fetch("/api/scan", { method: "POST", body: formData });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "L’analyse a échoué.");
      setNotice({ type: "success", text: payload.message });
      setLastResult(payload);
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      await refreshScans();
    } catch (error) {
      setNotice({ type: "error", text: error.message || "Le serveur est injoignable." });
    } finally {
      setBusy(false);
    }
  }

  function onDrop(event) {
    event.preventDefault();
    setDragging(false);
    chooseFile(event.dataTransfer.files[0]);
  }

  function downloadRedactedText() {
    if (!lastResult) return;
    const blob = new Blob([lastResult.redacted_text], { type: "text/plain;charset=utf-8" });
    const downloadUrl = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = downloadUrl;
    link.download = lastResult.output_filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(downloadUrl), 1000);
  }

  async function openReport(scanId) {
    try {
      const response = await fetch(`/api/scans/${scanId}`);
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Rapport introuvable.");
      setSelectedReport(payload.scan);
    } catch (error) {
      setNotice({ type: "error", text: error.message || "Impossible de charger le rapport." });
    }
  }

  async function removeReport(scanId) {
    try {
      const response = await fetch(`/api/scans/${scanId}`, { method: "DELETE" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Suppression impossible.");
      if (selectedReport?.id === scanId) setSelectedReport(null);
      if (lastResult?.scan_id === scanId) setLastResult(null);
      await refreshScans();
    } catch (error) {
      setNotice({ type: "error", text: error.message || "Suppression impossible." });
    }
  }

  async function clearHistory() {
    if (!scans.length || !window.confirm("Supprimer définitivement tous les rapports locaux ?")) return;
    try {
      const response = await fetch("/api/scans", { method: "DELETE" });
      const payload = await response.json();
      if (!response.ok) throw new Error(payload.error || "Suppression impossible.");
      setSelectedReport(null);
      setLastResult(null);
      setNotice({ type: "success", text: `${payload.deleted_count} rapport(s) supprimé(s).` });
      await refreshScans();
    } catch (error) {
      setNotice({ type: "error", text: error.message || "Suppression impossible." });
    }
  }

  if (!countryCode) {
    return (
      <main className="onboarding-shell">
        <section className="onboarding-panel">
          <span className="onboarding-mark"><ShieldCheck size={24} /></span>
          <p className="eyebrow"><span className="eyebrow-line" />CONFIGURATION INITIALE</p>
          <h1>Quel droit<br />vous concerne&nbsp;?</h1>
          <p className="onboarding-copy">Choisissez votre pays pour que l’assistant juridique cadre ses réponses selon la bonne juridiction.</p>
          <label className="country-field">PAYS DE RÉFÉRENCE
            <select value={onboardingCountry} onChange={(event) => setOnboardingCountry(event.target.value)}>
              <option value="">Sélectionner un pays</option>
              {Object.entries(countries).sort(([, first], [, second]) => first.name.localeCompare(second.name, "fr")).map(([code, country]) => (
                <option key={code} value={code}>{country.name}</option>
              ))}
            </select>
          </label>
          <button className="analyze-button onboarding-submit" type="button" disabled={!onboardingCountry} onClick={() => { selectCountry(onboardingCountry); window.location.hash = "assistant"; }}>
            Continuer <ArrowUpRight size={16} />
          </button>
          {!Object.keys(countries).length && <p className="country-loading">Chargement de la liste des pays…</p>}
          <p className="onboarding-foot"><LockKeyhole size={13} />Votre choix reste enregistré sur cet appareil.</p>
        </section>
      </main>
    );
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a className="brand-lockup" href="#assistant" aria-label="Legal Privacy Guardian, accueil">
          <span className="brand-mark"><ShieldCheck size={21} strokeWidth={2.2} /></span>
          <span className="brand-name">Legal Privacy<span>Guardian</span></span>
        </a>

        <label className="workspace-picker" htmlFor="workspace-country">
          <span className="workspace-icon"><FolderClosed size={16} /></span>
          <span className="workspace-copy"><small>PAYS DE RÉFÉRENCE</small>
            <select id="workspace-country" value={countryCode} onChange={(event) => selectCountry(event.target.value)}>
              {Object.entries(countries).sort(([, first], [, second]) => first.name.localeCompare(second.name, "fr")).map(([code, country]) => (
                <option key={code} value={code}>{country.name}</option>
              ))}
            </select>
          </span>
          <ChevronDown size={15} className="workspace-chevron" />
        </label>

        <div className="sidebar-bottom">
          <div className="local-status"><span className="pulse-dot" /><span><strong>Analyse locale avant envoi</strong><small>Les fichiers sont masqués en mémoire</small></span></div>
          <div className="sidebar-version"><span>PROTOTYPE</span><span>v0.1</span></div>
        </div>
      </aside>

      <main className="main-panel" id={activePage}>
        <header className="topbar">
          <div className="breadcrumb"><span>{countries[countryCode]?.name || "Espace"}</span><span className="crumb-separator">/</span><strong>{activePage === "assistant" ? "Assistant juridique" : activePage === "documents" ? "Analyse de document" : "Vue d’ensemble"}</strong></div>
          <div className="topbar-right"><span className="secure-label" title={geminiHealth?.error || ""}><LockKeyhole size={14} />{geminiHealth === null ? "Vérification Gemini…" : geminiHealth.available && geminiHealth.model_available ? "Gemini prêt · API Google" : "Gemini indisponible"}</span><span className="avatar" title="Application locale"><Activity size={14} /></span></div>
        </header>

        <div className="page-content">
          <section className="page-heading">
            <div>
              <p className="eyebrow"><span className="eyebrow-line" />{activePage === "assistant" ? "INFORMATION JURIDIQUE" : activePage === "documents" ? "PROTECTION DES DOCUMENTS" : "CENTRE DE CONFIDENTIALITÉ"}</p>
              <h1>{activePage === "assistant" ? <>Des réponses<br className="mobile-break" /> selon votre droit.</> : activePage === "documents" ? <>Vos documents,<br className="mobile-break" /> sous contrôle.</> : <>La confidentialité<br className="mobile-break" /> en pratique.</>}</h1>
              <p className="heading-subtitle">{activePage === "assistant" ? `Juridiction active : ${countries[countryCode]?.name || ""}.` : activePage === "documents" ? "Repérez et masquez localement les données sensibles." : "Analysez vos fichiers ou posez une question juridique."}</p>
            </div>
            <div className="heading-stamp"><Fingerprint size={20} /><span>Vérification<br /><strong>sur cet appareil</strong></span></div>
          </section>

          {activePage === "overview" && <section className="metrics-grid" aria-label="Résumé des analyses">
            <article className="metric metric-main">
              <span className="metric-icon mint"><FileCheck2 size={18} /></span>
              <span className="metric-label">Documents analysés</span>
              <strong className="metric-value">{scans.length}</strong>
              <span className="metric-foot">Historique récent</span>
            </article>
            <article className="metric">
              <span className="metric-icon coral"><AlertTriangle size={18} /></span>
              <span className="metric-label">À vérifier</span>
              <strong className="metric-value">{flaggedScans}</strong>
              <span className="metric-foot">Documents avec détection</span>
            </article>
            <article className="metric">
              <span className="metric-icon gold"><Fingerprint size={18} /></span>
              <span className="metric-label">Éléments repérés</span>
              <strong className="metric-value">{totalFindings}</strong>
              <span className="metric-foot">Sur les 100 derniers rapports</span>
            </article>
          </section>}

          {activePage === "overview" && <section className="overview-actions" id="overview" aria-label="Outils">
            <a className="overview-action" href="#assistant"><span className="overview-action-icon"><Scale size={19} /></span><span><strong>Assistant juridique</strong><small>Questions de droit en {countries[countryCode]?.name || ""}</small></span><ArrowUpRight size={17} /></a>
            <a className="overview-action" href="#documents"><span className="overview-action-icon"><FileCheck2 size={19} /></span><span><strong>Analyser un document</strong><small>Masquage local et historique des contrôles</small></span><ArrowUpRight size={17} /></a>
          </section>}

          {activePage === "documents" && <>
          <section className="work-grid" id="documents" aria-label="Nouvelle analyse">
            <div className="panel upload-panel">
              <div className="panel-heading">
                <div><p className="panel-kicker">NOUVEAU CONTRÔLE</p><h2>Analyser un document</h2></div>
                <span className="step-mark">01 <span>/ 03</span></span>
              </div>
              <form onSubmit={submitScan}>
                <div
                  className={`drop-zone${dragging ? " is-dragging" : ""}${file ? " has-file" : ""}`}
                  onDragEnter={(event) => { event.preventDefault(); setDragging(true); }}
                  onDragOver={(event) => event.preventDefault()}
                  onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setDragging(false); }}
                  onDrop={onDrop}
                >
                  <input
                    ref={inputRef}
                    className="visually-hidden"
                    id="document"
                    name="document"
                    type="file"
                    accept={SUPPORTED_EXTENSIONS.join(",")}
                    aria-label="Choisir un document à analyser"
                    onChange={(event) => chooseFile(event.target.files[0])}
                  />
                  {file ? (
                    <div className="file-selected">
                      <span className="file-icon"><FileText size={21} /></span>
                      <span className="file-copy"><strong>{file.name}</strong><small>{(file.size / 1024).toFixed(1)} Ko · Prêt à analyser</small></span>
                      <button className="remove-file" type="button" onClick={() => { setFile(null); inputRef.current.value = ""; }} aria-label="Retirer le fichier"><X size={17} /></button>
                    </div>
                  ) : (
                    <>
                      <span className="upload-icon"><UploadCloud size={22} /></span>
                      <strong>Déposez votre fichier ici</strong>
                      <span className="drop-caption">PDF, Office, RTF, HTML, CSV, JSON, XML, TXT/MD · 15 Mo max.</span>
                      <button className="browse-button" type="button" onClick={() => inputRef.current?.click()}>Parcourir les fichiers <ArrowUpRight size={14} /></button>
                    </>
                  )}
                </div>

                {notice && <div className={`notice ${notice.type}`} role="status"><span>{notice.type === "success" ? <Check size={16} /> : <AlertTriangle size={16} />}</span>{notice.text}</div>}

                <div className="upload-footer">
                  <span className="file-limit"><LockKeyhole size={14} />Texte extrait traité en mémoire</span>
                  <button className="analyze-button" type="submit" disabled={!file || busy}>
                    {busy ? <><LoaderCircle className="spin" size={17} /> Analyse…</> : <>Lancer l’analyse <ArrowDownToLine size={16} /></>}
                  </button>
                </div>
              </form>
              {lastResult && (
                <section className="result-preview" aria-labelledby="result-preview-title">
                  <div className="result-preview-heading">
                    <div><p className="panel-kicker">RÉSULTAT DU CONTRÔLE</p><h3 id="result-preview-title">Texte masqué</h3></div>
                    <button className="remove-file" type="button" onClick={() => setLastResult(null)} aria-label="Fermer le rapport"><X size={17} /></button>
                  </div>
                  <div className="finding-list">
                    {Object.entries(lastResult.findings).map(([category, count]) => (
                      <span className="finding-chip" key={category}><strong>{count}</strong>{category}</span>
                    ))}
                  </div>
                  <pre className="redacted-preview">{lastResult.redacted_text.slice(0, 12000)}{lastResult.redacted_text.length > 12000 ? "\n… aperçu limité; le fichier téléchargé contient le document complet." : ""}</pre>
                  <button className="download-button" type="button" onClick={downloadRedactedText}><Download size={15} />Télécharger le texte masqué (.txt)</button>
                </section>
              )}
            </div>

            <aside className="panel coverage-panel">
              <div className="coverage-top"><span className="coverage-symbol"><ShieldCheck size={20} /></span><span className="coverage-state"><span className="pulse-dot" />ACTIF</span></div>
              <p className="panel-kicker">MOTEUR DE PROTECTION</p>
              <h2>Détection locale</h2>
              <p className="coverage-description">Le texte extrait reste dans le traitement local. Le fichier d’origine n’est pas modifié.</p>
              <div className="coverage-rule" />
              <div className="coverage-types"><span>Motifs surveillés</span><strong>02 catégories</strong></div>
              <div className="type-row"><span className="type-dot email-dot" />Adresses e-mail <span className="type-ready">Prêt</span></div>
              <div className="type-row"><span className="type-dot phone-dot" />Téléphones français <span className="type-ready">Prêt</span></div>
              <div className="coverage-note"><AlertTriangle size={15} /><span>Les PDF scannés et images nécessitent un OCR non activé. La détection reste partielle.</span></div>
            </aside>
          </section>

          <section className="history-section" id="history">
            <div className="history-heading">
              <div><p className="panel-kicker">JOURNAL D’ACTIVITÉ</p><h2>Analyses récentes <span className="history-count">{scans.length}</span></h2></div>
              <div className="history-tools">
                <label className="search-box"><Search size={16} /><input aria-label="Rechercher un document" placeholder="Rechercher un fichier" value={query} onChange={(event) => setQuery(event.target.value)} /></label>
                <button className="clear-history-button" type="button" onClick={clearHistory} disabled={!scans.length} title="Supprimer tout l’historique"><Trash2 size={15} /><span>Vider</span></button>
              </div>
            </div>
            <div className="history-table-wrap">
              <table className="history-table">
                <thead><tr><th>DOCUMENT</th><th>DATE D’ANALYSE</th><th>RÉSULTAT</th><th aria-label="Détails" /></tr></thead>
                <tbody>
                  {visibleScans.map((scan) => {
                    const total = countFindings(scan.findings);
                    return (
                      <tr key={scan.id}>
                        <td><span className="document-cell-icon"><FileText size={16} /></span><span className="document-name">{scan.filename}</span></td>
                        <td className="date-cell"><Clock3 size={14} />{formatDate(scan.scanned_at)}</td>
                        <td>{total ? <span className="result-pill flagged"><span />{total} potentiel(s)</span> : <span className="result-pill clear"><span />Aucun repéré</span>}</td>
                        <td className="row-actions">
                          <button className="table-action" type="button" onClick={() => openReport(scan.id)} aria-label={`Consulter le rapport de ${scan.filename}`} title="Consulter le rapport"><Eye size={15} /></button>
                          <button className="table-action danger-action" type="button" onClick={() => removeReport(scan.id)} aria-label={`Supprimer ${scan.filename}`} title="Supprimer"><Trash2 size={14} /></button>
                        </td>
                      </tr>
                    );
                  })}
                  {!visibleScans.length && <tr><td className="empty-row" colSpan="4">{scans.length ? "Aucun fichier correspondant." : "Aucune analyse enregistrée."}</td></tr>}
                </tbody>
              </table>
            </div>
            <div className="history-foot"><span><span className="history-dot" />Base locale SQLite</span><span>100 rapports maximum</span></div>
          </section>
          </>}

          {activePage === "assistant" && <section className="assistant-layout" id="assistant" aria-label="Assistant juridique">
            <div className="assistant-chat">
              <div className="assistant-chat-heading"><span className="chat-icon"><Scale size={18} /></span><div><strong>Assistant juridique</strong><small>{countries[countryCode]?.name || ""} · Sources officielles de référence</small></div><span className="chat-country">{countryCode}</span></div>
              <div className="chat-messages" aria-live="polite">
                {!chatMessages.length && <div className="chat-empty"><MessageCircle size={24} /><strong>Que souhaitez-vous comprendre&nbsp;?</strong><span>Posez une question sur les lois et démarches de votre pays.</span></div>}
                {chatMessages.map((message, index) => <article className={`chat-message ${message.role}`} key={`${index}-${message.role}`}><span className="chat-message-label">{message.role === "user" ? "VOUS" : "ASSISTANT"}</span><p>{message.content}</p>{message.document && <div className="chat-document-result"><span>{message.document.filename} · {countFindings(message.document.findings)} élément(s) pseudonymisé(s)</span><small>Catégories repérées : {Object.entries(message.document.findings || {}).map(([category, count]) => `${category} (${count})`).join(", ") || "aucune par les règles prises en charge"}</small><button className="download-button" type="button" onClick={() => downloadAssistantDocument(message.document)}><Download size={14} />Télécharger le texte protégé (.txt)</button></div>}</article>)}
                {chatBusy && <div className="chat-loading"><LoaderCircle className="spin" size={16} />Préparation de la réponse…</div>}
              </div>
              {chatNotice && <div className="notice error" role="alert"><span><AlertTriangle size={16} /></span>{chatNotice}</div>}
              {availableRedactedDocument && <div className="redacted-available"><span>Le texte a été pseudonymisé localement. Ce traitement ne garantit pas l’anonymisation complète.</span><button className="download-button" type="button" onClick={() => downloadAssistantDocument(availableRedactedDocument)}><Download size={14} />Télécharger le texte protégé (.txt)</button></div>}
              <form className="chat-compose" onSubmit={submitQuestion}>
                <input ref={chatDocumentRef} className="visually-hidden" type="file" accept={SUPPORTED_EXTENSIONS.join(",")} aria-label="Choisir un document à joindre" onChange={(event) => chooseChatDocument(event.target.files[0])} />
                {chatFile && <div className="chat-attachment"><FileText size={15} /><span>{chatFile.name}</span><button className="remove-file" type="button" onClick={() => { setChatFile(null); if (chatDocumentRef.current) chatDocumentRef.current.value = ""; }} aria-label="Retirer le document joint"><X size={15} /></button></div>}
                <textarea value={chatInput} onChange={(event) => setChatInput(event.target.value)} maxLength={4000} rows={3} placeholder="Écrivez votre question…" aria-label="Votre question juridique" />
                <div className="chat-compose-footer"><span>{chatInput.length}/4 000 · Document pseudonymisé localement avant analyse</span><div className="chat-compose-actions"><button className="attach-button" type="button" onClick={() => chatDocumentRef.current?.click()} disabled={chatBusy}><Paperclip size={16} /><span>Joindre</span></button><button className="analyze-button" type="submit" disabled={!chatInput.trim() || chatBusy} aria-label="Envoyer la question">{chatBusy ? <LoaderCircle className="spin" size={17} /> : <Send size={16} />} Envoyer</button></div></div>
              </form>
            </div>
            <aside className="assistant-disclosure"><p className="panel-kicker">PÉRIMÈTRE JURIDIQUE</p><h2>Droit de {countries[countryCode]?.name || ""}</h2><p>Les réponses sont générées par Gemini via l’API Google. Elles peuvent être inexactes ou incomplètes et ne remplacent pas un avis juridique.</p><div className="coverage-rule" /><strong>Portails officiels</strong>{(countries[countryCode]?.sources || []).map((source) => <a key={source.url} href={source.url} target="_blank" rel="noreferrer">{source.name}<ArrowUpRight size={13} /></a>)}<p className="coverage-note"><AlertTriangle size={15} /><span>Le contenu des lois n’est pas récupéré en direct. Vérifiez les textes et leur version en vigueur sur les portails officiels.</span></p><p className="provider-warning"><LockKeyhole size={14} />Votre question et l’historique sont transmis à Google. Le document joint est pseudonymisé localement avant transmission, mais cette protection n’est pas une anonymisation complète. La clé API reste sur le serveur.</p></aside>
          </section>}

          <footer className="page-footer"><span>LEGAL PRIVACY GUARDIAN</span><span>Prototype de démonstration <span className="footer-separator">·</span> Détection limitée</span></footer>
        </div>
      </main>
      {selectedReport && (
        <div className="report-overlay" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) setSelectedReport(null); }}>
          <section className="report-dialog" role="dialog" aria-modal="true" aria-labelledby="report-title">
            <div className="report-dialog-heading">
              <span className="file-icon"><FileText size={21} /></span>
              <div><p className="panel-kicker">RAPPORT DE PROTECTION</p><h2 id="report-title">{selectedReport.filename}</h2><span>{formatDate(selectedReport.scanned_at)}</span></div>
              <button className="remove-file" type="button" onClick={() => setSelectedReport(null)} aria-label="Fermer le rapport"><X size={18} /></button>
            </div>
            <div className="report-findings">
              {Object.entries(selectedReport.findings).map(([category, count]) => (
                <div className="report-finding" key={category}><span>{category}</span><strong>{count}</strong></div>
              ))}
            </div>
            <p className="report-retention"><LockKeyhole size={15} />Le contenu original n’est pas conservé dans la base.</p>
            <button className="analyze-button dialog-close" type="button" onClick={() => setSelectedReport(null)}>Fermer</button>
          </section>
        </div>
      )}
    </div>
  );
}

export default App;
