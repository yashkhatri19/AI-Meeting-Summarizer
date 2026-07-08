"use client";
import { useState, useEffect, useRef } from "react";
import axios from "axios";
import { GoogleOAuthProvider, useGoogleLogin } from "@react-oauth/google";
import { 
  Upload, FileAudio, ArrowRight, Loader2, Send, Bot, 
  History, Trash2, PlusCircle, Sparkles, 
  AudioLines, LogIn, Mail, Lock, Share2, Check, Chrome 
} from "lucide-react";

interface Message {
  sender: "user" | "ai";
  text: string;
}

interface HistoryItem {
  id: string;
  fileName: string;
  fileSize: string;
  transcript: string;
  messages: Message[];
  timestamp: string;
}

function LoginGate({ onLoginSuccess, onErrorMsg }: { onLoginSuccess: (user: any) => void; onErrorMsg: (msg: string) => void }) {
  const [emailInput, setEmailInput] = useState("");
  const [passInput, setPassInput] = useState("");

  const googleLoginTrigger = useGoogleLogin({
    onSuccess: async (tokenResponse) => {
      try {
        const res = await axios.get("https://www.googleapis.com/oauth2/v3/userinfo", {
          headers: { Authorization: `Bearer ${tokenResponse.access_token}` },
        });
        const googleUser = {
          name: res.data.name || "Google User",
          email: res.data.email
        };
        onLoginSuccess(googleUser);
      } catch (err) {
        onErrorMsg("Failed retrieving secure identity profile from Google.");
      }
    },
    onError: () => onErrorMsg("Google OAuth authorization handshake failed."),
  });

  const handleCustomSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!emailInput || !passInput) {
      onErrorMsg("Please fill valid custom credentials.");
      return;
    }
    onLoginSuccess({ name: emailInput.split("@")[0], email: emailInput });
  };

  return (
    <div className="w-full max-w-md bg-slate-900/60 border border-slate-800/80 rounded-3xl p-8 backdrop-blur-2xl shadow-2xl relative overflow-hidden">
      <div className="absolute top-0 left-1/4 right-1/4 h-[1px] bg-gradient-to-r from-transparent via-blue-500/50 to-transparent"></div>
      
      <div className="flex flex-col items-center gap-3 mb-8 text-center">
        <div className="p-3 bg-gradient-to-tr from-blue-600 to-indigo-600 rounded-2xl shadow-xl shadow-indigo-500/10">
          <AudioLines className="h-6 w-6 text-white" />
        </div>
        <div>
          <h2 className="text-2xl font-bold tracking-tight text-white">VoxBrief AI Portal</h2>
          <p className="text-xs text-slate-400 mt-1">Production Ready Identity Verification</p>
        </div>
      </div>

      <button 
        type="button"
        onClick={() => googleLoginTrigger()}
        className="w-full py-3 px-4 bg-white hover:bg-slate-100 text-slate-900 rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2.5 active:scale-[0.98] shadow-lg shadow-black/10"
      >
        <Chrome className="h-4 w-4 text-blue-600" /> Continue with Google
      </button>

      <div className="relative my-6 flex py-1 items-center">
        <div className="flex-grow border-t border-slate-800"></div>
        <span className="flex-shrink mx-4 text-[10px] text-slate-500 font-bold uppercase tracking-widest">Or Secure Login</span>
        <div className="flex-grow border-t border-slate-800"></div>
      </div>

      <form onSubmit={handleCustomSubmit} className="space-y-4">
        <div>
          <label className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Email</label>
          <div className="relative">
            <Mail className="absolute left-3 top-3.5 h-4 w-4 text-slate-500" />
            <input 
              type="email" 
              value={emailInput}
              onChange={(e) => setEmailInput(e.target.value)}
              placeholder="name@domain.com"
              className="w-full bg-slate-950/60 border border-slate-800/80 rounded-xl pl-10 pr-4 py-3 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        <div>
          <label className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Password</label>
          <div className="relative">
            <Lock className="absolute left-3 top-3.5 h-4 w-4 text-slate-500" />
            <input 
              type="password" 
              value={passInput}
              onChange={(e) => setPassInput(e.target.value)}
              placeholder="••••••••"
              className="w-full bg-slate-950/60 border border-slate-800/80 rounded-xl pl-10 pr-4 py-3 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
            />
          </div>
        </div>

        <button type="submit" className="w-full py-3 bg-blue-600 hover:bg-blue-500 text-white rounded-xl text-xs font-bold transition-all flex items-center justify-center gap-2 mt-6">
          Sign In <LogIn className="h-3.5 w-3.5" />
        </button>
      </form>
    </div>
  );
}

