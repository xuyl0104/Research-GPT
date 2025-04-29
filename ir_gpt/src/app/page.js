"use client"
import React, { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import 'katex/dist/katex.min.css';


export default function ChatUI() {
  const [files, setFiles] = useState([]);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [sidebarWidth, setSidebarWidth] = useState(433);
  const sidebarRef = useRef();
  const resizerRef = useRef();
  const isDragging = useRef(false);
  const [selectedFileChunks, setSelectedFileChunks] = useState([]);
  const [embeddingStatus, setEmbeddingStatus] = useState(null);
  const scrollTargetRef = useRef(null);
  const [visibleChunks, setVisibleChunks] = useState({});
  const [expanded, setExpanded] = useState(true);
  const [previewedEvidence, setPreviewedEvidence] = useState([]);
  const [loadedFiles, setLoadedFiles] = useState(new Set());
  const [embeddingList, setEmbeddingList] = useState([]);
  const [selectedEmbedding, setSelectedEmbedding] = useState("");
  const [showEmbeddingDropdown, setShowEmbeddingDropdown] = useState(false);
  const [error, setError] = useState(null);
  const bottomRef = useRef(null);

  // progress bar
  const [activeFile, setActiveFile] = useState(null);
  const [uploadProgress, setUploadProgress] = useState(0); // 0 to 100%
  const [totalChunks, setTotalChunks] = useState(0);
  const [embeddedChunks, setEmbeddedChunks] = useState(0);

  // load button and embedding list
  const loadRef = useRef(null);
  const [showDropdown, setShowDropdown] = useState(false);


  useEffect(() => {
    const handleClickOutside = (e) => {
      if (loadRef.current && !loadRef.current.contains(e.target)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    const handleMouseMove = (e) => {
      if (isDragging.current) {
        const newWidth = e.clientX;
        if (newWidth > 150 && newWidth < 500) {
          setSidebarWidth(newWidth);
        }
      }
    };
    const handleMouseUp = () => {
      isDragging.current = false;
    };
    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  useEffect(() => {
    if (scrollTargetRef.current !== null) {
      const el = document.getElementById(scrollTargetRef.current);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "center" });
        el.classList.add("ring", "ring-blue-400");
        setTimeout(() => {
          el.classList.remove("ring", "ring-blue-400");
        }, 1500);
        scrollTargetRef.current = null;
      }
    }
  }, [selectedFileChunks]);

  useEffect(() => {
    if (bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages]);


  const scrollToChunk = async (chunkId, filename) => {
    const el = document.getElementById(chunkId);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
      el.classList.add("ring", "ring-blue-400");
      setTimeout(() => {
        el.classList.remove("ring", "ring-blue-400");
      }, 1500);
    } else if (filename && !loadedFiles.has(filename)) {
      try {
        const res = await fetch(`http://localhost:5000/preview-chunks?filename=${encodeURIComponent(filename)}`);
        const data = await res.json();
        if (data.chunks) {
          setSelectedFileChunks(data.chunks);
          setVisibleChunks(() => {
            const visibility = {};
            data.chunks.forEach((_, i) => {
              visibility[`chunk-${filename}-${i}`] = true;
            });
            return visibility;
          });
          setLoadedFiles((prev) => new Set(prev).add(filename));
          setTimeout(() => {
            const delayedEl = document.getElementById(chunkId);
            if (delayedEl) {
              delayedEl.scrollIntoView({ behavior: "smooth", block: "center" });
              delayedEl.classList.add("ring", "ring-blue-400");
              setTimeout(() => {
                delayedEl.classList.remove("ring", "ring-blue-400");
              }, 1500);
            }
          }, 300);
        }
      } catch (err) {
        console.error("Failed to auto-load file preview for", filename);
      }
    }
  };

  const toggleChunkVisibility = (chunkId) => {
    setVisibleChunks((prev) => ({
      ...prev,
      [chunkId]: !prev[chunkId]
    }));
  };

  const toggleAllChunks = (show) => {
    const visibility = {};
    selectedFileChunks.forEach((_, idx) => {
      visibility[`chunk-${idx}`] = show;
    });
    setVisibleChunks(visibility);
    setExpanded(show);
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    setMessages((prev) => [...prev, { from: "user", content: input }]);
    const currentInput = input;
    setInput("");
    setError(null);
    try {
      const res = await fetch("http://localhost:5000/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: currentInput }),
      });
      const data = await res.json();
      if (res.status !== 200) throw new Error(data.error || "Unknown error");
      if (data.answer) {
        setMessages((prev) => [...prev, { from: "bot", content: data.answer }]);
      }
    } catch (err) {
      console.error("Bot error:", err);
      setError(err.message || "Something went wrong");
    }
  };

  const handleFileUpload = (e) => {
    const uploadedFiles = Array.from(e.target.files).map((f) => ({
      name: f.name,
      path: URL.createObjectURL(f),
      blob: f
    }));
    setFiles((prev) => [...prev, ...uploadedFiles]);
  };

  const handleEmbedding = async () => {
    const name = prompt("Enter a name for this new embedding session:");
    if (!name) return;

    const formData = new FormData();
    files.forEach((file) => {
      if (file.blob) {
        formData.append("files", file.blob, file.name);
      }
    });

    setEmbeddingStatus("Uploading and processing...");
    setUploadProgress(0);
    setEmbeddedChunks(0);
    setTotalChunks(0);

    try {
      const res = await fetch(`http://localhost:5000/embed-files?append=true&name=${encodeURIComponent(name)}`, {
        method: "POST",
        body: formData
      });

      const reader = res.body.getReader();
      const decoder = new TextDecoder("utf-8");
      let partial = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        partial += decoder.decode(value, { stream: true });
        const lines = partial.split("\n");
        partial = lines.pop(); // Last line may be incomplete

        for (const line of lines) {
          if (line.startsWith("PROGRESS:")) {
            const match = line.match(/(\d+)\/(\d+)/);
            if (match) {
              const current = parseInt(match[1], 10);
              const total = parseInt(match[2], 10);
              setEmbeddedChunks(current);
              setTotalChunks(total);
              setUploadProgress((current / total) * 100);
            }
          }
        }
      }

      const result = JSON.parse(partial || "{}");
      setEmbeddingStatus(result.message || "Embedding complete");
      setSelectedEmbedding(name);
    } catch (err) {
      console.error("Error during embedding:", err);
      setEmbeddingStatus("Error during embedding");
    }

    setTimeout(() => {
      setUploadProgress(0);
      setEmbeddingStatus(null);
    }, 4000);
  };



  const fetchEmbeddingList = async () => {
    try {
      const res = await fetch("http://localhost:5000/list-embeddings");
      const data = await res.json();
      if (res.status !== 200) throw new Error(data.error || "Unknown error");
      setEmbeddingList(data.embeddings || []);
    } catch (err) {
      console.error("Failed to fetch embedding list:", err);
      setError("Could not fetch embedding list.");
    }
  };

  const handleSelectEmbedding = async (name) => {
    try {
      const res = await fetch(`http://localhost:5000/load-embedding?name=${encodeURIComponent(name)}`);
      const data = await res.json();
      if (res.status !== 200) throw new Error(data.error || "Unknown error");
      const savedFiles = data.files.map(name => ({ name, path: "", blob: null }));
      setFiles(savedFiles);
      setSelectedEmbedding(name);
      setShowEmbeddingDropdown(false);
    } catch (err) {
      console.error("Failed to load embedding:", err);
      setError("Could not load selected embedding.");
    }
  };

  const handleLoadSavedEmbedding = async () => {
    await fetchEmbeddingList();
    setShowEmbeddingDropdown(true);
  };

  const handleUnloadEmbedding = () => {
    setFiles([]);
    setMessages([]);
    setSelectedFileChunks([]);
    setVisibleChunks({});
    setLoadedFiles(new Set());
    setSelectedEmbedding("");
    setEmbeddingStatus("Embedding unloaded");
    setTimeout(() => setEmbeddingStatus(null), 4000);
  };

  const handleDeleteEmbedding = async () => {
    if (!selectedEmbedding) {
      alert("No embedding loaded.");
      return;
    }
    try {
      const res = await fetch(`http://localhost:5000/delete-embedding?name=${encodeURIComponent(selectedEmbedding)}`, { method: "POST" });
      const data = await res.json();
      if (res.status !== 200) throw new Error(data.error || "Unknown error");
      setFiles([]);
      setMessages([]);
      setSelectedFileChunks([]);
      setVisibleChunks({});
      setLoadedFiles(new Set());
      setSelectedEmbedding("");
      setEmbeddingStatus("Embedding deleted");
      setTimeout(() => setEmbeddingStatus(null), 4000);
    } catch (err) {
      console.error("Delete embedding failed:", err);
      setError("Failed to delete embedding.");
    }
  };


  const getFileIcon = (filename) => {
    const ext = filename.split('.').pop().toLowerCase();
    switch (ext) {
      case 'pdf': return '📄';
      case 'png':
      case 'jpg':
      case 'jpeg':
      case 'gif': return '🖼️';
      case 'doc':
      case 'docx': return '📝';
      case 'xls':
      case 'xlsx': return '📊';
      case 'zip':
      case 'rar': return '🗜️';
      default: return '📁';
    }
  };

  const handlePreviewChunks = (file) => {
    fetch(`http://localhost:5000/preview-chunks?filename=${encodeURIComponent(file.name)}`)
      .then(res => res.json())
      .then(data => {
        setSelectedFileChunks(data.chunks || []);
        const visibility = {};
        (data.chunks || []).forEach((_, idx) => {
          visibility[`chunk-${file.name}-${idx}`] = true;
        });
        setVisibleChunks(visibility);
        setLoadedFiles((prev) => new Set(prev).add(file.name));
      })
      .catch(() => setSelectedFileChunks(["Failed to load preview"]));
  };

  return (
    <div className="h-screen flex flex-col bg-white text-gray-900">
      <div className="flex flex-1 overflow-hidden">
        {/* sidebar */}
        <aside
          ref={sidebarRef}
          style={{ width: `${sidebarWidth}px` }}
          className="bg-gray-100 border-r p-4 hidden md:flex flex-col relative"
        >
          <h2 className="text-lg font-semibold mb-4">Uploaded Files</h2>

          {/* sidebar-buttons */}
          <div className="space-y-6 mb-6">

            {/* Group 1: Upload Files + Embedding */}
            <div className="flex gap-x-2">
              <label className="flex-1 bg-blue-500 hover:bg-blue-600 text-white py-2 rounded text-center cursor-pointer flex items-center justify-center gap-2">
                📁 Upload
                <input type="file" multiple onChange={handleFileUpload} className="hidden" />
              </label>

              <button
                onClick={handleEmbedding}
                className="flex-1 bg-green-500 hover:bg-green-600 text-white py-2 rounded flex items-center justify-center gap-2"
              >
                🧩 Embed
              </button>
            </div>

            {/* Group 2: Load + Unload + Delete */}
            {/* Group 2: Load + Unload + Delete */}
            <div className="flex gap-x-2 w-full">
              {/* Load with Dropdown */}
              <div ref={loadRef} className="relative flex-1">
                <button
                  onClick={async () => {
                    if (!showDropdown) {
                      await fetchEmbeddingList();
                    }
                    setShowDropdown(!showDropdown);
                  }}
                  className="w-full bg-purple-400 hover:bg-purple-500 text-white py-2 rounded flex items-center justify-center gap-2 h-full"
                >
                  🔄 Load
                  <span className={`ml-1 transform transition-transform ${showDropdown ? "rotate-180" : ""}`}>
                    ▾
                  </span>
                </button>

                {showDropdown && (
                  <ul className="absolute z-10 mt-1 w-full bg-white border rounded shadow text-sm text-left">
                    {embeddingList.length > 0 ? (
                      embeddingList.map((name) => (
                        <li
                          key={name}
                          onClick={() => {
                            handleSelectEmbedding(name);
                            setShowDropdown(false);
                          }}
                          className="px-3 py-2 hover:bg-gray-100 cursor-pointer"
                        >
                          {name}
                        </li>
                      ))
                    ) : (
                      <li className="px-3 py-2 text-gray-400">No embeddings</li>
                    )}
                  </ul>
                )}
              </div>

              {/* Unload button */}
              <button
                onClick={handleUnloadEmbedding}
                className="flex-1 bg-yellow-400 hover:bg-yellow-500 text-white py-2 rounded flex items-center justify-center gap-2 h-full"
              >
                🚪 Unload
              </button>

              {/* Delete button */}
              <button
                onClick={handleDeleteEmbedding}
                className="flex-1 bg-gray-300 hover:bg-gray-400 text-gray-700 py-2 rounded flex items-center justify-center gap-2 h-full text"
              >
                🗑️ Delete
              </button>
            </div>



            {uploadProgress > 0 && uploadProgress < 100 && (
              <div className="w-full bg-gray-200 rounded-full h-2.5 mb-4">
                <div
                  className="bg-blue-500 h-2.5 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                ></div>
                <p className="text-xs text-center mt-1 text-gray-500">{embeddedChunks} / {totalChunks} chunks embedded</p>
              </div>
            )}


            {/* Embedding Status */}
            {embeddingStatus && (
              <p className="text-xs text-center text-gray-600 italic mt-2">{embeddingStatus}</p>
            )}

          </div>

          {/* Sidebar Scrollable File List */}
          <div className="flex-1 overflow-y-auto">
            <ul className="space-y-3 text-sm text-gray-700">
              {files.map((file, idx) => (
                <li
                  key={idx}
                  onClick={() => {
                    setActiveFile(file.name);
                    handlePreviewChunks(file);
                  }}
                  className={`flex items-center justify-between p-3 rounded-lg cursor-pointer transition-colors ${activeFile === file.name ? 'bg-blue-50' : 'hover:bg-gray-100'
                    }`}
                >
                  {/* Left: Icon + File Info */}
                  <div className="flex items-center gap-3 truncate">
                    {/* File icon */}
                    <div className="text-3xl">
                      {getFileIcon(file.name)}
                    </div>

                    {/* File text info */}
                    <div className="flex flex-col truncate">
                      <span className="font-semibold truncate">{file.name}</span>
                      <span className="text-xs text-gray-500 truncate">
                        {file.blob ? `${(file.blob.size / 1024).toFixed(1)} KB` : 'Embedded'}
                      </span>
                    </div>
                  </div>

                  {/* (Optional) Right actions */}
                  {/* <button className="text-gray-400 hover:text-gray-600">
                    ⬇️
                  </button> */}
                </li>
              ))}
            </ul>
          </div>



          {/* sidebar-resizer */}
          <div
            ref={resizerRef}
            onMouseDown={() => (isDragging.current = true)}
            className="absolute top-0 right-0 w-2 h-full cursor-col-resize bg-transparent hover:bg-gray-300"
          ></div>
        </aside>

        {/* header line - ChatBot */}
        <div className="flex-1 flex flex-col">
          <header className="p-4 border-b flex items-center justify-between">
            <h1 className="text-xl font-bold">
              ChatBot {selectedEmbedding && <span className="text-sm text-gray-500 ml-2">({selectedEmbedding})</span>}
            </h1>

            <button className="md:hidden bg-gray-200 px-2 py-1 rounded">☰</button>
          </header>

          {/* messages display */}
          <main className="flex-1 overflow-y-auto p-4 space-y-4" id="chat">
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex flex-col gap-1 ${msg.from === "user" ? "items-end" : "items-start"}`}
              >
                {msg.from === "bot" && (
                  <img
                    src={`https://api.dicebear.com/7.x/personas/svg?seed=${msg.from}`}
                    className="w-8 h-8 rounded-full"
                    alt={msg.from}
                  />
                )}
                <div
                  className={`${msg.from === "user"
                    ? "bg-blue-100 text-right w-1/2"
                    : "bg-gray-200 w-[85%]"
                    } p-3 rounded-xl whitespace-pre-wrap max-w-full break-words`}
                >
                  <ReactMarkdown
                    remarkPlugins={[remarkMath]}
                    rehypePlugins={[rehypeKatex]}
                    components={{
                      p({ children }) {
                        return <p className="mb-2">{children}</p>;
                      },
                      code({ node, inline, className, children, ...props }) {
                        if (inline) {
                          return <code className="bg-gray-100 rounded px-1">{children}</code>;
                        }
                        return (
                          <div className="my-2">
                            <pre className="whitespace-pre-wrap break-words bg-gray-100 rounded p-2 overflow-x-auto">
                              {children}
                            </pre>
                          </div>
                        );
                      }
                    }}
                  >
                    {msg.content}
                  </ReactMarkdown>


                </div>
                {msg.evidence && msg.evidence.length > 0 && (
                  <ul className="mt-1 text-sm text-blue-600">
                    {msg.evidence.map((ev, i) => (
                      <li key={i}>
                        <button
                          onClick={() => scrollToChunk(`chunk-${ev.filename}-${ev.chunk_index}`, ev.filename)}
                          className="hover:underline"
                          title={ev.text}
                        >
                          🔍 {ev.filename}, Chunk {ev.chunk_index + 1}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            ))}
            {error && <div className="text-red-600 text-sm max-w-full break-words">⚠ {error}</div>}

            {selectedFileChunks.map((chunk, idx) => {
              const fileName = files[0]?.name || "file";
              const chunkId = `chunk-${fileName}-${idx}`;
              return (
                <li
                  id={chunkId}
                  key={chunkId}
                  onClick={() => toggleChunkVisibility(chunkId)}
                  className={`cursor-pointer p-2 bg-white rounded border shadow text-gray-800 transition-all duration-300 ${visibleChunks[chunkId] === false ? 'hidden' : ''}`}
                >
                  {chunk}
                </li>
              );
            })}

            <div className="flex items-start gap-3 animate-pulse">
              <img
                src="https://api.dicebear.com/7.x/personas/svg?seed=bot"
                className="w-8 h-8 rounded-full"
                alt="Bot"
              />
              <div className="flex space-x-1 bg-gray-200 p-3 rounded-xl">
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:-0.3s]" />
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce [animation-delay:-0.15s]" />
                <div className="w-2 h-2 bg-gray-500 rounded-full animate-bounce" />
              </div>
            </div>

            <div ref={bottomRef} />
          </main>

          {/* user input */}
          <form onSubmit={handleSend} className="p-4 border-t flex items-center gap-2">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.ctrlKey && e.key === "Enter") {
                  e.preventDefault(); // prevent newline
                  handleSend(e);
                }
              }}
              className="flex-1 resize-none border rounded-lg p-2 h-24 focus:outline-none focus:ring-2 focus:ring-blue-500"
              placeholder="Type a message..."
            ></textarea>
            <button
              type="submit"
              className="bg-blue-500 text-white px-4 py-2 rounded-lg h-12"
            >
              Send
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
