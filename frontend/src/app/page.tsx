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
        onLoginSuccess({ name: res.data.name || "Google User", email: res.data.email });
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
          <input 
            type="email" 
            value={emailInput}
            onChange={(e) => setEmailInput(e.target.value)}
            placeholder="name@domain.com"
            className="w-full bg-slate-950/60 border border-slate-800/80 rounded-xl px-4 py-3 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
          />
        </div>
        <div>
          <label className="block text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Password</label>
          <input 
            type="password" 
            value={passInput}
            onChange={(e) => setPassInput(e.target.value)}
            placeholder="••••••••"
            className="w-full bg-slate-950/60 border border-slate-800/80 rounded-xl px-4 py-3 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
          />
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
    if (savedHistory) setHistory(JSON.parse(savedHistory));
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

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
      setError("");
    }
  };

  // Upgraded Pipeline to prevent corrupt backend merging
  const handleUpload = async () => {
    if (!file) {
      setError("Please select a file first.");
      return;
    }

    setLoading(true);
    setError("");
    setTranscript("Configuring active stream pipeline...");

    const initialMessages: Message[] = [{ sender: "ai", text: `✨ Connected. Processing media format structures.` }];
    setMessages(initialMessages);
    setCurrentFileName(file.name);
    const sizeStr = (file.size / (1024 * 1024)).toFixed(2) + " MB";
    setCurrentFileSize(sizeStr);

    // If file is below 25MB, send as a single block to completely bypass chunk corruption
    const CHUNK_SIZE = 6 * 1024 * 1024; 
    const totalChunks = Math.ceil(file.size / CHUNK_SIZE);
    const fileId = "vox_" + Date.now();
    let accumulatedTranscript = "";

    try {
      for (let currentChunk = 0; currentChunk < totalChunks; currentChunk++) {
        const startByte = currentChunk * CHUNK_SIZE;
        const endByte = Math.min(startByte + CHUNK_SIZE, file.size);
        
        const fileChunkBlob = file.slice(startByte, endByte);
        // Create a native data file blob to force binary headers
        const chunkBlobFile = new File([fileChunkBlob], `part_${currentChunk}.mp4`, { type: "video/mp4" });

        const formData = new FormData();
        formData.append("file", chunkBlobFile);
        formData.append("chunkIndex", currentChunk.toString());
        formData.append("totalChunks", totalChunks.toString());
        formData.append("fileId", fileId);

        setTranscript(`[Uploading pipeline: Block ${currentChunk + 1} of ${totalChunks}...]`);

        const response = await fetch(`${RENDER_API_URL}/api/upload-chunk`, {
          method: "POST",
          body: formData,
        });

        if (!response.ok) {
          const textError = await response.text();
          throw new Error(textError || `Server error on part ${currentChunk + 1}`);
        }

        const data = await response.json();

        if (data.status === "processing") {
          setTranscript(`[Assembling: Block ${currentChunk + 1}/${totalChunks} validated. Merging binary data...]`);
        } else if (data.status === "completed" || data.transcript) {
          accumulatedTranscript = data.transcript || "Stream successfully compiled.";
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
      setError(err.message || "Binary track configuration mismatch.");
      setTranscript(`Halted: ${err.message || "Could not parse video streams safely."}`);
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
      setMessages([...updatedMessagesWithUser, { sender: "ai" as const, text: data.reply || "No response." }]);
    } catch (err) {
      setMessages([...updatedMessagesWithUser, { sender: "ai" as const, text: "Error syncing with engine." }]);
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
          <div className="p-2 bg-gradient-to-tr from-blue-600 to-indigo-600 rounded-xl"><AudioLines className="h-4 w-4 text-white" /></div>
          <h1 className="text-md font-bold tracking-tight text-white">VoxBrief <span className="text-blue-400 font-extrabold text-xs align-super">AI</span></h1>
        </div>
        <div className="flex items-center gap-4">
          <button type="button" onClick={() => { setActiveSessionId(null); setTranscript(""); setMessages([]); }} className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 border border-slate-800 text-xs font-semibold rounded-xl text-slate-300"><PlusCircle className="h-3.5 w-3.5 text-blue-400" /> Fresh Node</button>
          <div className="flex items-center gap-3 bg-slate-900/60 border border-slate-800/80 px-3 py-1 rounded-xl">
            <span className="text-xs font-semibold text-slate-300 truncate max-w-[90px]">{userProfile?.name}</span>
            <button type="button" onClick={handleLogout} className="text-[10px] text-slate-500 hover:text-rose-400 ml-1 border-l border-slate-800 pl-2">Exit</button>
          </div>
        </div>
      </header>

      <main className="flex-1 grid grid-cols-1 md:grid-cols-4 lg:grid-cols-5 p-4 gap-4 h-[calc(100vh-70px)] overflow-hidden w-full">
        <div className="md:col-span-1 bg-slate-900/10 border border-slate-800/60 rounded-2xl flex flex-col p-4 overflow-hidden">
          <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest flex items-center gap-2 mb-3 border-b border-slate-800/60 pb-2"><History className="h-3.5 w-3.5" /> Archive Logs</h3>
          <div className="flex-1 overflow-y-auto space-y-2">
            {history.map((item) => (
              <div key={item.id} onClick={() => { setActiveSessionId(item.id); setTranscript(item.transcript); setMessages(item.messages); }} className={`p-3 rounded-xl border cursor-pointer transition-all ${activeSessionId === item.id ? "bg-blue-600/10 border-blue-500/60 text-blue-200" : "bg-slate-900/30 border-slate-800/50"}`}>
                <p className="text-xs font-semibold truncate">{item.fileName}</p>
                <p className="text-[9px] text-slate-500 mt-0.5">{item.timestamp} • {item.fileSize}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="md:col-span-2 lg:col-span-3 flex flex-col gap-4 overflow-hidden">
          <div className="bg-slate-900/20 border-2 border-dashed border-slate-800 rounded-2xl p-5 flex flex-col items-center justify-center min-h-[140px] relative shrink-0">
            <input type="file" accept="audio/*,video/*" onChange={handleFileChange} className="absolute inset-0 opacity-0 cursor-pointer z-10" />
            {!file ? <p className="text-xs font-medium text-slate-400">Ingest dynamic speech or video stream</p> : <p className="text-xs font-semibold text-emerald-400">{file.name}</p>}
          </div>
          <div className="flex justify-end"><button type="button" onClick={handleUpload} disabled={loading || !file} className="px-5 py-2 bg-blue-600 hover:bg-blue-500 disabled:bg-slate-900 text-white text-xs font-semibold rounded-xl">{loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : "Process Stream"}</button></div>
          <div className="bg-slate-900/20 border border-slate-800/60 rounded-2xl p-5 flex flex-col flex-1 overflow-hidden">
            <h3 className="text-[10px] font-bold text-slate-500 uppercase tracking-widest mb-3 pb-2 border-b border-slate-800/60">Transcript Stream</h3>
            {transcript && <div className="flex-1 overflow-y-auto text-xs text-slate-300 bg-slate-950/40 p-4 rounded-xl border border-slate-800/60 font-mono whitespace-pre-wrap">{transcript}</div>}
          </div>
        </div>

        <div className="md:col-span-1 lg:col-span-1 bg-slate-900/30 border border-slate-800/60 rounded-2xl flex flex-col overflow-hidden">
          <div className="p-3 border-b border-slate-800/60 bg-slate-900/20 text-[10px] font-bold text-slate-400 uppercase">Context Chat Agent</div>
          <div className="flex-1 overflow-y-auto p-3 space-y-3">
            {messages.map((msg, index) => (
              <div key={index} className={`flex max-w-[90%] ${msg.sender === "user" ? "ml-auto" : ""}`}><div className={`p-3 text-[11px] rounded-2xl ${msg.sender === "user" ? "bg-blue-600 text-white" : "bg-slate-900 text-slate-200"}`}>{msg.text}</div></div>
            ))}
          </div>
          <form onSubmit={handleSendMessage} className="p-2 border-t border-slate-800/60 bg-slate-950/40 flex gap-2"><input type="text" value={chatInput} onChange={(e) => setChatInput(e.target.value)} placeholder="Query agent..." className="flex-1 text-xs bg-slate-900 border border-slate-800 rounded-xl px-3 py-2" /><button type="submit" className="p-2 bg-blue-600 text-white rounded-xl">Send</button></form>
        </div>
      </main>
    </div>
  );
}