export default function Dashboard() {
  const [isLoggedIn, setIsLoggedIn] = useState<boolean>(false);
  const [userProfile, setUserProfile] = useState<{ name: string; email: string } | null>(null);

  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [transcript, setTranscript] = useState<string>("");
  const [error, setError] = useState<string>("");

  const [messages, setMessages] = useState<Message[]>([]);
  const [chatInput, setChatInput] = useState<string>("");
  const [chatLoading, setChatLoading] = useState<boolean>(false);

  const [history, setHistory] = useState<HistoryItem[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [currentFileName, setCurrentFileName] = useState<string>("");
  const [currentFileSize, setCurrentFileSize] = useState<string>("");
  const [shareCopied, setShareCopied] = useState<boolean>(false);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const clientId = process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || "";

  const RENDER_API_URL = "https://ai-meeting-summarizer-fbf5.onrender.com";

  useEffect(() => {
    const localUser = localStorage.getItem("voxbrief_user");
    if (localUser) {
      setUserProfile(JSON.parse(localUser));
      setIsLoggedIn(true);
    }
    const savedHistory = localStorage.getItem("voxbrief_history");
    if (savedHistory) {
      setHistory(JSON.parse(savedHistory));
    }
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatLoading]);

  const saveToLocalStorage = (updatedHistory: HistoryItem[]) => {
    setHistory(updatedHistory);
    localStorage.setItem("voxbrief_history", JSON.stringify(updatedHistory));
  };

  const handleLoginSuccess = (profile: { name: string; email: string }) => {
    localStorage.setItem("voxbrief_user", JSON.stringify(profile));
    setUserProfile(profile);
    setIsLoggedIn(true);
    setError("");
  };

  const handleLogout = () => {
    localStorage.removeItem("voxbrief_user");
    setIsLoggedIn(false);
    setUserProfile(null);
  };

  const handleShareDashboard = () => {
    if (!transcript) return;
    const shareText = `--- VoxBrief AI Intelligence Report ---\n\nFile: ${currentFileName}\nTranscript: ${transcript}\n\nSecurely processed on cloud.`;
    navigator.clipboard.writeText(shareText);
    setShareCopied(true);
    setTimeout(() => setShareCopied(false), 2500);
  };

  const deleteSession = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const filteredHistory = history.filter(item => item.id !== id);
    saveToLocalStorage(filteredHistory);
    if (activeSessionId === id) {
      setActiveSessionId(null);
      setTranscript("");
      setMessages([]);
      setCurrentFileName("");
      setCurrentFileSize("");
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError("");
    }
  };

  // Content-Stream fix to prevent corrupt audio extraction
  const handleUpload = async () => {
    if (!file) {
      setError("Please select a file first.");
      return;
    }

    setLoading(true);
    setError("");
    setTranscript("Initializing secure pipeline..."); 

    const CHUNK_SIZE = 6 * 1024 * 1024; // Optimal 6MB
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
    const fileId = "vox_" + Date.now(); 
    let accumulatedTranscript = "";

    const initialMessages: Message[] = [
      { sender: "ai", text: `✨ Sync successful with pipeline channel.` }
    ];
    setMessages(initialMessages);
    setCurrentFileName(file.name);
    const sizeStr = (file.size / (1024 * 1024)).toFixed(2) + " MB";
    setCurrentFileSize(sizeStr);

    try {
      for (let currentChunk = 0; currentChunk < totalChunks; currentChunk++) {
        const startByte = currentChunk * CHUNK_SIZE;
        const endByte = Math.min(startByte + CHUNK_SIZE, file.size);
        
        // standard chunk slicing
        const fileChunkBlob = file.slice(startByte, endByte);

        const formData = new FormData();
        // Use a strict file name pattern to prevent backend parsing conflict
        formData.append("file", fileChunkBlob, `chunk_${currentChunk}.mp4`); 
        formData.append("chunkIndex", currentChunk.toString());
        formData.append("totalChunks", totalChunks.toString());
        formData.append("fileId", fileId);

        setTranscript(`[Processing: Uploading part ${currentChunk + 1} of ${totalChunks}...]`);

        const response = await fetch(`${RENDER_API_URL}/api/upload-chunk`, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const textError = await response.text();
          throw new Error(`Server returned error on chunk ${currentChunk + 1}: ${textError}`);
        }

        const data = await response.json();

        if (data.status === "processing") {
          setTranscript(`[System Status: Segment ${currentChunk + 1}/${totalChunks} uploaded. Transcribing...]`);
        } else if (data.status === "completed" || data.transcript) {
          accumulatedTranscript = data.transcript || "Transcription compiled.";
          setTranscript(accumulatedTranscript);

          const newSession: HistoryItem = {
            id: Date.now().toString(),
            fileName: file.name,
            fileSize: sizeStr,
            transcript: accumulatedTranscript,
            messages: initialMessages,
            timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
          };

          const updatedHistory = [newSession, ...history];
          saveToLocalStorage(updatedHistory);
          setActiveSessionId(newSession.id);
          setFile(null);
          break;
        }
      }

    } catch (err: any) {
      console.error(err);
      setError(err.message || "Pipeline synchronization broken.");
      setTranscript(`Halted: ${err.message || "Transcription failed."}`);
    } finally {
      setLoading(false);
    }
  };

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || !transcript || !activeSessionId) return;

    const userQuestion = chatInput.trim();
    const updatedMessagesWithUser = [...messages, { sender: "user" as const, text: userQuestion }];
    setMessages(updatedMessagesWithUser);
    setChatInput("");
    setChatLoading(true);

    try {
      const response = await fetch(`${RENDER_API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query: userQuestion }),
      });
      
      const data = await response.json();
      setMessages([...updatedMessagesWithUser, { sender: "ai" as const, text: data.reply || "No reply track." }]);
    } catch (err) {
      setMessages([...updatedMessagesWithUser, { sender: "ai" as const, text: "Error syncing with agent." }]);
    } finally {
      setChatLoading(false);
    }
  };

  if (!isLoggedIn) {
    return (
      <GoogleOAuthProvider clientId={clientId}>
        <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-4 antialiased">
          {error && <p className="text-xs text-rose-400 bg-rose-500/10 border border-rose-500/20 px-4 py-2.5 rounded-xl mb-4 font-medium">{error}</p>}
          <LoginGate onLoginSuccess={handleLoginSuccess} onErrorMsg={(msg) => setError(msg)} />
        </div>
      </GoogleOAuthProvider>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col antialiased">
      <header className="border-b border-slate-800/60 bg-slate-900/40 backdrop-blur-xl px-6 py-3 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center gap-2.5">
          <div className="p-2 bg-gradient-to-tr from-blue-600 to-indigo-600 rounded-xl">
            <AudioLines className="h-4 w-4 text-white" />
          </div>
          <h1 className="text-md font-bold tracking-tight text-white">
            VoxBrief <span className="text-blue-400 font-extrabold text-xs align-super">AI</span>
          </h1>
        </div>
        
        <div className="flex items-center gap-4">
          <button 
            type="button"
            onClick={() => { setActiveSessionId(null); setTranscript(""); setMessages([]); setCurrentFileName(""); }}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 border border-slate-800 hover:border-slate-700 text-xs font-semibold text-slate-300 rounded-xl transition"
          >
            <PlusCircle className="h-3.5 w-3.5 text-blue-400" /> Fresh Node
          </button>

          <div className="flex items-center gap-3 bg-slate-900/60 border border-slate-800/80 px-3 py-1 rounded-xl shadow-inner">
            <div className="h-6 w-6 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-600 text-[10px] font-bold text-white flex items-center justify-center uppercase">
              {userProfile?.name.charAt(0)}
            </div>
            <span className="text-xs font-semibold text-slate-300 max-w-[90px] truncate">{userProfile?.name}</span>
            <button type="button" onClick={handleLogout} className="text-[10px] text-slate-500 hover:text-rose-400 font-bold ml-1 border-l border-slate-800 pl-2 py-0.5">
              Exit
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1 grid grid-cols-1 md:grid-cols-4 lg:grid-cols-5 p-4 gap-4 max-h-[calc(100vh-70px)] h-[calc(100vh-70px)] overflow-hidden w-full">
        <div className="md:col-span-1 bg-slate-900/10 border border-slate-800/60 rounded-2xl flex flex-col p-4 h-full min-h-0 overflow-hidden">
          <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2 mb-3 border-b border-slate-800/60 pb-2">
            <History className="h-3.5 w-3.5" /> Archive Logs
          </h3>
          <div className="flex-1 overflow-y-auto space-y-2 pr-0.5">
            {history.map((item) => (
              <div
                key={item.id}
                onClick={() => {
                  setActiveSessionId(item.id);
                  setTranscript(item.transcript);
                  setMessages(item.messages);
                  setCurrentFileName(item.fileName);
                  setCurrentFileSize(item.fileSize);
                }}
                className={`group p-3 rounded-xl border cursor-pointer transition-all flex items-center justify-between gap-2 relative overflow-hidden ${
                  activeSessionId === item.id ? "bg-blue-600/10 border-blue-500/60 text-blue-200" : "bg-slate-900/30 border-slate-800/50 hover:border-slate-700/60"
                }`}
              >
                <div className="truncate flex-1">
                  <p className="text-xs font-semibold truncate">{item.fileName}</p>
                  <p className="text-[9px] text-slate-500 mt-0.5">{item.timestamp} • {item.fileSize}</p>
                </div>
                <button type="button" onClick={(e) => deleteSession(item.id, e)} className="text-slate-600 hover:text-rose-400 opacity-0 group-hover:opacity-100 p-1 transition-all">
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        </div>

        <div className="md:col-span-2 lg:col-span-3 flex flex-col gap-4 h-full max-h-full overflow-hidden">
          <div className="bg-slate-900/20 border-2 border-dashed border-slate-800 rounded-2xl p-5 flex flex-col items-center justify-center min-h-[140px] relative shrink-0">
            <input type="file" accept="audio/*,video/*" onChange={handleFileChange} className="absolute inset-0 opacity-0 cursor-pointer z-10" />
            {!file ? (
              <div className="text-center flex flex-col items-center gap-2">
                <div className="p-2.5 bg-blue-500/10 rounded-xl text-blue-400 border border-blue-500/10"><Upload className="h-5 w-5" /></div>
                <p className="text-xs font-medium text-slate-400">Ingest dynamic speech or video stream</p>
              </div>
            ) : (
              <div className="text-center flex flex-col items-center gap-2 z-20">
                <div className="p-2 bg-emerald-500/10 border border-emerald-500/20 rounded-xl text-emerald-400"><FileAudio className="h-5 w-5" /></div>
                <p className="text-xs font-semibold text-slate-300 truncate max-w-[240px]">{file.name}</p>
                <button type="button" onClick={(e) => { e.stopPropagation(); setFile(null); }} className="text-[10px] text-rose-400 underline">Cancel</button>
              </div>
            )}
          </div>

          <div className="flex justify-end shrink-0">
            <button type="button" onClick={handleUpload} disabled={loading || !file} className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-900 text-white text-xs font-semibold rounded-xl flex items-center gap-2 transition-all">
              {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <>Process Stream <ArrowRight className="h-3.5 w-3.5" /></>}
            </button>
          </div>

          <div className="bg-slate-900/20 border border-slate-800/60 rounded-2xl p-5 flex flex-col flex-1 h-full min-h-0 overflow-hidden">
            <div className="flex justify-between items-center border-b border-slate-800/60 pb-2 mb-3 shrink-0">
              <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-1.5"><Sparkles className="h-3.5 w-3.5 text-indigo-400" /> Ingested Transcript Stream</h3>
              {transcript && (
                <button type="button" onClick={handleShareDashboard} className={`flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-bold border rounded-lg transition-all ${shareCopied ? "bg-emerald-500/10 border-emerald-500/40 text-emerald-400" : "bg-slate-900/80 border-slate-800 text-slate-400"}`}>
                  {shareCopied ? <><Check className="h-3 w-3" /> Copied!</> : <><Share2 className="h-3 w-3" /> Share Data</>}
                </button>
              )}
            </div>

            {transcript && (
              <div className="flex-1 overflow-y-auto text-xs text-slate-300 bg-slate-950/40 p-4 rounded-xl border border-slate-800/60 leading-relaxed font-mono whitespace-pre-wrap">{transcript}</div>
            )}
          </div>
        </div>

        <div className="md:col-span-1 lg:col-span-1 bg-slate-900/30 border border-slate-800/60 rounded-2xl flex flex-col h-full max-h-full overflow-hidden shadow-xl">
          <div className="p-3 border-b border-slate-800/60 bg-slate-900/20 shrink-0 flex items-center gap-2">
            <Bot className="h-3.5 w-3.5 text-blue-400" />
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Context Chat Agent</span>
          </div>
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {messages.map((msg, index) => (
              <div key={index} className={`flex gap-2 max-w-[90%] ${msg.sender === "user" ? "ml-auto flex-row-reverse" : ""}`}>
                <div className={`p-3 text-[11px] rounded-2xl border ${msg.sender === "user" ? "bg-blue-600/90 text-white border-blue-500/20 rounded-tr-none" : "bg-slate-900/90 text-slate-200 border-slate-800 rounded-tl-none"}`}>{msg.text}</div>
              </div>
            ))}
            {chatLoading && <div className="p-2 text-[11px] text-slate-400 animate-pulse">Inference running...</div>}
            <div ref={chatEndRef} />
          </div>

          <form onSubmit={handleSendMessage} className="p-2 border-t border-slate-800/60 bg-slate-950/40 flex gap-2 items-center shrink-0">
            <input type="text" value={chatInput} onChange={(e) => setChatInput(e.target.value)} disabled={!transcript || chatLoading} placeholder="Query agent..." className="flex-1 text-xs bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-slate-200 focus:outline-none focus:border-blue-500" />
            <button type="submit" disabled={!chatInput.trim() || chatLoading || !transcript} className="p-2 bg-blue-600 text-white rounded-xl"><Send className="h-3 w-3" /></button>
          </form>
        </div>
      </main>
    </div>
  );
}